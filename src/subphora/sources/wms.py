# Copyright (c) 2026 Almoon-D. All rights reserved.
"""WMS and ArcGIS map requests, and the parsers of the feature information they answer.

Observed behaviour (docs/knowledge/igme.md, miteco-basins.md, junta-andalucia.md, soil.md):
- GeoServer (MITECO) answers GetFeatureInfo as GeoJSON (``application/json``), its fields
  named by readable aliases; ArcGIS (IGME) as GeoJSON (``application/geo+json``, MAGNA and
  the water points) or its own XML (``text/xml``: ``FIELDS`` elements whose attributes are
  the fields).
- A service that cannot answer still says HTTP 200, with an exception report in the body:
  the body decides.
- WMS 1.3.0 takes BBOX in the CRS's own axis order (latitude first for EPSG:4326 and 4258).
"""

import json
import xml.etree.ElementTree as ET
from collections.abc import Sequence
from typing import Literal

type InfoParser = Literal["geojson", "esri_xml"]
type Box = tuple[float, float, float, float]
type Attributes = dict[str, str]

WEB_MERCATOR = "EPSG:3857"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_EXCEPTION_ROOTS = frozenset({"ServiceExceptionReport", "ExceptionReport"})


class FeatureInfoError(ValueError):
    """An answer that is not the feature information the parser expects."""


def _bbox(box: Box) -> str:
    return ",".join(f"{value:.6f}" for value in box)


def export_params(layers: str, size_px: int, box: Box) -> dict[str, str]:
    """The ArcGIS REST export of ``box`` (EPSG:3857 metres) as a transparent PNG."""
    return {
        "bbox": _bbox(box),
        "bboxSR": "3857",
        "imageSR": "3857",
        "size": f"{size_px},{size_px}",
        "format": "png32",
        "transparent": "true",
        "layers": layers,
        "f": "image",
    }


def feature_info_params(
    layer: str,
    style: str,
    crs: str,
    box: Box,
    size_px: int,
    info_format: str,
    feature_count: int,
) -> dict[str, str]:
    """GetFeatureInfo at the centre pixel of a ``size_px`` image of ``box``.

    ``box`` is in ``crs``'s own axis order, as WMS 1.3.0 wants it.
    """
    centre = str(size_px // 2)
    return {
        "SERVICE": "WMS",
        "VERSION": "1.3.0",
        "REQUEST": "GetFeatureInfo",
        "LAYERS": layer,
        "QUERY_LAYERS": layer,
        "STYLES": style,
        "CRS": crs,
        "BBOX": _bbox(box),
        "WIDTH": str(size_px),
        "HEIGHT": str(size_px),
        "I": centre,
        "J": centre,
        "INFO_FORMAT": info_format,
        "FEATURE_COUNT": str(feature_count),
    }


def legend_params(layer: str, style: str) -> dict[str, str]:
    """GetLegendGraphic; MapServer requires SLD_VERSION in WMS 1.3.0, the others ignore it."""
    params = {
        "SERVICE": "WMS",
        "VERSION": "1.3.0",
        "REQUEST": "GetLegendGraphic",
        "FORMAT": "image/png",
        "LAYER": layer,
        "SLD_VERSION": "1.1.0",
    }
    if style:
        params["STYLE"] = style
    return params


def is_png(content: bytes) -> bool:
    return content.startswith(PNG_SIGNATURE)


def parse_feature_info(content: bytes, parser: InfoParser) -> list[Attributes]:
    """Every feature's fields as text; raises FeatureInfoError for anything else."""
    match parser:
        case "geojson":
            return _parse_geojson(content)
        case "esri_xml":
            return [
                dict(element.attrib) for element in _xml(content) if _local(element.tag) == "FIELDS"
            ]


def allowed_fields(
    features: Sequence[Attributes], fields: Sequence[str]
) -> list[list[tuple[str, str]]]:
    """Each feature reduced to ``fields``, in that order; a feature with none is dropped."""
    kept = []
    for feature in features:
        values = [(name, feature[name].strip()) for name in fields if feature.get(name) is not None]
        if values:
            kept.append(values)
    return kept


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _xml(content: bytes) -> ET.Element:
    try:
        root = ET.fromstring(content)
    except ET.ParseError as exc:
        raise FeatureInfoError(f"not XML: {exc}") from exc
    if _local(root.tag) in _EXCEPTION_ROOTS:
        message = " ".join(" ".join(root.itertext()).split())
        raise FeatureInfoError(f"the service refused: {message[:200]}")
    return root


def _parse_geojson(content: bytes) -> list[Attributes]:
    if content.lstrip().startswith(b"<"):
        _xml(content)  # an exception report raises here
        raise FeatureInfoError("XML where GeoJSON was expected")
    try:
        body = json.loads(content)
    except ValueError as exc:
        raise FeatureInfoError(f"not JSON: {exc}") from exc
    features = body.get("features") if isinstance(body, dict) else None
    if not isinstance(features, list):
        raise FeatureInfoError("not a GeoJSON FeatureCollection")
    parsed = []
    for feature in features:
        properties = feature.get("properties") if isinstance(feature, dict) else None
        if not isinstance(properties, dict):
            raise FeatureInfoError("a feature without properties")
        parsed.append(
            {
                str(k): str(v)
                for k, v in properties.items()
                if v is not None and not isinstance(v, dict | list)
            }
        )
    return parsed
