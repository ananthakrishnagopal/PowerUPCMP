from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from semifab_poc.models.virtual_metrology import (
    CommonPreprocessor,
    FeatureRoleBundle,
    LoadedTargetLabels,
    ModelKind,
    NativePrestonProxy,
    VMDataset,
    VMObservationWindow,
    VirtualMetrologyError,
    VirtualMetrologyPredictor,
    deterministic_group_folds,
    grouped_bootstrap_metrics,
    grouped_bootstrap_paired_mae_difference,
    join_features_and_labels,
    load_virtual_metrology_config,
    make_policy_datasets,
    regression_metrics,
    select_hyperparameters,
    split_conformal_quantile,
)


CONFIG_PATH = Path("configs/models/virtual_metrology.yaml")


def _synthetic_frame(row_count: int = 120) -> tuple[pd.DataFrame, np.ndarray]:
    index = np.arange(row_count, dtype=float)
    pressure_scale = 0.8 + 0.4 * (index / max(1.0, row_count - 1.0))
    rotation_scale = 0.9 + 0.2 * np.sin(index / 9.0)
    payload: dict[str, np.ndarray] = {
        "ACTIVE_POLISH_PROXY__DURATION_FRACTION": np.ones(row_count),
        "x_linear": index / row_count,
        "x_curved": np.cos(index / 7.0),
    }
    pressure_names = (
        "PRESSURIZED_CHAMBER_PRESSURE",
        "MAIN_OUTER_AIR_BAG_PRESSURE",
        "CENTER_AIR_BAG_PRESSURE",
        "RETAINER_RING_PRESSURE",
        "RIPPLE_AIR_BAG_PRESSURE",
        "EDGE_AIR_BAG_PRESSURE",
    )
    for offset, name in enumerate(pressure_names):
        payload[f"ACTIVE_POLISH_PROXY__{name}__TW_MEAN"] = (
            pressure_scale * (10.0 + offset)
        )
    payload["ACTIVE_POLISH_PROXY__WAFER_ROTATION__TW_MEAN"] = rotation_scale * 80.0
    payload["ACTIVE_POLISH_PROXY__STAGE_ROTATION__TW_MEAN"] = rotation_scale * 75.0
    payload["ACTIVE_POLISH_PROXY__HEAD_ROTATION__TW_MEAN"] = rotation_scale * 65.0
    frame = pd.DataFrame(payload)
    target = 70.0 + 15.0 * pressure_scale * rotation_scale + 4.0 * payload["x_linear"]
    return frame, target


def _dataset(
    frame: pd.DataFrame,
    target: np.ndarray,
    indices: np.ndarray,
    identity: str,
) -> VMDataset:
    return VMDataset(
        features=frame.iloc[indices].copy(),
        target=np.asarray(target)[indices],
        wafer_ids=tuple(f"w{int(index // 2):03d}" for index in indices),
        stages=tuple("A" if int(index) % 2 == 0 else "B" for index in indices),
        split_identity=identity,
    )


def _tree_parameters() -> dict[str, object]:
    return {
        "loss": "squared_error",
        "max_leaf_nodes": 7,
        "min_samples_leaf": 20,
        "l2_regularization": 0.1,
    }


def test_strict_wp09_configuration_loads_and_rejects_unknown_key(tmp_path: Path) -> None:
    config = load_virtual_metrology_config(CONFIG_PATH)
    assert config.schema_version == "1.0.0"
    assert config.models.required_families == (
        "mean",
        "linear",
        "ridge",
        "physics",
        "tree",
        "hybrid",
    )
    payload = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    payload["unexpected"] = True
    broken = tmp_path / "broken.yaml"
    broken.write_text(yaml.safe_dump(payload), encoding="utf-8")
    with pytest.raises(VirtualMetrologyError, match="invalid WP09 configuration"):
        load_virtual_metrology_config(broken)


