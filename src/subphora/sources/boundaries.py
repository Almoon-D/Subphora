# Copyright (c) 2026 Almoon-D. All rights reserved.
"""One area's official boundary from a national WFS (docs/knowledge/regional-layers.md).

Observed behaviour:
- The IGN's administrative units (``au:AdministrativeUnit``, deegree) and MITECO's
  river-basin districts (``agua:demarhidro_2027``, GeoServer) both take a WFS 2.0 standard
  filter on the area's code and answer GeoJSON in EPSG:4326, longitude first.
- The IGN answers full-detail geometry (Catalonia: 15 MB, 150,000 vertices); MITECO rounds
  to four decimals (ES060: 1.4 MB).
- A service that cannot answer still says HTTP 200, with an exception report in the body.
"""

import json
import re
from xml.sax.saxutils import escape

WGS84 = "EPSG:4326"


class BoundaryParseError(ValueError):
    """An answer that is not the boundary asked for."""


def boundary_params(
    type_name: str,
    code_property: str,
    code: str,
    namespaces: dict[str, str],
    output_format: str,
) -> dict[str, str]:
    """GetFeature of the features whose ``code_property`` equals ``code``, in EPSG:4326."""
    declarations = "".join(
        f' xmlns:{prefix}="{escape(uri)}"' for prefix, uri in sorted(namespaces.items())
    )
    fes = (
        f'<fes:Filter xmlns:fes="http://www.opengis.net/fes/2.0"{declarations}>'
        "<fes:PropertyIsEqualTo>"
        f"<fes:ValueReference>{escape(code_property)}</fes:ValueReference>"
        f"<fes:Literal>{escape(code)}</fes:Literal>"
        "</fes:PropertyIsEqualTo></fes:Filter>"
    )
    return {
        "SERVICE": "WFS",
        "VERSION": "2.0.0",
        "REQUEST": "GetFeature",
        "TYPENAMES": type_name,
        "OUTPUTFORMAT": output_format,
        "SRSNAME": WGS84,
        "FILTER": fes,
    }


def parse_boundary(content: bytes) -> list[object]:
    """The geometries of every feature of the answer; raises BoundaryParseError."""
    if content.lstrip().startswith(b"<"):
        raise BoundaryParseError(f"the service answered XML, not GeoJSON: {_xml_message(content)}")
    try:
        body = json.loads(content)
    except ValueError as exc:
        raise BoundaryParseError(f"not JSON: {exc}") from exc
    features = body.get("features") if isinstance(body, dict) else None
    if not isinstance(features, list):
        raise BoundaryParseError("not a GeoJSON FeatureCollection")
    if not features:
        raise BoundaryParseError("no feature has that code")
    geometries = [f.get("geometry") if isinstance(f, dict) else None for f in features]
    if any(geometry is None for geometry in geometries):
        raise BoundaryParseError("a feature without geometry")
    return geometries


def _xml_message(content: bytes) -> str:
    text = re.sub(rb"<[^>]+>", b" ", content).decode("utf-8", errors="replace")
    return " ".join(text.split())[:200]
