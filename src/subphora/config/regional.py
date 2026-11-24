# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Schema of ``config/defaults/regional.yaml``: regional detail over the national layers.

Decision 0023: where a region, province or basin authority publishes a more detailed
official service for a map theme, the map uses it inside that authority's area; the
national layer stays the baseline everywhere and the fallback. The rule a regional layer
must meet is data here (``rule``); ``qualification_failures`` applies it, and the settings
refuse a regional layer that fails it, so no layer reaches the map without its evidence.
"""

import re
from typing import Literal, Self

from pydantic import Field, PositiveFloat, model_validator

from subphora.config.base import Section
from subphora.config.map import FeatureInfo, Legend
from subphora.domain.layers import LayerDetail

_ID = r"^[a-z0-9]+(-[a-z0-9]+)*$"
# An ISO 3166-2 region (ES-NC) or a river-basin district code (ES060).
_AREA = re.compile(r"^ES-[A-Z]{2}$|^ES\d{3}$")


class QualificationRule(Section):
    """The rule of decision 0023, the same for every region."""

    # Only a public body's own service qualifies.
    official_only: bool
    # How many years older than the national edition a regional one may be: 0 is "at least
    # as recent". A national layer whose edition is not stated cannot be shown to be older.
    max_years_older: int = Field(ge=0)
    # A map at 1:N resolves about N times this many metres on the ground (0.5 mm on the
    # sheet), which compares a scale with a grid cell.
    metres_per_scale_unit: PositiveFloat
    # Finer: the regional ground resolution is below this fraction of the national one.
    finer_than_ratio: PositiveFloat = Field(le=1)
    # Themes whose answer is a legal status: only the competent authority's layer counts.
    legal_themes: list[str]


class BoundarySource(Section):
    """A national WFS that serves one area's boundary by its code."""

    service: str
    type_name: str = Field(min_length=1)
    # The property that holds the area's code, and the namespaces its prefix needs.
    code_property: str = Field(min_length=1)
    namespaces: dict[str, str] = Field(default_factory=dict)
    output_format: str = Field(min_length=1)


class Boundaries(Section):
    # Every vertex is rounded to this grid (degrees): shared borders stay shared.
    grid_deg: PositiveFloat = Field(lt=1)
    sources: dict[Literal["region", "district"], BoundarySource]


class Area(Section):
    id: str
    kind: Literal["region", "district"]
    # The area's code in its boundary service.
    code: str = Field(min_length=1)
    # West, south, east, north in EPSG:4326, enclosing the official boundary: tiles and
    # taps outside it never fetch the boundary. A boundary found outside it is an error.
    bbox: tuple[float, float, float, float]

    @model_validator(mode="after")
    def _valid(self) -> Self:
        if not _AREA.match(self.id):
            raise ValueError(f"area {self.id!r} is not an ISO 3166-2 region or a district code")
        west, south, east, north = self.bbox
        if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
            raise ValueError(f"area {self.id}: bbox must be west, south, east, north")
        return self


class Evidence(Section):
    """What the survey (docs/knowledge/regional-layers.md) found about the regional layer."""

    official: bool
    detail: LayerDetail
    # What it holds that the national layer does not; None when it is only finer.
    adds: str | None = None
    # A clip of the national layer (the same data inside the area) never qualifies.
    clip_of_national: bool
    # Whether its publisher is the competent authority for the theme in its areas.
    competent_authority: bool
    # The national layer's edition inside this layer's areas, for a national layer that
    # states no single edition because it is published in parts, each with its own (GEODE's
    # zones): the newest part over the areas, from the publisher's metadata. None otherwise.
    national_edition: int | None = Field(default=None, ge=1900, le=2100)


class RegionalLayer(Section):
    id: str = Field(pattern=_ID)
    # The national overlay (map.yaml) this layer details: the panel entry it belongs to.
    theme: str
    areas: list[str] = Field(min_length=1)
    service: str
    layer: str
    style: str = ""
    min_zoom: int = Field(ge=0, le=24)
    # The deepest zoom its service draws (a scale range that stops short of the overlays'
    # max_zoom); the browser enlarges that level's tiles beyond it. None: the overlays'.
    max_zoom: int | None = Field(default=None, ge=0, le=24)
    legend: Legend
    info: FeatureInfo | None
    evidence: Evidence

    @model_validator(mode="after")
    def _zoom_range(self) -> Self:
        if self.max_zoom is not None and self.max_zoom < self.min_zoom:
            raise ValueError(f"regional layer {self.id}: max_zoom is below min_zoom")
        return self


class RegionalSettings(Section):
    rule: QualificationRule
    boundaries: Boundaries
    areas: list[Area]
    layers: list[RegionalLayer]

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        area_ids = [area.id for area in self.areas]
        layer_ids = [layer.id for layer in self.layers]
        for kind, ids in (("area", area_ids), ("regional layer", layer_ids)):
            duplicates = sorted({i for i in ids if ids.count(i) > 1})
            if duplicates:
                raise ValueError(f"duplicate {kind} ids: {duplicates}")
        for area in self.areas:
            if area.kind not in self.boundaries.sources:
                raise ValueError(f"area {area.id}: no boundary source for kind {area.kind}")
        for layer in self.layers:
            unknown = sorted(set(layer.areas) - set(area_ids))
            if unknown:
                raise ValueError(f"regional layer {layer.id}: unknown areas {unknown}")
        return self

    def area(self, area_id: str) -> Area:
        for area in self.areas:
            if area.id == area_id:
                return area
        raise KeyError(area_id)

    def of_theme(self, theme: str) -> list[RegionalLayer]:
        return [layer for layer in self.layers if layer.theme == theme]

    def layer(self, layer_id: str) -> RegionalLayer:
        for layer in self.layers:
            if layer.id == layer_id:
                return layer
        raise KeyError(layer_id)


def ground_resolution_m(detail: LayerDetail, rule: QualificationRule) -> float | None:
    """The metres on the ground a layer resolves, from its scale or grid cell."""
    if detail.cell_m is not None:
        return detail.cell_m
    if detail.scale_denominator is not None:
        return detail.scale_denominator * rule.metres_per_scale_unit
    return None


def qualification_failures(
    rule: QualificationRule,
    theme: str,
    evidence: Evidence,
    national: LayerDetail,
) -> list[str]:
    """Why the regional layer does not qualify over the national one; empty if it does."""
    failures: list[str] = []
    if rule.official_only and not evidence.official:
        failures.append("it is not an official service")
    if evidence.clip_of_national:
        failures.append("it is a clip of the national layer")
    if theme in rule.legal_themes and not evidence.competent_authority:
        failures.append("its publisher is not the competent authority for this legal status")
    regional_year = evidence.detail.edition
    national_year = national.edition if national.edition is not None else evidence.national_edition
    if regional_year is None:
        failures.append("its edition is not stated")
    elif national_year is None:
        failures.append("the national edition is not stated, so it cannot be shown as recent")
    elif regional_year < national_year - rule.max_years_older:
        failures.append(f"its edition {regional_year} is older than the national {national_year}")
    regional_m = ground_resolution_m(evidence.detail, rule)
    national_m = ground_resolution_m(national, rule)
    finer = (
        regional_m is not None
        and national_m is not None
        and regional_m < national_m * rule.finer_than_ratio
    )
    if not finer and not evidence.adds:
        failures.append("it is neither finer than the national layer nor richer in attributes")
    return failures


__all__ = [
    "Area",
    "Boundaries",
    "BoundarySource",
    "Evidence",
    "QualificationRule",
    "RegionalLayer",
    "RegionalSettings",
    "ground_resolution_m",
    "qualification_failures",
]
