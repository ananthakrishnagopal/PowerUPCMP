import hashlib
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from semifab_poc.data.provenance import (
    DatasetManifest,
    ProvenanceError,
    RawFileManifest,
    sha256_file,
    verify_dataset_manifest,
    verify_raw_file,
)


def _raw_manifest(path: Path, dataset_id: str = "dataset-1") -> RawFileManifest:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return RawFileManifest(
        dataset_id=dataset_id,
        source_owner="Example owner",
        authoritative_url="https://example.org/data.csv",
        licence_name="Example licence",
        licence_url="https://example.org/licence",
        access_date=date(2026, 7, 10),
        expected_filename=path.name,
        byte_size=path.stat().st_size,
        sha256=digest,
        schema_version="1.0",
        local_raw_path=path,
    )


def test_sha256_and_raw_file_verification(tmp_path: Path) -> None:
    path = tmp_path / "sample.csv"
    path.write_bytes(b"a,b\n1,2\n")
    manifest = _raw_manifest(path)
    assert sha256_file(path) == manifest.sha256
    verify_raw_file(manifest)


def test_raw_file_checksum_mismatch_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "sample.csv"
    path.write_bytes(b"a,b\n1,2\n")
    manifest = _raw_manifest(path).model_copy(update={"sha256": "b" * 64})
    with pytest.raises(ProvenanceError, match="SHA-256 mismatch"):
        verify_raw_file(manifest)


def test_dataset_manifest_requires_complete_provenance(tmp_path: Path) -> None:
    path = tmp_path / "sample.csv"
    path.write_bytes(b"a,b\n1,2\n")
    raw = _raw_manifest(path)
    manifest = DatasetManifest(
        dataset_id="dataset-1",
        title="Verified fixture",
        source_owner="Example owner",
        authoritative_url="https://example.org/data.csv",
        licence_name="Example licence",
        licence_url="https://example.org/licence",
        access_date=date(2026, 7, 10),
        schema_version="1.0",
        local_raw_directory=tmp_path,
        raw_files=(raw,),
    )
    verify_dataset_manifest(manifest)


def test_dataset_manifest_rejects_mismatched_child_dataset(tmp_path: Path) -> None:
    path = tmp_path / "sample.csv"
    path.write_bytes(b"data")
    raw = _raw_manifest(path, dataset_id="other")
    with pytest.raises(ValidationError, match="parent dataset_id"):
        DatasetManifest(
            dataset_id="dataset-1",
            title="Invalid fixture",
            source_owner="Example owner",
            authoritative_url="https://example.org/data.csv",
            licence_name="Example licence",
            licence_url="https://example.org/licence",
            access_date=date(2026, 7, 10),
            schema_version="1.0",
            local_raw_directory=tmp_path,
            raw_files=(raw,),
        )


def test_raw_filename_must_not_contain_a_path(tmp_path: Path) -> None:
    path = tmp_path / "sample.csv"
    path.write_bytes(b"data")
    manifest = _raw_manifest(path)
    with pytest.raises(ValidationError, match="basename"):
        RawFileManifest(**{**manifest.model_dump(), "expected_filename": "nested/sample.csv"})
