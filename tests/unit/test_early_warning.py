from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from semifab_poc.data.schema import DataOrigin, ObservationRecord, QualityFlag
from semifab_poc.models.early_warning import (
    CensorReason,
    EarlyWarningError,
    EarlyWarningPredictor,
    ModelKind,
    StreamingFeatureExtractor,
    WarningDataset,
    WarningObservationWindow,
    generate_excursion_labels,
    load_early_warning_config,
    split_conformal_quantile,
)


ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "configs" / "models" / "early_warning.yaml"


def _observation(
    signal_id: str,
    unit: str,
    value: float,
    *,
    step: int = 10,
    source_s: float = 1.0,
    arrival_s: float = 1.0,
    sample_index: int = 0,
) -> ObservationRecord:
    return ObservationRecord(
        run_id="warning-run",
        sample_index=sample_index,
        source_step_index=step,
        source_timestamp_s=source_s,
        observed_timestamp_s=source_s,
        arrival_timestamp_s=arrival_s,
        sensor_id=f"sensor-{signal_id}",
        signal_id=signal_id,
        value=value,
        unit=unit,
        quality_flags=(QualityFlag.VALID,),
        uncertainty_std=0.0,
        data_origin=DataOrigin.SYNTHETIC_SIMULATOR,
    )


def _normalization() -> dict[str, tuple[float, float]]:
    return {
        "electrical.grid_voltage": (0.0, 1.0),
        "electrical.ups_output_voltage": (0.0, 1.0),
        "electrical.ups_battery_energy": (0.0, 1000.0),
        "drive.motor_angular_speed": (0.0, 188.5),
        "pump.volumetric_flow": (0.0, 2.0e-4),
        "upw.supply_pressure": (0.0, 300_000.0),
        "upw.tool_flow": (0.0, 1.0e-4),
        "upw.temperature": (293.15, 10.0),
    }


def _all_observations(*, arrival_s: float = 1.0) -> tuple[ObservationRecord, ...]:
    values = (
        ("electrical.grid_voltage", "pu", 1.0),
        ("electrical.ups_output_voltage", "pu", 1.0),
        ("electrical.ups_battery_energy", "J", 1000.0),
        ("drive.motor_angular_speed", "rad/s", 188.5),
        ("pump.volumetric_flow", "m^3/s", 2.0e-4),
        ("upw.supply_pressure", "Pa", 300_000.0),
        ("upw.tool_flow", "m^3/s", 1.0e-4),
        ("upw.temperature", "K", 293.15),
    )
    return tuple(
        _observation(signal, unit, value, arrival_s=arrival_s, sample_index=index)
        for index, (signal, unit, value) in enumerate(values)
    )


def _window(observations: tuple[ObservationRecord, ...]) -> WarningObservationWindow:
    return WarningObservationWindow(
        run_id="warning-run",
        decision_step_index=10,
        decision_timestamp_s=1.0,
        observations=observations,
        process_mode="DRESS",
        polish_start_s=7.0,
        normalization_by_signal=_normalization(),
        sensor_sample_period_s=0.05,
        battery_capacity_ratio=0.5,
        ups_load_ratio=0.8,
    )


def _dataset() -> WarningDataset:
    rows: list[list[float]] = []
    labels: list[int] = []
    run_ids: list[str] = []
    split_ids: list[str] = []
    decision_times: list[float] = []
    onset_times: list[float] = []
    split_sizes = {
        "TRAIN": 40,
        "CALIBRATION": 24,
        "CONFORMAL_CALIBRATION": 24,
        "TEST": 24,
    }
    rng = np.random.default_rng(71)
    for split, count in split_sizes.items():
        for index in range(count):
            label = index % 2
            rows.append(
                [
                    label + rng.normal(0.0, 0.10),
                    0.5 * label + rng.normal(0.0, 0.15),
                    np.nan if index % 11 == 0 else rng.normal(),
                ]
            )
            labels.append(label)
            run_ids.append(f"{split.lower()}-{index // 2}")
            split_ids.append(split)
            decision_times.append(float(index % 2))
            onset_times.append(2.0 if label else np.nan)
    return WarningDataset(
        feature_names=("x0", "x1", "x2"),
        features=np.asarray(rows, dtype=float),
        labels=np.asarray(labels, dtype=int),
        run_ids=tuple(run_ids),
        split_ids=tuple(split_ids),
        decision_step_indices=np.arange(len(rows), dtype=int),
        decision_timestamps_s=np.asarray(decision_times, dtype=float),
        first_excursion_timestamps_s=np.asarray(onset_times, dtype=float),
    )


def test_wp12_configuration_is_strict_and_frozen() -> None:
    config = load_early_warning_config(CONFIG_PATH)
    assert config.target.horizon_s == 3.0
    assert config.target.persistence_s == 0.25
    assert config.target.lower_relative_fraction == 0.95
    assert config.target.upper_relative_fraction == 1.05
    assert config.experiment_revision == "1.4-no-test-selection"
    assert config.evaluation.observation_robustness_family_positions == (
        "UPPER_MEDIAN",
        "MAXIMUM",
    )
    assert (
        config.splits.conformal_calibration_seed_start
        not in {
            config.splits.train_seed_start,
            config.splits.calibration_seed_start,
            config.splits.test_seed_start,
        }
    )
    assert "cmp.mrr" in config.features.forbidden_signal_ids


