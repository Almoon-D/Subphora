# Copyright (c) 2026 Almoon-D. All rights reserved.
"""A synthetic Spain for the national build: every nationwide service behind one
httpx.MockTransport, answering any window with made-up but well-formed data.

- IGN MDT WCS: a GeoTIFF of the requested window at the coverage's cell (25 m or 5 m), a
  valley running north-south whose floor falls to the south.
- SoilGrids WCS: 25 % clay everywhere.
- IGME permeability: one polygon over the whole window, class ALTA, in two pages.
- IGME water points: two springs and a surface stream at the window's centre, none with a
  recorded yield; with ``wells``, also a productive borehole every ``wells`` metres along
  the valley floor and a borehole without a recorded yield beside each.
- MITECO groundwater bodies: one body over the window's west half (all of it with
  ``whole_body``), status Malo.
- IGN administrative units: a small square around a point in Madrid.
- IGME MAGNA faults: a fault running north-south through the window's centre and a
  contact (not a fault) running east-west.
- IGME MAGNA structural measurements: a bedding dip of 20° toward the east at the box's
  centre and a cleavage (not bedding) beside it; none at all when ``bedding`` is false.
- IGME MAGNA lithology: limestone west of 500 m before the box's centre, marl from there
  to the centre (where the fault runs) and sandstone east of it; none when ``lithology``
  is false.
- The borehole of the water points (300 m east of the centre) went 120 m deep.
"""

import io
import json
import re
from collections.abc import Callable
from typing import Any
from urllib.parse import parse_qs

import httpx
import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.transform import from_origin

from subphora.config import Settings
from tests.support import fast_settings

type Handler = Callable[[httpx.Request], httpx.Response]

# The valley floor of the synthetic terrain: a north-south line at this easting.
_VALLEY_CRS = "EPSG:25830"
_VALLEY_X = 440_000.0
# A small area in Madrid (degrees), the boundary of the synthetic province.
MADRID = (-3.71, 40.41, -3.69, 40.43)
_NUMBER = r"(-?\d+(?:\.\d+)?)"


def terrain_elevation(xs: Any, ys: Any) -> Any:
    """The synthetic terrain (EPSG:25830): a valley at ``_VALLEY_X`` falling to the south."""
    return 600 + np.abs(xs - _VALLEY_X) * 0.05 + (ys - 4_470_000) * 0.01


def small_settings() -> Settings:
    """The real configuration with no waiting, a 1 km buffer and tiles up to zoom 9."""
    settings = fast_settings()
    national = settings.national.model_copy(
        update={
            "buffer_m": 1000.0,
            "tiles": settings.national.tiles.model_copy(update={"max_zoom": 9}),
        }
    )
    return settings.model_copy(update={"national": national})


def geotiff(
    bounds: tuple[float, float, float, float],
    crs: str,
    cell: float,
    fill: Callable[[np.ndarray, np.ndarray], np.ndarray],
    dtype: str,
) -> bytes:
    west, south, east, north = bounds
    width = max(1, round((east - west) / cell))
    height = max(1, round((north - south) / cell))
    columns, rows = np.meshgrid(np.arange(width), np.arange(height))
    xs = west + (columns + 0.5) * cell
    ys = north - (rows + 0.5) * cell
    data = fill(xs, ys).astype(dtype)
    buffer = io.BytesIO()
    with rasterio.open(
        buffer,
        "w",
        driver="GTiff",
        width=width,
        height=height,
        count=1,
        dtype=dtype,
        crs=crs,
        transform=from_origin(west, north, cell, cell),
    ) as dataset:
        dataset.write(data, 1)
    return buffer.getvalue()


def _subsets(request: httpx.Request, first: str, second: str) -> tuple[float, ...]:
    values = parse_qs(request.url.query.decode(), keep_blank_values=True)
    subsets = values.get("subset", []) + values.get("SUBSET", [])
    found: dict[str, tuple[float, float]] = {}
    for subset in subsets:
        match = re.match(rf"(\w+)\({_NUMBER},{_NUMBER}\)", subset)
        if match:
            found[match.group(1)] = (float(match.group(2)), float(match.group(3)))
    return (found[first][0], found[second][0], found[first][1], found[second][1])


