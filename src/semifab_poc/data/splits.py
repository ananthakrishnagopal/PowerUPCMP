"""Leakage-safe grouped split primitives for tabular process data."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

import numpy as np
import pandas as pd


class SplitError(ValueError):
    """Raised when a grouped split cannot satisfy the leakage contract."""


GroupKey = tuple[object, ...]


@dataclass(frozen=True)
class SplitAudit:
    group_columns: tuple[str, ...]
    train_groups: frozenset[GroupKey]
    validation_groups: frozenset[GroupKey]
    test_groups: frozenset[GroupKey]
    row_counts: dict[str, int]

    @property
    def overlaps(self) -> dict[str, frozenset[GroupKey]]:
        return {
            "train_validation": self.train_groups & self.validation_groups,
            "train_test": self.train_groups & self.test_groups,
            "validation_test": self.validation_groups & self.test_groups,
        }

    @property
    def leakage_free(self) -> bool:
        return not any(self.overlaps.values())


@dataclass(frozen=True)
class SplitResult:
    train: pd.DataFrame
    validation: pd.DataFrame
    test: pd.DataFrame
    group_columns: tuple[str, ...]
    train_groups: frozenset[GroupKey]
    validation_groups: frozenset[GroupKey]
    test_groups: frozenset[GroupKey]

    def audit(self) -> SplitAudit:
        return SplitAudit(
            group_columns=self.group_columns,
            train_groups=self.train_groups,
            validation_groups=self.validation_groups,
            test_groups=self.test_groups,
            row_counts={
                "train": len(self.train),
                "validation": len(self.validation),
                "test": len(self.test),
            },
        )


@dataclass(frozen=True)
class FitScopeAudit:
    fit_groups: frozenset[GroupKey]
    allowed_train_groups: frozenset[GroupKey]
    validation_groups: frozenset[GroupKey]
    test_groups: frozenset[GroupKey]

    @property
    def training_only(self) -> bool:
        return (
            self.fit_groups <= self.allowed_train_groups
            and not self.fit_groups & self.validation_groups
            and not self.fit_groups & self.test_groups
        )


@dataclass(frozen=True)
class HoldoutResult:
    development: pd.DataFrame
    holdout: pd.DataFrame
    group_column: str
    development_values: frozenset[object]
    holdout_values: frozenset[object]
    interpretation: str

    @property
    def leakage_free(self) -> bool:
        return not self.development_values & self.holdout_values


@dataclass(frozen=True)
class OfficialPrecedenceAudit:
    """Feature-only evidence for collision removal across source partitions."""

    group_columns: tuple[str, ...]
    original_group_counts: dict[str, int]
    retained_group_counts: dict[str, int]
    original_row_counts: dict[str, int]
    retained_row_counts: dict[str, int]
    dropped_row_counts: dict[str, int]
    original_overlap_counts: dict[str, int]
    retained_overlap_counts: dict[str, int]
    interpretation: str

    @property
    def leakage_free(self) -> bool:
        return not any(self.retained_overlap_counts.values())

    def to_dict(self) -> dict[str, object]:
        return {
            "group_columns": list(self.group_columns),
            "original_group_counts": self.original_group_counts,
            "retained_group_counts": self.retained_group_counts,
            "original_row_counts": self.original_row_counts,
            "retained_row_counts": self.retained_row_counts,
            "dropped_row_counts": self.dropped_row_counts,
            "original_overlap_counts": self.original_overlap_counts,
            "retained_overlap_counts": self.retained_overlap_counts,
            "leakage_free": self.leakage_free,
            "interpretation": self.interpretation,
        }


@dataclass(frozen=True)
class OfficialPrecedenceResult:
    """Official-role frames after applying whole-group source precedence."""

    training: pd.DataFrame
    test: pd.DataFrame
    validation: pd.DataFrame
    audit: OfficialPrecedenceAudit


def _group_keys(frame: pd.DataFrame, columns: tuple[str, ...]) -> pd.Series:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise SplitError(f"missing grouping columns: {missing}")
    if frame.empty:
        raise SplitError("cannot split an empty frame")
    if frame.loc[:, list(columns)].isna().any().any():
        raise SplitError("grouping columns may not contain missing values")
    return frame.loc[:, list(columns)].apply(lambda row: tuple(row.tolist()), axis=1)


def official_group_precedence_split(
    training: pd.DataFrame,
    test: pd.DataFrame,
    validation: pd.DataFrame,
    group_columns: Sequence[str],
) -> OfficialPrecedenceResult:
    """Apply conservative ``training > test > validation`` group precedence.

    The official source roles are preserved, but a group occurring in an
    earlier source partition is excluded from every later partition. Validation
    is compared with the *original* test group set, including test groups that
    were themselves excluded because they collide with training. This makes all
    retained partitions mutually group-disjoint without reassigning rows.
    """

    columns = tuple(group_columns)
    if not columns:
        raise SplitError("at least one precedence grouping column is required")
    frames = {"training": training, "test": test, "validation": validation}
    keys = {name: _group_keys(frame, columns) for name, frame in frames.items()}
    original_groups = {
        name: frozenset(series.tolist()) for name, series in keys.items()
    }
    retained_groups = {
        "training": original_groups["training"],
        "test": original_groups["test"] - original_groups["training"],
        "validation": original_groups["validation"]
        - original_groups["training"]
        - original_groups["test"],
    }
    retained_frames = {
        name: frame.loc[keys[name].isin(retained_groups[name])].copy()
        for name, frame in frames.items()
    }
    if any(frame.empty for frame in retained_frames.values()):
        raise SplitError("official precedence split produced an empty retained partition")

    original_overlaps = {
        "training_test": len(original_groups["training"] & original_groups["test"]),
        "training_validation": len(
            original_groups["training"] & original_groups["validation"]
        ),
        "test_validation": len(original_groups["test"] & original_groups["validation"]),
    }
    retained_overlaps = {
        "training_test": len(retained_groups["training"] & retained_groups["test"]),
        "training_validation": len(
            retained_groups["training"] & retained_groups["validation"]
        ),
        "test_validation": len(retained_groups["test"] & retained_groups["validation"]),
    }
    audit = OfficialPrecedenceAudit(
        group_columns=columns,
        original_group_counts={name: len(groups) for name, groups in original_groups.items()},
        retained_group_counts={name: len(groups) for name, groups in retained_groups.items()},
        original_row_counts={name: len(frame) for name, frame in frames.items()},
        retained_row_counts={name: len(frame) for name, frame in retained_frames.items()},
        dropped_row_counts={
            name: len(frames[name]) - len(retained_frames[name]) for name in frames
        },
        original_overlap_counts=original_overlaps,
        retained_overlap_counts=retained_overlaps,
        interpretation="OFFICIAL_ROLE_PRECEDENCE_WHOLE_GROUP_DISJOINT",
    )
    if not audit.leakage_free:
        raise SplitError("official precedence split retained overlapping groups")
    return OfficialPrecedenceResult(
        training=retained_frames["training"],
        test=retained_frames["test"],
        validation=retained_frames["validation"],
        audit=audit,
    )


def _partition_counts(group_count: int, train_fraction: float, validation_fraction: float) -> tuple[int, int, int]:
    if group_count < 3:
        raise SplitError("at least three distinct groups are required")
    if not (0.0 < train_fraction < 1.0 and 0.0 < validation_fraction < 1.0):
        raise SplitError("train_fraction and validation_fraction must be between zero and one")
    if train_fraction + validation_fraction >= 1.0:
        raise SplitError("train_fraction + validation_fraction must be less than one")
    train_count = max(1, int(round(group_count * train_fraction)))
    validation_count = max(1, int(round(group_count * validation_fraction)))
    if train_count + validation_count >= group_count:
        validation_count = group_count - train_count - 1
    if validation_count < 1:
        train_count = group_count - 2
        validation_count = 1
    return train_count, validation_count, group_count - train_count - validation_count


def grouped_split(
    frame: pd.DataFrame,
    group_columns: Sequence[str],
    *,
    train_fraction: float = 0.70,
    validation_fraction: float = 0.15,
    random_state: int = 0,
) -> SplitResult:
    """Split whole groups, never individual rows, into train/validation/test.

    Group assignments are generated before any fitted transform is allowed to run.
    The returned frames retain original rows and indices for downstream audits.
    """

    columns = tuple(group_columns)
    if not columns:
        raise SplitError("at least one grouping column is required")
    if random_state < 0:
        raise SplitError("random_state must be non-negative")
    keys = _group_keys(frame, columns)
    unique_groups = list(dict.fromkeys(keys.tolist()))
    train_count, validation_count, _ = _partition_counts(
        len(unique_groups), train_fraction, validation_fraction
    )
    rng = np.random.default_rng(random_state)
    shuffled = [unique_groups[index] for index in rng.permutation(len(unique_groups))]
    train_groups = frozenset(shuffled[:train_count])
    validation_groups = frozenset(shuffled[train_count : train_count + validation_count])
    test_groups = frozenset(shuffled[train_count + validation_count :])
    if train_groups & validation_groups or train_groups & test_groups or validation_groups & test_groups:
        raise SplitError("internal grouped-split overlap detected")

    train_mask = keys.isin(train_groups)
    validation_mask = keys.isin(validation_groups)
    test_mask = keys.isin(test_groups)
    result = SplitResult(
        train=frame.loc[train_mask].copy(),
        validation=frame.loc[validation_mask].copy(),
        test=frame.loc[test_mask].copy(),
        group_columns=columns,
        train_groups=train_groups,
        validation_groups=validation_groups,
        test_groups=test_groups,
    )
    audit = result.audit()
    if not audit.leakage_free or sum(audit.row_counts.values()) != len(frame):
        raise SplitError("grouped split failed leakage or row-conservation audit")
    return result


def assert_no_group_overlap(result: SplitResult) -> None:
    """Raise if any group appears in more than one split."""

    audit = result.audit()
    if not audit.leakage_free:
        raise SplitError(f"group overlap detected: {audit.overlaps}")


def chronological_group_split(
    frame: pd.DataFrame,
    group_columns: Sequence[str],
    time_column: str,
    *,
    train_fraction: float = 0.70,
    validation_fraction: float = 0.15,
) -> SplitResult:
    """Partition whole groups chronologically using group-minimum metadata time."""

    columns = tuple(group_columns)
    keys = _group_keys(frame, columns)
    if time_column not in frame.columns:
        raise SplitError(f"missing chronological split column: {time_column}")
    times = pd.to_numeric(frame[time_column], errors="coerce")
    if not np.isfinite(times.to_numpy(dtype=float)).all():
        raise SplitError("chronological split time must be finite")
    group_metadata = pd.DataFrame({"_GROUP": keys, "_TIME": times}).groupby(
        "_GROUP", sort=False
    )["_TIME"].min()
    ordered_groups = sorted(group_metadata.index, key=lambda key: (group_metadata[key], repr(key)))
    train_count, validation_count, _ = _partition_counts(
        len(ordered_groups), train_fraction, validation_fraction
    )
    train_groups = frozenset(ordered_groups[:train_count])
    validation_groups = frozenset(
        ordered_groups[train_count : train_count + validation_count]
    )
    test_groups = frozenset(ordered_groups[train_count + validation_count :])
    result = SplitResult(
        train=frame.loc[keys.isin(train_groups)].copy(),
        validation=frame.loc[keys.isin(validation_groups)].copy(),
        test=frame.loc[keys.isin(test_groups)].copy(),
        group_columns=columns,
        train_groups=train_groups,
        validation_groups=validation_groups,
        test_groups=test_groups,
    )
    if not result.audit().leakage_free or sum(result.audit().row_counts.values()) != len(frame):
        raise SplitError("chronological grouped split failed leakage or row conservation")
    return result


def audit_fit_scope(fit_frame: pd.DataFrame, split: SplitResult) -> FitScopeAudit:
    """Audit that a fitted transform saw training groups only."""

    fit_groups = frozenset(_group_keys(fit_frame, split.group_columns).tolist())
    audit = FitScopeAudit(
        fit_groups=fit_groups,
        allowed_train_groups=split.train_groups,
        validation_groups=split.validation_groups,
        test_groups=split.test_groups,
    )
    if not audit.training_only:
        raise SplitError("fitted transform scope contains non-training groups")
    return audit


def held_out_group_values(
    frame: pd.DataFrame,
    group_column: str,
    holdout_values: Sequence[object],
    *,
    interpretation: str,
) -> HoldoutResult:
    """Create a named group-value stress holdout without relabelling its meaning."""

    if group_column not in frame.columns:
        raise SplitError(f"missing holdout group column: {group_column}")
    if frame[group_column].isna().any():
        raise SplitError("holdout group column may not contain missing values")
    requested = frozenset(holdout_values)
    if not requested:
        raise SplitError("at least one holdout value is required")
    available = frozenset(frame[group_column].unique().tolist())
    if not requested <= available:
        raise SplitError("requested holdout values are absent")
    development_values = available - requested
    if not development_values:
        raise SplitError("holdout would leave no development groups")
    result = HoldoutResult(
        development=frame.loc[frame[group_column].isin(development_values)].copy(),
        holdout=frame.loc[frame[group_column].isin(requested)].copy(),
        group_column=group_column,
        development_values=development_values,
        holdout_values=requested,
        interpretation=interpretation,
    )
    if not result.leakage_free or result.development.empty or result.holdout.empty:
        raise SplitError("group-value holdout failed leakage or non-empty checks")
    return result


def physical_machine_holdout_feasibility(
    frame: pd.DataFrame,
    machine_column: str = "META_MACHINE_ID",
) -> dict[str, object]:
    """Report rather than conceal whether a physical-machine holdout is possible."""

    if machine_column not in frame.columns:
        raise SplitError(f"missing machine metadata column: {machine_column}")
    values = sorted(map(str, frame[machine_column].dropna().unique()))
    return {
        "machine_column": machine_column,
        "values": values,
        "distinct_count": len(values),
        "physical_machine_holdout_feasible": len(values) > 1,
    }