def test_split_conformal_quantile_uses_exact_finite_sample_rank() -> None:
    scores = np.asarray([0.4, 0.1, 0.3, 0.2])
    # ceil((4 + 1) * (1 - 0.4)) = 3, so select the third order statistic.
    assert split_conformal_quantile(scores, alpha=0.4) == 0.3
    # When the finite-sample rank exceeds n, the maximum score is required.
    assert split_conformal_quantile(scores, alpha=0.1) == 0.4


def test_persistent_polish_excursion_is_labelled_and_other_modes_are_not() -> None:
    config = load_early_warning_config(CONFIG_PATH).target.model_copy(
        update={"horizon_s": 2.0, "persistence_s": 0.2}
    )
    timestamps = np.arange(0.0, 10.1, 0.1)
    reference = np.ones_like(timestamps)
    true = np.ones_like(timestamps)
    modes = np.where(timestamps >= 5.0, "POLISH", "DRESS")
    true[(timestamps >= 5.5) & (timestamps <= 6.5)] = 0.90
    decisions = tuple(range(len(timestamps)))
    result = generate_excursion_labels(
        run_id="label-run",
        timestamps_s=timestamps,
        true_mrr_m_s=true,
        reference_mrr_m_s=reference,
        process_modes=modes,
        decision_step_indices=decisions,
        config=config,
    )
    assert result.episode_onset_step_indices == (55,)
    by_step = {label.decision_step_index: label for label in result.labels}
    assert by_step[40].excursion_within_horizon is True
    assert by_step[54].first_excursion_step_index == 55
    assert 55 not in by_step
    assert result.censor_counts[CensorReason.POST_EXCURSION_ONSET] > 0
    assert result.censor_counts[CensorReason.INCOMPLETE_FUTURE_HORIZON] > 0
    assert result.censor_counts[CensorReason.NO_ACTIVE_POLISH_OPPORTUNITY] > 0


def test_hold_zero_mrr_never_creates_a_violation() -> None:
    config = load_early_warning_config(CONFIG_PATH).target
    timestamps = np.arange(0.0, 8.01, 0.01)
    modes = np.where(timestamps < 4.0, "HOLD", "POLISH")
    reference = np.where(modes == "POLISH", 1.0, 0.0)
    true = reference.copy()
    result = generate_excursion_labels(
        run_id="hold-run",
        timestamps_s=timestamps,
        true_mrr_m_s=true,
        reference_mrr_m_s=reference,
        process_modes=modes,
        decision_step_indices=range(0, len(timestamps), 10),
        config=config,
    )
    assert result.episode_onset_step_indices == ()
    assert not any(label.excursion_within_horizon for label in result.labels)


def test_streaming_features_reject_future_arrivals_and_forbidden_signals() -> None:
    config = load_early_warning_config(CONFIG_PATH)
    extractor = StreamingFeatureExtractor(config.features)
    vector = extractor.transform(_window(_all_observations()))
    assert vector.feature_cutoff_step_index == 10
    assert "upw.supply_pressure:history_deficit_area_s" in vector.names
    assert not any(name.startswith("cmp.mrr") for name in vector.names)
    with pytest.raises(EarlyWarningError, match="future-arrival"):
        extractor.transform(_window(_all_observations(arrival_s=1.1)))
    forbidden = _observation("cmp.mrr", "m/s", 1.0e-9)
    with pytest.raises(EarlyWarningError, match="forbidden"):
        extractor.transform(_window((forbidden,)))


@pytest.mark.parametrize(
    "model_kind",
    (ModelKind.PREVALENCE, ModelKind.LOGISTIC, ModelKind.GRADIENT_BOOSTED),
)
def test_predictors_fit_calibrate_and_return_conformal_sets(model_kind: ModelKind) -> None:
    config = load_early_warning_config(CONFIG_PATH)
    dataset = _dataset()
    predictor = EarlyWarningPredictor(model_kind, config.features, config.models).fit(dataset)
    test = dataset.subset("TEST")
    probabilities, prediction_sets, latency = predictor.predict_features(test.features)
    assert len(probabilities) == len(test.labels)
    assert np.all((probabilities >= 0.0) & (probabilities <= 1.0))
    assert all(set(values) <= {0, 1} for values in prediction_sets)
    assert np.all(latency >= 0.0)


def test_predictor_save_load_verifies_checksum(tmp_path: Path) -> None:
    config = load_early_warning_config(CONFIG_PATH)
    dataset = _dataset()
    predictor = EarlyWarningPredictor(ModelKind.LOGISTIC, config.features, config.models).fit(
        dataset
    )
    destination = tmp_path / "warning.pkl"
    predictor.save(destination)
    loaded = EarlyWarningPredictor.load(destination)
    test = dataset.subset("TEST")
    original = predictor.predict_features(test.features)[0]
    restored = loaded.predict_features(test.features)[0]
    assert np.array_equal(original, restored)
    destination.write_bytes(destination.read_bytes() + b"tamper")
    with pytest.raises(EarlyWarningError, match="checksum"):
        EarlyWarningPredictor.load(destination)
