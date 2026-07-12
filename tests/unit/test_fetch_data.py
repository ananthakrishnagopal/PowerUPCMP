from pathlib import Path

import pytest

from semifab_poc.data.fetch import FetchError, _validate_csv, validate_local_source


def _source(**overrides):
    source = {
        "id": "FIXTURE",
        "access_approval": "USER_AUTHORIZED_LOCAL_ARCHIVE",
        "licence_status": "USER_AUTHORIZED_UNVERIFIED_DATASET_LICENCE",
        "local_raw_directory": "data/raw/fixture",
        "local_candidate_archive": {
            "path": "fixture.zip",
            "byte_size": 1,
            "sha256": "a" * 64,
            "selected_original_prefixes": ["data/"],
            "excluded_prefixes": ["answers/"],
            "user_authorization_scope": "local fixture",
        },
    }
    source.update(overrides)
    return source


def test_unapproved_source_is_rejected_before_archive_access() -> None:
    source = _source(access_approval="NOT_REQUESTED")
    with pytest.raises(FetchError, match="USER_AUTHORIZED_LOCAL_ARCHIVE"):
        validate_local_source(source)


def test_missing_archive_metadata_is_rejected() -> None:
    source = _source(local_candidate_archive={"path": "fixture.zip"})
    with pytest.raises(FetchError, match="metadata missing"):
        validate_local_source(source)


def test_unverified_licence_requires_explicit_status() -> None:
    source = _source(licence_status="UNVERIFIED")
    with pytest.raises(FetchError, match="licence status"):
        validate_local_source(source)


def test_header_only_time_series_is_an_explicit_empty_trace(tmp_path: Path) -> None:
    import zipfile

    header = (
        "MACHINE_ID,MACHINE_DATA,TIMESTAMP,WAFER_ID,STAGE,CHAMBER,"
        "USAGE_OF_BACKING_FILM,USAGE_OF_DRESSER,USAGE_OF_POLISHING_TABLE,"
        "USAGE_OF_DRESSER_TABLE,PRESSURIZED_CHAMBER_PRESSURE,MAIN_OUTER_AIR_BAG_PRESSURE,"
        "CENTER_AIR_BAG_PRESSURE,RETAINER_RING_PRESSURE,RIPPLE_AIR_BAG_PRESSURE,"
        "USAGE_OF_MEMBRANE,USAGE_OF_PRESSURIZED_SHEET,SLURRY_FLOW_LINE_A,"
        "SLURRY_FLOW_LINE_B,SLURRY_FLOW_LINE_C,WAFER_ROTATION,STAGE_ROTATION,"
        "HEAD_ROTATION,DRESSING_WATER_STATUS,EDGE_AIR_BAG_PRESSURE\n"
    )
    archive = tmp_path / "fixture.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("root/CMP-test-000.csv", header)
    with zipfile.ZipFile(archive) as zf:
        rows, columns, empty_trace = _validate_csv(zf, "root/CMP-test-000.csv", "timeseries")
    assert rows == 0
    assert empty_trace is True
    assert len(columns) == 25