def _box(request: httpx.Request, name: str) -> tuple[float, float, float, float]:
    raw = request.url.params[name].split(",")
    west, south, east, north = (float(v) for v in raw[:4])
    return (west, south, east, north)


def _feature(geometry: dict[str, Any], **properties: Any) -> dict[str, Any]:
    return {"type": "Feature", "geometry": geometry, "properties": properties}


def _square(west: float, south: float, east: float, north: float) -> dict[str, Any]:
    ring = [[west, south], [east, south], [east, north], [west, north], [west, south]]
    return {"type": "Polygon", "coordinates": [ring]}


def _collection(features: list[dict[str, Any]], **extra: Any) -> httpx.Response:
    return httpx.Response(200, json={"type": "FeatureCollection", "features": features, **extra})


class FakeSpain:
    """Answers every nationwide service; ``fail`` maps a host to a status to answer."""

    def __init__(
        self,
        fail: dict[str, int] | None = None,
        *,
        bedding: bool = True,
        lithology: bool = True,
        timeout: frozenset[str] = frozenset(),
        wells: float | None = None,
        whole_body: bool = False,
    ) -> None:
        self.fail = fail or {}
        self.bedding = bedding
        self.lithology = lithology
        self.wells = wells
        self.whole_body = whole_body
        # Hosts whose every request times out.
        self.timeout = timeout
        self.requests: list[httpx.Request] = []

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self._handle)

    def _handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        host = request.url.host
        if host in self.timeout:
            raise httpx.ReadTimeout("synthetic timeout", request=request)
        if host in self.fail:
            return httpx.Response(self.fail[host], content=b"<error/>")
        path = request.url.path
        if host == "servicios.idee.es":
            return self._terrain(request)
        if host == "maps.isric.org":
            box = _subsets(request, "long", "lat")
            content = geotiff(box, "EPSG:4326", 0.002, lambda x, _y: np.full(x.shape, 250), "int16")
            return httpx.Response(200, content=content, headers={"content-type": "image/tiff"})
        if host == "mapas.igme.es" and "Permeabilidad" in path:
            return self._permeability(request)
        if host == "mapas.igme.es" and "PuntosAgua" in path:
            return self._water_points(request)
        if host == "mapas.igme.es" and path.endswith("IGME_MAGNA_50/MapServer/9/query"):
            return self._faults(request)
        if host == "mapas.igme.es" and path.endswith("IGME_MAGNA_50/MapServer/5/query"):
            return self._bedding(request)
        if host == "mapas.igme.es" and path.endswith("IGME_MAGNA_50/MapServer/11/query"):
            return self._lithology(request)
        if host == "gis.miteco.gob.es" and request.url.params.get("REQUEST") == "GetFeatureInfo":
            return self._feature_info(request)
        if host == "gis.miteco.gob.es":
            return self._bodies(request)
        if host == "www.ign.es":
            return _collection([_feature(_square(*MADRID), nationalCode="34132800000")])
        return httpx.Response(404)

    @staticmethod
    def _terrain(request: httpx.Request) -> httpx.Response:
        box = _subsets(request, "x", "y")
        coverage = request.url.params["CoverageId"]
        crs = f"EPSG:{coverage.removeprefix('Elevacion').split('_')[0]}"
        cell = float(coverage.split("_")[1])
        content = geotiff(box, crs, cell, terrain_elevation, "int16")
        return httpx.Response(200, content=content, headers={"content-type": "image/tiff"})

    @staticmethod
    def _permeability(request: httpx.Request) -> httpx.Response:
        west, south, east, north = _box(request, "geometry")
        offset = int(request.url.params["resultOffset"])
        if offset == 0:
            feature = _feature(
                _square(west, south, east, north), PERME="ALTA", DCO="CARBONATADAS-ALTA"
            )
            return _collection([feature], exceededTransferLimit=True)
        blank = _feature(
            _square(west, south, west + 100, south + 100), PERME=" ", DCO="Masa de agua superficial"
        )
        return _collection([blank])

    def _water_points(self, request: httpx.Request) -> httpx.Response:
        west, south, east, north = _box(request, "geometry")
        x, y = (west + east) / 2, (south + north) / 2

        def point(px: float, py: float, kind: str, **extra: Any) -> dict[str, Any]:
            return _feature({"type": "Point", "coordinates": [px, py]}, Naturaleza=kind, **extra)

        points = [
            point(x, y, "Manantial"),
            point(x + 300, y, "Sondeo", PROF_m=120.0, COTA_msnm=0.0),
            point(x - 3000, y, "Cauce superficial"),
        ]
        if self.wells:
            crs = f"EPSG:{request.url.params['outSR']}"
            to_grid = Transformer.from_crs(_VALLEY_CRS, crs, always_xy=True)
            to_valley = Transformer.from_crs(crs, _VALLEY_CRS, always_xy=True)
            _, low = to_valley.transform(x, south)
            _, high = to_valley.transform(x, north)
            for northing in np.arange(low, high, self.wells):
                px, py = to_grid.transform(_VALLEY_X, float(northing))
                points.append(point(px, py, "Sondeo", Caudal_Referencia_L_s=2.5))
                qx, qy = to_grid.transform(_VALLEY_X + 2500, float(northing))
                points.append(point(qx, qy, "Pozo", Caudal_Referencia_L_s=0.0))
        return _collection(points, exceededTransferLimit=False)

    @staticmethod
    def _faults(request: httpx.Request) -> httpx.Response:
        west, south, east, north = _box(request, "geometry")
        x, y = (west + east) / 2, (south + north) / 2
        fault = _feature(
            {"type": "LineString", "coordinates": [[x, south], [x, north]]}, TIPO="Falla conocida"
        )
        contact = _feature(
            {"type": "MultiLineString", "coordinates": [[[west, y], [east, y]]]},
            TIPO="Contacto concordante",
        )
        return _collection([fault, contact])

    def _bedding(self, request: httpx.Request) -> httpx.Response:
        if not self.bedding:
            return _collection([])
        west, south, east, north = _box(request, "geometry")
        x, y = (west + east) / 2, (south + north) / 2

        def measurement(dx: float, kind: str, dip: int) -> dict[str, Any]:
            line = {"type": "LineString", "coordinates": [[x + dx - 10, y], [x + dx + 10, y]]}
            return _feature(line, NOMBRE=kind, DIRECCION=90, BUZAMIENTO=dip)

        return _collection(
            [measurement(0, "Estratificación", 20), measurement(30, "Primera esquistosidad", 80)]
        )

    def _lithology(self, request: httpx.Request) -> httpx.Response:
        if not self.lithology:
            return _collection([])
        west, south, east, north = _box(request, "geometry")
        x = (west + east) / 2
        return _collection(
            [
                _feature(_square(west, south, x - 500, north), DLO="Calizas"),
                _feature(_square(x - 500, south, x, north), DLO="Margas"),
                _feature(_square(x, south, east, north), DLO="Areniscas"),
            ]
        )

    @staticmethod
    def _feature_info(request: httpx.Request) -> httpx.Response:
        """A tap on MITECO's layers: the synthetic body, in poor quantitative status and
        not declared at risk, everywhere; no public water domain."""
        layer = request.url.params["LAYERS"]
        features = []
        if layer == "estado_masas_aguasub_2027":
            features.append(
                {
                    "type": "Feature",
                    "geometry": None,
                    "properties": {
                        "Cód. Masa de agua": "ES030MSBT000",
                        "Nombre masa de agua": "Synthetic body",
                        "Estado cuantitativo": "Malo",
                    },
                }
            )
        return httpx.Response(200, json={"type": "FeatureCollection", "features": features})

    def _bodies(self, request: httpx.Request) -> httpx.Response:
        raw = request.url.params["bbox"].split(",")
        west, south, east, north = (float(v) for v in raw[:4])
        body = _feature(
            _square(west, south, east if self.whole_body else (west + east) / 2, north),
            cod_masa="ES030MSBT000",
            nom_masa="Synthetic body",
            est_cu_desc="Malo",
        )
        return httpx.Response(
            200,
            content=json.dumps(
                {"type": "FeatureCollection", "features": [body], "numberMatched": 1}
            ).encode(),
        )
