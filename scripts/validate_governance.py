#!/usr/bin/env python3
"""Validate orchestration YAML, task DAG, assumption links, and Markdown links."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_TASK_FIELDS = {
    "id",
    "title",
    "phase",
    "state",
    "priority",
    "dependencies",
    "inputs",
    "outputs",
    "files_owned",
    "acceptance_tests",
    "assumptions",
    "blockers",
}
ALLOWED_TASK_STATES = {
    "PLANNED",
    "READY",
    "IN_PROGRESS",
    "IMPLEMENTED",
    "VALIDATED",
    "BLOCKED",
    "FAILED",
    "COMPLETE",
}
MARKDOWN_LINK = re.compile(r"\[[^]]*\]\(([^)]+)\)")


class UniqueKeyLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects duplicate mapping keys."""


def _construct_unique_mapping(
    loader: UniqueKeyLoader,
    node: yaml.nodes.MappingNode,
    deep: bool = False,
) -> dict[Any, Any]:
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise ValueError(f"duplicate YAML key {key!r} at line {key_node.start_mark.line + 1}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def load_unique(path: Path) -> Any:
    return yaml.load(path.read_text(encoding="utf-8"), Loader=UniqueKeyLoader)


def validate_task_graph(manifest: dict[str, Any], assumptions: dict[str, Any]) -> dict[str, int]:
    tasks = manifest["tasks"]
    task_ids = [task["id"] for task in tasks]
    if len(set(task_ids)) != len(task_ids):
        raise ValueError("task IDs must be unique")
    task_by_id = {task["id"]: task for task in tasks}
    assumption_ids = {item["id"] for item in assumptions["assumptions"]}
    for task in tasks:
        missing = REQUIRED_TASK_FIELDS - set(task)
        if missing:
            raise ValueError(f"task {task['id']} missing fields {sorted(missing)}")
        if task["state"] not in ALLOWED_TASK_STATES:
            raise ValueError(f"task {task['id']} has invalid state {task['state']}")
        unknown_dependencies = set(task["dependencies"]) - set(task_ids)
        if unknown_dependencies:
            raise ValueError(
                f"task {task['id']} has unknown dependencies {sorted(unknown_dependencies)}"
            )
        unknown_assumptions = set(task["assumptions"]) - assumption_ids
        if unknown_assumptions:
            raise ValueError(
                f"task {task['id']} has unknown assumptions {sorted(unknown_assumptions)}"
            )

    visiting: set[str] = set()
    complete: set[str] = set()

    def visit(task_id: str) -> None:
        if task_id in visiting:
            raise ValueError(f"task dependency cycle contains {task_id}")
        if task_id in complete:
            return
        visiting.add(task_id)
        for dependency in task_by_id[task_id]["dependencies"]:
            visit(dependency)
        visiting.remove(task_id)
        complete.add(task_id)

    for task_id in task_ids:
        visit(task_id)
    return {"task_count": len(tasks), "assumption_count": len(assumption_ids)}


def validate_markdown_links() -> tuple[int, int]:
    files = list(ROOT.rglob("*.md"))
    checked = 0
    missing: list[tuple[str, str]] = []
    for path in files:
        for target in MARKDOWN_LINK.findall(path.read_text(encoding="utf-8", errors="replace")):
            if target.startswith(("http://", "https://", "mailto:", "#", "/")):
                continue
            local_target = target.split("#", 1)[0]
            if not local_target:
                continue
            checked += 1
            if not (path.parent / local_target).resolve().exists():
                missing.append((str(path.relative_to(ROOT)), target))
    if missing:
        raise ValueError(f"missing local Markdown links: {missing}")
    return len(files), checked


def main() -> int:
    yaml_paths = sorted((ROOT / "orchestration").glob("*.yaml")) + sorted(
        (ROOT / "configs").rglob("*.yaml")
    )
    parsed = {str(path.relative_to(ROOT)): load_unique(path) for path in yaml_paths}
    graph = validate_task_graph(
        parsed["orchestration/task_manifest.yaml"],
        parsed["orchestration/assumptions.yaml"],
    )
    markdown_files, local_links = validate_markdown_links()
    print(
        json.dumps(
            {
                "yaml_file_count": len(yaml_paths),
                "duplicate_yaml_keys": 0,
                **graph,
                "task_dag": "ACYCLIC",
                "markdown_file_count": markdown_files,
                "valid_local_markdown_link_count": local_links,
                "missing_local_markdown_links": 0,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
