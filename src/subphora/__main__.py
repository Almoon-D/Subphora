"""Command-line entry point: ``uv run subphora --help``."""

import argparse
import logging
from collections.abc import Sequence

from subphora import __version__
from subphora.config import load_settings


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="subphora")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("config", help="validate the configuration and print it")
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    settings = load_settings()
    logging.basicConfig(level=settings.core.log_level)
    if args.command == "config":
        print(settings.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
