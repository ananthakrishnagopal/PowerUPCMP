"""PHM 2016 CMP loader, label joins, audit reports, and feature aggregation."""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
import yaml

from .splits import SplitResult, grouped_split


class PhmDataError(ValueError):
    """Raised when extracted PHM files fail manifest, schema, or join checks."""


TIMESERIES_COLUMNS = (
    "MACHINE_ID",
    "MACHINE_DATA",
    "TIMESTAMP",
    "WAFER_ID",
    "STAGE",
    "CHAMBER",
    "USAGE_OF_BACKING_FILM",
    "USAGE_OF_DRESSER",
    "USAGE_OF_POLISHING_TABLE",
    "USAGE_OF_DRESSER_TABLE",
    "PRESSURIZED_CHAMBER_PRESSURE",
    "MAIN_OUTER_AIR_BAG_PRESSURE",
    "CENTER_AIR_BAG_PRESSURE",
    "RETAINER_RING_PRESSURE",
    "RIPPLE_AIR_BAG_PRESSURE",
    "USAGE_OF_MEMBRANE",
    "USAGE_OF_PRESSURIZED_SHEET",
    "SLURRY_FLOW_LINE_A",
    "SLURRY_FLOW_LINE_B",
    "SLURRY_FLOW_LINE_C",
    "WAFER_ROTATION",
    "STAGE_ROTATION",
    "HEAD_ROTATION",
    "DRESSING_WATER_STATUS",
    "EDGE_AIR_BAG_PRESSURE",
)
REMOVAL_COLUMNS = ("WAFER_ID", "STAGE", "AVG_REMOVAL_RATE")
_TRACE_RE = re.compile(r"^CMP-(training|test|validation)-(\d{3})\.csv$")
_SPLITS = ("training", "test", "validation")
_ID_COLUMNS = ("WAFER_ID", "STAGE", "MACHINE_ID", "MACHINE_DATA", "CHAMBER")


@dataclass(frozen=True)
class PhmDataset:
    """Loaded PHM tables with measured labels kept separate by split."""

    training_timeseries: pd.DataFrame
    test_timeseries: pd.DataFrame
    validation_timeseries: pd.DataFrame
    training_labels: pd.DataFrame
    test_labels: pd.DataFrame
    validation_labels: pd.DataFrame
    trace_inventory: pd.DataFrame
    extraction_manifest: dict[str, Any]

    @property
    def timeseries(self) -> pd.DataFrame:
        return pd.concat(
            [self.training_timeseries, self.test_timeseries, self.validation_timeseries],
            ignore_index=True,
        )


@dataclass(frozen=True)
class LabelJoinResult:
    frame: pd.DataFrame
    audit: dict[str, Any]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_manifest(root: Path) -> dict[str, Any]:
    path = root / "extraction_manifest.yaml"
    if not path.is_file():
        raise PhmDataError(f"extraction manifest is missing: {path}")
    try:
        manifest = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise PhmDataError(f"cannot read extraction manifest: {exc}") from exc
    if not isinstance(manifest, dict) or not isinstance(manifest.get("members"), list):
        raise PhmDataError("extraction manifest must contain a members list")
    if manifest.get("dataset_id") != "PHM_2016_CMP":
        raise PhmDataError("unexpected dataset_id in extraction manifest")
    if manifest.get("archive_integrity") != "VERIFIED":
        raise PhmDataError("archive integrity is not marked VERIFIED")
    if manifest.get("answer_tables_excluded") is not True:
        raise PhmDataError("answer tables must be excluded")
    if manifest.get("derived_experiments_excluded") is not True:
        raise PhmDataError("derived experiments must be excluded")
    return manifest


def _verify_member(root: Path, member: dict[str, Any], verify_checksums: bool) -> Path:
    relative = Path(str(member["relative_path"]))
    if relative.is_absolute() or ".." in relative.parts:
        raise PhmDataError(f"unsafe manifest relative path: {relative}")
    path = root / "original" / relative
    if not path.is_file():
        raise PhmDataError(f"manifest member is missing: {path}")
    expected_size = int(member["byte_size"])
    if path.stat().st_size != expected_size:
        raise PhmDataError(f"size mismatch for {path}")
    if verify_checksums and _sha256(path) != member["sha256"]:
        raise PhmDataError(f"SHA-256 mismatch for {path}")
    return path


