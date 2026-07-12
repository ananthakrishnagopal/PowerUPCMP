from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from semifab_poc.data.schema import (
    DataOrigin,
    LatentStateRecord,
    ObservationRecord,
    PublicMeasurementRecord,
    QualityFlag,
    RunManifest,
    SemanticClass,
    SourceUnitStatus,
)


SHA = "a" * 64


def test_latent_and_observation_records_are_distinct() -> None:
    latent = LatentStateRecord(
        run_id="run-1",
        step_index=0,
        timestamp_s=0.0,
        signal_id="upw.supply_pressure",
        value=100_000.0,
        unit="Pa",
        subsystem="upw",
        provenance_id="synthetic-default-v1",
    )
    observed = ObservationRecord(
        run_id="run-1",
        sample_index=0,
        source_step_index=0,
        source_timestamp_s=0.0,
        observed_timestamp_s=0.0,
        arrival_timestamp_s=0.01,
        sensor_id="pressure-1",
        signal_id="upw.supply_pressure",
        value=99_900.0,
        unit="Pa",
        quality_flags=(QualityFlag.VALID,),
        data_origin=DataOrigin.SYNTHETIC_SIMULATOR,
    )
    assert latent.semantic_class is SemanticClass.SIMULATED_PHYSICAL_STATE
    assert observed.semantic_class is SemanticClass.OBSERVED_SENSOR_STATE
    assert latent.data_origin is DataOrigin.SYNTHETIC_SIMULATOR
    assert type(latent) is not type(observed)


def test_signal_units_and_ranges_are_checked() -> None:
    with pytest.raises(ValidationError, match="requires unit"):
        LatentStateRecord(
            run_id="run-1",
            step_index=0,
            timestamp_s=0.0,
            signal_id="upw.supply_pressure",
            value=100.0,
            unit="kPa",
            subsystem="upw",
            provenance_id="synthetic-default-v1",
        )
    with pytest.raises(ValidationError, match="below"):
        LatentStateRecord(
            run_id="run-1",
            step_index=0,
            timestamp_s=0.0,
            signal_id="pump.power",
            value=-1.0,
            unit="W",
            subsystem="pump",
            provenance_id="synthetic-default-v1",
        )


def test_r3_dimensionless_water_quality_proxy_rejects_physical_conductivity_unit() -> None:
    common = dict(
        run_id="run-1",
        step_index=0,
        timestamp_s=0.0,
        signal_id="upw.water_quality_deviation_proxy",
        value=0.1,
        subsystem="upw",
        provenance_id="synthetic-upw-conserved-v2",
    )
    record = LatentStateRecord(**common, unit="1")
    assert record.unit == "1"
    with pytest.raises(ValidationError, match="requires unit"):
        LatentStateRecord(**common, unit="S/m")


def test_missing_observation_requires_quality_flag() -> None:
    with pytest.raises(ValidationError, match="MISSING"):
        ObservationRecord(
            run_id="run-1",
            sample_index=0,
            source_step_index=0,
            source_timestamp_s=0.0,
            observed_timestamp_s=0.0,
            arrival_timestamp_s=0.0,
            sensor_id="flow-1",
            signal_id="upw.tool_flow",
            unit="m^3/s",
            data_origin=DataOrigin.SYNTHETIC_SIMULATOR,
        )


def test_observation_arrival_cannot_precede_source_generation() -> None:
    with pytest.raises(ValidationError, match="cannot precede"):
        ObservationRecord(
            run_id="run-1",
            sample_index=0,
            source_step_index=10,
            source_timestamp_s=0.10,
            observed_timestamp_s=0.08,
            arrival_timestamp_s=0.09,
            sensor_id="pressure-1",
            signal_id="upw.supply_pressure",
            value=100_000.0,
            unit="Pa",
            quality_flags=(QualityFlag.TIMESTAMP_JITTERED,),
            data_origin=DataOrigin.SYNTHETIC_SIMULATOR,
        )


