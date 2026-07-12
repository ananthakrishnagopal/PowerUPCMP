"""Build deterministic, label-separated PHM phase-feature artifacts."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from .phm_cmp import load_phm_dataset
from .phm_semantics import (
    LabelAnomalyPolicy,
    apply_training_label_policy,
    build_official_feature_sets,
    join_group_labels,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_csv_atomic(frame: pd.DataFrame, path: Path) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    frame.to_csv(temporary, index=False)
    temporary.replace(path)
    return {
        "path": str(path),
        "row_count": int(len(frame)),
        "column_count": int(len(frame.columns)),
        "byte_size": path.stat().st_size,
        "sha256": _sha256(path),
    }


def build_feature_bundle(
    *,
    root: Path,
    output_dir: Path,
    verify_checksums: bool = True,
    gap_threshold_s: float = 10.0,
) -> dict[str, Any]:
    """Write official-split features and separate native labels with a manifest."""

    dataset = load_phm_dataset(root, verify_checksums=verify_checksums)
    feature_sets = build_official_feature_sets(dataset, gap_threshold_s=gap_threshold_s)
    files: dict[str, Any] = {}
    joins: dict[str, Any] = {}
    feature_audits: dict[str, Any] = {}

    for split in ("training", "test", "validation"):
        feature_result = getattr(feature_sets, split)
        labels = getattr(dataset, f"{split}_labels")
        feature_path = output_dir / f"{split}_phase_features.csv"
        label_path = output_dir / f"{split}_labels_native.csv"
        feature_evidence = _write_csv_atomic(feature_result.frame, feature_path)
        feature_evidence.update(
            {
                "role": "OFFLINE_VM_FEATURES_WITHOUT_TARGET",
                "contains_target": False,
            }
        )
        files[f"{split}_features"] = feature_evidence
        label_evidence = _write_csv_atomic(labels, label_path)
        label_evidence.update(
            {
                "role": "OFFLINE_NATIVE_TARGETS_SEPARATE_FROM_FEATURES",
                "source_unit_status": "NOT_DECLARED_BY_ORIGINAL_SOURCE",
            }
        )
        files[f"{split}_labels"] = label_evidence
        joins[split] = join_group_labels(feature_result, labels, split=split).audit
        feature_audits[split] = feature_result.audit

    label_policy_audits: dict[str, Any] = {}
    for policy in LabelAnomalyPolicy:
        policy_result = apply_training_label_policy(dataset.training_labels, policy)
        policy_name = policy.value.lower()
        evidence = _write_csv_atomic(
            policy_result.frame,
            output_dir / f"training_labels_{policy_name}.csv",
        )
        evidence.update(
            {
                "role": "PREREGISTERED_TRAINING_LABEL_TREATMENT",
                "policy": policy.value,
            }
        )
        files[f"training_label_policy_{policy_name}"] = evidence
        label_policy_audits[policy.value] = policy_result.audit

    manifest = {
        "bundle_version": "PHM_PHASE_FEATURES_V1",
        "dataset_id": "PHM_2016_CMP",
        "archive_sha256": dataset.extraction_manifest["archive_sha256"],
        "canonical_schema_version": "2.0.0",
        "target": "AVG_REMOVAL_RATE",
        "target_unit_status": "NOT_DECLARED_BY_ORIGINAL_SOURCE",
        "process_signal_units": "PROPRIETARY_SCALED_WITH_HIDDEN_FACTORS",
        "gap_threshold_s": gap_threshold_s,
        "process_modes_are_input_only_proxies": True,
        "complete_trace_features_streaming_eligible": False,
        "official_split_roles": {
            "training": "FIT_AND_TUNING_ONLY",
            "test": "OFFLINE_HOLDOUT",
            "validation": "FINAL_PUBLIC_HOLDOUT",
        },
        "feature_audits": feature_audits,
        "label_join_audits": joins,
        "label_policy_audits": label_policy_audits,
        "files": files,
    }
    manifest_path = output_dir / "feature_manifest.yaml"
    temporary = manifest_path.with_suffix(".yaml.tmp")
    temporary.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    temporary.replace(manifest_path)
    manifest["manifest"] = {
        "path": str(manifest_path),
        "byte_size": manifest_path.stat().st_size,
        "sha256": _sha256(manifest_path),
    }
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build phase-aware PHM offline-VM features.")
    parser.add_argument("--root", type=Path, default=Path("data/raw/phm_2016_cmp"))
    parser.add_argument(
        "--output-dir", type=Path, default=Path("data/processed/phm_2016_cmp")
    )
    parser.add_argument("--gap-threshold-s", type=float, default=10.0)
    parser.add_argument("--skip-checksums", action="store_true")
    args = parser.parse_args(argv)
    manifest = build_feature_bundle(
        root=args.root,
        output_dir=args.output_dir,
        verify_checksums=not args.skip_checksums,
        gap_threshold_s=args.gap_threshold_s,
    )
    print(yaml.safe_dump({"manifest": manifest["manifest"], "files": len(manifest["files"])}))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