def _normalize_ids(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    for column in _ID_COLUMNS:
        if column in result.columns:
            result[column] = result[column].astype("string")
    if "STAGE" in result.columns:
        result["STAGE"] = result["STAGE"].str.strip()
    return result


def _classify_member(relative: str, category: str) -> tuple[str, str]:
    if category == "removal_rate":
        match = re.search(r"CMP-(training|test|validation)-removalrate\.csv$", relative)
        if not match:
            raise PhmDataError(f"unrecognized removal-rate member: {relative}")
        return match.group(1), "removal_rate"
    match = _TRACE_RE.search(Path(relative).name)
    if not match:
        raise PhmDataError(f"unrecognized time-series member: {relative}")
    return match.group(1), "timeseries"


def load_phm_dataset(root: str | Path = "data/raw/phm_2016_cmp", *, verify_checksums: bool = True) -> PhmDataset:
    """Load extracted original CMP tables and preserve split provenance.

    Test and validation MRR tables are returned separately for offline evaluation;
    only the training table is joined by :func:`join_training_labels`.
    """

    data_root = Path(root)
    manifest = _read_manifest(data_root)
    members = manifest["members"]
    if len(members) != 558:
        raise PhmDataError(f"expected 558 selected members, got {len(members)}")
    series_frames: dict[str, list[pd.DataFrame]] = {split: [] for split in _SPLITS}
    label_frames: dict[str, list[pd.DataFrame]] = {split: [] for split in _SPLITS}
    inventory_rows: list[dict[str, Any]] = []

    for member in members:
        relative = str(member["relative_path"])
        split, category = _classify_member(relative, str(member["category"]))
        path = _verify_member(data_root, member, verify_checksums)
        if category == "timeseries":
            frame = pd.read_csv(path)
            if tuple(frame.columns) != TIMESERIES_COLUMNS:
                raise PhmDataError(f"time-series schema mismatch for {path}")
            frame = _normalize_ids(frame)
            if not frame.empty and frame[["WAFER_ID", "STAGE", "MACHINE_ID"]].isna().any().any():
                raise PhmDataError(f"missing grouping identifier in non-empty trace: {path}")
            frame["SOURCE_ROW_INDEX"] = pd.RangeIndex(len(frame), dtype="int64")
            frame["TRACE_ID"] = Path(relative).stem
            frame["SOURCE_MEMBER"] = relative
            frame["SPLIT"] = split
            series_frames[split].append(frame)
            inventory_rows.append(
                {
                    "TRACE_ID": Path(relative).stem,
                    "SPLIT": split,
                    "SOURCE_MEMBER": relative,
                    "ROW_COUNT": int(len(frame)),
                    "EMPTY_TRACE": bool(member.get("empty_trace", len(frame) == 0)),
                }
            )
        else:
            labels = pd.read_csv(path)
            if tuple(labels.columns) != REMOVAL_COLUMNS:
                raise PhmDataError(f"removal-rate schema mismatch for {path}")
            labels = _normalize_ids(labels)
            if labels[["WAFER_ID", "STAGE"]].isna().any().any():
                raise PhmDataError(f"missing label grouping identifier: {path}")
            if labels.duplicated(["WAFER_ID", "STAGE"]).any():
                raise PhmDataError(f"duplicate removal-rate key in {path}")
            labels["SPLIT"] = split
            labels["SOURCE_MEMBER"] = relative
            label_frames[split].append(labels)

    for split in _SPLITS:
        if len(series_frames[split]) != 185:
            raise PhmDataError(f"expected 185 {split} traces, got {len(series_frames[split])}")
        if len(label_frames[split]) != 1:
            raise PhmDataError(f"expected one {split} removal-rate table, got {len(label_frames[split])}")

    def combine(frames: list[pd.DataFrame], columns: tuple[str, ...]) -> pd.DataFrame:
        nonempty = [frame for frame in frames if not frame.empty]
        if not nonempty:
            return pd.DataFrame(
                columns=[*columns, "SOURCE_ROW_INDEX", "TRACE_ID", "SOURCE_MEMBER", "SPLIT"]
            )
        return pd.concat(nonempty, ignore_index=True)

    dataset = PhmDataset(
        training_timeseries=combine(series_frames["training"], TIMESERIES_COLUMNS),
        test_timeseries=combine(series_frames["test"], TIMESERIES_COLUMNS),
        validation_timeseries=combine(series_frames["validation"], TIMESERIES_COLUMNS),
        training_labels=label_frames["training"][0],
        test_labels=label_frames["test"][0],
        validation_labels=label_frames["validation"][0],
        trace_inventory=pd.DataFrame(inventory_rows),
        extraction_manifest=manifest,
    )
    return dataset


def join_training_labels(dataset: PhmDataset) -> LabelJoinResult:
    """Join training MRR labels with training rows using a many-to-one audit."""

    features = dataset.training_timeseries
    labels = dataset.training_labels
    keys = ["WAFER_ID", "STAGE"]
    feature_keys = features[keys].drop_duplicates()
    label_keys = labels[keys].drop_duplicates()
    missing = feature_keys.merge(label_keys, on=keys, how="left", indicator=True)
    missing_keys = missing.loc[missing["_merge"] == "left_only", keys]
    orphan = label_keys.merge(feature_keys, on=keys, how="left", indicator=True)
    orphan_keys = orphan.loc[orphan["_merge"] == "left_only", keys]
    if not missing_keys.empty:
        raise PhmDataError(f"training feature keys without labels: {len(missing_keys)}")
    joined = features.merge(labels[keys + ["AVG_REMOVAL_RATE"]], on=keys, how="left", validate="many_to_one")
    if joined["AVG_REMOVAL_RATE"].isna().any():
        raise PhmDataError("training label join produced missing MRR values")
    audit = {
        "feature_rows": int(len(features)),
        "label_rows": int(len(labels)),
        "feature_key_count": int(len(feature_keys)),
        "label_key_count": int(len(label_keys)),
        "missing_label_key_count": int(len(missing_keys)),
        "orphan_label_key_count": int(len(orphan_keys)),
        "join_validation": "many_to_one",
        "label_column": "AVG_REMOVAL_RATE",
        "test_and_validation_labels_joined": False,
    }
    return LabelJoinResult(joined, audit)


def missingness_report(dataset: PhmDataset) -> dict[str, Any]:
    """Return JSON-safe missingness and empty-trace evidence by split."""

    report: dict[str, Any] = {
        "dataset_id": dataset.extraction_manifest["dataset_id"],
        "archive_sha256": dataset.extraction_manifest["archive_sha256"],
        "splits": {},
        "empty_trace_count": int(dataset.trace_inventory["EMPTY_TRACE"].sum()),
    }
    for split in _SPLITS:
        frame = getattr(dataset, f"{split}_timeseries")
        numeric = frame.select_dtypes(include="number")
        nonfinite = {
            column: int((~numeric[column].map(math.isfinite)).sum())
            for column in numeric.columns
            if not numeric.empty
        }
        report["splits"][split] = {
            "row_count": int(len(frame)),
            "trace_count": int((dataset.trace_inventory["SPLIT"] == split).sum()),
            "empty_trace_count": int(
                ((dataset.trace_inventory["SPLIT"] == split) & dataset.trace_inventory["EMPTY_TRACE"]).sum()
            ),
            "wafer_count": int(frame["WAFER_ID"].nunique(dropna=True)),
            "missing_by_column": {column: int(value) for column, value in frame.isna().sum().items() if value},
            "nonfinite_numeric_by_column": nonfinite,
        }
    return report


def engineer_training_features(joined: pd.DataFrame) -> pd.DataFrame:
    """Compatibility wrapper for phase-aware per-wafer feature engineering.

    Labels are separated before any annotation or aggregation and joined back
    only after group features exist. New code should call the explicit R2 APIs
    in :mod:`semifab_poc.data.phm_semantics`.
    """

    required = {"WAFER_ID", "STAGE", "AVG_REMOVAL_RATE"}
    missing = required - set(joined.columns)
    if missing:
        raise PhmDataError(f"labeled frame missing columns: {sorted(missing)}")
    keys = ["WAFER_ID", "STAGE"]
    label_counts = joined.groupby(keys, dropna=False)["AVG_REMOVAL_RATE"].nunique()
    if (label_counts > 1).any():
        raise PhmDataError("MRR label is not constant within a wafer/stage group")
    labels = joined.groupby(keys, dropna=False, as_index=False)["AVG_REMOVAL_RATE"].first()
    from .phm_semantics import engineer_phase_aware_features

    feature_result = engineer_phase_aware_features(joined.drop(columns=["AVG_REMOVAL_RATE"]))
    return feature_result.frame.merge(labels, on=keys, how="left", validate="one_to_one")


def split_training_features(
    features: pd.DataFrame,
    *,
    random_state: int = 0,
) -> SplitResult:
    """Create train/validation/test groups without splitting a wafer."""

    return grouped_split(features, ["WAFER_ID"], random_state=random_state)
