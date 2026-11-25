# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Command-line entry point: ``uv run subphora --help``."""

import argparse
import asyncio
import json
import logging
from collections.abc import Sequence
from typing import Any

from subphora import __version__
from subphora.config import Settings, load_settings
from subphora.sources import CatalogueClient, CheckStatus, check_catalogue, format_table

EXIT_FAILED_CHECK = 1
EXIT_USAGE = 2


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="subphora")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command")
    config = sub.add_parser("config", help="validate the configuration and print it")
    config.add_argument("key", nargs="?", help="print only this dotted key, e.g. api.port")
    sub.add_parser("serve", help="run the API server (host and port from config/api.yaml)")
    sources = sub.add_parser("sources", help="the catalogue of external services")
    sources_sub = sources.add_subparsers(dest="sources_command", required=True)
    check = sources_sub.add_parser(
        "check", help="check every service live: capabilities, EPSG:3857, CORS, a sample"
    )
    check.add_argument(
        "--only", action="append", metavar="ID", help="check only this service (repeatable)"
    )
    sources_sub.add_parser("list", help="print the catalogue: services, licences, limits")
    national = sub.add_parser("national", help="the national water-potential map")
    national_sub = national.add_subparsers(dest="national_command", required=True)
    build = national_sub.add_parser(
        "build",
        help="download the nationwide inputs, compute the index and confidence grids, "
        "and write the map's tiles (data/national)",
    )
    target = build.add_mutually_exclusive_group(required=True)
    target.add_argument(
        "--region",
        action="append",
        metavar="AREA",
        help="a province (ES-Z), a region (ES-AR) or a box west,south,east,north in "
        "degrees (repeatable)",
    )
    target.add_argument("--all", action="store_true", help="every province of Spain")
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    settings = load_settings()
    logging.basicConfig(level=settings.core.log_level)
    if args.command == "config":
        return _print_config(settings, args.key)
    if args.command == "serve":
        return _serve(settings)
    if args.command == "national":
        return _national_build(settings, args.region, all_provinces=args.all)
    if args.sources_command == "list":
        print(_catalogue_table(settings))
        return 0
    return _sources_check(settings, args.only)


def _print_config(settings: Settings, key: str | None) -> int:
    if key is None:
        print(settings.model_dump_json(indent=2))
        return 0
    value: Any = settings.model_dump(mode="json")
    for part in key.split("."):
        if not isinstance(value, dict) or part not in value:
            print(f"unknown configuration key: {key}")
            return EXIT_USAGE
        value = value[part]
    print(value if isinstance(value, str | int | float) else json.dumps(value))
    return 0


def _serve(settings: Settings) -> int:
    # Imported here: the other commands do not need the web stack.
    import uvicorn

    from subphora.api import create_app

    # No access log: request paths carry cadastral references, which may be the owner's
    # private parcels (hard rule 6).
    uvicorn.run(
        create_app(settings),
        host=settings.api.host,
        port=settings.api.port,
        access_log=False,
        log_level=settings.core.log_level.lower(),
    )
    return 0


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


def _national_build(settings: Settings, specs: list[str] | None, *, all_provinces: bool) -> int:
    # Imported here: the other commands do not need the raster stack.
    import os
    from concurrent.futures import ProcessPoolExecutor

    from subphora.config import REPO_ROOT
    from subphora.services.national import (
        NationalBuilder,
        RegionSpecError,
        all_regions,
        resolve_region,
    )
    from subphora.store import FileCache

    try:
        regions = (
            all_regions(settings)
            if all_provinces
            else [r for spec in specs or [] for r in resolve_region(settings, spec)]
        )
    except RegionSpecError as exc:
        print(exc)
        return EXIT_USAGE
    workers = settings.national.build.workers or os.cpu_count() or 1

    async def run() -> int:
        async with CatalogueClient(settings.sources, __version__) as client:
            cache = FileCache(settings.store.cache_path(REPO_ROOT))
            builder = NationalBuilder(client, settings, cache, REPO_ROOT)
            with ProcessPoolExecutor(max_workers=workers) as executor:
                report = await builder.build(regions, executor, workers)
        for result in report.built:
            print(f"{result.region_id}: built, {result.scored} of {result.cells} cells scored")
        for failure in report.failed:
            print(f"{failure.region_id}: FAILED: {failure.detail}")
        for layer, count in report.tiles.items():
            print(f"{layer}: {count} tiles")
        if report.built:
            print(f"Written to {builder.output}")
        return EXIT_FAILED_CHECK if report.failed else 0

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
