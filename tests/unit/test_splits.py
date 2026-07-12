import pandas as pd
import pytest

from semifab_poc.data.splits import (
    SplitError,
    audit_fit_scope,
    chronological_group_split,
    grouped_split,
    held_out_group_values,
    physical_machine_holdout_feasibility,
)


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "wafer_id": [f"w{i}" for i in range(12) for _ in range(2)],
            "machine_id": [f"m{i % 3}" for i in range(12) for _ in range(2)],
            "value": list(range(24)),
        }
    )


def test_grouped_split_has_zero_group_overlap_and_conserves_rows() -> None:
    result = grouped_split(_frame(), ["wafer_id"], random_state=7)
    audit = result.audit()
    assert audit.leakage_free
    assert not any(audit.overlaps.values())
    assert sum(audit.row_counts.values()) == 24
    assert len(result.train_groups | result.validation_groups | result.test_groups) == 12


def test_grouped_split_is_reproducible_for_a_seed() -> None:
    frame = _frame()
    first = grouped_split(frame, ["wafer_id"], random_state=11)
    second = grouped_split(frame, ["wafer_id"], random_state=11)
    assert first.train_groups == second.train_groups
    assert first.validation_groups == second.validation_groups
    assert first.test_groups == second.test_groups
    assert first.train.index.tolist() == second.train.index.tolist()


def test_grouped_split_rejects_missing_or_insufficient_groups() -> None:
    with pytest.raises(SplitError, match="grouping columns"):
        grouped_split(_frame(), ["unknown"])
    with pytest.raises(SplitError, match="at least three"):
        grouped_split(pd.DataFrame({"wafer_id": ["w1", "w1"]}), ["wafer_id"])
    broken = _frame().copy()
    broken.loc[0, "wafer_id"] = None
    with pytest.raises(SplitError, match="missing values"):
        grouped_split(broken, ["wafer_id"])


def test_grouped_split_rejects_row_split_without_groups() -> None:
    with pytest.raises(SplitError, match="at least one grouping"):
        grouped_split(_frame(), [])


def test_chronological_group_split_preserves_whole_wafer_order() -> None:
    frame = _frame().assign(META_GROUP_START_TIMESTAMP=lambda item: item.index // 2)
    result = chronological_group_split(frame, ["wafer_id"], "META_GROUP_START_TIMESTAMP")
    assert result.audit().leakage_free
    assert result.train["META_GROUP_START_TIMESTAMP"].max() < result.validation[
        "META_GROUP_START_TIMESTAMP"
    ].min()
    assert result.validation["META_GROUP_START_TIMESTAMP"].max() < result.test[
        "META_GROUP_START_TIMESTAMP"
    ].min()


def test_fit_scope_audit_rejects_nontraining_groups() -> None:
    split = grouped_split(_frame(), ["wafer_id"], random_state=5)
    assert audit_fit_scope(split.train, split).training_only
    contaminated = pd.concat([split.train, split.validation.iloc[:1]])
    with pytest.raises(SplitError, match="non-training"):
        audit_fit_scope(contaminated, split)


def test_regime_holdout_and_physical_machine_feasibility_are_explicit() -> None:
    frame = _frame().assign(
        META_MACHINE_ID="2",
        META_MACHINE_DATA=lambda item: item["machine_id"],
    )
    feasibility = physical_machine_holdout_feasibility(frame)
    assert feasibility["physical_machine_holdout_feasible"] is False
    holdout = held_out_group_values(
        frame,
        "META_MACHINE_DATA",
        ["m2"],
        interpretation="REGIME_STRESS_TEST_NOT_MACHINE_GENERALIZATION",
    )
    assert holdout.leakage_free
    assert set(holdout.holdout["META_MACHINE_DATA"]) == {"m2"}
    assert "NOT_MACHINE_GENERALIZATION" in holdout.interpretation
