"""CLI report generation for the extracted PHM dataset."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .phm_cmp import join_training_labels, load_phm_dataset, missingness_report
from .phm_semantics import semantic_audit_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate PHM CMP integrity and semantic reports.")
    parser.add_argument("--root", default="data/raw/phm_2016_cmp")
    parser.add_argument("--output", default="reports/data/phm_missingness.json")
    parser.add_argument("--semantic-output", default="reports/data/phm_semantic_audit.json")
    parser.add_argument("--skip-checksums", action="store_true")
    args = parser.parse_args(argv)
    dataset = load_phm_dataset(args.root, verify_checksums=not args.skip_checksums)
    report = missingness_report(dataset)
    report["training_label_join"] = join_training_labels(dataset).audit
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    semantic = semantic_audit_report(dataset)
    semantic_output = Path(args.semantic_output)
    semantic_output.parent.mkdir(parents=True, exist_ok=True)
    semantic_output.write_text(json.dumps(semantic, indent=2, sort_keys=True), encoding="utf-8")
    print(
        json.dumps(
            {
                "missingness_output": str(output),
                "semantic_output": str(semantic_output),
                "empty_trace_count": report["empty_trace_count"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