def test_public_measurement_has_measured_semantics() -> None:
    measurement = PublicMeasurementRecord(
        dataset_id="phm-2016-cmp",
        source_file_sha256=SHA,
        source_row_id="row-1",
        wafer_id="wafer-1",
        machine_id="tool-1",
        trace_id="trace-1",
        source_timestamp=datetime.now(timezone.utc),
        signal_id="cmp.mrr",
        value=1.0e-9,
        source_unit="m/s",
        source_unit_status=SourceUnitStatus.DECLARED,
        canonical_value=1.0e-9,
        canonical_unit="m/s",
        conversion_id="identity:m/s",
        quality_flags=(QualityFlag.VALID,),
    )
    assert measurement.semantic_class is SemanticClass.MEASURED_PROCESS_OUTPUT
    assert measurement.data_origin is DataOrigin.PUBLIC_MEASURED


def test_public_native_mrr_can_remain_unconverted_without_being_missing() -> None:
    measurement = PublicMeasurementRecord(
        dataset_id="phm-2016-cmp",
        source_file_sha256=SHA,
        source_row_id="wafer-1-stage-A",
        wafer_id="wafer-1",
        machine_id="2",
        trace_id="CMP-training-001",
        source_timestamp=1.0,
        signal_id="cmp.mrr",
        value=72.0,
        source_unit="PHM_NATIVE_UNDECLARED",
        source_unit_status=SourceUnitStatus.NATIVE_UNDECLARED,
        canonical_value=None,
        canonical_unit=None,
        conversion_id=None,
        quality_flags=(QualityFlag.UNIT_UNRESOLVED,),
    )
    assert measurement.value == 72.0
    assert measurement.canonical_value is None
    assert QualityFlag.MISSING not in measurement.quality_flags


def test_public_conversion_requires_declared_unit_and_conversion_id() -> None:
    common = dict(
        dataset_id="phm-2016-cmp",
        source_file_sha256=SHA,
        source_row_id="row-1",
        signal_id="cmp.mrr",
        value=60.0,
        source_unit="nm/min",
        canonical_value=1.0e-9,
        canonical_unit="m/s",
        quality_flags=(QualityFlag.VALID,),
    )
    with pytest.raises(ValidationError, match="declared source unit"):
        PublicMeasurementRecord(
            **common,
            source_unit_status=SourceUnitStatus.NATIVE_UNDECLARED,
            conversion_id="nm-min-to-m-s-v1",
        )
    with pytest.raises(ValidationError, match="conversion_id"):
        PublicMeasurementRecord(
            **common,
            source_unit_status=SourceUnitStatus.DECLARED,
            conversion_id=None,
        )


def test_run_manifest_rejects_bad_hash() -> None:
    with pytest.raises(ValidationError):
        RunManifest(
            run_id="run-1",
            scenario_id="normal",
            controller_id="no-action",
            config_sha256="bad",
            code_revision="UNCOMMITTED",
            run_seed=0,
            child_seed_map={"plant": 1},
            dt_s=0.01,
            duration_s=1.0,
            started_at_utc=datetime.now(timezone.utc),
            software_versions={"python": "3.13"},
            dataset_manifest_ids=(),
            parameter_provenance_ids={"electrical": "synthetic-electrical-v1"},
            synthetic_only=True,
        )


def test_run_manifest_requires_nonempty_parameter_provenance() -> None:
    common = dict(
        run_id="run-1",
        scenario_id="normal",
        controller_id="no-action",
        config_sha256=SHA,
        code_revision="UNCOMMITTED",
        run_seed=0,
        child_seed_map={"plant": 1},
        dt_s=0.01,
        duration_s=1.0,
        started_at_utc=datetime.now(timezone.utc),
        software_versions={"python": "3.13"},
        dataset_manifest_ids=(),
        synthetic_only=True,
    )
    with pytest.raises(ValidationError):
        RunManifest(**common, parameter_provenance_ids={})
    with pytest.raises(ValidationError, match="non-empty strings"):
        RunManifest(**common, parameter_provenance_ids={"pump": ""})
