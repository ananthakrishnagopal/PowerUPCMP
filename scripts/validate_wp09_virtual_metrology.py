#!/usr/bin/env python3
"""Prepare or execute the frozen, leakage-safe WP09 experiment."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from semifab_poc.models.virtual_metrology import (
    VirtualMetrologyError,
    load_virtual_metrology_config,
    prepare_feature_only_roles,
    run_virtual_metrology_experiment,
    sha256_file,
    write_json_atomic,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs" / "models" / "virtual_metrology.yaml"
SPLIT_MANIFEST_PATH = (
    ROOT / "reports" / "virtual_metrology" / "wp09_split_manifest.json"
)
OUTPUT_DIR = ROOT / "reports" / "virtual_metrology"
OPENING_MARKER_PATH = OUTPUT_DIR / "wp09_holdout_opening.json"
RESULTS_PATH = OUTPUT_DIR / "wp09_validation.json"

FOCUSED_TEST_PATHS = (
    "tests/unit/test_virtual_metrology.py",
    "tests/integration/test_vm_evaluation.py",
)
REQUIRED_COMMITTED_PATHS = (
    "configs/models/virtual_metrology.yaml",
    "orchestration/decisions/wp09_virtual_metrology.md",
    "reports/virtual_metrology/wp09_split_manifest.json",
    "scripts/validate_wp09_virtual_metrology.py",
    "src/semifab_poc/models/virtual_metrology.py",
    "tests/integration/test_vm_evaluation.py",
    "tests/unit/test_virtual_metrology.py",
)


def _git(
    arguments: Sequence[str],
    *,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        ["git", "-C", str(ROOT), *arguments],
        check=False,
        capture_output=True,
        text=True,
    )
    if check and completed.returncode != 0:
        message = completed.stderr.strip() or completed.stdout.strip()
        raise VirtualMetrologyError(
            f"git precondition failed for {' '.join(arguments)}: {message}"
        )
    return completed


def _require_clean_committed_checkpoint() -> dict[str, Any]:
    status = _git(["status", "--porcelain=v1", "--untracked-files=all"])
    if status.stdout.strip():
        raise VirtualMetrologyError(
            "one-shot holdout opening requires a completely clean Git worktree"
        )
    head = _git(["rev-parse", "HEAD"]).stdout.strip()
    tracked_hashes: dict[str, str] = {}
    for relative_path in REQUIRED_COMMITTED_PATHS:
        _git(["ls-files", "--error-unmatch", "--", relative_path])
        _git(["cat-file", "-e", f"{head}:{relative_path}"])
        tracked_hashes[relative_path] = sha256_file(ROOT / relative_path)
    return {
        "git_head": head,
        "git_worktree_clean": True,
        "required_committed_path_sha256": tracked_hashes,
    }


def _load_split_manifest() -> dict[str, Any]:
    try:
        payload = json.loads(SPLIT_MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise VirtualMetrologyError(f"cannot load frozen split manifest: {exc}") from exc
    if not isinstance(payload, dict):
        raise VirtualMetrologyError("frozen split manifest root must be a mapping")
    if payload.get("holdout_targets_accessed") is not False:
        raise VirtualMetrologyError("frozen split manifest is not target-blind")
    return payload


def _run_focused_preflight_tests() -> dict[str, Any]:
    command = [
        sys.executable,
        "-m",
        "pytest",
        *FOCUSED_TEST_PATHS,
        "-W",
        "error",
        "-q",
        "-p",
        "no:cacheprovider",
    ]
    completed = subprocess.run(command, cwd=ROOT, check=False)
    if completed.returncode != 0:
        raise VirtualMetrologyError(
            "synthetic and target-blind WP09 preflight tests did not pass"
        )
    return {
        "passed": True,
        "warning_policy": "ERROR",
        "pytest_cache_provider_disabled": True,
        "test_paths": list(FOCUSED_TEST_PATHS),
        "test_path_sha256": {
            path: sha256_file(ROOT / path) for path in FOCUSED_TEST_PATHS
        },
    }


def prepare_splits() -> dict[str, Any]:
    config = load_virtual_metrology_config(CONFIG_PATH)
    _, manifest = prepare_feature_only_roles(config, repository_root=ROOT)
    write_json_atomic(manifest, SPLIT_MANIFEST_PATH)
    return {
        "mode": "PREPARE_FEATURE_ONLY_SPLITS",
        "holdout_targets_accessed": False,
        "manifest": str(SPLIT_MANIFEST_PATH.relative_to(ROOT)),
        "manifest_sha256": sha256_file(SPLIT_MANIFEST_PATH),
        "deterministic_payload_sha256": manifest["deterministic_payload_sha256"],
        "roles": {
            role: {
                "row_count": evidence["row_count"],
                "group_count": evidence["group_count"],
            }
            for role, evidence in manifest["roles"].items()
        },
    }


def run_one_shot(*, authorize_holdout_open: bool) -> dict[str, Any]:
    if not authorize_holdout_open:
        raise VirtualMetrologyError(
            "--run-one-shot also requires the explicit --authorize-holdout-open flag"
        )
    if OPENING_MARKER_PATH.exists() or RESULTS_PATH.exists():
        raise VirtualMetrologyError(
            "the WP09 one-shot opening was already consumed; follow the failure policy "
            "before considering any rerun"
        )

    config = load_virtual_metrology_config(CONFIG_PATH)
    bundle, replayed_manifest = prepare_feature_only_roles(
        config, repository_root=ROOT
    )
    frozen_manifest = _load_split_manifest()
    if replayed_manifest != frozen_manifest:
        raise VirtualMetrologyError("committed split manifest does not replay exactly")

    git_evidence = _require_clean_committed_checkpoint()
    test_evidence = _run_focused_preflight_tests()
    post_test_git_evidence = _require_clean_committed_checkpoint()
    if post_test_git_evidence != git_evidence:
        raise VirtualMetrologyError("Git checkpoint changed during WP09 preflight tests")

    preflight_evidence = {
        **git_evidence,
        "split_manifest_path": str(SPLIT_MANIFEST_PATH.relative_to(ROOT)),
        "split_manifest_sha256": sha256_file(SPLIT_MANIFEST_PATH),
        "split_manifest_payload_sha256": frozen_manifest[
            "deterministic_payload_sha256"
        ],
        "focused_tests": test_evidence,
        "explicit_holdout_authorization": True,
        "scientific_choices_frozen_before_target_access": True,
    }
    opening_marker = {
        "schema_version": "1.0.0",
        "state": "OPENING_AUTHORIZATION_CONSUMED_RUN_STARTED",
        "accessed_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_head": git_evidence["git_head"],
        "split_manifest_payload_sha256": frozen_manifest[
            "deterministic_payload_sha256"
        ],
        "claim_boundary": "OFFLINE_PUBLIC_AVERAGE_MRR_ONLY",
    }
    write_json_atomic(opening_marker, OPENING_MARKER_PATH)

    results = run_virtual_metrology_experiment(
        config,
        bundle,
        frozen_manifest,
        output_dir=OUTPUT_DIR,
        repository_root=ROOT,
        preflight_evidence=preflight_evidence,
    )
    return {
        "mode": "ONE_SHOT_PUBLIC_VM_VALIDATION",
        "results": results["results_artifact"],
        "deterministic_payload_sha256": results["deterministic_payload_sha256"],
        "recommended_family": results["model_selection"]["recommended_family"],
        "interpretation_gates": results["interpretation_gates"],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare or execute the frozen WP09 public-data experiment."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--prepare-splits",
        action="store_true",
        help="write only the target-blind whole-wafer split manifest",
    )
    mode.add_argument(
        "--run-one-shot",
        action="store_true",
        help="execute every frozen WP09 primary and sensitivity analysis",
    )
    parser.add_argument(
        "--authorize-holdout-open",
        action="store_true",
        help="explicitly consume the one-shot test/validation-target authorization",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.prepare_splits:
            if args.authorize_holdout_open:
                raise VirtualMetrologyError(
                    "holdout authorization is invalid in feature-only preparation mode"
                )
            summary = prepare_splits()
        else:
            summary = run_one_shot(
                authorize_holdout_open=args.authorize_holdout_open
            )
    except VirtualMetrologyError as exc:
        parser.exit(2, f"WP09 guard refused execution: {exc}\n")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
