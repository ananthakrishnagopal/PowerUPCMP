"""Leakage-safe public-data virtual metrology in source-native numeric scale.

The module implements the frozen WP09 protocol. It deliberately keeps PHM
source-native values separate from the SI synthetic simulator and provides a
feature-only preparation path that never opens official holdout targets.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import itertools
import json
import math
import os
import pickle
import platform
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd
import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from semifab_poc.data.splits import (
    chronological_group_split,
    grouped_split,
    official_group_precedence_split,
)


class VirtualMetrologyError(ValueError):
    """Raised when a WP09 configuration, dataset, split, or model is invalid."""


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, validate_assignment=True)


class DatasetConfig(_StrictModel):
    dataset_id: str = Field(min_length=1)
    feature_contract: str = Field(min_length=1)
    feature_manifest: str = Field(min_length=1)
    expected_feature_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    target: str = Field(min_length=1)
    target_unit_status: str = Field(min_length=1)
    process_signal_unit_status: str = Field(min_length=1)
    primary_gap_threshold_s: float = Field(gt=0.0)
    expected_predictor_count: int = Field(gt=0)
    target_in_feature_files: bool


class SplitConfig(_StrictModel):
    group_column: str = Field(min_length=1)
    stage_column: str = Field(min_length=1)
    official_precedence: tuple[str, ...]
    expected_retained_rows: dict[str, int]
    expected_retained_groups: dict[str, int]
    full_source_partition_interpretation: str = Field(min_length=1)
    inner_random_seed: int = Field(ge=0)
    train_core_fraction: float = Field(gt=0.0, lt=1.0)
    model_selection_fraction: float = Field(gt=0.0, lt=1.0)
    interval_calibration_fraction: float = Field(gt=0.0, lt=1.0)
    tuning_group_folds: int = Field(gt=1)
    fold_assignment: str = Field(min_length=1)
    chronological_time_column: str = Field(min_length=1)
    chronological_fractions: tuple[float, float, float]

    @model_validator(mode="after")
    def validate_split_contract(self) -> SplitConfig:
        if self.official_precedence != ("training", "test", "validation"):
            raise ValueError("official precedence must be training, test, validation")
        fractions = (
            self.train_core_fraction,
            self.model_selection_fraction,
            self.interval_calibration_fraction,
        )
        if not math.isclose(sum(fractions), 1.0, rel_tol=0.0, abs_tol=1.0e-12):
            raise ValueError("inner split fractions must sum to one")
        if not math.isclose(
            sum(self.chronological_fractions), 1.0, rel_tol=0.0, abs_tol=1.0e-12
        ):
            raise ValueError("chronological fractions must sum to one")
        expected_roles = {"training", "test", "validation"}
        if set(self.expected_retained_rows) != expected_roles:
            raise ValueError("expected retained row roles are incomplete")
        if set(self.expected_retained_groups) != expected_roles:
            raise ValueError("expected retained group roles are incomplete")
        return self


class FeatureConfig(_StrictModel):
    metadata_prefix: str = Field(min_length=1)
    forbidden_predictors: tuple[str, ...]
    nonfinite_policy: str = Field(min_length=1)
    imputation: str = Field(min_length=1)
    missing_indicators: str = Field(min_length=1)
    zero_variance_policy: str = Field(min_length=1)
    target_driven_selection: bool
    feature_sets: dict[str, str]
    consumable_signal_names: tuple[str, ...]


class TargetPolicyConfig(_StrictModel):
    primary: str = Field(min_length=1)
    sensitivities: tuple[str, ...]
    select_from_holdouts: bool
    reuse_primary_hyperparameters: bool


class PrestonProxyConfig(_StrictModel):
    active_prefix: str = Field(min_length=1)
    active_duration_feature: str = Field(min_length=1)
    pressure_signal_names: tuple[str, ...] = Field(min_length=1)
    surface_rotation_signal_names: tuple[str, str]
    head_rotation_signal_name: str = Field(min_length=1)
    statistic: str = Field(min_length=1)
    positive_normalizer: str = Field(min_length=1)
    pressure_aggregation: str = Field(min_length=1)
    velocity_aggregation: str = Field(min_length=1)
    no_active_support_exposure: float = Field(ge=0.0)
    coefficient_fit: str = Field(min_length=1)
    coefficient_unit: str = Field(min_length=1)


class LinearModelConfig(_StrictModel):
    fit_intercept: bool


class RidgeModelConfig(_StrictModel):
    fit_intercept: bool
    alpha_grid: tuple[float, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_alphas(self) -> RidgeModelConfig:
        if any(not math.isfinite(value) or value <= 0.0 for value in self.alpha_grid):
            raise ValueError("ridge alpha values must be finite and positive")
        return self


class GradientBoostedModelConfig(_StrictModel):
    max_iter: int = Field(gt=0)
    learning_rate: float = Field(gt=0.0)
    early_stopping: bool
    max_bins: int = Field(gt=1, le=255)
    loss_grid: tuple[str, ...] = Field(min_length=1)
    max_leaf_nodes_grid: tuple[int, ...] = Field(min_length=1)
    min_samples_leaf_grid: tuple[int, ...] = Field(min_length=1)
    l2_regularization_grid: tuple[float, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_grid(self) -> GradientBoostedModelConfig:
        if self.early_stopping:
            raise ValueError("WP09 forbids internal early stopping")
        if any(value <= 1 for value in self.max_leaf_nodes_grid):
            raise ValueError("max leaf nodes must exceed one")
        if any(value <= 1 for value in self.min_samples_leaf_grid):
            raise ValueError("minimum samples per leaf must exceed one")
        if any(value < 0.0 for value in self.l2_regularization_grid):
            raise ValueError("L2 regularization must be non-negative")
        return self


class HybridModelConfig(_StrictModel):
    tune_residual_model_separately: bool


class ModelConfig(_StrictModel):
    random_seed: int = Field(ge=0)
    prediction_floor: float = Field(ge=0.0)
    tuning_metric: str = Field(min_length=1)
    tie_tolerance: float = Field(ge=0.0)
    family_simplicity_order: tuple[str, ...]
    required_families: tuple[str, ...]
    linear: LinearModelConfig
    ridge: RidgeModelConfig
    gradient_boosted: GradientBoostedModelConfig
    hybrid: HybridModelConfig

    @model_validator(mode="after")
    def validate_families(self) -> ModelConfig:
        required = {"mean", "linear", "ridge", "physics", "tree", "hybrid"}
        if set(self.required_families) != required:
            raise ValueError("all six required WP09 model families must be present")
        if set(self.family_simplicity_order) != required:
            raise ValueError("family simplicity order must contain all six families")
        return self


class UncertaintyConfig(_StrictModel):
    method: str = Field(min_length=1)
    alpha: float = Field(gt=0.0, lt=1.0)
    finite_sample_rank: str = Field(min_length=1)
    lower_bound_floor: float = Field(ge=0.0)
    minimum_interpretation_coverage: float = Field(ge=0.0, le=1.0)
    claim: str = Field(min_length=1)


class EvaluationConfig(_StrictModel):
    relative_error_denominator_floor: float = Field(gt=0.0)
    grouped_bootstrap_repetitions: int = Field(gt=0)
    grouped_bootstrap_seed: int = Field(ge=0)
    bootstrap_percentiles: tuple[float, float, float]
    report_strata: tuple[str, ...]
    required_metrics: tuple[str, ...]
    error_distribution_statistics: tuple[str, ...]
    report_full_collision_contaminated_partitions: bool
    test_used_for_selection: bool
    validation_opened_once: bool


class SensitivityConfig(_StrictModel):
    gap_threshold_s: tuple[float, ...]
    proxy_feature_sets: tuple[str, ...]
    proxy_models: tuple[str, ...]
    consumable_feature_sets: tuple[str, ...]
    consumable_models: tuple[str, ...]
    chronological_all_models: bool


class PublicPredictionGate(_StrictModel):
    comparison: str
    require_lower_mae_on: tuple[str, ...]
    require_validation_bootstrap_upper_below_zero: bool


class HybridGate(_StrictModel):
    baseline_selection_role: str
    require_lower_mae_on: tuple[str, ...]
    require_validation_bootstrap_upper_below_zero: bool


class ConsumableGate(_StrictModel):
    comparison: str
    require_positive_on: tuple[str, ...]
    require_validation_bootstrap_lower_above_zero: bool


class InterpretationGateConfig(_StrictModel):
    public_prediction: PublicPredictionGate
    hybrid_improvement: HybridGate
    consumable_association: ConsumableGate


class HoldoutOpeningConfig(_StrictModel):
    require_decision_and_config_committed: bool
    require_feature_only_split_manifest: bool
    require_synthetic_fixture_tests: bool
    require_nonadaptive_runner: bool
    run_all_primary_and_sensitivities_together: bool


class VirtualMetrologyConfig(_StrictModel):
    schema_version: str
    experiment_revision: str
    dataset: DatasetConfig
    splits: SplitConfig
    features: FeatureConfig
    target_policies: TargetPolicyConfig
    preston_proxy: PrestonProxyConfig
    models: ModelConfig
    uncertainty: UncertaintyConfig
    evaluation: EvaluationConfig
    sensitivities: SensitivityConfig
    interpretation_gates: InterpretationGateConfig
    holdout_opening: HoldoutOpeningConfig

    @model_validator(mode="after")
    def validate_contract(self) -> VirtualMetrologyConfig:
        if self.schema_version != "1.0.0":
            raise ValueError("only WP09 schema version 1.0.0 is supported")
        if self.dataset.target_in_feature_files:
            raise ValueError("WP09 feature files must remain target-free")
        if self.features.target_driven_selection:
            raise ValueError("target-driven feature selection is forbidden")
        if self.target_policies.select_from_holdouts:
            raise ValueError("label-policy selection from holdouts is forbidden")
        if self.evaluation.test_used_for_selection:
            raise ValueError("official test may not select WP09 models")
        if not self.evaluation.validation_opened_once:
            raise ValueError("final public validation must use the one-shot policy")
        return self


def sha256_file(path: str | Path) -> str:
    """Return a streaming SHA-256 digest for a local file."""

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(payload: Any) -> str:
    """Hash a JSON-safe payload with stable ordering and separators."""

    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def load_virtual_metrology_config(path: str | Path) -> VirtualMetrologyConfig:
    """Load the strict frozen WP09 configuration."""

    config_path = Path(path)
    try:
        payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise VirtualMetrologyError(f"cannot load WP09 configuration: {exc}") from exc
    if not isinstance(payload, dict):
        raise VirtualMetrologyError("WP09 configuration root must be a mapping")
    try:
        return VirtualMetrologyConfig.model_validate(payload)
    except Exception as exc:
        raise VirtualMetrologyError(f"invalid WP09 configuration: {exc}") from exc


class ModelKind(str, Enum):
    MEAN = "mean"
    LINEAR = "linear"
    RIDGE = "ridge"
    PHYSICS = "physics"
    TREE = "tree"
    HYBRID = "hybrid"


@dataclass(frozen=True)
class VMDataset:
    """One offline native-scale regression role with explicit wafer identity."""

    features: pd.DataFrame
    target: np.ndarray
    wafer_ids: tuple[str, ...]
    stages: tuple[str, ...]
    split_identity: str

    def validate(self) -> None:
        target = np.asarray(self.target, dtype=float)
        row_count = len(self.features)
        if row_count == 0:
            raise VirtualMetrologyError("VM dataset cannot be empty")
        if target.ndim != 1 or len(target) != row_count:
            raise VirtualMetrologyError("VM target must be one-dimensional and row-aligned")
        if len(self.wafer_ids) != row_count or len(self.stages) != row_count:
            raise VirtualMetrologyError("VM identities must be row-aligned")
        if not np.all(np.isfinite(target)) or np.any(target < 0.0):
            raise VirtualMetrologyError("VM target must be finite and non-negative")
        if not self.split_identity:
            raise VirtualMetrologyError("VM split identity is required")
        if len(set(self.features.columns)) != len(self.features.columns):
            raise VirtualMetrologyError("VM feature columns must be unique")


@dataclass(frozen=True)
class VMObservationWindow:
    """Complete offline wafer-stage feature rows for prediction."""

    features: pd.DataFrame
    split_identity: str


@dataclass(frozen=True)
class VMPrediction:
    values: np.ndarray
    raw_values: np.ndarray
    lower: np.ndarray | None
    upper: np.ndarray | None
    model_kind: ModelKind
    target_unit_status: str
    raw_negative_prediction_count: int
    clipped_prediction_count: int
    latency_s: float


@dataclass(frozen=True)
class PreprocessingState:
    raw_columns: tuple[str, ...]
    medians: np.ndarray
    retained_indices: np.ndarray
    retained_names: tuple[str, ...]
    means: np.ndarray
    standard_deviations: np.ndarray
    dropped_names: tuple[str, ...]
    state_sha256: str


class CommonPreprocessor:
    """Fit-only median, universal missing indicator, and variance screen."""

    def __init__(self, raw_columns: Sequence[str]) -> None:
        self.raw_columns = tuple(raw_columns)
        if not self.raw_columns:
            raise VirtualMetrologyError("preprocessor requires raw feature columns")
        self.state: PreprocessingState | None = None

    def _numeric_matrix(self, frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        missing = [column for column in self.raw_columns if column not in frame.columns]
        if missing:
            raise VirtualMetrologyError(f"missing VM predictors: {missing[:10]}")
        numeric = frame.loc[:, list(self.raw_columns)].apply(pd.to_numeric, errors="coerce")
        values = numeric.to_numpy(dtype=float)
        finite = np.isfinite(values)
        values = np.where(finite, values, np.nan)
        return values, ~finite

    def fit(self, frame: pd.DataFrame) -> CommonPreprocessor:
        values, missing = self._numeric_matrix(frame)
        finite_counts = np.sum(~missing, axis=0)
        if np.any(finite_counts == 0):
            names = [
                self.raw_columns[index]
                for index in np.flatnonzero(finite_counts == 0).tolist()
            ]
            raise VirtualMetrologyError(
                f"fit role contains all-missing predictors: {names[:10]}"
            )
        medians = np.array(
            [np.median(values[~missing[:, index], index]) for index in range(values.shape[1])],
            dtype=float,
        )
        imputed = np.where(missing, medians[None, :], values)
        augmented = np.concatenate([imputed, missing.astype(float)], axis=1)
        augmented_names = self.raw_columns + tuple(
            f"MISSING__{column}" for column in self.raw_columns
        )
        variances = np.var(augmented, axis=0, ddof=0)
        retained_indices = np.flatnonzero(variances > 0.0)
        if len(retained_indices) == 0:
            raise VirtualMetrologyError("variance screen removed every derived predictor")
        retained = augmented[:, retained_indices]
        means = np.mean(retained, axis=0)
        standard_deviations = np.std(retained, axis=0, ddof=0)
        if not np.all(np.isfinite(standard_deviations)) or np.any(
            standard_deviations <= 0.0
        ):
            raise VirtualMetrologyError("retained predictor scaling is invalid")
        retained_names = tuple(augmented_names[index] for index in retained_indices)
        retained_set = set(retained_indices.tolist())
        dropped_names = tuple(
            name for index, name in enumerate(augmented_names) if index not in retained_set
        )
        state_payload = {
            "raw_columns": list(self.raw_columns),
            "medians": medians.tolist(),
            "retained_indices": retained_indices.tolist(),
            "means": means.tolist(),
            "standard_deviations": standard_deviations.tolist(),
        }
        self.state = PreprocessingState(
            raw_columns=self.raw_columns,
            medians=medians,
            retained_indices=retained_indices,
            retained_names=retained_names,
            means=means,
            standard_deviations=standard_deviations,
            dropped_names=dropped_names,
            state_sha256=canonical_sha256(state_payload),
        )
        return self

    def transform(self, frame: pd.DataFrame, *, scale: bool) -> np.ndarray:
        if self.state is None:
            raise VirtualMetrologyError("preprocessor is not fitted")
        values, missing = self._numeric_matrix(frame)
        imputed = np.where(missing, self.state.medians[None, :], values)
        augmented = np.concatenate([imputed, missing.astype(float)], axis=1)
        transformed = augmented[:, self.state.retained_indices]
        if scale:
            transformed = (
                transformed - self.state.means[None, :]
            ) / self.state.standard_deviations[None, :]
        if not np.all(np.isfinite(transformed)):
            raise VirtualMetrologyError("preprocessing produced non-finite values")
        return transformed


@dataclass(frozen=True)
class PrestonProxyState:
    feature_columns: tuple[str, ...]
    positive_medians: dict[str, float]
    coefficient_native: float
    state_sha256: str


class NativePrestonProxy:
    """Dimensionless pressure-speed exposure with native-scale coefficient."""

    def __init__(self, config: PrestonProxyConfig) -> None:
        self.config = config
        self.state: PrestonProxyState | None = None

    def _feature_name(self, signal: str) -> str:
        return f"{self.config.active_prefix}__{signal}__{self.config.statistic}"

    @property
    def feature_columns(self) -> tuple[str, ...]:
        return (
            self.config.active_duration_feature,
            *(self._feature_name(signal) for signal in self.config.pressure_signal_names),
            *(
                self._feature_name(signal)
                for signal in self.config.surface_rotation_signal_names
            ),
            self._feature_name(self.config.head_rotation_signal_name),
        )

    def _numeric_column(self, frame: pd.DataFrame, column: str) -> np.ndarray:
        if column not in frame.columns:
            raise VirtualMetrologyError(f"missing Preston proxy feature: {column}")
        return pd.to_numeric(frame[column], errors="coerce").to_numpy(dtype=float)

    def _fit_positive_medians(self, frame: pd.DataFrame) -> dict[str, float]:
        active_duration = self._numeric_column(frame, self.config.active_duration_feature)
        active = np.isfinite(active_duration) & (active_duration > 0.0)
        if not np.any(active):
            raise VirtualMetrologyError("fit role contains no active-polish proxy support")
        medians: dict[str, float] = {}
        pressure_columns = {
            self._feature_name(name) for name in self.config.pressure_signal_names
        }
        for column in self.feature_columns[1:]:
            raw = self._numeric_column(frame, column)
            values = raw if column in pressure_columns else np.abs(raw)
            candidates = values[active & np.isfinite(values) & (values > 0.0)]
            if len(candidates) == 0:
                raise VirtualMetrologyError(
                    f"Preston proxy has no positive fit normalizer for {column}"
                )
            median = float(np.median(candidates))
            if not math.isfinite(median) or median <= 0.0:
                raise VirtualMetrologyError(f"invalid Preston normalizer for {column}")
            medians[column] = median
        return medians

    def exposure(
        self,
        frame: pd.DataFrame,
        positive_medians: Mapping[str, float] | None = None,
    ) -> np.ndarray:
        medians = positive_medians
        if medians is None:
            if self.state is None:
                raise VirtualMetrologyError("Preston proxy is not fitted")
            medians = self.state.positive_medians
        active_duration = self._numeric_column(frame, self.config.active_duration_feature)
        active = np.isfinite(active_duration) & (active_duration > 0.0)
        pressure_columns = {
            self._feature_name(name) for name in self.config.pressure_signal_names
        }

        def normalized(column: str) -> np.ndarray:
            normalizer = float(medians[column])
            raw = self._numeric_column(frame, column)
            values = raw if column in pressure_columns else np.abs(raw)
            values = np.where(np.isfinite(values), values, normalizer)
            result = np.maximum(values, 0.0) / normalizer
            return np.where(active, result, 0.0)

        pressures = np.column_stack(
            [normalized(self._feature_name(name)) for name in self.config.pressure_signal_names]
        )
        pressure_proxy = np.mean(pressures, axis=1)
        wafer_rotation = normalized(
            self._feature_name(self.config.surface_rotation_signal_names[0])
        )
        stage_rotation = normalized(
            self._feature_name(self.config.surface_rotation_signal_names[1])
        )
        head_rotation = normalized(self._feature_name(self.config.head_rotation_signal_name))
        velocity_proxy = (np.maximum(wafer_rotation, stage_rotation) + head_rotation) / 2.0
        exposure = np.where(active, pressure_proxy * velocity_proxy, 0.0)
        if not np.all(np.isfinite(exposure)) or np.any(exposure < 0.0):
            raise VirtualMetrologyError("Preston exposure must be finite and non-negative")
        return exposure

    def fit(self, frame: pd.DataFrame, target: Sequence[float]) -> NativePrestonProxy:
        y = np.asarray(target, dtype=float)
        if y.ndim != 1 or len(y) != len(frame) or not np.all(np.isfinite(y)):
            raise VirtualMetrologyError("invalid target for Preston proxy fit")
        medians = self._fit_positive_medians(frame)
        exposure = self.exposure(frame, medians)
        denominator = float(np.dot(exposure, exposure))
        if not math.isfinite(denominator) or denominator <= 0.0:
            raise VirtualMetrologyError("Preston coefficient denominator is not positive")
        coefficient = max(0.0, float(np.dot(exposure, y) / denominator))
        payload = {
            "feature_columns": list(self.feature_columns),
            "positive_medians": medians,
            "coefficient_native": coefficient,
        }
        self.state = PrestonProxyState(
            feature_columns=self.feature_columns,
            positive_medians=medians,
            coefficient_native=coefficient,
            state_sha256=canonical_sha256(payload),
        )
        return self

    def predict(self, frame: pd.DataFrame) -> np.ndarray:
        if self.state is None:
            raise VirtualMetrologyError("Preston proxy is not fitted")
        return self.state.coefficient_native * self.exposure(frame)


class VirtualMetrologyPredictor:
    """Frozen Predictor 1.0 implementation for one WP09 model family."""

    artifact_version = "1.0.0"

    def __init__(
        self,
        config: VirtualMetrologyConfig,
        model_kind: ModelKind | str,
        feature_columns: Sequence[str],
        hyperparameters: Mapping[str, Any] | None = None,
    ) -> None:
        self.config = config
        self.model_kind = ModelKind(model_kind)
        self.feature_columns = tuple(feature_columns)
        self.hyperparameters = dict(hyperparameters or {})
        self.preprocessor: CommonPreprocessor | None = None
        self.physics: NativePrestonProxy | None = None
        self.model: Any = None
        self.fit_group_sha256: str | None = None
        self.fit_split_identity: str | None = None
        self._fit_group_ids: tuple[str, ...] = ()
        self.conformal_radius: float | None = None
        self.calibration_split_identity: str | None = None
        self.calibration_group_sha256: str | None = None
        self.calibration_group_count: int | None = None
        self.calibration_row_count: int | None = None
        self.fitted = False

    def _require_sklearn(self) -> tuple[Any, Any, Any]:
        try:
            from sklearn.ensemble import HistGradientBoostingRegressor
            from sklearn.linear_model import LinearRegression, Ridge
        except ImportError as exc:
            raise VirtualMetrologyError(
                "WP09 requires the optional scikit-learn model dependency"
            ) from exc
        return LinearRegression, Ridge, HistGradientBoostingRegressor

    def _tree_model(self) -> Any:
        _, _, hist_gradient_boosting = self._require_sklearn()
        required = {
            "loss",
            "max_leaf_nodes",
            "min_samples_leaf",
            "l2_regularization",
        }
        if set(self.hyperparameters) != required:
            raise VirtualMetrologyError(
                f"tree hyperparameters must be exactly {sorted(required)}"
            )
        tree = self.config.models.gradient_boosted
        return hist_gradient_boosting(
            loss=str(self.hyperparameters["loss"]),
            max_iter=tree.max_iter,
            learning_rate=tree.learning_rate,
            max_leaf_nodes=int(self.hyperparameters["max_leaf_nodes"]),
            min_samples_leaf=int(self.hyperparameters["min_samples_leaf"]),
            l2_regularization=float(self.hyperparameters["l2_regularization"]),
            max_bins=tree.max_bins,
            early_stopping=tree.early_stopping,
            random_state=self.config.models.random_seed,
        )

    def fit(self, dataset: VMDataset) -> VirtualMetrologyPredictor:
        dataset.validate()
        y = np.asarray(dataset.target, dtype=float)
        groups = sorted(set(map(str, dataset.wafer_ids)))
        self.fit_group_sha256 = canonical_sha256(groups)
        self.fit_split_identity = dataset.split_identity
        self._fit_group_ids = tuple(groups)

        if self.model_kind is ModelKind.MEAN:
            if self.hyperparameters:
                raise VirtualMetrologyError("mean predictor accepts no hyperparameters")
            self.model = float(np.mean(y))
        elif self.model_kind is ModelKind.PHYSICS:
            if self.hyperparameters:
                raise VirtualMetrologyError("physics predictor accepts no hyperparameters")
            self.physics = NativePrestonProxy(self.config.preston_proxy).fit(
                dataset.features, y
            )
        else:
            linear_regression, ridge_regression, _ = self._require_sklearn()
            self.preprocessor = CommonPreprocessor(self.feature_columns).fit(dataset.features)
            scale = self.model_kind in {ModelKind.LINEAR, ModelKind.RIDGE}
            design = self.preprocessor.transform(dataset.features, scale=scale)
            if self.model_kind is ModelKind.LINEAR:
                if self.hyperparameters:
                    raise VirtualMetrologyError("linear predictor accepts no hyperparameters")
                self.model = linear_regression(
                    fit_intercept=self.config.models.linear.fit_intercept
                ).fit(design, y)
            elif self.model_kind is ModelKind.RIDGE:
                if set(self.hyperparameters) != {"alpha"}:
                    raise VirtualMetrologyError("ridge predictor requires only alpha")
                self.model = ridge_regression(
                    alpha=float(self.hyperparameters["alpha"]),
                    fit_intercept=self.config.models.ridge.fit_intercept,
                ).fit(design, y)
            elif self.model_kind is ModelKind.TREE:
                self.model = self._tree_model().fit(design, y)
            elif self.model_kind is ModelKind.HYBRID:
                self.physics = NativePrestonProxy(self.config.preston_proxy).fit(
                    dataset.features, y
                )
                residual = y - self.physics.predict(dataset.features)
                self.model = self._tree_model().fit(design, residual)
            else:  # pragma: no cover - Enum exhaustiveness guard
                raise VirtualMetrologyError(f"unsupported model kind: {self.model_kind}")
        self.fitted = True
        return self

    def _raw_predict(self, frame: pd.DataFrame) -> np.ndarray:
        if not self.fitted:
            raise VirtualMetrologyError("VM predictor is not fitted")
        if self.model_kind is ModelKind.MEAN:
            raw = np.full(len(frame), float(self.model), dtype=float)
        elif self.model_kind is ModelKind.PHYSICS:
            if self.physics is None:
                raise VirtualMetrologyError("physics predictor state is missing")
            raw = self.physics.predict(frame)
        else:
            if self.preprocessor is None:
                raise VirtualMetrologyError("preprocessor state is missing")
            scale = self.model_kind in {ModelKind.LINEAR, ModelKind.RIDGE}
            design = self.preprocessor.transform(frame, scale=scale)
            statistical = np.asarray(self.model.predict(design), dtype=float)
            if self.model_kind is ModelKind.HYBRID:
                if self.physics is None:
                    raise VirtualMetrologyError("hybrid physics state is missing")
                raw = self.physics.predict(frame) + statistical
            else:
                raw = statistical
        if raw.shape != (len(frame),) or not np.all(np.isfinite(raw)):
            raise VirtualMetrologyError("VM predictor produced invalid values")
        return raw

    def predict(self, observation_window: VMObservationWindow) -> VMPrediction:
        started = time.perf_counter()
        raw = self._raw_predict(observation_window.features)
        values = np.maximum(self.config.models.prediction_floor, raw)
        radius = self.conformal_radius
        lower = None
        upper = None
        if radius is not None:
            lower = np.maximum(self.config.uncertainty.lower_bound_floor, values - radius)
            upper = values + radius
        latency = time.perf_counter() - started
        negative_count = int(np.sum(raw < self.config.models.prediction_floor))
        return VMPrediction(
            values=values,
            raw_values=raw,
            lower=lower,
            upper=upper,
            model_kind=self.model_kind,
            target_unit_status=self.config.dataset.target_unit_status,
            raw_negative_prediction_count=negative_count,
            clipped_prediction_count=negative_count,
            latency_s=latency,
        )

    def calibrate(self, dataset: VMDataset) -> float:
        dataset.validate()
        calibration_groups = sorted(set(map(str, dataset.wafer_ids)))
        if set(calibration_groups) & set(self._fit_group_ids):
            raise VirtualMetrologyError("calibration groups overlap fit groups")
        prediction = self.predict(
            VMObservationWindow(dataset.features, dataset.split_identity)
        )
        scores = np.abs(np.asarray(dataset.target, dtype=float) - prediction.values)
        self.conformal_radius = split_conformal_quantile(
            scores, self.config.uncertainty.alpha
        )
        self.calibration_split_identity = dataset.split_identity
        self.calibration_group_sha256 = canonical_sha256(calibration_groups)
        self.calibration_group_count = len(calibration_groups)
        self.calibration_row_count = len(dataset.target)
        return self.conformal_radius

    def save(self, path: str | Path) -> None:
        if not self.fitted:
            raise VirtualMetrologyError("cannot save an unfitted VM predictor")
        artifact_path = Path(path)
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        payload = pickle.dumps(self, protocol=pickle.HIGHEST_PROTOCOL)
        temporary = artifact_path.with_suffix(artifact_path.suffix + ".tmp")
        temporary.write_bytes(payload)
        os.replace(temporary, artifact_path)
        digest_path = artifact_path.with_suffix(artifact_path.suffix + ".sha256")
        digest_temporary = digest_path.with_suffix(digest_path.suffix + ".tmp")
        digest_temporary.write_text(
            hashlib.sha256(payload).hexdigest() + "\n", encoding="utf-8"
        )
        os.replace(digest_temporary, digest_path)

    @classmethod
    def load(cls, path: str | Path) -> VirtualMetrologyPredictor:
        artifact_path = Path(path)
        digest_path = artifact_path.with_suffix(artifact_path.suffix + ".sha256")
        try:
            payload = artifact_path.read_bytes()
            expected = digest_path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise VirtualMetrologyError(f"cannot load VM artifact: {exc}") from exc
        observed = hashlib.sha256(payload).hexdigest()
        if observed != expected:
            raise VirtualMetrologyError("VM artifact checksum mismatch")
        restored = pickle.loads(payload)
        if not isinstance(restored, cls):
            raise VirtualMetrologyError("VM artifact has incompatible type")
        if restored.artifact_version.split(".", 1)[0] != cls.artifact_version.split(".", 1)[0]:
            raise VirtualMetrologyError("VM artifact major version is incompatible")
        return restored


def split_conformal_quantile(scores: Sequence[float], alpha: float) -> float:
    """Return the exact finite-sample higher split-conformal order statistic."""

    values = np.asarray(scores, dtype=float)
    if values.ndim != 1 or len(values) == 0 or not np.all(np.isfinite(values)):
        raise VirtualMetrologyError("conformal scores must be a non-empty finite vector")
    if not math.isfinite(alpha) or not 0.0 < alpha < 1.0:
        raise VirtualMetrologyError("conformal alpha must lie strictly within (0, 1)")
    rank = min(len(values), math.ceil((len(values) + 1) * (1.0 - alpha)))
    return float(np.partition(values, rank - 1)[rank - 1])


def predictor_columns(frame: pd.DataFrame, config: VirtualMetrologyConfig) -> tuple[str, ...]:
    """Extract the frozen target-free predictor contract from a feature frame."""

    forbidden = set(config.features.forbidden_predictors)
    columns = tuple(
        column
        for column in frame.columns
        if column not in forbidden and not column.startswith(config.features.metadata_prefix)
    )
    if len(columns) != config.dataset.expected_predictor_count:
        raise VirtualMetrologyError(
            f"expected {config.dataset.expected_predictor_count} predictors, found {len(columns)}"
        )
    if config.dataset.target in columns:
        raise VirtualMetrologyError("MRR target leaked into predictor columns")
    return columns


def feature_set_columns(
    all_predictors: Sequence[str],
    feature_set: str,
    config: VirtualMetrologyConfig,
) -> tuple[str, ...]:
    """Return one preregistered raw feature subset without target inspection."""

    columns = tuple(all_predictors)
    if feature_set == "FULL":
        selected = columns
    elif feature_set == "ACTIVE_ONLY":
        prefix = f"{config.preston_proxy.active_prefix}__"
        selected = tuple(
            column
            for column in columns
            if "__" not in column or column.startswith(prefix)
        )
    elif feature_set == "NO_UNRESOLVED":
        selected = tuple(
            column for column in columns if not column.startswith("UNRESOLVED_PROXY__")
        )
    elif feature_set == "WITHOUT_CONSUMABLE_USAGE":
        tokens = tuple(
            f"__{signal}__" for signal in config.features.consumable_signal_names
        )
        selected = tuple(
            column
            for column in columns
            if not any(token in column for token in tokens)
        )
    else:
        raise VirtualMetrologyError(f"unknown WP09 feature set: {feature_set}")
    if not selected:
        raise VirtualMetrologyError(f"feature set {feature_set} is empty")
    return selected


def deterministic_group_folds(
    groups: Sequence[str],
    *,
    n_splits: int,
    seed: int,
) -> tuple[tuple[np.ndarray, np.ndarray], ...]:
    """Assign sorted whole groups to deterministic cyclic validation folds."""

    values = np.asarray(list(map(str, groups)), dtype=object)
    unique = sorted(set(values.tolist()))
    if n_splits < 2 or len(unique) < n_splits:
        raise VirtualMetrologyError("insufficient groups for deterministic folds")
    rng = np.random.default_rng(seed)
    permuted = [unique[index] for index in rng.permutation(len(unique))]
    fold_by_group = {group: rank % n_splits for rank, group in enumerate(permuted)}
    folds: list[tuple[np.ndarray, np.ndarray]] = []
    for fold_index in range(n_splits):
        validation_mask = np.array(
            [fold_by_group[str(group)] == fold_index for group in values], dtype=bool
        )
        train_indices = np.flatnonzero(~validation_mask)
        validation_indices = np.flatnonzero(validation_mask)
        if len(train_indices) == 0 or len(validation_indices) == 0:
            raise VirtualMetrologyError("deterministic group fold is empty")
        folds.append((train_indices, validation_indices))
    return tuple(folds)


def subset_dataset(dataset: VMDataset, indices: Sequence[int], split_identity: str) -> VMDataset:
    """Return a row-conserving subset with aligned identities."""

    array = np.asarray(indices, dtype=int)
    return VMDataset(
        features=dataset.features.iloc[array].copy(),
        target=np.asarray(dataset.target, dtype=float)[array],
        wafer_ids=tuple(np.asarray(dataset.wafer_ids, dtype=object)[array].tolist()),
        stages=tuple(np.asarray(dataset.stages, dtype=object)[array].tolist()),
        split_identity=split_identity,
    )


def model_hyperparameter_candidates(
    config: VirtualMetrologyConfig, model_kind: ModelKind | str
) -> tuple[dict[str, Any], ...]:
    """Enumerate the frozen deterministic hyperparameter grid."""

    kind = ModelKind(model_kind)
    if kind in {ModelKind.MEAN, ModelKind.LINEAR, ModelKind.PHYSICS}:
        return ({},)
    if kind is ModelKind.RIDGE:
        return tuple({"alpha": value} for value in config.models.ridge.alpha_grid)
    tree = config.models.gradient_boosted
    return tuple(
        {
            "loss": loss,
            "max_leaf_nodes": max_leaf_nodes,
            "min_samples_leaf": min_samples_leaf,
            "l2_regularization": l2_regularization,
        }
        for loss, max_leaf_nodes, min_samples_leaf, l2_regularization in itertools.product(
            tree.loss_grid,
            tree.max_leaf_nodes_grid,
            tree.min_samples_leaf_grid,
            tree.l2_regularization_grid,
        )
    )


def select_hyperparameters(
    dataset: VMDataset,
    config: VirtualMetrologyConfig,
    model_kind: ModelKind | str,
    feature_columns: Sequence[str],
) -> dict[str, Any]:
    """Select one candidate using pooled out-of-fold whole-wafer MAE."""

    dataset.validate()
    kind = ModelKind(model_kind)
    folds = deterministic_group_folds(
        dataset.wafer_ids,
        n_splits=config.splits.tuning_group_folds,
        seed=config.splits.inner_random_seed,
    )
    candidate_rows: list[dict[str, Any]] = []
    for candidate_index, candidate in enumerate(model_hyperparameter_candidates(config, kind)):
        absolute_error_sum = 0.0
        row_count = 0
        fold_preprocessor_hashes: list[str | None] = []
        for fold_index, (train_indices, validation_indices) in enumerate(folds):
            training = subset_dataset(dataset, train_indices, f"TUNING_FOLD_{fold_index}_FIT")
            validation = subset_dataset(
                dataset, validation_indices, f"TUNING_FOLD_{fold_index}_VALIDATION"
            )
            predictor = VirtualMetrologyPredictor(
                config, kind, feature_columns, candidate
            ).fit(training)
            prediction = predictor.predict(
                VMObservationWindow(validation.features, validation.split_identity)
            )
            absolute_error_sum += float(
                np.sum(np.abs(np.asarray(validation.target) - prediction.values))
            )
            row_count += len(validation.target)
            fold_preprocessor_hashes.append(
                predictor.preprocessor.state.state_sha256
                if predictor.preprocessor is not None and predictor.preprocessor.state is not None
                else None
            )
        candidate_rows.append(
            {
                "candidate_index": candidate_index,
                "hyperparameters": candidate,
                "pooled_oof_mae": absolute_error_sum / row_count,
                "row_count": row_count,
                "fold_preprocessor_hashes": fold_preprocessor_hashes,
            }
        )
    best = candidate_rows[0]
    for row in candidate_rows[1:]:
        if row["pooled_oof_mae"] < best["pooled_oof_mae"] - config.models.tie_tolerance:
            best = row
    return {
        "model_kind": kind.value,
        "selected_hyperparameters": best["hyperparameters"],
        "selected_pooled_oof_mae": best["pooled_oof_mae"],
        "candidate_results": candidate_rows,
        "test_or_validation_used": False,
    }


def error_distribution(values: Sequence[float]) -> dict[str, float]:
    """Return the frozen distribution summary for a finite error vector."""

    array = np.asarray(values, dtype=float)
    if array.ndim != 1 or len(array) == 0 or not np.all(np.isfinite(array)):
        raise VirtualMetrologyError("error distribution requires finite values")
    return {
        "mean": float(np.mean(array)),
        "median": float(np.median(array)),
        "std": float(np.std(array, ddof=0)),
        "p05": float(np.percentile(array, 5.0)),
        "p95": float(np.percentile(array, 95.0)),
        "worst": float(np.max(array)),
    }


def regression_metrics(
    target: Sequence[float],
    prediction: Sequence[float],
    *,
    relative_denominator_floor: float,
    lower: Sequence[float] | None = None,
    upper: Sequence[float] | None = None,
) -> dict[str, Any]:
    """Compute the complete frozen WP09 point and interval metric set."""

    y = np.asarray(target, dtype=float)
    predicted = np.asarray(prediction, dtype=float)
    if y.ndim != 1 or predicted.shape != y.shape or len(y) == 0:
        raise VirtualMetrologyError("metric inputs must be non-empty aligned vectors")
    if not np.all(np.isfinite(y)) or not np.all(np.isfinite(predicted)):
        raise VirtualMetrologyError("metric inputs must be finite")
    error = predicted - y
    absolute = np.abs(error)
    relative = absolute / np.maximum(np.abs(y), relative_denominator_floor)
    denominator = float(np.sum((y - np.mean(y)) ** 2))
    r2 = None if denominator <= 0.0 else 1.0 - float(np.sum(error**2)) / denominator
    metrics: dict[str, Any] = {
        "row_count": len(y),
        "mae": float(np.mean(absolute)),
        "rmse": float(np.sqrt(np.mean(error**2))),
        "relative_mae": float(np.mean(relative)),
        "r2": r2,
        "bias": float(np.mean(error)),
        "absolute_error_distribution": error_distribution(absolute),
        "relative_error_distribution": error_distribution(relative),
    }
    if lower is not None or upper is not None:
        if lower is None or upper is None:
            raise VirtualMetrologyError("both interval bounds are required")
        lower_array = np.asarray(lower, dtype=float)
        upper_array = np.asarray(upper, dtype=float)
        if lower_array.shape != y.shape or upper_array.shape != y.shape:
            raise VirtualMetrologyError("interval bounds must align with target")
        if np.any(lower_array > upper_array):
            raise VirtualMetrologyError("interval lower bound exceeds upper bound")
        metrics["interval_coverage"] = float(
            np.mean((y >= lower_array) & (y <= upper_array))
        )
        metrics["interval_mean_width"] = float(np.mean(upper_array - lower_array))
    return metrics


def grouped_bootstrap_metrics(
    target: Sequence[float],
    prediction: Sequence[float],
    groups: Sequence[str],
    *,
    repetitions: int,
    seed: int,
    relative_denominator_floor: float,
    percentiles: Sequence[float] = (2.5, 50.0, 97.5),
) -> dict[str, dict[str, float]]:
    """Bootstrap complete wafers and summarize core regression metrics."""

    y = np.asarray(target, dtype=float)
    predicted = np.asarray(prediction, dtype=float)
    group_array = np.asarray(list(map(str, groups)), dtype=object)
    if len(y) != len(predicted) or len(y) != len(group_array):
        raise VirtualMetrologyError("grouped bootstrap inputs are not aligned")
    unique_groups = np.array(sorted(set(group_array.tolist())), dtype=object)
    if len(unique_groups) == 0 or repetitions <= 0:
        raise VirtualMetrologyError("grouped bootstrap requires groups and repetitions")
    indices_by_group = {
        group: np.flatnonzero(group_array == group) for group in unique_groups
    }
    rng = np.random.default_rng(seed)
    samples: dict[str, list[float]] = {
        "mae": [],
        "rmse": [],
        "relative_mae": [],
        "r2": [],
        "bias": [],
    }
    for _ in range(repetitions):
        drawn = rng.choice(unique_groups, size=len(unique_groups), replace=True)
        indices = np.concatenate([indices_by_group[group] for group in drawn])
        metrics = regression_metrics(
            y[indices],
            predicted[indices],
            relative_denominator_floor=relative_denominator_floor,
        )
        for name in samples:
            value = metrics[name]
            if value is not None:
                samples[name].append(float(value))
    output: dict[str, dict[str, float]] = {}
    labels = ("p02_5", "p50", "p97_5")
    for name, values in samples.items():
        if not values:
            continue
        quantiles = np.percentile(np.asarray(values), percentiles)
        output[name] = {label: float(value) for label, value in zip(labels, quantiles)}
    return output


def grouped_bootstrap_paired_mae_difference(
    target: Sequence[float],
    prediction_a: Sequence[float],
    prediction_b: Sequence[float],
    groups: Sequence[str],
    *,
    repetitions: int,
    seed: int,
    percentiles: Sequence[float] = (2.5, 50.0, 97.5),
) -> dict[str, float]:
    """Return grouped-bootstrap MAE(A)-MAE(B) percentiles."""

    y = np.asarray(target, dtype=float)
    a = np.asarray(prediction_a, dtype=float)
    b = np.asarray(prediction_b, dtype=float)
    group_array = np.asarray(list(map(str, groups)), dtype=object)
    if not (len(y) == len(a) == len(b) == len(group_array)):
        raise VirtualMetrologyError("paired bootstrap inputs are not aligned")
    unique_groups = np.array(sorted(set(group_array.tolist())), dtype=object)
    indices_by_group = {
        group: np.flatnonzero(group_array == group) for group in unique_groups
    }
    rng = np.random.default_rng(seed)
    differences = np.empty(repetitions, dtype=float)
    for index in range(repetitions):
        drawn = rng.choice(unique_groups, size=len(unique_groups), replace=True)
        rows = np.concatenate([indices_by_group[group] for group in drawn])
        differences[index] = np.mean(np.abs(a[rows] - y[rows])) - np.mean(
            np.abs(b[rows] - y[rows])
        )
    quantiles = np.percentile(differences, percentiles)
    return {
        "p02_5": float(quantiles[0]),
        "p50": float(quantiles[1]),
        "p97_5": float(quantiles[2]),
    }


@dataclass(frozen=True)
class FeatureRoleBundle:
    source_training: pd.DataFrame
    source_test: pd.DataFrame
    source_validation: pd.DataFrame
    retained_training: pd.DataFrame
    retained_test: pd.DataFrame
    retained_validation: pd.DataFrame
    train_core: pd.DataFrame
    model_selection: pd.DataFrame
    interval_calibration: pd.DataFrame
    predictor_columns: tuple[str, ...]
    source_manifest: dict[str, Any]


def _sorted_group_values(frame: pd.DataFrame, column: str) -> list[str]:
    return sorted(map(str, frame[column].unique().tolist()))


def _row_key_sha256(frame: pd.DataFrame, group_column: str, stage_column: str) -> str:
    keys = sorted(
        (str(group), str(stage))
        for group, stage in frame.loc[:, [group_column, stage_column]].itertuples(
            index=False, name=None
        )
    )
    return canonical_sha256(keys)


def prepare_feature_only_roles(
    config: VirtualMetrologyConfig,
    *,
    repository_root: str | Path = ".",
) -> tuple[FeatureRoleBundle, dict[str, Any]]:
    """Verify feature artifacts and freeze all roles without reading targets."""

    root = Path(repository_root)
    manifest_path = root / config.dataset.feature_manifest
    observed_manifest_sha256 = sha256_file(manifest_path)
    if observed_manifest_sha256 != config.dataset.expected_feature_manifest_sha256:
        raise VirtualMetrologyError(
            "feature manifest hash differs from the preregistered WP09 value"
        )
    try:
        source_manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise VirtualMetrologyError(f"cannot read feature manifest: {exc}") from exc
    if not isinstance(source_manifest, dict):
        raise VirtualMetrologyError("feature manifest root must be a mapping")
    if source_manifest.get("target") != config.dataset.target:
        raise VirtualMetrologyError("feature manifest target contract mismatch")
    if source_manifest.get("gap_threshold_s") != config.dataset.primary_gap_threshold_s:
        raise VirtualMetrologyError("feature manifest gap threshold mismatch")

    frames: dict[str, pd.DataFrame] = {}
    file_evidence: dict[str, Any] = {}
    for role in ("training", "test", "validation"):
        entry = source_manifest["files"][f"{role}_features"]
        path = root / entry["path"]
        observed_sha256 = sha256_file(path)
        if observed_sha256 != entry["sha256"]:
            raise VirtualMetrologyError(f"{role} feature checksum mismatch")
        frame = pd.read_csv(
            path,
            dtype={config.splits.group_column: str, config.splits.stage_column: str},
        )
        if len(frame) != entry["row_count"] or len(frame.columns) != entry["column_count"]:
            raise VirtualMetrologyError(f"{role} feature shape mismatch")
        if config.dataset.target in frame.columns:
            raise VirtualMetrologyError(f"target leaked into {role} feature frame")
        frames[role] = frame
        file_evidence[role] = {
            "path": entry["path"],
            "sha256": observed_sha256,
            "row_count": len(frame),
            "column_count": len(frame.columns),
        }

    columns = predictor_columns(frames["training"], config)
    for role in ("test", "validation"):
        if predictor_columns(frames[role], config) != columns:
            raise VirtualMetrologyError("official feature predictor order differs by role")

    precedence = official_group_precedence_split(
        frames["training"],
        frames["test"],
        frames["validation"],
        [config.splits.group_column],
    )
    if precedence.audit.retained_row_counts != config.splits.expected_retained_rows:
        raise VirtualMetrologyError("precedence retained-row counts differ from config")
    if precedence.audit.retained_group_counts != config.splits.expected_retained_groups:
        raise VirtualMetrologyError("precedence retained-group counts differ from config")

    inner = grouped_split(
        precedence.training,
        [config.splits.group_column],
        train_fraction=config.splits.train_core_fraction,
        validation_fraction=config.splits.model_selection_fraction,
        random_state=config.splits.inner_random_seed,
    )
    roles = {
        "TRAIN_CORE": inner.train,
        "MODEL_SELECTION": inner.validation,
        "INTERVAL_CALIBRATION": inner.test,
        "OFFICIAL_TEST_RETAINED": precedence.test,
        "OFFICIAL_VALIDATION_RETAINED": precedence.validation,
    }
    group_lists = {
        name: _sorted_group_values(frame, config.splits.group_column)
        for name, frame in roles.items()
    }
    all_role_sets = {name: set(values) for name, values in group_lists.items()}
    overlap_counts: dict[str, int] = {}
    names = list(group_lists)
    for left_index, left in enumerate(names):
        for right in names[left_index + 1 :]:
            overlap_counts[f"{left}__{right}"] = len(
                all_role_sets[left] & all_role_sets[right]
            )
    if any(overlap_counts.values()):
        raise VirtualMetrologyError(f"feature-only role overlap detected: {overlap_counts}")

    split_manifest = {
        "schema_version": "1.0.0",
        "dataset_id": config.dataset.dataset_id,
        "feature_contract": config.dataset.feature_contract,
        "holdout_targets_accessed": False,
        "target_in_feature_files": False,
        "source_feature_manifest": {
            "path": config.dataset.feature_manifest,
            "sha256": observed_manifest_sha256,
        },
        "feature_files": file_evidence,
        "predictor_count": len(columns),
        "predictor_order_sha256": canonical_sha256(list(columns)),
        "official_precedence_audit": precedence.audit.to_dict(),
        "roles": {
            name: {
                "row_count": len(frame),
                "group_count": len(group_lists[name]),
                "group_values": group_lists[name],
                "group_values_sha256": canonical_sha256(group_lists[name]),
                "wafer_stage_keys_sha256": _row_key_sha256(
                    frame, config.splits.group_column, config.splits.stage_column
                ),
            }
            for name, frame in roles.items()
        },
        "pairwise_group_overlap_counts": overlap_counts,
        "inner_split_seed": config.splits.inner_random_seed,
        "inner_split_fractions": {
            "TRAIN_CORE": config.splits.train_core_fraction,
            "MODEL_SELECTION": config.splits.model_selection_fraction,
            "INTERVAL_CALIBRATION": config.splits.interval_calibration_fraction,
        },
        "config_payload_sha256": canonical_sha256(config.model_dump(mode="json")),
        "claim_boundary": (
            "FEATURE_IDENTITY_AND_SPLIT_PROVENANCE_ONLY_NO_TARGET_OR_MODEL_RESULT"
        ),
    }
    split_manifest["deterministic_payload_sha256"] = canonical_sha256(split_manifest)
    bundle = FeatureRoleBundle(
        source_training=frames["training"],
        source_test=frames["test"],
        source_validation=frames["validation"],
        retained_training=precedence.training,
        retained_test=precedence.test,
        retained_validation=precedence.validation,
        train_core=inner.train,
        model_selection=inner.validation,
        interval_calibration=inner.test,
        predictor_columns=columns,
        source_manifest=source_manifest,
    )
    return bundle, split_manifest


@dataclass(frozen=True)
class LoadedTargetLabels:
    """Verified label tables opened only by the one-shot experiment boundary."""

    training_by_policy: dict[str, pd.DataFrame]
    test: pd.DataFrame
    validation: pd.DataFrame
    access_audit: dict[str, Any]


def _read_verified_label_file(
    root: Path,
    entry: Mapping[str, Any],
    config: VirtualMetrologyConfig,
) -> pd.DataFrame:
    path = root / str(entry["path"])
    observed_sha256 = sha256_file(path)
    if observed_sha256 != entry["sha256"]:
        raise VirtualMetrologyError(f"label checksum mismatch: {entry['path']}")
    frame = pd.read_csv(
        path,
        dtype={config.splits.group_column: str, config.splits.stage_column: str},
    )
    if len(frame) != entry["row_count"] or len(frame.columns) != entry["column_count"]:
        raise VirtualMetrologyError(f"label shape mismatch: {entry['path']}")
    required = {
        config.splits.group_column,
        config.splits.stage_column,
        config.dataset.target,
    }
    if not required <= set(frame.columns):
        raise VirtualMetrologyError(f"label columns missing from {entry['path']}")
    if frame.duplicated([config.splits.group_column, config.splits.stage_column]).any():
        raise VirtualMetrologyError(f"duplicate label key in {entry['path']}")
    target = pd.to_numeric(frame[config.dataset.target], errors="coerce").to_numpy(dtype=float)
    if not np.all(np.isfinite(target)) or np.any(target < 0.0):
        raise VirtualMetrologyError(f"invalid native MRR target in {entry['path']}")
    return frame


def load_verified_target_labels(
    bundle: FeatureRoleBundle,
    config: VirtualMetrologyConfig,
    *,
    repository_root: str | Path = ".",
) -> LoadedTargetLabels:
    """Open every required target file once after the frozen-run guards pass."""

    root = Path(repository_root)
    files = bundle.source_manifest["files"]
    policy_entries = {
        "ORIGINAL": "training_label_policy_original",
        "EXCLUDE_FOUR_PREREGISTERED": (
            "training_label_policy_exclude_four_preregistered"
        ),
        "HYPOTHETICAL_DIVIDE_FOUR_BY_60": (
            "training_label_policy_hypothetical_divide_four_by_60"
        ),
    }
    expected_policies = {
        config.target_policies.primary,
        *config.target_policies.sensitivities,
    }
    if set(policy_entries) != expected_policies:
        raise VirtualMetrologyError("configured target policies differ from frozen files")
    training_by_policy = {
        policy: _read_verified_label_file(root, files[entry_name], config)
        for policy, entry_name in policy_entries.items()
    }
    test = _read_verified_label_file(root, files["test_labels"], config)
    validation = _read_verified_label_file(root, files["validation_labels"], config)
    label_evidence = {
        policy: {
            "path": files[entry_name]["path"],
            "sha256": files[entry_name]["sha256"],
            "row_count": len(training_by_policy[policy]),
        }
        for policy, entry_name in policy_entries.items()
    }
    label_evidence["OFFICIAL_TEST_NATIVE"] = {
        "path": files["test_labels"]["path"],
        "sha256": files["test_labels"]["sha256"],
        "row_count": len(test),
    }
    label_evidence["OFFICIAL_VALIDATION_NATIVE"] = {
        "path": files["validation_labels"]["path"],
        "sha256": files["validation_labels"]["sha256"],
        "row_count": len(validation),
    }
    return LoadedTargetLabels(
        training_by_policy=training_by_policy,
        test=test,
        validation=validation,
        access_audit={
            "holdout_targets_accessed": True,
            "accessed_at_utc": datetime.now(timezone.utc).isoformat(),
            "files": label_evidence,
            "policy_selected_from_holdout": False,
            "claim_boundary": "OFFLINE_PUBLIC_AVERAGE_MRR_ONLY",
        },
    )


def join_features_and_labels(
    features: pd.DataFrame,
    labels: pd.DataFrame,
    config: VirtualMetrologyConfig,
    *,
    role: str,
    allow_missing: bool = False,
) -> pd.DataFrame:
    """Join one target per completed wafer-stage feature row with an exact audit."""

    keys = [config.splits.group_column, config.splits.stage_column]
    feature_view = features.copy()
    feature_view["_WP09_ROW_ORDER"] = np.arange(len(feature_view), dtype=int)
    label_view = labels.loc[:, [*keys, config.dataset.target]]
    joined = feature_view.merge(label_view, on=keys, how="left", validate="one_to_one")
    joined = joined.sort_values("_WP09_ROW_ORDER", kind="mergesort").drop(
        columns="_WP09_ROW_ORDER"
    )
    target = pd.to_numeric(joined[config.dataset.target], errors="coerce").to_numpy(
        dtype=float
    )
    if len(joined) != len(features):
        raise VirtualMetrologyError(f"{role} feature/label join is incomplete")
    finite = np.isfinite(target)
    if not allow_missing and not np.all(finite):
        raise VirtualMetrologyError(f"{role} feature/label join is incomplete")
    if not np.any(finite) or np.any(target[finite] < 0.0):
        raise VirtualMetrologyError(f"{role} contains a negative MRR target")
    return joined


def make_vm_dataset(
    joined: pd.DataFrame,
    feature_columns: Sequence[str],
    config: VirtualMetrologyConfig,
    *,
    split_identity: str,
) -> VMDataset:
    """Convert a joined role into the typed Predictor input contract."""

    dataset = VMDataset(
        features=joined.loc[:, list(feature_columns)].copy(),
        target=pd.to_numeric(joined[config.dataset.target], errors="coerce").to_numpy(
            dtype=float
        ),
        wafer_ids=tuple(joined[config.splits.group_column].astype(str).tolist()),
        stages=tuple(joined[config.splits.stage_column].astype(str).tolist()),
        split_identity=split_identity,
    )
    dataset.validate()
    return dataset


def make_policy_datasets(
    bundle: FeatureRoleBundle,
    labels: LoadedTargetLabels,
    config: VirtualMetrologyConfig,
    *,
    policy: str,
    feature_columns: Sequence[str],
) -> dict[str, VMDataset]:
    """Materialize every frozen role for one training-label policy."""

    if policy not in labels.training_by_policy:
        raise VirtualMetrologyError(f"unknown target policy: {policy}")
    training_labels = labels.training_by_policy[policy]
    role_frames = {
        "TRAIN_CORE": (bundle.train_core, training_labels),
        "MODEL_SELECTION": (bundle.model_selection, training_labels),
        "INTERVAL_CALIBRATION": (bundle.interval_calibration, training_labels),
        "OFFICIAL_TEST_RETAINED": (bundle.retained_test, labels.test),
        "OFFICIAL_VALIDATION_RETAINED": (
            bundle.retained_validation,
            labels.validation,
        ),
        "OFFICIAL_TEST_FULL_COLLISION_CONTAMINATED": (
            bundle.source_test,
            labels.test,
        ),
        "OFFICIAL_VALIDATION_FULL_COLLISION_CONTAMINATED": (
            bundle.source_validation,
            labels.validation,
        ),
    }
    datasets: dict[str, VMDataset] = {}
    for role, (features, role_labels) in role_frames.items():
        excluded_training_role = policy == "EXCLUDE_FOUR_PREREGISTERED" and role in {
            "TRAIN_CORE",
            "MODEL_SELECTION",
            "INTERVAL_CALIBRATION",
        }
        joined = join_features_and_labels(
            features,
            role_labels,
            config,
            role=f"{policy}:{role}",
            allow_missing=excluded_training_role,
        )
        if excluded_training_role:
            joined = joined.loc[joined[config.dataset.target].notna()].copy()
        datasets[role] = make_vm_dataset(
            joined,
            feature_columns,
            config,
            split_identity=f"{policy}:{role}",
        )
    return datasets


def concatenate_vm_datasets(
    left: VMDataset,
    right: VMDataset,
    *,
    split_identity: str,
) -> VMDataset:
    """Join two disjoint fit roles while preserving row and group identity."""

    left.validate()
    right.validate()
    if tuple(left.features.columns) != tuple(right.features.columns):
        raise VirtualMetrologyError("cannot concatenate differing feature contracts")
    if set(left.wafer_ids) & set(right.wafer_ids):
        raise VirtualMetrologyError("cannot concatenate overlapping wafer roles")
    dataset = VMDataset(
        features=pd.concat([left.features, right.features], ignore_index=True),
        target=np.concatenate([left.target, right.target]),
        wafer_ids=left.wafer_ids + right.wafer_ids,
        stages=left.stages + right.stages,
        split_identity=split_identity,
    )
    dataset.validate()
    return dataset


def prediction_evaluation(
    dataset: VMDataset,
    prediction: VMPrediction,
    config: VirtualMetrologyConfig,
    *,
    include_bootstrap: bool,
    bootstrap_seed_offset: int = 0,
) -> dict[str, Any]:
    """Evaluate one prediction overall and by source stage."""

    dataset.validate()
    if len(prediction.values) != len(dataset.target):
        raise VirtualMetrologyError("prediction is not aligned with evaluation role")
    overall = regression_metrics(
        dataset.target,
        prediction.values,
        relative_denominator_floor=config.evaluation.relative_error_denominator_floor,
        lower=prediction.lower,
        upper=prediction.upper,
    )
    result: dict[str, Any] = {
        "split_identity": dataset.split_identity,
        "target_unit_status": config.dataset.target_unit_status,
        "overall": overall,
        "by_stage": {},
        "raw_negative_prediction_count": prediction.raw_negative_prediction_count,
        "clipped_prediction_count": prediction.clipped_prediction_count,
        "prediction_latency_s": prediction.latency_s,
        "throughput_rows_s": (
            len(dataset.target) / prediction.latency_s
            if prediction.latency_s > 0.0
            else None
        ),
    }
    stages = np.asarray(dataset.stages, dtype=object)
    for stage in ("A", "B"):
        mask = stages == stage
        if not np.any(mask):
            raise VirtualMetrologyError(f"evaluation role lacks Stage {stage}")
        lower = prediction.lower[mask] if prediction.lower is not None else None
        upper = prediction.upper[mask] if prediction.upper is not None else None
        result["by_stage"][stage] = regression_metrics(
            np.asarray(dataset.target)[mask],
            prediction.values[mask],
            relative_denominator_floor=(
                config.evaluation.relative_error_denominator_floor
            ),
            lower=lower,
            upper=upper,
        )
    if include_bootstrap:
        result["grouped_bootstrap_95"] = grouped_bootstrap_metrics(
            dataset.target,
            prediction.values,
            dataset.wafer_ids,
            repetitions=config.evaluation.grouped_bootstrap_repetitions,
            seed=config.evaluation.grouped_bootstrap_seed + bootstrap_seed_offset,
            relative_denominator_floor=(
                config.evaluation.relative_error_denominator_floor
            ),
            percentiles=config.evaluation.bootstrap_percentiles,
        )
    return result


def prediction_rows(
    dataset: VMDataset,
    prediction: VMPrediction,
    *,
    policy: str,
    analysis: str,
) -> pd.DataFrame:
    """Return auditable row-aligned prediction evidence without SI relabelling."""

    frame = pd.DataFrame(
        {
            "ANALYSIS": analysis,
            "TARGET_POLICY": policy,
            "ROLE": dataset.split_identity,
            "WAFER_ID": dataset.wafer_ids,
            "STAGE": dataset.stages,
            "TARGET_NATIVE": dataset.target,
            "PREDICTION_NATIVE": prediction.values,
            "RAW_PREDICTION_NATIVE": prediction.raw_values,
        }
    )
    if prediction.lower is not None and prediction.upper is not None:
        frame["INTERVAL_LOWER_NATIVE"] = prediction.lower
        frame["INTERVAL_UPPER_NATIVE"] = prediction.upper
    return frame


def write_json_atomic(payload: Any, path: str | Path) -> None:
    """Write a JSON artifact atomically with non-finite values forbidden."""

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, output)


def write_csv_atomic(frame: pd.DataFrame, path: str | Path) -> None:
    """Write a CSV artifact atomically without changing the input frame."""

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    frame.to_csv(temporary, index=False, lineterminator="\n")
    os.replace(temporary, output)


def _predictor_evidence(predictor: VirtualMetrologyPredictor) -> dict[str, Any]:
    return {
        "model_kind": predictor.model_kind.value,
        "hyperparameters": predictor.hyperparameters,
        "fit_split_identity": predictor.fit_split_identity,
        "fit_group_sha256": predictor.fit_group_sha256,
        "fit_group_count": len(predictor._fit_group_ids),
        "preprocessor_state_sha256": (
            predictor.preprocessor.state.state_sha256
            if predictor.preprocessor is not None
            and predictor.preprocessor.state is not None
            else None
        ),
        "preprocessor_retained_derived_feature_count": (
            len(predictor.preprocessor.state.retained_names)
            if predictor.preprocessor is not None
            and predictor.preprocessor.state is not None
            else None
        ),
        "preprocessor_dropped_derived_feature_count": (
            len(predictor.preprocessor.state.dropped_names)
            if predictor.preprocessor is not None
            and predictor.preprocessor.state is not None
            else None
        ),
        "physics_state_sha256": (
            predictor.physics.state.state_sha256
            if predictor.physics is not None and predictor.physics.state is not None
            else None
        ),
        "physics_coefficient_native": (
            predictor.physics.state.coefficient_native
            if predictor.physics is not None and predictor.physics.state is not None
            else None
        ),
        "conformal_radius_native": predictor.conformal_radius,
        "calibration_split_identity": predictor.calibration_split_identity,
        "calibration_group_sha256": predictor.calibration_group_sha256,
        "calibration_group_count": predictor.calibration_group_count,
        "calibration_row_count": predictor.calibration_row_count,
        "target_unit_status": predictor.config.dataset.target_unit_status,
    }


def _runtime_evidence() -> dict[str, Any]:
    package_versions: dict[str, str] = {}
    for distribution in ("numpy", "pandas", "pydantic", "PyYAML", "scikit-learn"):
        try:
            package_versions[distribution] = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            package_versions[distribution] = "NOT_INSTALLED"
    return {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "packages": package_versions,
    }


def _repository_relative_path(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError as exc:
        raise VirtualMetrologyError(
            f"WP09 artifact must remain inside the repository: {path}"
        ) from exc


def _selection_winner(
    scores: Mapping[str, float],
    simplicity_order: Sequence[str],
    tie_tolerance: float,
) -> str:
    if not scores:
        raise VirtualMetrologyError("model selection scores cannot be empty")
    order = {name: index for index, name in enumerate(simplicity_order)}
    unknown = set(scores) - set(order)
    if unknown:
        raise VirtualMetrologyError(f"selection scores contain unknown families: {unknown}")
    best = min(scores, key=lambda name: (scores[name], order[name]))
    best_score = scores[best]
    tied = [
        name for name, score in scores.items() if abs(score - best_score) <= tie_tolerance
    ]
    return min(tied, key=order.__getitem__)


def _fit_calibrated_predictor(
    config: VirtualMetrologyConfig,
    model_kind: ModelKind,
    hyperparameters: Mapping[str, Any],
    feature_columns: Sequence[str],
    fit: VMDataset,
    calibration: VMDataset,
) -> VirtualMetrologyPredictor:
    predictor = VirtualMetrologyPredictor(
        config, model_kind, feature_columns, hyperparameters
    ).fit(fit)
    predictor.calibrate(calibration)
    return predictor


def _evaluate_role(
    predictor: VirtualMetrologyPredictor,
    dataset: VMDataset,
    config: VirtualMetrologyConfig,
    *,
    include_bootstrap: bool,
    bootstrap_seed_offset: int,
) -> tuple[VMPrediction, dict[str, Any]]:
    prediction = predictor.predict(VMObservationWindow(dataset.features, dataset.split_identity))
    report = prediction_evaluation(
        dataset,
        prediction,
        config,
        include_bootstrap=include_bootstrap,
        bootstrap_seed_offset=bootstrap_seed_offset,
    )
    return prediction, report


def _chronological_original_datasets(
    bundle: FeatureRoleBundle,
    labels: LoadedTargetLabels,
    config: VirtualMetrologyConfig,
    feature_columns: Sequence[str],
) -> dict[str, VMDataset]:
    joined = join_features_and_labels(
        bundle.retained_training,
        labels.training_by_policy[config.target_policies.primary],
        config,
        role="ORIGINAL:CHRONOLOGICAL_SOURCE",
    )
    split = chronological_group_split(
        joined,
        [config.splits.group_column],
        config.splits.chronological_time_column,
        train_fraction=config.splits.chronological_fractions[0],
        validation_fraction=config.splits.chronological_fractions[1],
    )
    return {
        "EARLY_FIT": make_vm_dataset(
            split.train,
            feature_columns,
            config,
            split_identity="ORIGINAL:CHRONOLOGICAL_EARLY_FIT",
        ),
        "MIDDLE_INTERVAL_CALIBRATION": make_vm_dataset(
            split.validation,
            feature_columns,
            config,
            split_identity="ORIGINAL:CHRONOLOGICAL_MIDDLE_INTERVAL_CALIBRATION",
        ),
        "LATE_EVALUATION": make_vm_dataset(
            split.test,
            feature_columns,
            config,
            split_identity="ORIGINAL:CHRONOLOGICAL_LATE_EVALUATION",
        ),
    }


def _gap_sensitivity_config(
    config: VirtualMetrologyConfig,
    *,
    manifest_path: Path,
    repository_root: Path,
    gap_threshold_s: float,
) -> VirtualMetrologyConfig:
    manifest_reference = _repository_relative_path(manifest_path, repository_root)
    dataset = config.dataset.model_copy(
        update={
            "feature_manifest": manifest_reference,
            "expected_feature_manifest_sha256": sha256_file(manifest_path),
            "primary_gap_threshold_s": gap_threshold_s,
        }
    )
    return config.model_copy(update={"dataset": dataset})


def _strip_nondeterministic_fields(value: Any) -> Any:
    excluded = {
        "accessed_at_utc",
        "prediction_latency_s",
        "throughput_rows_s",
        "model_artifacts",
    }
    if isinstance(value, dict):
        return {
            key: _strip_nondeterministic_fields(item)
            for key, item in value.items()
            if key not in excluded
        }
    if isinstance(value, list):
        return [_strip_nondeterministic_fields(item) for item in value]
    return value


def run_virtual_metrology_experiment(
    config: VirtualMetrologyConfig,
    bundle: FeatureRoleBundle,
    split_manifest: Mapping[str, Any],
    *,
    output_dir: str | Path,
    repository_root: str | Path = ".",
    preflight_evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute the frozen nonadaptive WP09 experiment and write local evidence."""

    root = Path(repository_root).resolve()
    output_candidate = Path(output_dir)
    output = (
        output_candidate.resolve()
        if output_candidate.is_absolute()
        else (root / output_candidate).resolve()
    )
    _repository_relative_path(output, root)
    output.mkdir(parents=True, exist_ok=True)
    if split_manifest.get("holdout_targets_accessed") is not False:
        raise VirtualMetrologyError("WP09 split manifest is not feature-only")
    fresh_bundle, fresh_split_manifest = prepare_feature_only_roles(
        config, repository_root=root
    )
    if fresh_split_manifest != dict(split_manifest):
        raise VirtualMetrologyError("committed feature-only split manifest does not replay")
    if fresh_bundle.predictor_columns != bundle.predictor_columns:
        raise VirtualMetrologyError("feature role bundle differs from frozen split manifest")

    labels = load_verified_target_labels(bundle, config, repository_root=root)
    full_columns = feature_set_columns(bundle.predictor_columns, "FULL", config)
    original_roles = make_policy_datasets(
        bundle,
        labels,
        config,
        policy=config.target_policies.primary,
        feature_columns=full_columns,
    )
    model_kinds = tuple(ModelKind(name) for name in config.models.required_families)

    tuning: dict[str, Any] = {}
    for model_kind in model_kinds:
        tuning[model_kind.value] = select_hyperparameters(
            original_roles["TRAIN_CORE"],
            config,
            model_kind,
            full_columns,
        )
    selected_hyperparameters = {
        name: row["selected_hyperparameters"] for name, row in tuning.items()
    }

    selection_reports: dict[str, Any] = {}
    selection_scores: dict[str, float] = {}
    for model_kind in model_kinds:
        predictor = VirtualMetrologyPredictor(
            config,
            model_kind,
            full_columns,
            selected_hyperparameters[model_kind.value],
        ).fit(original_roles["TRAIN_CORE"])
        prediction = predictor.predict(
            VMObservationWindow(
                original_roles["MODEL_SELECTION"].features,
                original_roles["MODEL_SELECTION"].split_identity,
            )
        )
        metrics = regression_metrics(
            original_roles["MODEL_SELECTION"].target,
            prediction.values,
            relative_denominator_floor=(
                config.evaluation.relative_error_denominator_floor
            ),
        )
        selection_scores[model_kind.value] = metrics["mae"]
        selection_reports[model_kind.value] = {
            "metrics": metrics,
            "predictor": _predictor_evidence(predictor),
        }
    recommended_family = _selection_winner(
        selection_scores,
        config.models.family_simplicity_order,
        config.models.tie_tolerance,
    )
    nonhybrid_scores = {
        name: score for name, score in selection_scores.items() if name != "hybrid"
    }
    strongest_nonhybrid = _selection_winner(
        nonhybrid_scores,
        config.models.family_simplicity_order,
        config.models.tie_tolerance,
    )

    development = concatenate_vm_datasets(
        original_roles["TRAIN_CORE"],
        original_roles["MODEL_SELECTION"],
        split_identity="ORIGINAL:DEVELOPMENT_CORE_PLUS_SELECTION",
    )
    primary_reports: dict[str, Any] = {}
    primary_predictions: dict[str, dict[str, VMPrediction]] = {}
    prediction_frames: list[pd.DataFrame] = []
    model_artifacts: dict[str, Any] = {}
    retained_roles = (
        "OFFICIAL_TEST_RETAINED",
        "OFFICIAL_VALIDATION_RETAINED",
    )
    contaminated_roles = (
        "OFFICIAL_TEST_FULL_COLLISION_CONTAMINATED",
        "OFFICIAL_VALIDATION_FULL_COLLISION_CONTAMINATED",
    )
    for family_index, model_kind in enumerate(model_kinds):
        predictor = _fit_calibrated_predictor(
            config,
            model_kind,
            selected_hyperparameters[model_kind.value],
            full_columns,
            development,
            original_roles["INTERVAL_CALIBRATION"],
        )
        family_reports: dict[str, Any] = {"predictor": _predictor_evidence(predictor)}
        family_predictions: dict[str, VMPrediction] = {}
        for role_index, role in enumerate((*retained_roles, *contaminated_roles)):
            prediction, report = _evaluate_role(
                predictor,
                original_roles[role],
                config,
                include_bootstrap=role in retained_roles,
                bootstrap_seed_offset=role_index,
            )
            family_reports[role] = report
            family_predictions[role] = prediction
            prediction_frames.append(
                prediction_rows(
                    original_roles[role],
                    prediction,
                    policy=config.target_policies.primary,
                    analysis=f"PRIMARY_{model_kind.value}",
                )
            )
        model_path = output / "models" / f"{model_kind.value}.pkl"
        predictor.save(model_path)
        model_artifacts[model_kind.value] = {
            "path": _repository_relative_path(model_path, root),
            "sha256": sha256_file(model_path),
            "checksum_path": _repository_relative_path(
                model_path.with_suffix(model_path.suffix + ".sha256"), root
            ),
            "family_index": family_index,
        }
        primary_reports[model_kind.value] = family_reports
        primary_predictions[model_kind.value] = family_predictions

    label_sensitivity_reports: dict[str, Any] = {}
    for policy_index, policy in enumerate(config.target_policies.sensitivities):
        roles = make_policy_datasets(
            bundle,
            labels,
            config,
            policy=policy,
            feature_columns=full_columns,
        )
        policy_development = concatenate_vm_datasets(
            roles["TRAIN_CORE"],
            roles["MODEL_SELECTION"],
            split_identity=f"{policy}:DEVELOPMENT_CORE_PLUS_SELECTION",
        )
        policy_reports: dict[str, Any] = {}
        for model_kind in model_kinds:
            predictor = _fit_calibrated_predictor(
                config,
                model_kind,
                selected_hyperparameters[model_kind.value],
                full_columns,
                policy_development,
                roles["INTERVAL_CALIBRATION"],
            )
            model_reports: dict[str, Any] = {"predictor": _predictor_evidence(predictor)}
            for role_index, role in enumerate(retained_roles):
                prediction, report = _evaluate_role(
                    predictor,
                    roles[role],
                    config,
                    include_bootstrap=True,
                    bootstrap_seed_offset=100 + 10 * policy_index + role_index,
                )
                model_reports[role] = report
                prediction_frames.append(
                    prediction_rows(
                        roles[role],
                        prediction,
                        policy=policy,
                        analysis=f"LABEL_SENSITIVITY_{model_kind.value}",
                    )
                )
            policy_reports[model_kind.value] = model_reports
        label_sensitivity_reports[policy] = policy_reports

    chronological_roles = _chronological_original_datasets(
        bundle, labels, config, full_columns
    )
    chronological_reports: dict[str, Any] = {
        "role_counts": {
            name: {
                "rows": len(dataset.target),
                "groups": len(set(dataset.wafer_ids)),
            }
            for name, dataset in chronological_roles.items()
        },
        "models": {},
    }
    for model_kind in model_kinds:
        predictor = _fit_calibrated_predictor(
            config,
            model_kind,
            selected_hyperparameters[model_kind.value],
            full_columns,
            chronological_roles["EARLY_FIT"],
            chronological_roles["MIDDLE_INTERVAL_CALIBRATION"],
        )
        prediction, report = _evaluate_role(
            predictor,
            chronological_roles["LATE_EVALUATION"],
            config,
            include_bootstrap=True,
            bootstrap_seed_offset=200,
        )
        chronological_reports["models"][model_kind.value] = {
            "predictor": _predictor_evidence(predictor),
            "LATE_EVALUATION": report,
        }
        prediction_frames.append(
            prediction_rows(
                chronological_roles["LATE_EVALUATION"],
                prediction,
                policy=config.target_policies.primary,
                analysis=f"CHRONOLOGICAL_{model_kind.value}",
            )
        )

    ablation_cache: dict[
        tuple[str, str],
        tuple[dict[str, Any], dict[str, VMPrediction], dict[str, VMDataset]],
    ] = {}

    def run_ablation(feature_set: str, model_name: str) -> tuple[
        dict[str, Any], dict[str, VMPrediction], dict[str, VMDataset]
    ]:
        cache_key = (feature_set, model_name)
        if cache_key in ablation_cache:
            return ablation_cache[cache_key]
        columns = feature_set_columns(bundle.predictor_columns, feature_set, config)
        roles = make_policy_datasets(
            bundle,
            labels,
            config,
            policy=config.target_policies.primary,
            feature_columns=columns,
        )
        fit = concatenate_vm_datasets(
            roles["TRAIN_CORE"],
            roles["MODEL_SELECTION"],
            split_identity=f"ORIGINAL:{feature_set}:DEVELOPMENT",
        )
        predictor = _fit_calibrated_predictor(
            config,
            ModelKind(model_name),
            selected_hyperparameters[model_name],
            columns,
            fit,
            roles["INTERVAL_CALIBRATION"],
        )
        reports: dict[str, Any] = {
            "feature_count": len(columns),
            "feature_order_sha256": canonical_sha256(list(columns)),
            "predictor": _predictor_evidence(predictor),
        }
        predictions: dict[str, VMPrediction] = {}
        for role_index, role in enumerate(retained_roles):
            prediction, report = _evaluate_role(
                predictor,
                roles[role],
                config,
                include_bootstrap=True,
                bootstrap_seed_offset=300 + role_index,
            )
            reports[role] = report
            predictions[role] = prediction
            prediction_frames.append(
                prediction_rows(
                    roles[role],
                    prediction,
                    policy=config.target_policies.primary,
                    analysis=f"ABLATION_{feature_set}_{model_name}",
                )
            )
        ablation_cache[cache_key] = (reports, predictions, roles)
        return ablation_cache[cache_key]

    proxy_ablation_reports: dict[str, Any] = {}
    for feature_set in config.sensitivities.proxy_feature_sets:
        proxy_ablation_reports[feature_set] = {}
        for model_name in config.sensitivities.proxy_models:
            reports, _, _ = run_ablation(feature_set, model_name)
            proxy_ablation_reports[feature_set][model_name] = reports

    consumable_ablation_reports: dict[str, Any] = {}
    for feature_set in config.sensitivities.consumable_feature_sets:
        consumable_ablation_reports[feature_set] = {}
        for model_name in config.sensitivities.consumable_models:
            reports, _, _ = run_ablation(feature_set, model_name)
            consumable_ablation_reports[feature_set][model_name] = reports

    gap_reports: dict[str, Any] = {}
    for gap_index, gap_threshold_s in enumerate(config.sensitivities.gap_threshold_s):
        slug = str(gap_threshold_s).replace(".", "p")
        gap_output = root / "data" / "interim" / f"phm_2016_cmp_gap_{slug}"
        from semifab_poc.data.build_features import build_feature_bundle

        build_feature_bundle(
            root=root / "data" / "raw" / "phm_2016_cmp",
            output_dir=gap_output,
            verify_checksums=True,
            gap_threshold_s=gap_threshold_s,
        )
        gap_manifest_path = gap_output / "feature_manifest.yaml"
        gap_config = _gap_sensitivity_config(
            config,
            manifest_path=gap_manifest_path,
            repository_root=root,
            gap_threshold_s=gap_threshold_s,
        )
        gap_bundle, gap_split_manifest = prepare_feature_only_roles(
            gap_config, repository_root=root
        )
        gap_labels = load_verified_target_labels(
            gap_bundle, gap_config, repository_root=root
        )
        gap_columns = feature_set_columns(gap_bundle.predictor_columns, "FULL", gap_config)
        gap_roles = make_policy_datasets(
            gap_bundle,
            gap_labels,
            gap_config,
            policy=gap_config.target_policies.primary,
            feature_columns=gap_columns,
        )
        gap_development = concatenate_vm_datasets(
            gap_roles["TRAIN_CORE"],
            gap_roles["MODEL_SELECTION"],
            split_identity=f"ORIGINAL:GAP_{gap_threshold_s}:DEVELOPMENT",
        )
        threshold_reports: dict[str, Any] = {
            "gap_threshold_s": gap_threshold_s,
            "feature_manifest": {
                "path": _repository_relative_path(gap_manifest_path, root),
                "sha256": sha256_file(gap_manifest_path),
            },
            "split_manifest_payload_sha256": gap_split_manifest[
                "deterministic_payload_sha256"
            ],
            "models": {},
        }
        for model_kind in model_kinds:
            predictor = _fit_calibrated_predictor(
                gap_config,
                model_kind,
                selected_hyperparameters[model_kind.value],
                gap_columns,
                gap_development,
                gap_roles["INTERVAL_CALIBRATION"],
            )
            model_reports: dict[str, Any] = {"predictor": _predictor_evidence(predictor)}
            for role_index, role in enumerate(retained_roles):
                prediction, report = _evaluate_role(
                    predictor,
                    gap_roles[role],
                    gap_config,
                    include_bootstrap=True,
                    bootstrap_seed_offset=400 + 10 * gap_index + role_index,
                )
                model_reports[role] = report
                prediction_frames.append(
                    prediction_rows(
                        gap_roles[role],
                        prediction,
                        policy=gap_config.target_policies.primary,
                        analysis=f"GAP_{gap_threshold_s}_{model_kind.value}",
                    )
                )
            threshold_reports["models"][model_kind.value] = model_reports
        gap_reports[str(gap_threshold_s)] = threshold_reports

    validation_role = "OFFICIAL_VALIDATION_RETAINED"
    test_role = "OFFICIAL_TEST_RETAINED"
    recommended_difference = grouped_bootstrap_paired_mae_difference(
        original_roles[validation_role].target,
        primary_predictions[recommended_family][validation_role].values,
        primary_predictions["mean"][validation_role].values,
        original_roles[validation_role].wafer_ids,
        repetitions=config.evaluation.grouped_bootstrap_repetitions,
        seed=config.evaluation.grouped_bootstrap_seed + 700,
        percentiles=config.evaluation.bootstrap_percentiles,
    )
    public_gate = {
        "recommended_family": recommended_family,
        "test_mae_lower_than_mean": (
            primary_reports[recommended_family][test_role]["overall"]["mae"]
            < primary_reports["mean"][test_role]["overall"]["mae"]
        ),
        "validation_mae_lower_than_mean": (
            primary_reports[recommended_family][validation_role]["overall"]["mae"]
            < primary_reports["mean"][validation_role]["overall"]["mae"]
        ),
        "validation_paired_mae_difference": recommended_difference,
    }
    public_gate["supported"] = bool(
        public_gate["test_mae_lower_than_mean"]
        and public_gate["validation_mae_lower_than_mean"]
        and recommended_difference["p97_5"] < 0.0
    )

    hybrid_difference = grouped_bootstrap_paired_mae_difference(
        original_roles[validation_role].target,
        primary_predictions["hybrid"][validation_role].values,
        primary_predictions[strongest_nonhybrid][validation_role].values,
        original_roles[validation_role].wafer_ids,
        repetitions=config.evaluation.grouped_bootstrap_repetitions,
        seed=config.evaluation.grouped_bootstrap_seed + 701,
        percentiles=config.evaluation.bootstrap_percentiles,
    )
    hybrid_gate = {
        "strongest_nonhybrid_selected_on_model_selection": strongest_nonhybrid,
        "test_mae_lower_than_baseline": (
            primary_reports["hybrid"][test_role]["overall"]["mae"]
            < primary_reports[strongest_nonhybrid][test_role]["overall"]["mae"]
        ),
        "validation_mae_lower_than_baseline": (
            primary_reports["hybrid"][validation_role]["overall"]["mae"]
            < primary_reports[strongest_nonhybrid][validation_role]["overall"]["mae"]
        ),
        "validation_paired_mae_difference": hybrid_difference,
    }
    hybrid_gate["supported"] = bool(
        hybrid_gate["test_mae_lower_than_baseline"]
        and hybrid_gate["validation_mae_lower_than_baseline"]
        and hybrid_difference["p97_5"] < 0.0
    )

    consumable_gate_models: dict[str, Any] = {}
    for model_index, model_name in enumerate(config.sensitivities.consumable_models):
        _, full_predictions, full_roles = ablation_cache[("FULL", model_name)]
        _, without_predictions, _ = ablation_cache[
            ("WITHOUT_CONSUMABLE_USAGE", model_name)
        ]
        differences: dict[str, float] = {}
        for role in retained_roles:
            target = full_roles[role].target
            differences[role] = float(
                np.mean(np.abs(without_predictions[role].values - target))
                - np.mean(np.abs(full_predictions[role].values - target))
            )
        validation_interval = grouped_bootstrap_paired_mae_difference(
            full_roles[validation_role].target,
            without_predictions[validation_role].values,
            full_predictions[validation_role].values,
            full_roles[validation_role].wafer_ids,
            repetitions=config.evaluation.grouped_bootstrap_repetitions,
            seed=config.evaluation.grouped_bootstrap_seed + 710 + model_index,
            percentiles=config.evaluation.bootstrap_percentiles,
        )
        consumable_gate_models[model_name] = {
            "without_minus_full_mae": differences,
            "validation_paired_difference": validation_interval,
            "supported_for_model": bool(
                all(value > 0.0 for value in differences.values())
                and validation_interval["p02_5"] > 0.0
            ),
        }
    consumable_gate = {
        "models": consumable_gate_models,
        "supported": all(
            row["supported_for_model"] for row in consumable_gate_models.values()
        ),
        "interpretation": "ASSOCIATION_ONLY_NOT_CAUSAL_CONSUMABLE_DEGRADATION",
    }

    coverage_failures: list[dict[str, Any]] = []
    for model_name, model_report in primary_reports.items():
        for role in retained_roles:
            coverage = model_report[role]["overall"]["interval_coverage"]
            if coverage < config.uncertainty.minimum_interpretation_coverage:
                coverage_failures.append(
                    {"model": model_name, "role": role, "coverage": coverage}
                )

    predictions_path = output / "wp09_predictions.csv"
    prediction_table = pd.concat(prediction_frames, ignore_index=True)
    write_csv_atomic(prediction_table, predictions_path)
    results: dict[str, Any] = {
        "schema_version": "1.0.0",
        "experiment_revision": config.experiment_revision,
        "dataset_id": config.dataset.dataset_id,
        "evidence_plane": "PUBLIC_PHM_SOURCE_NATIVE_OFFLINE_AVERAGE_MRR",
        "target": config.dataset.target,
        "target_unit_status": config.dataset.target_unit_status,
        "process_signal_unit_status": config.dataset.process_signal_unit_status,
        "runtime": _runtime_evidence(),
        "preflight_evidence": dict(preflight_evidence or {}),
        "config_payload_sha256": canonical_sha256(config.model_dump(mode="json")),
        "split_manifest_payload_sha256": split_manifest[
            "deterministic_payload_sha256"
        ],
        "target_access_audit": labels.access_audit,
        "selected_hyperparameters": selected_hyperparameters,
        "tuning": tuning,
        "model_selection": {
            "role": "MODEL_SELECTION",
            "scores_mae": selection_scores,
            "reports": selection_reports,
            "recommended_family": recommended_family,
            "strongest_nonhybrid": strongest_nonhybrid,
            "test_or_validation_used": False,
        },
        "primary_original_10s_full_features": primary_reports,
        "label_policy_sensitivities": label_sensitivity_reports,
        "chronological_stress": chronological_reports,
        "proxy_missing_mode_ablation": proxy_ablation_reports,
        "consumable_usage_ablation": consumable_ablation_reports,
        "gap_threshold_sensitivities": gap_reports,
        "interpretation_gates": {
            "C001_public_prediction": public_gate,
            "C008_hybrid_improvement": hybrid_gate,
            "C009_consumable_association": consumable_gate,
            "uncertainty_coverage_failures": coverage_failures,
        },
        "model_artifacts": model_artifacts,
        "prediction_artifact": {
            "path": _repository_relative_path(predictions_path, root),
            "row_count": len(prediction_table),
            "sha256": sha256_file(predictions_path),
        },
        "claim_boundary": {
            "measured_output": "AVERAGE_MRR_SOURCE_NATIVE_UNIT_UNDECLARED",
            "process_modes": "INPUT_DERIVED_PROXIES_NOT_MEASURED_PHASES",
            "full_source_holdouts": (
                "COLLISION_CONTAMINATED_DIAGNOSTICS_NOT_INDEPENDENT_WAFERS"
            ),
            "physics": "DIMENSIONLESS_NATIVE_SCALE_PROXY_NOT_SI_PRESTON_CALIBRATION",
            "consumables": "ASSOCIATION_ONLY",
            "excluded": [
                "electrical_or_UPW_causality",
                "spatial_uniformity_validation",
                "physical_defects",
                "yield",
                "equipment_damage",
                "production_control",
            ],
        },
    }
    deterministic_payload = _strip_nondeterministic_fields(results)
    results["deterministic_payload_sha256"] = canonical_sha256(deterministic_payload)
    results_path = output / "wp09_validation.json"
    write_json_atomic(results, results_path)
    results["results_artifact"] = {
        "path": _repository_relative_path(results_path, root),
        "sha256": sha256_file(results_path),
    }
    return results
