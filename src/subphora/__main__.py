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
    serve = sub.add_parser("serve", help="run the API server (host and port from config/api.yaml)")
    serve.add_argument("--host", help="listen on this address instead (the container: 0.0.0.0)")
    users = sub.add_parser("users", help="the people who may sign in (no public sign-up)")
    users_sub = users.add_subparsers(dest="users_command", required=True)
    for command, text in (
        ("add", "add a user; the password is asked twice"),
        ("password", "set a user's password; their devices sign in again"),
        ("remove", "remove a user and end their sessions"),
    ):
        parser_ = users_sub.add_parser(command, help=text)
        parser_.add_argument("name", help="the login name: lower case, digits, '.', '-', '_'")
        if command != "remove":
            parser_.add_argument(
                "--password-stdin",
                action="store_true",
                help="read the password from the first line of standard input",
            )
    users_sub.add_parser("list", help="the users' names")
    backup = sub.add_parser("backup", help="backups of data/ (config/defaults/backup.yaml)")
    backup_sub = backup.add_subparsers(dest="backup_command", required=True)
    backup_sub.add_parser("create", help="write one archive, read it back, prune old ones")
    backup_sub.add_parser("list", help="the archives in the destination")
    verify = backup_sub.add_parser("verify", help="read an archive back: files, sums, databases")
    verify.add_argument("archive", help="the .tar.gz to check")
    restore = backup_sub.add_parser(
        "restore", help="put an archive's files in place of data/ (stop the server first)"
    )
    restore.add_argument("archive", help="the .tar.gz to restore")
    backup_sub.add_parser("nightly", help="run the backup every night, for ever (the service)")
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
    piezometry = sub.add_parser("piezometry", help="the piezometric levels (depth to water)")
    piezometry_sub = piezometry.add_subparsers(dest="piezometry_command", required=True)
    piezometry_import = piezometry_sub.add_parser(
        "import",
        help="summarise the national piezometry database you downloaded by hand "
        "(config/defaults/piezometry.yaml: input) for the depth to water",
    )
    piezometry_import.add_argument(
        "--file", metavar="PATH", help="the downloaded .zip or .accdb instead of the configured one"
    )
    field = sub.add_parser("field", help="the field observations synced to this server")
    field_sub = field.add_subparsers(dest="field_command", required=True)
    field_sub.add_parser(
        "summary", help="count the stored records by kind, their files and tracks (data/field)"
    )
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    settings = load_settings()
    logging.basicConfig(level=settings.core.log_level)
    if args.command == "config":
        return _print_config(settings, args.key)
    if args.command == "serve":
        return _serve(settings, args.host)
    if args.command == "users":
        return _users(settings, args.users_command, args)
    if args.command == "backup":
        return _backup(settings, args.backup_command, getattr(args, "archive", None))
    if args.command == "national":
        return _national_build(settings, args.region, all_provinces=args.all)
    if args.command == "piezometry":
        return _piezometry_import(settings, args.file)
    if args.command == "field":
        return _field_summary(settings)
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


def _serve(settings: Settings, host: str | None) -> int:
    # Imported here: the other commands do not need the web stack.
    import uvicorn

    from subphora.api import create_app

    # No access log: request paths carry cadastral references, which may be the owner's
    # private parcels (hard rule 6).
    uvicorn.run(
        create_app(settings),
        host=host or settings.api.host,
        port=settings.api.port,
        access_log=False,
        log_level=settings.core.log_level.lower(),
    )
    return 0


def _read_password(from_stdin: bool) -> str | None:
    import getpass
    import sys

    if from_stdin:
        return sys.stdin.readline().rstrip("\r\n")
    first = getpass.getpass("Password: ")
    if getpass.getpass("Again: ") != first:
        print("FAILED: the two passwords differ")
        return None
    return first


def _users(settings: Settings, command: str, args: argparse.Namespace) -> int:
    from subphora.config import REPO_ROOT
    from subphora.domain.auth import AuthError
    from subphora.services.auth import AuthService

    service = AuthService(settings, REPO_ROOT)
    try:
        if command == "list":
            names = asyncio.run(service.users())
            print("\n".join(names) if names else "no users yet: subphora users add <name>")
            return 0
        name = service.check_name(args.name)
        if command == "remove":
            asyncio.run(service.remove_user(name))
            print(f"{name}: removed")
            return 0
        password = _read_password(args.password_stdin)
        if password is None:
            return EXIT_USAGE
        if command == "add":
            asyncio.run(service.add_user(name, password))
            print(f"{name}: added")
        else:
            asyncio.run(service.set_password(name, password))
            print(f"{name}: password set; their devices sign in again")
    except AuthError as exc:
        print(f"FAILED: {exc.detail}")
        return EXIT_FAILED_CHECK
    return 0


