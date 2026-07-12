"""Local command-line entry point for the PoC foundation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from . import __version__
from .config import ConfigError, load_runtime_config
from .logging import configure_logging


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="semifab-poc",
        description="Simulation-first semiconductor CMP predictive-control PoC tools.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command")

    validate = subparsers.add_parser(
        "validate-config", help="strictly validate a runtime YAML configuration"
    )
    validate.add_argument("path", type=Path, help="path to the runtime YAML file")
    validate.add_argument("--log-level", default="INFO", help="DEBUG, INFO, WARNING, ERROR, CRITICAL")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command is None:
        build_parser().print_help()
        return 0
    if args.command == "validate-config":
        configure_logging(args.log_level)
        try:
            config = load_runtime_config(args.path)
        except ConfigError as exc:
            print(f"configuration error: {exc}")
            return 2
        print(json.dumps(config.model_dump(mode="json"), indent=2))
        return 0
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