def test_common_preprocessor_is_fit_only_deterministic_and_nonmutating() -> None:
    frame = pd.DataFrame(
        {
            "a": [1.0, np.nan, 3.0, 5.0],
            "b": [2.0, 2.0, 4.0, 4.0],
            "constant": [9.0, 9.0, 9.0, 9.0],
        }
    )
    original = frame.copy(deep=True)
    first = CommonPreprocessor(frame.columns).fit(frame)
    second = CommonPreprocessor(frame.columns).fit(frame)
    transformed = first.transform(frame, scale=True)
    pd.testing.assert_frame_equal(frame, original)
    assert np.isfinite(transformed).all()
    assert first.state is not None and second.state is not None
    assert first.state.state_sha256 == second.state.state_sha256
    assert "constant" in first.state.dropped_names
    assert "MISSING__a" in first.state.retained_names
    assert "MISSING__b" in first.state.dropped_names


def test_common_preprocessor_rejects_all_missing_fit_feature() -> None:
    frame = pd.DataFrame({"usable": [1.0, 2.0], "missing": [np.nan, np.nan]})
    with pytest.raises(VirtualMetrologyError, match="all-missing predictors"):
        CommonPreprocessor(frame.columns).fit(frame)


def test_native_preston_proxy_is_nonnegative_monotone_and_gates_no_active_support() -> None:
    config = load_virtual_metrology_config(CONFIG_PATH)
    frame, target = _synthetic_frame(20)
    proxy = NativePrestonProxy(config.preston_proxy).fit(frame, target)
    baseline = proxy.predict(frame)
    higher = frame.copy()
    for name in config.preston_proxy.pressure_signal_names:
        column = f"ACTIVE_POLISH_PROXY__{name}__TW_MEAN"
        higher[column] *= 1.1
    increased = proxy.predict(higher)
    no_active = higher.copy()
    no_active[config.preston_proxy.active_duration_feature] = 0.0
    assert np.all(increased >= baseline)
    assert np.all(proxy.predict(no_active) == 0.0)
    assert proxy.state is not None
    assert proxy.state.coefficient_native >= 0.0
    assert proxy.state.feature_columns == proxy.feature_columns


@pytest.mark.parametrize(
    ("model_kind", "hyperparameters"),
    [
        (ModelKind.MEAN, {}),
        (ModelKind.LINEAR, {}),
        (ModelKind.RIDGE, {"alpha": 1.0}),
        (ModelKind.PHYSICS, {}),
        (ModelKind.TREE, _tree_parameters()),
        (ModelKind.HYBRID, _tree_parameters()),
    ],
)
def test_all_six_models_fit_predict_and_calibrate_without_group_overlap(
    model_kind: ModelKind,
    hyperparameters: dict[str, object],
) -> None:
    config = load_virtual_metrology_config(CONFIG_PATH)
    frame, target = _synthetic_frame()
    fit = _dataset(frame, target, np.arange(0, 80), "FIT")
    calibration = _dataset(frame, target, np.arange(80, 100), "CALIBRATION")
    test = _dataset(frame, target, np.arange(100, 120), "TEST")
    predictor = VirtualMetrologyPredictor(
        config, model_kind, frame.columns, hyperparameters
    ).fit(fit)
    radius = predictor.calibrate(calibration)
    prediction = predictor.predict(VMObservationWindow(test.features, "TEST"))
    assert radius >= 0.0
    assert np.all(prediction.values >= 0.0)
    assert prediction.lower is not None and prediction.upper is not None
    assert np.all(prediction.lower >= 0.0)
    assert np.all(prediction.lower <= prediction.values)
    assert np.all(prediction.values <= prediction.upper)
    assert predictor.fit_group_sha256 is not None
    assert predictor.calibration_split_identity == "CALIBRATION"
    assert predictor.calibration_group_sha256 is not None
    assert predictor.calibration_group_count == 10
    assert predictor.calibration_row_count == 20