def _backup(settings: Settings, command: str, archive: str | None) -> int:
    from pathlib import Path

    from subphora.config import REPO_ROOT
    from subphora.domain.backup import BackupError, BackupSummary
    from subphora.services.backup import BackupService
    from subphora.store.backup import archives

    service = BackupService(settings, REPO_ROOT)

    def show(summary: BackupSummary, what: str) -> None:
        print(
            f"{summary.archive}: {what}; {summary.files} files ({summary.databases} databases), "
            f"{summary.size_bytes} bytes, made {summary.created_at.isoformat()}"
        )

    try:
        if command == "create":
            summary, pruned = service.run()
            show(summary, "written and verified")
            print(f"in {service.destination}; {len(pruned)} older archives deleted")
        elif command == "list":
            found = archives(service.destination)
            print("\n".join(p.name for p in found) if found else "no archives yet")
        elif command == "verify":
            show(service.verify(Path(archive or "")), "verified")
        elif command == "restore":
            previous = service.restore(Path(archive or ""))
            print("restored")
            if previous is not None:
                print(f"the files that were there are kept in {previous}")
        else:
            asyncio.run(service.nightly())
    except BackupError as exc:
        print(f"FAILED ({exc.failure.value}): {exc.detail}")
        return EXIT_FAILED_CHECK
    return 0


def _field_summary(settings: Settings) -> int:
    from subphora.config import REPO_ROOT
    from subphora.services.field import FieldService

    summary = asyncio.run(FieldService(settings, REPO_ROOT).summary())
    for count in summary.kinds:
        files = f", {count.with_media} with their file" if count.with_media else ""
        print(f"{count.kind.value}: {count.records} records{files}")
    print(f"tracks: {summary.tracks}")
    if summary.first_recorded_at and summary.last_recorded_at:
        first = summary.first_recorded_at.isoformat()
        print(f"recorded from {first} to {summary.last_recorded_at.isoformat()} (UTC)")
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
            print(
                f"{result.region_id}: built, {result.scored} of {result.cells} cells scored; "
                f"domains: {result.validated} validated, {result.chance} no better than "
                f"chance, {result.unmeasured} without enough wells"
            )
        for failure in report.failed:
            print(f"{failure.region_id}: FAILED: {failure.detail}")
        for layer, count in report.tiles.items():
            print(f"{layer}: {count} tiles")
        if report.built:
            print(f"Written to {builder.output}")
        return EXIT_FAILED_CHECK if report.failed else 0

    return asyncio.run(run())


def _piezometry_import(settings: Settings, file: str | None) -> int:
    from datetime import UTC, datetime
    from pathlib import Path

    from subphora.config import REPO_ROOT
    from subphora.services.piezometry import import_piezometry
    from subphora.sources.piezometry import PiezometryReadError

    if file is not None:
        piezometry = settings.piezometry.model_copy(update={"input": Path(file).resolve()})
        settings = settings.model_copy(update={"piezometry": piezometry})
    try:
        dataset = import_piezometry(settings, REPO_ROOT, datetime.now(UTC))
    except (PiezometryReadError, ValueError) as exc:
        print(f"FAILED: {exc}")
        return EXIT_FAILED_CHECK
    print(
        f"{len(dataset.piezometers)} piezometers kept of {dataset.piezometers_read} "
        f"({dataset.left_out} left out), from {dataset.levels_read} levels"
    )
    for source in dataset.sources:
        used = sum(1 for p in dataset.piezometers if source.service_id in p.sources)
        print(
            f"  {source.service_id} ({source.file_name}): {used} piezometers, "
            f"levels {source.levels_from} to {source.levels_to}"
        )
    imported = {s.service_id for s in dataset.sources}
    for basin in settings.piezometry.basins:
        if basin.service not in imported:
            print(f"  {basin.service}: not imported ({basin.input} missing or no level kept)")
    print(f"Written to {settings.piezometry.output_path(REPO_ROOT)}")
    return 0


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
