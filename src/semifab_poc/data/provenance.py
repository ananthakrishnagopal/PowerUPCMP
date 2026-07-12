"""Dataset and raw-file provenance validation without network access."""

from __future__ import annotations

import hashlib
from datetime import date, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProvenanceError(ValueError):
    """Raised when a dataset manifest or raw file fails provenance checks."""


class ProvenanceModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, validate_assignment=True)


class RawFileManifest(ProvenanceModel):
    dataset_id: str = Field(min_length=1)
    source_owner: str = Field(min_length=1)
    authoritative_url: str = Field(pattern=r"^https?://[^\s]+$")
    licence_name: str = Field(min_length=1)
    licence_url: str = Field(pattern=r"^https?://[^\s]+$")
    access_date: date | datetime
    expected_filename: str = Field(min_length=1)
    byte_size: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    schema_version: str = Field(min_length=1)
    local_raw_path: Path

    @model_validator(mode="after")
    def validate_filename(self) -> RawFileManifest:
        if Path(self.expected_filename).name != self.expected_filename:
            raise ValueError("expected_filename must be a basename, not a path")
        if self.local_raw_path.name != self.expected_filename:
            raise ValueError("local_raw_path filename must match expected_filename")
        return self


class DatasetManifest(ProvenanceModel):
    dataset_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    source_owner: str = Field(min_length=1)
    authoritative_url: str = Field(pattern=r"^https?://[^\s]+$")
    licence_name: str = Field(min_length=1)
    licence_url: str = Field(pattern=r"^https?://[^\s]+$")
    access_date: date | datetime
    schema_version: str = Field(min_length=1)
    local_raw_directory: Path
    raw_files: tuple[RawFileManifest, ...] = Field(min_length=1)
    synthetic_only: bool = False

    @model_validator(mode="after")
    def validate_children(self) -> DatasetManifest:
        if any(raw.dataset_id != self.dataset_id for raw in self.raw_files):
            raise ValueError("every raw file must reference the parent dataset_id")
        if len({raw.expected_filename for raw in self.raw_files}) != len(self.raw_files):
            raise ValueError("raw file filenames must be unique within a dataset manifest")
        if self.synthetic_only:
            raise ValueError("synthetic outputs must use a simulator manifest, not public raw files")
        return self


def sha256_file(path: str | Path, chunk_size: int = 1024 * 1024) -> str:
    """Compute a streaming SHA-256 digest without modifying the file."""

    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    digest = hashlib.sha256()
    try:
        with Path(path).open("rb") as handle:
            for chunk in iter(lambda: handle.read(chunk_size), b""):
                digest.update(chunk)
    except OSError as exc:
        raise ProvenanceError(f"cannot read raw file {path}: {exc}") from exc
    return digest.hexdigest()


def verify_raw_file(manifest: RawFileManifest) -> None:
    """Verify existence, exact basename, byte size, and SHA-256 from a manifest."""

    path = manifest.local_raw_path
    if not path.is_file():
        raise ProvenanceError(f"raw file is missing: {path}")
    if path.name != manifest.expected_filename:
        raise ProvenanceError(f"filename mismatch: expected {manifest.expected_filename}, got {path.name}")
    actual_size = path.stat().st_size
    if actual_size != manifest.byte_size:
        raise ProvenanceError(f"byte-size mismatch for {path}: expected {manifest.byte_size}, got {actual_size}")
    actual_sha256 = sha256_file(path)
    if actual_sha256 != manifest.sha256:
        raise ProvenanceError(f"SHA-256 mismatch for {path}: expected {manifest.sha256}, got {actual_sha256}")


def verify_dataset_manifest(manifest: DatasetManifest) -> None:
    """Verify every raw file referenced by a validated dataset manifest."""

    for raw_file in manifest.raw_files:
        verify_raw_file(raw_file)
