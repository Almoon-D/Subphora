# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Command-line entry point: ``uv run subphora --help``."""

import argparse
import asyncio
import logging
from collections.abc import Sequence

from subphora import __version__
from subphora.config import Settings, load_settings
from subphora.sources import CatalogueClient, CheckStatus, check_catalogue, format_table

EXIT_FAILED_CHECK = 1
EXIT_USAGE = 2


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="subphora")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("config", help="validate the configuration and print it")
    sources = sub.add_parser("sources", help="the catalogue of external services")
    sources_sub = sources.add_subparsers(dest="sources_command", required=True)
    check = sources_sub.add_parser(
        "check", help="check every service live: capabilities, EPSG:3857, CORS, a sample"
    )
    check.add_argument(
        "--only", action="append", metavar="ID", help="check only this service (repeatable)"
    )
    sources_sub.add_parser("list", help="print the catalogue: services, licences, limits")
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    settings = load_settings()
    logging.basicConfig(level=settings.core.log_level)
    if args.command == "config":
        print(settings.model_dump_json(indent=2))
        return 0
    if args.sources_command == "list":
        print(_catalogue_table(settings))
        return 0
    return _sources_check(settings, args.only)


def _sources_check(settings: Settings, only: list[str] | None) -> int:
    services = settings.sources.services
    if only:
        known = {service.id for service in services}
        unknown = sorted(set(only) - known)
        if unknown:
            print(f"unknown service id: {', '.join(unknown)}; see `subphora sources list`")
            return EXIT_USAGE
        services = [service for service in services if service.id in only]

    async def run() -> int:
        async with CatalogueClient(settings.sources, __version__) as client:
            origin = settings.sources.client.cors_probe_origin
            results = await check_catalogue(client, services, origin)
        print(format_table(results))
        return EXIT_FAILED_CHECK if any(r.status is CheckStatus.FAILED for r in results) else 0

    return asyncio.run(run())


def _catalogue_table(settings: Settings) -> str:
    lines = []
    for service in settings.sources.services:
        limits = service.politeness
        cache = "never cached" if limits.cache_lifetime_s == 0 else f"{limits.cache_lifetime_s} s"
        key = f", key from ${service.key_env}" if service.key_env else ""
        area = ", ".join(service.coverage)
        if service.coverage_excludes:
            area += " except " + ", ".join(service.coverage_excludes)
        lines.append(
            f"{service.id} ({service.kind}) {service.host}{key}\n"
            f"  covers: {area}\n"
            f"  {service.name} — {service.publisher}\n"
            f"  licence: {service.licence} ({service.terms_url})\n"
            f"  attribution: {service.attribution}\n"
            f"  layers: {', '.join(service.layers) or '-'}; CRS: {', '.join(service.crs) or '-'}\n"
            f"  limits: {limits.max_concurrent} at a time, {limits.min_interval_s} s apart; "
            f"cache {cache}\n"
            f"  knowledge: {service.knowledge}"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