def test_calibration_rejects_fit_wafer_overlap() -> None:
    config = load_virtual_metrology_config(CONFIG_PATH)
    frame, target = _synthetic_frame(40)
    fit = _dataset(frame, target, np.arange(0, 30), "FIT")
    overlap = VMDataset(
        features=frame.iloc[30:32].copy(),
        target=target[30:32],
        wafer_ids=(fit.wafer_ids[0], "new-wafer"),
        stages=("A", "B"),
        split_identity="BROKEN_CALIBRATION",
    )
    predictor = VirtualMetrologyPredictor(
        config, ModelKind.MEAN, frame.columns
    ).fit(fit)
    with pytest.raises(VirtualMetrologyError, match="overlap fit groups"):
        predictor.calibrate(overlap)


def test_predictor_artifact_round_trip_and_checksum_guard(tmp_path: Path) -> None:
    config = load_virtual_metrology_config(CONFIG_PATH)
    frame, target = _synthetic_frame(40)
    fit = _dataset(frame, target, np.arange(0, 30), "FIT")
    test = _dataset(frame, target, np.arange(30, 40), "TEST")
    predictor = VirtualMetrologyPredictor(
        config, ModelKind.RIDGE, frame.columns, {"alpha": 1.0}
    ).fit(fit)
    path = tmp_path / "ridge.pkl"
    predictor.save(path)
    restored = VirtualMetrologyPredictor.load(path)
    expected = predictor.predict(VMObservationWindow(test.features, "TEST"))
    observed = restored.predict(VMObservationWindow(test.features, "TEST"))
    assert observed.values == pytest.approx(expected.values)
    path.write_bytes(path.read_bytes() + b"corrupt")
    with pytest.raises(VirtualMetrologyError, match="checksum mismatch"):
        VirtualMetrologyPredictor.load(path)


def test_deterministic_group_folds_never_split_a_wafer() -> None:
    groups = [f"w{index // 2}" for index in range(30)]
    first = deterministic_group_folds(groups, n_splits=5, seed=90209)
    second = deterministic_group_folds(groups, n_splits=5, seed=90209)
    for (fit_a, validation_a), (fit_b, validation_b) in zip(first, second):
        assert fit_a.tolist() == fit_b.tolist()
        assert validation_a.tolist() == validation_b.tolist()
        assert not set(np.asarray(groups)[fit_a]) & set(np.asarray(groups)[validation_a])


def test_ridge_hyperparameter_selection_is_grouped_and_holdout_free() -> None:
    config = load_virtual_metrology_config(CONFIG_PATH)
    frame, target = _synthetic_frame(60)
    dataset = _dataset(frame, target, np.arange(60), "TRAIN_CORE")
    result = select_hyperparameters(
        dataset, config, ModelKind.RIDGE, frame.columns
    )
    assert result["selected_hyperparameters"]["alpha"] in config.models.ridge.alpha_grid
    assert len(result["candidate_results"]) == len(config.models.ridge.alpha_grid)
    assert result["test_or_validation_used"] is False
    assert all(row["row_count"] == 60 for row in result["candidate_results"])


def test_conformal_metric_and_grouped_bootstrap_equations_are_exact_and_seeded() -> None:
    scores = [0.1, 0.2, 0.3, 0.4]
    assert split_conformal_quantile(scores, 0.25) == pytest.approx(0.4)
    target = np.array([1.0, 2.0, 3.0, 4.0])
    prediction = np.array([1.0, 1.0, 4.0, 4.0])
    metrics = regression_metrics(
        target,
        prediction,
        relative_denominator_floor=1.0e-12,
        lower=prediction - 1.0,
        upper=prediction + 1.0,
    )
    assert metrics["mae"] == pytest.approx(0.5)
    assert metrics["rmse"] == pytest.approx(np.sqrt(0.5))
    assert metrics["bias"] == pytest.approx(0.0)
    assert metrics["interval_coverage"] == pytest.approx(1.0)
    groups = ["w1", "w1", "w2", "w2"]
    first = grouped_bootstrap_metrics(
        target,
        prediction,
        groups,
        repetitions=50,
        seed=7,
        relative_denominator_floor=1.0e-12,
    )
    second = grouped_bootstrap_metrics(
        target,
        prediction,
        groups,
        repetitions=50,
        seed=7,
        relative_denominator_floor=1.0e-12,
    )
    assert first == second
    difference = grouped_bootstrap_paired_mae_difference(
        target,
        prediction,
        target,
        groups,
        repetitions=50,
        seed=7,
    )
    assert difference["p50"] >= 0.0


