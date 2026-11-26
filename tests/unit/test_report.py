# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The per-area PDF report and the export pack, on the synthetic Spain: every section and
attribution in the PDF, a missing input written as missing, the pack's GIS files opening
with their CRS declared, field records and their files only when asked, and the refusals."""

import csv
import hashlib
import io
import json
import re
import uuid
import zipfile
from pathlib import Path
from typing import Any

import httpx
import numpy as np
import pyogrio
import pytest
import rasterio
from pypdf import PdfReader

from subphora.config import REPO_ROOT, Settings
from subphora.domain.field import ObservationKind
from subphora.domain.legal import LegalState
from subphora.report.catalogue import Catalogue, CatalogueError
from subphora.report.document import fetcher
from subphora.services.export import Missing
from tests.national_support import FakeSpain
from tests.parcel_support import parcel_settings, point_area, serve, write_levels
from tests.unit.test_parcel_jobs import analyse

# The datasets a detailed map reads (services/parcel.py), each named in the report.
DATASETS = (
    "permeability",
    "terrain",
    "soil",
    "groundwater_bodies",
    "water_points",
    "faults",
    "bedding",
)
PHOTO = b"\xff\xd8\xff\xe0 synthetic jpeg bytes"
SECTIONS = (
    "Informe de potencial de agua subterránea",
    "Resumen del área",
    "Mapas",
    "Puntos candidatos",
    "Acierto medido del modelo",
    "Observaciones de campo",
    "Fuentes, fechas y atribuciones",
    "Limitaciones",
    "Aviso legal",
)


@pytest.fixture
def settings() -> Settings:
    return parcel_settings()


def pdf_text(content: bytes) -> str:
    reader = PdfReader(io.BytesIO(content))
    text = "\n".join(page.extract_text() for page in reader.pages)
    return re.sub(r"\s+", " ", text)


def observations(area_id: str, lon: float, lat: float) -> list[dict[str, Any]]:
    fix = {"longitude": lon, "latitude": lat, "accuracy_m": 4.0, "fixed_at": "2026-11-26T10:00:00Z"}
    note = {
        "id": str(uuid.uuid7()),
        "kind": "note",
        "recorded_at": "2026-11-26T10:00:05Z",
        "position": fix,
        "target": {"area_id": area_id, "rank": 1, "longitude": lon, "latitude": lat},
        "text": "Afloramiento de calizas",
    }
    photo = {
        "id": str(uuid.uuid7()),
        "kind": "photo",
        "recorded_at": "2026-11-26T10:01:00Z",
        "position": fix,
        "target": None,
        "text": "Brocal",
        "media": {
            "content_type": "image/jpeg",
            "size_bytes": len(PHOTO),
            "sha256": hashlib.sha256(PHOTO).hexdigest(),
        },
    }
    # Far from the area and guided nowhere in it: not the area's.
    elsewhere = {
        **note,
        "id": str(uuid.uuid7()),
        "target": None,
        "position": {**fix, "longitude": -5.0},
    }
    return [note, photo, elsewhere]


async def record_field(client: httpx.AsyncClient, area_id: str, lon: float, lat: float) -> None:
    records = observations(area_id, lon, lat)
    sent = await client.post("/api/field/observations", json={"observations": records})
    assert sent.status_code == 200
    stored = await client.put(
        f"/api/field/observations/{records[1]['id']}/media",
        content=PHOTO,
        headers={"Content-Type": "image/jpeg"},
    )
    assert stored.status_code == 201


def unpack(content: bytes, folder: Path) -> tuple[zipfile.ZipFile, dict[str, Any]]:
    pack = zipfile.ZipFile(io.BytesIO(content))
    pack.extractall(folder)
    return pack, json.loads(pack.read("manifest.json"))


async def test_the_report_and_pack_hold_everything_with_depth_and_field_records(
    settings: Settings, tmp_path: Path
) -> None:
    write_levels(settings, tmp_path)
    async with serve(settings, tmp_path, FakeSpain(whole_body=True)) as client:
        _, body = await analyse(client, point_area())
        analysis = body["job"]["analysis"]
        area_id = analysis["id"]
        first = analysis["candidates"][0]
        await record_field(client, area_id, first["longitude"], first["latitude"])
        pdf = await client.get(f"/api/parcel/{area_id}/report.pdf")
        plain = await client.get(f"/api/parcel/{area_id}/pack.zip")
        with_media = await client.get(f"/api/parcel/{area_id}/pack.zip", params={"media": "true"})
    assert pdf.status_code == 200, pdf.text
    assert pdf.headers["content-type"] == "application/pdf"
    assert f"subphora-{area_id}.pdf" in pdf.headers["content-disposition"]
    text = pdf_text(pdf.content)
    for heading in SECTIONS:
        assert heading in text
    # Scores with their confidence, called an index; every candidate with its figures.
    assert "Índice 0," in text
    assert "Confianza " in text
    assert "no es una probabilidad" in text
    for candidate in analysis["candidates"]:
        assert f"Candidato {candidate['rank']}" in text
    assert "Profundidad del agua: unos" in text
    assert "Coste de perforación: entre" in text
    assert "Roca carbonatada (posible karst)" in text
    assert "Organismo competente" in text
    assert "Orientación, no asesoramiento legal" in text
    # Every source with its date and attribution, and its licence from the catalogue.
    for source in analysis["sources"].values():
        assert source["attribution"] in text
    assert "Consultado el 2" in text
    assert "Licencia:" in text
    assert "Niveles piezométricos:" in text
    # The field records of the area, not the one made elsewhere.
    assert "Afloramiento de calizas" in text
    assert "2 registros" in text

    assert plain.status_code == with_media.status_code == 200
    assert plain.headers["content-type"] == "application/zip"
    pack, manifest = unpack(plain.content, tmp_path / "plain")
    names = set(pack.namelist())
    assert {
        "report.pdf",
        "layers.gpkg",
        "potential-index.tif",
        "potential-confidence.tif",
        "depth.tif",
        "candidates.csv",
        "contributions.csv",
        "sources.csv",
        "observations.csv",
        "manifest.json",
        "LEEME.txt",
    } <= names
    assert not any(n.startswith("media/") for n in names)
    assert manifest["crs"] == "EPSG:25830"
    assert manifest["missing"] == ["media_left_out"]
    assert "Fotos y notas de voz: no se han incluido" in pack.read("LEEME.txt").decode()
    gpkg = tmp_path / "plain" / "layers.gpkg"
    layers = {name for name, _ in pyogrio.list_layers(gpkg)}
    assert layers == {"area", "candidates", "observations"}
    for name in layers:
        assert pyogrio.read_info(gpkg, layer=name)["crs"] == "EPSG:25830"
    candidates = pyogrio.read_info(gpkg, layer="candidates")
    assert candidates["features"] == len(analysis["candidates"])
    assert pyogrio.read_info(gpkg, layer="observations")["features"] == 2
    assert pyogrio.read_info(gpkg, layer="area")["geometry_type"] == "Polygon"
    for name in ("potential-index.tif", "potential-confidence.tif", "depth.tif"):
        with rasterio.open(tmp_path / "plain" / name) as cog:
            assert str(cog.crs) == "EPSG:25830"
            assert cog.tags(ns="IMAGE_STRUCTURE")["LAYOUT"] == "COG"
            assert np.isfinite(cog.read(1)).any()
    with rasterio.open(tmp_path / "plain" / "depth.tif") as depth:
        assert depth.descriptions == ("depth_m", "low_m", "high_m")
        x, y = first["local"]["x"], first["local"]["y"]
        value = next(depth.sample([(x, y)]))[0]
    assert value == pytest.approx(first["depth"]["depth_m"], abs=0.01)
    rows = list(csv.DictReader(io.StringIO(pack.read("candidates.csv").decode("utf-8-sig"))))
    assert [int(r["rank"]) for r in rows] == [c["rank"] for c in analysis["candidates"]]
    assert rows[0]["confidence"]
    assert rows[0]["legal_state"] == first["legal"]["state"]

    media_pack, media_manifest = unpack(with_media.content, tmp_path / "media")
    files = [n for n in media_pack.namelist() if n.startswith("media/")]
    assert len(files) == 1
    assert media_pack.read(files[0]) == PHOTO
    assert media_manifest["missing"] == []
    meta, _, _, columns = pyogrio.raw.read(tmp_path / "media" / "layers.gpkg", layer="observations")
    media_files = dict(zip(meta["fields"], columns, strict=True))["media_file"]
    assert files[0] in set(media_files)


async def test_missing_inputs_are_written_as_missing(settings: Settings, tmp_path: Path) -> None:
    async with serve(settings, tmp_path) as client:
        _, body = await analyse(client, point_area())
        area_id = body["job"]["id"]
        pdf = await client.get(f"/api/parcel/{area_id}/report.pdf")
        packed = await client.get(f"/api/parcel/{area_id}/pack.zip")
    text = pdf_text(pdf.content)
    # No levels imported: the depth says why, the cost is not estimated, nothing is blank.
    assert "Profundidad del agua: desconocida, no se han importado" in text
    assert "Coste de perforación: sin estimar" in text
    assert "desconocido" in text
    assert "No hay observaciones de campo en esta área" in text
    # The criterion with no input at this scale is listed as missing.
    assert "Profundidad del nivel del agua: aún no hay datos para este mapa" in text
    pack, manifest = unpack(packed.content, tmp_path / "pack")
    assert "depth.tif" not in pack.namelist()
    assert manifest["missing"] == ["depth_not_imported", "no_observations"]
    readme = pack.read("LEEME.txt").decode()
    assert "no se han importado los niveles piezométricos" in readme
    # The empty observations layer is still there, with its CRS.
    gpkg = tmp_path / "pack" / "layers.gpkg"
    info = pyogrio.read_info(gpkg, layer="observations")
    assert info["features"] == 0
    assert info["crs"] == "EPSG:25830"


async def test_a_report_is_refused_until_the_map_is_done(
    settings: Settings, tmp_path: Path
) -> None:
    async with serve(settings, tmp_path) as client:
        unknown = await client.get("/api/parcel/0123456789abcdef/report.pdf")
        pack = await client.get("/api/parcel/0123456789abcdef/pack.zip")
        malformed = await client.get("/api/parcel/not-an-id/report.pdf")
    assert unknown.status_code == pack.status_code == 404
    assert unknown.json()["code"] == pack.json()["code"] == "unknown_job"
    assert malformed.status_code == 422


async def test_a_lost_outline_or_catalogue_is_reported(settings: Settings, tmp_path: Path) -> None:
    broken = settings.model_copy(
        update={
            "report": settings.report.model_copy(update={"catalogue": tmp_path / "missing.json"})
        }
    )
    async with serve(broken, tmp_path) as client:
        _, body = await analyse(client, point_area())
        area_id = body["job"]["id"]
        no_catalogue = await client.get(f"/api/parcel/{area_id}/report.pdf")
        (settings.parcel.jobs.output_path(tmp_path) / "outlines" / f"{area_id}.json").unlink()
        no_outline = await client.get(f"/api/parcel/{area_id}/pack.zip")
    assert no_catalogue.status_code == 500
    assert no_catalogue.json()["code"] == "catalogue_unreadable"
    assert no_outline.status_code == 500
    assert no_outline.json()["code"] == "unreadable"


def test_the_report_loads_nothing_but_embedded_images() -> None:
    for url in ("https://www.ign.es/logo.png", "file:///etc/passwd"):
        with pytest.raises(ValueError, match="disallowed protocol"):
            fetcher().fetch(url)


# The catalogue.


def catalogue() -> Catalogue:
    settings = parcel_settings().report
    return Catalogue.load(settings.catalogue_path(REPO_ROOT), settings.zone("EPSG:25830"))


def test_numbers_and_dates_are_written_the_spanish_way() -> None:
    from datetime import UTC, datetime

    c = catalogue()
    assert c.number(13352) == "13.352"
    assert c.number(1234) == "1234"
    assert c.number(2.5, 2) == "2,50"
    assert c.number(-0.001, 1) == "0,0"
    assert c.quantity(1500, "m") == "1,5 km"
    assert c.quantity(0.456, "index") == "0,46"
    assert c.percent(0.25) == "25\u00a0%"
    # 23:30 UTC is already the next day in Madrid, and not yet in the Canaries.
    late = datetime(2026, 11, 26, 23, 30, tzinfo=UTC)
    assert c.day(late) == "27/11/2026"
    canary = Catalogue({}, parcel_settings().report.zone("EPSG:4083"))
    assert canary.day(late) == "26/11/2026"


def test_a_missing_message_or_parameter_is_an_error() -> None:
    c = catalogue()
    with pytest.raises(CatalogueError, match="no message"):
        c.t("report.nothing")
    with pytest.raises(CatalogueError, match="missing parameter"):
        c.t("report.id")
    assert c.lookup("report.nothing", "fallback") == "fallback"
    with pytest.raises(CatalogueError):
        Catalogue.load(REPO_ROOT / "pyproject.toml", parcel_settings().report.zone("x"))


def test_every_message_the_report_names_is_in_the_catalogue() -> None:
    messages = json.loads((REPO_ROOT / "web/src/i18n/es.json").read_text(encoding="utf-8"))
    named: set[str] = set()
    for module in ("document.py", "pack.py"):
        source = (REPO_ROOT / "src/subphora/report" / module).read_text(encoding="utf-8")
        named |= set(re.findall(r"""(?:\.t|lookup)\(\s*["']([a-zA-Z0-9_.-]+)["']""", source))
    built = (
        [f"report.limit.{n}" for n in range(1, 7)]
        + [f"report.legalShort.{state}" for state in LegalState]
        + [f"report.kind.{kind}" for kind in ObservationKind]
        + [f"pack.missing.{missing}" for missing in Missing]
        + [f"report.dataset.{dataset}" for dataset in DATASETS]
    )
    assert sorted((named | set(built)) - set(messages)) == []


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"layers": ["terrain-slope-missing"]}, "not layers of the detailed map"),
        ({"time_zone": "Europe/Atlantis"}, "is not a time zone"),
        ({"time_zones": {"Canarias": "Atlantic/Canary"}}, "is not an EPSG code"),
        ({"layers": ["potential-index", "potential-index"]}, "listed twice"),
    ],
)
def test_report_settings_refuse(change: dict[str, Any], message: str) -> None:
    from subphora.config import load_settings

    raw = load_settings().model_dump(mode="json")
    raw["report"] = {**raw["report"], **change}
    with pytest.raises(ValueError, match=message):
        Settings.model_validate(raw)
