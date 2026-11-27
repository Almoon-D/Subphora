# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Settings: expert defaults in ``config/defaults/``, owner overrides in ``config/owner.yaml``.

Values live in YAML, mechanics in code. A key the schema does not declare is an error, so a
typo can never be silently ignored.
"""

from pathlib import Path
from typing import Any, Literal, Self

import yaml
from pydantic import model_validator

from subphora.config.auth import AuthSettings
from subphora.config.backup import BackupSettings
from subphora.config.base import Section
from subphora.config.depth import DrillingSettings, PiezometrySettings
from subphora.config.field import FieldSettings
from subphora.config.legal import LegalSettings
from subphora.config.map import Legend, MapSettings
from subphora.config.model import BreaksLookup, ModelSettings
from subphora.config.national import NationalSettings
from subphora.config.packs import PacksSettings
from subphora.config.parcel import ParcelSettings
from subphora.config.regional import RegionalSettings, qualification_failures
from subphora.config.report import ReportSettings
from subphora.config.search import SearchSettings
from subphora.config.section import SectionSettings
from subphora.config.server import ApiSettings, StoreSettings
from subphora.config.sources import Service, SourcesSettings, host_of
from subphora.config.validation import ValidationSettings
from subphora.config.wells import WellsSettings
from subphora.domain.potential import Variable

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_DIR = REPO_ROOT / "config"

__all__ = [
    "CONFIG_DIR",
    "REPO_ROOT",
    "ApiSettings",
    "AuthSettings",
    "BackupSettings",
    "CoreSettings",
    "DrillingSettings",
    "FieldSettings",
    "LegalSettings",
    "MapSettings",
    "ModelSettings",
    "NationalSettings",
    "PacksSettings",
    "ParcelSettings",
    "PiezometrySettings",
    "RegionalSettings",
    "ReportSettings",
    "SearchSettings",
    "Section",
    "SectionSettings",
    "Settings",
    "SourcesSettings",
    "StoreSettings",
    "ValidationSettings",
    "WellsSettings",
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
    section: SectionSettings
    legal: LegalSettings
    field: FieldSettings
    packs: PacksSettings
    report: ReportSettings
    auth: AuthSettings
    backup: BackupSettings
    wells: WellsSettings

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
    def _wells_layer_drawable(self) -> Self:
        """The layer updated with the owner's wells takes the legend of a national tile
        layer of the index, and its id is no other detailed-map layer's."""
        update = self.wells.update
        layers = {layer.id: layer for layer in self.national.tiles.layers}
        legend = layers.get(update.legend_layer)
        if legend is None or legend.variable is not Variable.INDEX:
            raise ValueError("wells.update.legend_layer: not a national tile layer of the index")
        if update.layer_id in layers or update.layer_id in self.parcel.layers:
            raise ValueError("wells.update.layer_id: already another layer's id")
        return self

    @model_validator(mode="after")
    def _section_inputs_consistent(self) -> Self:
        """The section's lithology is a catalogued REST layer with a defined ageing profile."""
        lithology = self.section.lithology
        self._catalogued("section.lithology", lithology.service, "rest")
        if lithology.ageing not in self.model.confidence.ageing:
            raise ValueError(f"section.lithology: no ageing profile {lithology.ageing!r}")
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
    def _legal_layers_answer(self) -> Self:
        """Every layer the legal filter reads is a map overlay or a regional layer with
        feature info, and every field it reads is one that layer's answer keeps."""
        legal = self.legal
        bodies = legal.bodies
        reads = [
            ("legal.bodies", bodies.status_layer, bodies.code_field),
            ("legal.bodies", bodies.status_layer, bodies.name_field),
            ("legal.bodies", bodies.status_layer, bodies.quantitative_field),
            ("legal.bodies", bodies.at_risk_layer, bodies.at_risk_code_field),
            ("legal.bodies", bodies.at_risk_layer, bodies.declaration_field),
        ]
        reads += [(f"legal.rules.{rule}", m.layer, m.field) for rule, m in legal.layer_matches()]
        for rule in legal.rules:
            if rule.kind == "zone":
                reads.append((f"legal.rules.{rule.id}", rule.match.layer, rule.label_field))
        overlays = {overlay.id: overlay.info for overlay in self.map.overlays.layers}
        regional = {layer.id: layer.info for layer in self.regional.layers}
        for key, layer_id, field in reads:
            if layer_id not in overlays and layer_id not in regional:
                raise ValueError(f"{key}: {layer_id!r} is not a map or regional layer")
            info = overlays.get(layer_id) or regional.get(layer_id)
            if info is None:
                raise ValueError(f"{key}: {layer_id} answers no feature info")
            if field not in info.fields:
                raise ValueError(f"{key}: {layer_id}'s answer does not keep {field!r}")
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
            "vegetation": "rest",
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
        vegetation = datasets.vegetation
        self._catalogued("national.datasets.vegetation", vegetation.pixels_service, "download")
        self._catalogued(
            "national.datasets.vegetation.irrigation", vegetation.irrigation.service, "rest"
        )
        self._catalogued(
            "national.context.ground_motion",
            self.national.context.ground_motion.service,
            "download",
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

    @model_validator(mode="after")
    def _packs_carry_only_storable(self) -> Self:
        """A pack carries only base maps whose service's terms allow storing them (hard
        rule 4), and national tile layers that the detailed map also draws."""
        bases = {base.id: base for base in self.map.base_maps}
        for base in self.packs.base_maps:
            key = f"packs.base_maps.{base.id}"
            if base.id not in bases:
                raise ValueError(f"{key}: not a map base map")
            service = self.sources.service(bases[base.id].service)
            if service.offline != "allowed":
                raise ValueError(f"{key}: {service.id}'s terms do not allow storing it")
        known = {layer.id for layer in self.national.tiles.layers}
        unknown = sorted(set(self.packs.layers) - known)
        if unknown:
            raise ValueError(f"packs.layers: {unknown} are not national tile layers")
        undrawn = sorted(set(self.packs.layers) - set(self.parcel.layers))
        if undrawn:
            raise ValueError(f"packs.layers: {undrawn} are not drawn by the detailed map")
        return self

    @model_validator(mode="after")
    def _report_layers_drawn(self) -> Self:
        unknown = sorted(set(self.report.layers) - set(self.parcel.layers))
        if unknown:
            raise ValueError(f"report.layers: {unknown} are not layers of the detailed map")
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
    legal = raw.get("legal")
    if isinstance(legal, dict) and isinstance(legal.get("country"), str):
        raw["legal"] = {**legal, **_legal_rules(config_dir / "legal" / legal["country"])}
    return Settings.model_validate(raw)


def _legal_rules(folder: Path) -> dict[str, Any]:
    """``areas.yaml`` and the rules of every other file of a country's legal folder; each
    rule file holds the rules of the one area its name gives (``es-an.yaml``: ES-AN)."""
    rules: list[Any] = []
    for path in sorted(folder.glob("*.yaml")):
        if path.name == "areas.yaml":
            continue
        content = _read(path)
        area = path.stem.upper()
        listed = content.get("rules") if isinstance(content, dict) else None
        if not isinstance(listed, list):
            raise ValueError(f"{path.name}: a rule file holds a list under 'rules'")
        for rule in listed:
            if isinstance(rule, dict) and rule.get("area") != area:
                raise ValueError(f"{path.name}: rule {rule.get('id')!r} is not keyed {area}")
        rules.extend(listed)
    return {"areas": _read(folder / "areas.yaml"), "rules": rules}
