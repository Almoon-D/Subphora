# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Schema of ``config/defaults/map.yaml``: the view and the layers the front end draws.

Whether each layer's service can be drawn as configured (catalogued, offering the layer,
with CORS and EPSG:3857 or a proxy route) is checked against the source catalogue by
``Settings``.
"""

from typing import Literal, Self

from pydantic import Field, PositiveInt, model_validator

from subphora.config.base import Section
from subphora.config.sources import host_of

_ZOOM = Field(ge=0, le=24)
_OPACITY = Field(ge=0, le=1)


class InitialView(Section):
    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-85, le=85)
    zoom: float = _ZOOM


class BaseMap(Section):
    """A WMTS tile layer in a Web Mercator tile matrix set."""

    id: str = Field(min_length=1)
    service: str
    layer: str
    format: str
    tile_matrix_set: str
    tile_size: PositiveInt
    max_zoom: int = _ZOOM


class CadastreLayer(Section):
    """A WMS layer drawn as one untiled image per view."""

    service: str
    layer: str
    style: str
    format: str
    min_zoom: float = _ZOOM
    refresh_delay_ms: int = Field(ge=0)
    max_image_px: PositiveInt
    visible: bool
    opacity: float = _OPACITY


class Legend(Section):
    """``wms``: the service's GetLegendGraphic; ``url``: an image the capabilities name;
    ``none``: the service has no legend a person can read."""

    kind: Literal["wms", "url", "none"]
    url: str | None = None

    @model_validator(mode="after")
    def _url_for_url_kind(self) -> Self:
        if (self.kind == "url") != (self.url is not None):
            raise ValueError("a legend has a url exactly when its kind is url")
        if self.url is not None:
            host_of(self.url)
        return self


class ArcgisExport(Section):
    """The ArcGIS REST export of a map service, drawn in EPSG:3857 by the proxy."""

    # A catalogued ``rest`` service, and the path of the map service's export under it.
    service: str
    path: str = Field(pattern=r"^/.+/MapServer/export$")
    # The export's ``layers`` parameter, e.g. ``show:0``.
    layers: str = Field(min_length=1)


class FeatureInfo(Section):
    """How a tap reads the features of a layer, and which of their fields are shown."""

    info_format: str = Field(min_length=1)
    # geojson: a GeoJSON FeatureCollection; esri_xml: ArcGIS's FeatureInfoResponse.
    parser: Literal["geojson", "esri_xml"]
    # The only fields shown, by the names the service gives them, in this order.
    fields: list[str] = Field(min_length=1)


class Overlay(Section):
    """An official WMS layer, drawn as tiles directly or through the API's proxy."""

    id: str = Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")
    group: str
    service: str
    layer: str
    style: str = ""
    opacity: float = _OPACITY
    min_zoom: int = _ZOOM
    legend: Legend
    info: FeatureInfo | None
    export: ArcgisExport | None = None


class Overlays(Section):
    groups: list[str] = Field(min_length=1)
    tile_size: PositiveInt
    max_zoom: int = _ZOOM
    info_image_px: int = Field(ge=3, le=255)
    info_feature_count: PositiveInt
    visible_at_start: list[str]
    layers: list[Overlay] = Field(min_length=1)

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        ids = [layer.id for layer in self.layers]
        duplicates = sorted({i for i in ids if ids.count(i) > 1})
        if duplicates:
            raise ValueError(f"duplicate overlay ids: {duplicates}")
        for layer in self.layers:
            if layer.group not in self.groups:
                raise ValueError(f"overlay {layer.id}: group {layer.group!r} is not in groups")
            if layer.min_zoom > self.max_zoom:
                raise ValueError(f"overlay {layer.id}: min_zoom is above max_zoom")
        unknown = sorted(set(self.visible_at_start) - set(ids))
        if unknown:
            raise ValueError(f"visible_at_start names unknown overlays: {unknown}")
        return self

    def layer(self, layer_id: str) -> Overlay:
        for layer in self.layers:
            if layer.id == layer_id:
                return layer
        raise KeyError(layer_id)


class MapSettings(Section):
    initial_view: InitialView
    parcel_padding_px: int = Field(ge=0)
    # The first is shown when the map opens.
    base_maps: list[BaseMap] = Field(min_length=1)
    cadastre: CadastreLayer
    overlays: Overlays

    @model_validator(mode="after")
    def _unique_base_ids(self) -> Self:
        ids = [base.id for base in self.base_maps]
        if len(set(ids)) != len(ids):
            raise ValueError("base map ids must be unique")
        return self