def _role_frame(rows: list[tuple[str, str, float]]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["WAFER_ID", "STAGE", "x"])


def _label_frame(rows: list[tuple[str, str, float]]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["WAFER_ID", "STAGE", "AVG_REMOVAL_RATE"])


def test_synthetic_target_boundary_joins_once_and_applies_training_only_exclusion() -> None:
    config = load_virtual_metrology_config(CONFIG_PATH)
    train_core = _role_frame([("w1", "A", 1.0), ("w2", "B", 2.0)])
    model_selection = _role_frame([("w3", "A", 3.0)])
    calibration = _role_frame([("w4", "B", 4.0)])
    retained_training = pd.concat(
        [train_core, model_selection, calibration], ignore_index=True
    )
    test = _role_frame([("w5", "A", 5.0), ("w6", "B", 6.0)])
    validation = _role_frame([("w7", "A", 7.0), ("w8", "B", 8.0)])
    original_training_labels = _label_frame(
        [
            ("w1", "A", 11.0),
            ("w2", "B", 12.0),
            ("w3", "A", 13.0),
            ("w4", "B", 14.0),
        ]
    )
    excluded_training_labels = original_training_labels.loc[
        original_training_labels["WAFER_ID"] != "w2"
    ].copy()
    labels = LoadedTargetLabels(
        training_by_policy={
            "ORIGINAL": original_training_labels,
            "EXCLUDE_FOUR_PREREGISTERED": excluded_training_labels,
            "HYPOTHETICAL_DIVIDE_FOUR_BY_60": original_training_labels.copy(),
        },
        test=_label_frame([("w5", "A", 15.0), ("w6", "B", 16.0)]),
        validation=_label_frame([("w7", "A", 17.0), ("w8", "B", 18.0)]),
        access_audit={"fixture": True},
    )
    bundle = FeatureRoleBundle(
        source_training=retained_training,
        source_test=test,
        source_validation=validation,
        retained_training=retained_training,
        retained_test=test,
        retained_validation=validation,
        train_core=train_core,
        model_selection=model_selection,
        interval_calibration=calibration,
        predictor_columns=("x",),
        source_manifest={},
    )

    original = make_policy_datasets(
        bundle,
        labels,
        config,
        policy="ORIGINAL",
        feature_columns=("x",),
    )
    excluded = make_policy_datasets(
        bundle,
        labels,
        config,
        policy="EXCLUDE_FOUR_PREREGISTERED",
        feature_columns=("x",),
    )

    assert len(original["TRAIN_CORE"].target) == 2
    assert len(excluded["TRAIN_CORE"].target) == 1
    assert excluded["TRAIN_CORE"].wafer_ids == ("w1",)
    assert len(excluded["OFFICIAL_TEST_RETAINED"].target) == 2
    assert len(excluded["OFFICIAL_VALIDATION_RETAINED"].target) == 2

    missing = labels.test.iloc[:1].copy()
    with pytest.raises(VirtualMetrologyError, match="join is incomplete"):
        join_features_and_labels(test, missing, config, role="BROKEN_TEST")


def test_wp09_cli_refuses_one_shot_without_explicit_target_authorization(
    capsys: pytest.CaptureFixture[str],
) -> None:
    script_path = Path("scripts/validate_wp09_virtual_metrology.py")
    specification = importlib.util.spec_from_file_location(
        "validate_wp09_virtual_metrology", script_path
    )
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)

    with pytest.raises(SystemExit) as exc_info:
        module.main(["--run-one-shot"])

    assert exc_info.value.code == 2
    assert "requires the explicit --authorize-holdout-open flag" in capsys.readouterr().err
