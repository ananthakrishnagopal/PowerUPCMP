"""Registry-gated local archive validation and extraction.

This module intentionally does not fetch URLs. The current PHM source is a
user-supplied local archive with an explicitly recorded, but not independently
verified, dataset licence. Only the original CMP measurement and removal-rate
members are selected; derived experiments and answer tables are excluded.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping, Sequence

import yaml


class FetchError(ValueError):
    """Raised when a source is not approved or an archive fails validation."""


_TIMESERIES_HEADER = [
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
]
_REMOVAL_HEADER = ["WAFER_ID", "STAGE", "AVG_REMOVAL_RATE"]
_SERIES_RE = re.compile(r"/CMP-(training|test|validation)-(\d{3})\.csv$")
_REMOVAL_RE = re.compile(r"/CMP-(training|test|validation)-removalrate\.csv$")


@dataclass(frozen=True)
class ArchiveMember:
    archive_name: str
    output_relative_path: str
    category: str
    byte_size: int
    sha256: str
    row_count: int
    columns: tuple[str, ...]
    empty_trace: bool


def sha256_file(path: str | Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_registry(path: str | Path) -> dict[str, Any]:
    registry_path = Path(path)
    try:
        data = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise FetchError(f"cannot load registry {registry_path}: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("sources"), list):
        raise FetchError("registry must contain a sources list")
    return data


def get_source(registry: Mapping[str, Any], source_id: str) -> dict[str, Any]:
    for source in registry["sources"]:
        if isinstance(source, dict) and source.get("id") == source_id:
            return source
    raise FetchError(f"source_id is not registered: {source_id}")


def validate_local_source(source: Mapping[str, Any]) -> None:
    """Require an explicit local-use authorization and complete archive metadata."""

    candidate = source.get("local_candidate_archive")
    if not isinstance(candidate, dict):
        raise FetchError("source has no local_candidate_archive metadata")
    required = ["path", "byte_size", "sha256", "selected_original_prefixes", "excluded_prefixes"]
    missing = [key for key in required if key not in candidate]
    if missing:
        raise FetchError(f"local archive metadata missing: {missing}")
    if source.get("access_approval") != "USER_AUTHORIZED_LOCAL_ARCHIVE":
        raise FetchError("local archive requires USER_AUTHORIZED_LOCAL_ARCHIVE access approval")
    scope = str(candidate.get("user_authorization_scope", ""))
    if not scope:
        raise FetchError("local archive user authorization scope is not recorded")
    if source.get("licence_status") != "USER_AUTHORIZED_UNVERIFIED_DATASET_LICENCE":
        raise FetchError("unexpected licence status for locally authorized archive")
    if not source.get("local_raw_directory"):
        raise FetchError("source local_raw_directory is required")


def _validate_member_path(name: str) -> None:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        raise FetchError(f"unsafe archive member path: {name}")


def _selected_member(name: str, source: Mapping[str, Any]) -> bool:
    candidate = source["local_candidate_archive"]
    prefixes = tuple(candidate["selected_original_prefixes"])
    excluded = tuple(candidate["excluded_prefixes"])
    relative_name = name.split("/", 1)[1] if "/" in name else name
    return (
        relative_name.startswith(prefixes)
        and not relative_name.startswith(excluded)
        and not relative_name.endswith("/")
    )


def _output_path(name: str) -> tuple[str, str]:
    if "/CMP-data/" in name:
        relative = "CMP-data/" + name.split("/CMP-data/", 1)[1]
        category = "timeseries"
    elif "/2016 PHM DATA CHALLENGE CMP VALIDATION DATA SET/validation/" in name:
        relative = "CMP-data/validation/" + name.split(
            "/2016 PHM DATA CHALLENGE CMP VALIDATION DATA SET/validation/", 1
        )[1]
        category = "timeseries"
    elif name.endswith("-removalrate.csv"):
        relative = "removal-rates/" + name.rsplit("/", 1)[1]
        category = "removal_rate"
    else:
        raise FetchError(f"selected member is not a recognized CMP raw file: {name}")
    return relative, category


def _validate_csv(zf: zipfile.ZipFile, name: str, category: str) -> tuple[int, tuple[str, ...], bool]:
    expected = _REMOVAL_HEADER if category == "removal_rate" else _TIMESERIES_HEADER
    with zf.open(name, "r") as binary:
        text = (line.decode("utf-8-sig") for line in binary)
        reader = csv.reader(text)
        try:
            header = next(reader)
        except StopIteration as exc:
            raise FetchError(f"empty CSV member: {name}") from exc
        if header != expected:
            raise FetchError(f"schema mismatch for {name}: expected {expected}, got {header}")
        row_count = 0
        for row in reader:
            if len(row) != len(expected):
                raise FetchError(f"row width mismatch in {name} at row {row_count + 2}")
            row_count += 1
    if row_count == 0 and category == "removal_rate":
        raise FetchError(f"CSV member has no data rows: {name}")
    return row_count, tuple(header), row_count == 0


def inspect_archive(archive_path: str | Path, source: Mapping[str, Any]) -> tuple[ArchiveMember, ...]:
    """Validate archive identity and selected CSV schemas without extracting."""

    validate_local_source(source)
    archive = Path(archive_path)
    if not archive.is_file():
        raise FetchError(f"archive does not exist: {archive}")
    candidate = source["local_candidate_archive"]
    expected_size = int(candidate["byte_size"])
    if archive.stat().st_size != expected_size:
        raise FetchError(f"archive size mismatch: expected {expected_size}, got {archive.stat().st_size}")
    expected_sha = str(candidate["sha256"])
    actual_sha = sha256_file(archive)
    if actual_sha != expected_sha:
        raise FetchError(f"archive SHA-256 mismatch: expected {expected_sha}, got {actual_sha}")

    selected: list[ArchiveMember] = []
    try:
        with zipfile.ZipFile(archive) as zf:
            bad_member = zf.testzip()
            if bad_member is not None:
                raise FetchError(f"ZIP CRC failure in member: {bad_member}")
            names = [info.filename for info in zf.infolist() if _selected_member(info.filename, source)]
            for name in names:
                _validate_member_path(name)
                relative, category = _output_path(name)
                rows, columns, empty_trace = _validate_csv(zf, name, category)
                with zf.open(name, "r") as stream:
                    digest = hashlib.sha256()
                    byte_size = 0
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(chunk)
                        byte_size += len(chunk)
                selected.append(
                    ArchiveMember(
                        name, relative, category, byte_size, digest.hexdigest(), rows, columns, empty_trace
                    )
                )
    except zipfile.BadZipFile as exc:
        raise FetchError(f"invalid ZIP archive {archive}: {exc}") from exc

    series = {"training": set(), "test": set(), "validation": set()}
    removals = set()
    for member in selected:
        match = _SERIES_RE.search(member.archive_name)
        if match:
            series[match.group(1)].add(int(match.group(2)))
        removal = _REMOVAL_RE.search(member.archive_name)
        if removal:
            removals.add(removal.group(1))
    expected_indices = set(range(185))
    for category, indices in series.items():
        if indices != expected_indices:
            raise FetchError(f"{category} CSV index set mismatch: expected 0..184, got {sorted(indices)}")
    if removals != set(series):
        raise FetchError(f"removal-rate table set mismatch: {sorted(removals)}")
    if any("PHM16TestValidationAnswers" in member.archive_name for member in selected):
        raise FetchError("answer tables must not be selected for raw ingestion")
    return tuple(sorted(selected, key=lambda item: item.output_relative_path))


def extract_archive(
    archive_path: str | Path,
    source: Mapping[str, Any],
    destination: str | Path | None = None,
) -> dict[str, Any]:
    """Extract only validated original CMP members, refusing overwrite."""

    members = inspect_archive(archive_path, source)
    root = Path(destination or source["local_raw_directory"])
    extraction_root = root / "original"
    if extraction_root.exists() and any(extraction_root.iterdir()):
        raise FetchError(f"refusing to overwrite existing extraction: {extraction_root}")
    extraction_root.mkdir(parents=True, exist_ok=True)
    archive = Path(archive_path)
    with zipfile.ZipFile(archive) as zf:
        for member in members:
            output = extraction_root / member.output_relative_path
            output.parent.mkdir(parents=True, exist_ok=True)
            if output.exists():
                raise FetchError(f"refusing to overwrite extracted file: {output}")
            with zf.open(member.archive_name, "r") as source_stream, output.open("xb") as target_stream:
                for chunk in iter(lambda: source_stream.read(1024 * 1024), b""):
                    target_stream.write(chunk)

    manifest = {
        "manifest_version": "1.0.0",
        "dataset_id": source["id"],
        "archive_path": str(archive),
        "archive_byte_size": archive.stat().st_size,
        "archive_sha256": sha256_file(archive),
        "archive_integrity": "VERIFIED",
        "user_authorization_scope": source["local_candidate_archive"]["user_authorization_scope"],
        "dataset_licence_status": source["licence_status"],
        "extracted_at_utc": datetime.now(timezone.utc).isoformat(),
        "answer_tables_excluded": True,
        "derived_experiments_excluded": True,
        "members": [
            {
                "archive_name": member.archive_name,
                "relative_path": member.output_relative_path,
                "category": member.category,
                "byte_size": member.byte_size,
                "sha256": member.sha256,
                "row_count": member.row_count,
                "columns": list(member.columns),
                "empty_trace": member.empty_trace,
            }
            for member in members
        ],
    }
    manifest_path = root / "extraction_manifest.yaml"
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate/extract the registered local PHM CMP archive.")
    parser.add_argument("--registry", default="orchestration/data_sources.yaml")
    parser.add_argument("--source-id", default="PHM_2016_CMP")
    parser.add_argument("--archive", default="PHM-Data-Challenge-master.zip")
    parser.add_argument("--destination", default=None)
    parser.add_argument("--extract", action="store_true", help="extract validated original CMP members")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        source = get_source(load_registry(args.registry), args.source_id)
        if args.extract:
            result = extract_archive(args.archive, source, args.destination)
        else:
            members = inspect_archive(args.archive, source)
            result = {"validated_members": len(members), "extract_performed": False}
        print(json.dumps(result, indent=2, default=str))
        return 0
    except (FetchError, OSError, zipfile.BadZipFile) as exc:
        print(f"fetch error: {exc}")
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
