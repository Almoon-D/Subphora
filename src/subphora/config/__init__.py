# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Settings: expert defaults in ``config/defaults/``, owner overrides in ``config/owner.yaml``.

Values live in YAML, mechanics in code. A key the schema does not declare is an error, so a
typo can never be silently ignored.
"""

from pathlib import Path
from typing import Any, Literal, Self

import yaml
from pydantic import model_validator

from subphora.config.base import Section
from subphora.config.depth import DrillingSettings, PiezometrySettings
from subphora.config.map import Legend, MapSettings
from subphora.config.model import BreaksLookup, ModelSettings
from subphora.config.national import NationalSettings
from subphora.config.parcel import ParcelSettings
from subphora.config.regional import RegionalSettings, qualification_failures
from subphora.config.search import SearchSettings
from subphora.config.server import ApiSettings, StoreSettings
from subphora.config.sources import Service, SourcesSettings, host_of
from subphora.config.validation import ValidationSettings
from subphora.domain.potential import Variable

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_DIR = REPO_ROOT / "config"

__all__ = [
    "CONFIG_DIR",
    "REPO_ROOT",
    "ApiSettings",
    "CoreSettings",
    "DrillingSettings",
    "MapSettings",
    "ModelSettings",
    "NationalSettings",
    "ParcelSettings",
    "PiezometrySettings",
    "RegionalSettings",
    "SearchSettings",
    "Section",
    "Settings",
    "SourcesSettings",
    "StoreSettings",
    "ValidationSettings",
    "load_settings",
]


class CoreSettings(Section):
    """``config/defaults/core.yaml``: replace with the project's first real section."""

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class Settings(Section):
    core: CoreSettings
    sources: SourcesSettings
    api: ApiSettings
    store: StoreSettings
    map: MapSettings
    regional: RegionalSettings
    search: SearchSettings
    model: ModelSettings
    national: NationalSettings
    parcel: ParcelSettings
    validation: ValidationSettings
    piezometry: PiezometrySettings
    drilling: DrillingSettings

    @model_validator(mode="after")
    def _validation_and_depth_consistent(self) -> Self:
        """The criteria left out of the validated index exist, and the piezometric levels
        (national and basin) are catalogued downloads, each read once."""
        ids = {c.id for c in self.model.criteria}
        unknown = sorted(set(self.validation.labels.excluded_criteria) - ids)
        if unknown:
            raise ValueError(f"validation.labels.excluded_criteria: {unknown} are not criteria")
        self._catalogued("piezometry.service", self.piezometry.service, "download")
        services = [self.piezometry.service]
        for index, basin in enumerate(self.piezometry.basins):
            self._catalogued(f"piezometry.basins[{index}].service", basin.service, "download")
            services.append(basin.service)
        if len(set(services)) != len(services):
            raise ValueError("piezometry: each source of levels is imported once")
        return self

    @model_validator(mode="after")
    def _map_layers_are_drawable(self) -> Self:
        """Each map layer is a catalogued layer, drawable as configured.

        The base maps and the cadastre are drawn by the browser from the service, so their
        services need EPSG:3857 and CORS. An overlay whose service lacks CORS is drawn by the
        API's proxy; one whose service lacks EPSG:3857 names an ArcGIS export of the same
        map service, which the proxy draws.
        """
        direct = [
            (f"map.base_maps.{base.id}", base.service, base.layer, "wmts")
            for base in self.map.base_maps
        ]
        direct.append(("map.cadastre", self.map.cadastre.service, self.map.cadastre.layer, "wms"))
        for key, service_id, layer, kind in direct:
            service = self._catalogued(key, service_id, kind, layer)
            if not (service.web_mercator and service.cors):
                raise ValueError(f"{key}: {service_id} needs EPSG:3857 and CORS to be drawn")
        for overlay in self.map.overlays.layers:
            key = f"map.overlays.{overlay.id}"
            service = self._catalogued(key, overlay.service, "wms", overlay.layer)
            if service.web_mercator and overlay.export is not None:
                raise ValueError(f"{key}: {service.id} offers EPSG:3857; no export is needed")
            if not service.web_mercator and not service.crs:
                raise ValueError(f"{key}: {service.id} lists no CRS to ask its features in")
            if not service.web_mercator:
                if overlay.export is None:
                    raise ValueError(f"{key}: {service.id} lacks EPSG:3857 and has no export")
                export = self._catalogued(key, overlay.export.service, "rest")
                if export.host != service.host:
                    raise ValueError(f"{key}: the export must be on {service.host}")
            self._check_legend(key, overlay.legend, service)
        return self

    @model_validator(mode="after")
    def _regional_layers_qualify(self) -> Self:
        """Every regional layer details a national theme, can be drawn, and qualifies under
        the rule of decision 0023 against that theme's national layer."""
        regional = self.regional
        for source in regional.boundaries.sources.values():
            self._catalogued("regional.boundaries", source.service, "wfs", source.type_name)
        themes = {overlay.id: overlay for overlay in self.map.overlays.layers}
        for layer in regional.layers:
            key = f"regional.layers.{layer.id}"
            national = themes.get(layer.theme)
            if national is None:
                raise ValueError(f"{key}: theme {layer.theme!r} is not a map overlay")
            if layer.id in themes:
                raise ValueError(f"{key}: its id is a map overlay's")
            service = self._catalogued(key, layer.service, "wms", layer.layer)
            if not service.web_mercator:
                raise ValueError(f"{key}: {service.id} lacks EPSG:3857")
            if max(layer.min_zoom, layer.max_zoom or 0) > self.map.overlays.max_zoom:
                raise ValueError(f"{key}: its zoom range reaches above the overlays' max_zoom")
            if national.detail.edition is not None and layer.evidence.national_edition is not None:
                raise ValueError(
                    f"{key}: {national.id} states its edition; national_edition is only for a "
                    "national layer published in parts"
                )
            for area_id in layer.areas:
                area = regional.area(area_id)
                if area.kind == "region" and area_id not in service.coverage:
                    raise ValueError(f"{key}: {service.id} does not cover {area_id}")
            self._check_legend(key, layer.legend, service)
            failures = qualification_failures(
                regional.rule, layer.theme, layer.evidence, national.detail
            )
            if failures:
                raise ValueError(f"{key} does not qualify: {'; '.join(failures)}")
        return self

    @model_validator(mode="after")
    def _search_services_catalogued(self) -> Self:
        self._catalogued("search.sigpac", self.search.sigpac.service, "rest")
        self._catalogued("search.cartociudad", self.search.cartociudad.service, "rest")
        return self

    @model_validator(mode="after")
    def _national_inputs_catalogued(self) -> Self:
        """Each nationwide input reads a catalogued service of the right kind, with the
        layers it asks for, and ages by a profile of model.yaml."""
        datasets = self.national.datasets
        kinds = {
            "permeability": "rest",
            "terrain": "wcs",
            "soil": "wcs",
            "groundwater_bodies": "wfs",
            "water_points": "rest",
        }
        for name, dataset in datasets.all().items():
            key = f"national.datasets.{name}"
            self._catalogued(key, dataset.service, kinds[name])
            if dataset.ageing not in self.model.confidence.ageing:
                raise ValueError(f"{key}: no ageing profile {dataset.ageing!r} in model.yaml")
        for grid in self.national.grids:
            key = f"national.grids.{grid.id}"
            self._catalogued(key, datasets.terrain.service, "wcs", grid.terrain.coverage)
            known = {territory.id for territory in self.search.territories}
            unknown = sorted(set(grid.territories) - known)
            if unknown:
                raise ValueError(f"{key}: {unknown} are not search.yaml territories")
        self._catalogued(
            "national.datasets.soil", datasets.soil.service, "wcs", datasets.soil.coverage
        )
        bodies = datasets.groundwater_bodies
        service = self._catalogued(
            "national.datasets.groundwater_bodies", bodies.service, "wfs", bodies.type_name
        )
        if bodies.srs not in service.crs:
            raise ValueError(
                f"national.datasets.groundwater_bodies: {service.id} lacks {bodies.srs}"
            )
        return self

    @model_validator(mode="after")
    def _parcel_inputs_consistent(self) -> Self:
        """The detailed map's inputs read catalogued services and age by profiles of
        model.yaml; every national grid has a 5 m coverage; its layers are national tile
        layers; and no distance it caps is read by a lookup beyond the cap."""
        parcel = self.parcel
        terrain = parcel.terrain
        for grid in self.national.grids:
            coverage = terrain.coverages.get(grid.id)
            if coverage is None:
                raise ValueError(f"parcel.terrain: no coverage for the {grid.id} grid")
            self._catalogued("parcel.terrain", terrain.service, "wcs", coverage.coverage)
        unknown_grids = sorted(set(terrain.coverages) - {g.id for g in self.national.grids})
        if unknown_grids:
            raise ValueError(f"parcel.terrain: {unknown_grids} are not national grids")
        for key, service, ageing in (
            ("parcel.terrain", terrain.service, terrain.ageing),
            ("parcel.faults", parcel.faults.service, parcel.faults.ageing),
            ("parcel.bedding", parcel.bedding.service, parcel.bedding.ageing),
        ):
            self._catalogued(key, service, "wcs" if key == "parcel.terrain" else "rest")
            if ageing not in self.model.confidence.ageing:
                raise ValueError(f"{key}: no ageing profile {ageing!r} in model.yaml")
        known = {layer.id for layer in self.national.tiles.layers}
        unknown = sorted(set(parcel.layers) - known)
        if unknown:
            raise ValueError(f"parcel.layers: {unknown} are not national tile layers")
        reaches = {
            Variable.DRAINAGE_DISTANCE_M: ("buffer_m", parcel.buffer_m),
            Variable.WATER_POINT_DISTANCE_M: (
                "water_points_radius_m",
                parcel.water_points_radius_m,
            ),
        }
        for criterion in self.model.criteria:
            reach = reaches.get(criterion.variable) if criterion.variable else None
            if (
                reach is not None
                and isinstance(criterion.lookup, BreaksLookup)
                and reach[1] < criterion.lookup.breaks[-1]
            ):
                raise ValueError(
                    f"parcel.{reach[0]} is below the last break of {criterion.id}'s lookup"
                )
        if parcel.water_points_radius_m < self.model.confidence.evidence_none_beyond_m:
            raise ValueError("parcel.water_points_radius_m is below evidence_none_beyond_m")
        return self

    @staticmethod
    def _check_legend(key: str, legend: Legend, service: Service) -> None:
        if legend.url is not None and host_of(legend.url) != service.host:
            raise ValueError(f"{key}: the legend must be on {service.host}")

    def _catalogued(
        self, key: str, service_id: str, kind: str, layer: str | None = None
    ) -> Service:
        try:
            service: Service = self.sources.service(service_id)
        except KeyError:
            raise ValueError(f"{key}: {service_id!r} is not in the catalogue") from None
        if service.kind != kind:
            raise ValueError(f"{key}: {service_id} is a {service.kind}, not a {kind}")
        if layer is not None and layer not in service.layers:
            raise ValueError(f"{key}: {service_id} does not list layer {layer!r}")
        return service


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _read(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} must hold a mapping")
    return data


def load_settings(config_dir: Path = CONFIG_DIR) -> Settings:
    """Every ``defaults/<section>.yaml`` under its file name, then ``owner.yaml`` on top."""
    raw: dict[str, Any] = {
        path.stem: _read(path) for path in sorted((config_dir / "defaults").glob("*.yaml"))
    }
    owner = config_dir / "owner.yaml"
    if owner.exists():
        raw = _merge(raw, _read(owner))
    return Settings.model_validate(raw)
