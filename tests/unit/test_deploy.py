# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The deployment (MASTER_PLAN §4.9, decisions 0037 to 0039), read as files: the compose
file's services, volumes and ports, the variables it needs and the example that lists
them, the images' contents, Caddy's headers, nothing private in the build context, and
Dependabot watching the images. A real build and start are a command, not a test
(deploy/GUIA.md)."""

import re
from pathlib import Path
from typing import Any

import yaml

from tests.support import ROOT

DEPLOY = ROOT / "deploy"


def pinned(path: str) -> str:
    """The version a pin file holds (its copyright line aside)."""
    lines = (ROOT / path).read_text(encoding="utf-8").splitlines()
    return next(line.strip() for line in lines if line.strip() and not line.startswith("#"))


def compose() -> dict[str, Any]:
    data = yaml.safe_load((DEPLOY / "compose.yaml").read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def env_example() -> dict[str, str]:
    values = {}
    for line in (DEPLOY / ".env.example").read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#"):
            key, _, value = line.partition("=")
            values[key] = value
    return values


def test_the_services_are_the_api_caddy_and_the_backup() -> None:
    services = compose()["services"]
    assert set(services) == {"api", "web", "backup", "duckdns"}
    assert services["duckdns"]["profiles"] == ["duckdns"]
    for name in ("api", "web", "backup", "duckdns"):
        assert services[name]["restart"] == "unless-stopped", name
    assert services["backup"]["command"] == ["subphora", "backup", "nightly"]
    assert services["web"]["depends_on"]["api"]["condition"] == "service_healthy"
    for name in ("api", "backup"):
        assert services[name]["user"] == "${SUBPHORA_UID:-1000}:${SUBPHORA_GID:-1000}", name


def test_only_caddy_publishes_ports() -> None:
    services = compose()["services"]
    assert services["web"]["ports"] == ["80:80", "443:443", "443:443/udp"]
    for name in ("api", "backup", "duckdns"):
        assert "ports" not in services[name], name


def test_data_and_backups_are_volumes_never_in_an_image() -> None:
    services = compose()["services"]
    for name in ("api", "backup"):
        volumes = services[name]["volumes"]
        assert "${SUBPHORA_DATA_DIR:-../data}:/app/data" in volumes
        assert "../config/owner.yaml:/app/config/owner.yaml:ro" in volumes
    assert (
        "${SUBPHORA_BACKUP_DIR:?set SUBPHORA_BACKUP_DIR in .env}:/app/backups"
        in (services["backup"]["volumes"])
    )
    ignored = (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
    for private in ("data", "backups", "**/.env", "**/.env.*", ".git"):
        assert private in ignored, private


def test_every_variable_the_compose_file_reads_is_in_the_example() -> None:
    text = (DEPLOY / "compose.yaml").read_text(encoding="utf-8")
    # ${NAME…} is read by compose; $${NAME} is passed to the container's shell.
    read = set(re.findall(r"(?<!\$)\$\{([A-Z0-9_]+)", text))
    assert read == {
        "SUBPHORA_DATA_DIR",
        "SUBPHORA_UID",
        "SUBPHORA_GID",
        "SUBPHORA_DOMAIN",
        "SUBPHORA_BACKUP_DIR",
        "DUCKDNS_SUBDOMAIN",
        "DUCKDNS_TOKEN",
    }
    assert read <= set(env_example())


def test_the_example_holds_no_secret_and_names_every_api_key() -> None:
    values = env_example()
    for key in ("SUBPHORA_DOMAIN", "SUBPHORA_BACKUP_DIR", "DUCKDNS_TOKEN", "DUCKDNS_SUBDOMAIN"):
        assert values[key] == "", key
    sources = yaml.safe_load((ROOT / "config/defaults/sources.yaml").read_text(encoding="utf-8"))
    keys = {s["key_env"] for s in sources["services"] if s.get("key_env")}
    for key in keys:
        assert values.get(key) == "", key


def test_the_api_image_carries_what_the_report_needs() -> None:
    dockerfile = (DEPLOY / "api.Dockerfile").read_text(encoding="utf-8")
    for package in ("libpango-1.0-0", "libpangoft2-1.0-0", "libharfbuzz-subset0"):
        assert package in dockerfile, package
    assert "fonts-dejavu-core" in dockerfile  # report.css: "DejaVu Sans"
    assert "mdbtools" in dockerfile  # subphora piezometry import
    assert "COPY web/src/i18n/es.json ./web/src/i18n/es.json" in dockerfile
    assert "uv sync --locked --no-dev" in dockerfile
    assert "USER subphora" in dockerfile
    assert '"--host", "0.0.0.0"' in dockerfile
    assert f"FROM python:{pinned('.python-version')}-slim" in dockerfile


def test_the_web_image_builds_on_the_pinned_node() -> None:
    dockerfile = (DEPLOY / "web.Dockerfile").read_text(encoding="utf-8")
    node = pinned(".nvmrc").lstrip("v").split(".")[0]
    assert f"FROM node:{node}-" in dockerfile
    assert "COPY deploy/Caddyfile /etc/caddy/Caddyfile" in dockerfile


def test_caddy_sends_the_api_on_and_lets_updates_reach_the_phones() -> None:
    caddyfile = (DEPLOY / "Caddyfile").read_text(encoding="utf-8")
    assert "{$SUBPHORA_DOMAIN} {" in caddyfile
    assert "reverse_proxy api:8000" in caddyfile
    # /sw.js (decision 0037) and the page are revalidated; only hashed assets are cached.
    assert "@mutable not path /assets/*" in caddyfile
    assert 'header @mutable Cache-Control "no-cache"' in caddyfile
    assert "Strict-Transport-Security" in caddyfile
    assert "try_files {path} /index.html" in caddyfile


def test_the_pwa_is_installable() -> None:
    import json

    manifest = json.loads((ROOT / "web/public/manifest.webmanifest").read_text(encoding="utf-8"))
    assert manifest["display"] == "standalone"
    assert manifest["start_url"] == "/"
    sizes = {icon["sizes"] for icon in manifest["icons"]}
    assert {"192x192", "512x512"} <= sizes
    for icon in manifest["icons"]:
        assert (ROOT / "web/public" / icon["src"].lstrip("/")).is_file()
    page = (ROOT / "web/index.html").read_text(encoding="utf-8")
    assert '<link rel="manifest" href="/manifest.webmanifest" />' in page
    assert 'rel="apple-touch-icon"' in page


def test_dependabot_watches_the_images() -> None:
    config = yaml.safe_load((ROOT / ".github/dependabot.yml").read_text(encoding="utf-8"))
    watched = {(u["package-ecosystem"], u["directory"]) for u in config["updates"]}
    assert ("docker", "/deploy") in watched
    assert ("docker-compose", "/deploy") in watched


def test_the_guide_covers_every_step() -> None:
    guide = (DEPLOY / "GUIA.md").read_text(encoding="utf-8")
    for command in (
        "up -d --build",
        "subphora users add",
        "subphora backup create",
        "subphora backup restore",
        "--profile duckdns",
    ):
        assert command in guide, command


def test_no_deploy_file_is_left_out_of_the_tests() -> None:
    known = {
        "compose.yaml",
        ".env.example",
        "api.Dockerfile",
        "web.Dockerfile",
        "Caddyfile",
        "GUIA.md",
        ".env",  # the owner's own, git-ignored
    }
    assert {p.name for p in Path(DEPLOY).iterdir()} <= known
