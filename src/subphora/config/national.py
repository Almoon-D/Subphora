# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Schema of ``config/defaults/national.yaml``: the national grids, the nationwide inputs
the batch build downloads, and the map layers it publishes as tiles (MASTER_PLAN §4.3).

Whether each dataset's service is catalogued, and each ageing profile defined, is checked
against the other sections by ``Settings``.
"""

import re
from datetime import date
from itertools import pairwise
from pathlib import Path
from typing import Self

from pydantic import Field, PositiveFloat, PositiveInt, model_validator

from subphora.config.base import Section
from subphora.domain.layers import LayerDetail
from subphora.domain.potential import CATEGORICAL, Variable

_ID = r"^[a-z0-9]+(-[a-z0-9]+)*$"
_EPSG = r"^EPSG:\d+$"
_REGION = re.compile(r"^[A-Z]{2}-[A-Z0-9]{1,3}$")
_COLOUR = r"^#[0-9a-f]{6}$"
_ZOOM = Field(ge=0, le=22)


class TerrainCoverage(Section):
    """The IGN WCS coverage that holds a grid's elevation."""

    coverage: str = Field(min_length=1)
    crs: str = Field(pattern=_EPSG)
    # West, south, east, north in the coverage's CRS: windows are clipped to it.
    extent: tuple[float, float, float, float]

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        west, south, east, north = self.extent
        if not (west < east and south < north):
            raise ValueError("extent must be west, south, east, north")
        return self


class GridSettings(Section):
    id: str = Field(pattern=_ID)
    crs: str = Field(pattern=_EPSG)
    # The ISO regions on this grid; the grid with none takes every other region.
    regions: list[str]
    # search.yaml territories whose boxes lie on this grid.
    territories: list[str] = Field(min_length=1)
    terrain: TerrainCoverage

    @model_validator(mode="after")
    def _regions(self) -> Self:
        bad = [r for r in self.regions if not _REGION.match(r)]
        if bad:
            raise ValueError(f"grid {self.id}: {bad} are not ISO 3166-2 codes")
        return self


class Dataset(Section):
    service: str
    detail: LayerDetail
    # An ageing profile of model.yaml.
    ageing: str = Field(min_length=1)


class PermeabilityDataset(Dataset):
    path: str = Field(pattern=r"^/.+/MapServer/\d+/query$")
    class_field: str = Field(min_length=1)
    label_field: str = Field(min_length=1)
    page_size: PositiveInt
    generalise_m: float = Field(ge=0)


class TerrainDataset(Dataset):
    window_m: PositiveFloat
    overlap_m: float = Field(ge=0)
    sea_value: int
    channel_area_km2: PositiveFloat
    min_slope_deg: PositiveFloat = Field(lt=90)


class SoilDataset(Dataset):
    coverage: str = Field(min_length=1)
    window_deg: PositiveFloat = Field(le=10)
    nodata_value: int
    scale: PositiveFloat


class GroundwaterBodiesDataset(Dataset):
    type_name: str = Field(min_length=1)
    status_field: str = Field(min_length=1)
    name_field: str = Field(min_length=1)
    code_field: str = Field(min_length=1)
    srs: str = Field(pattern=_EPSG)
    page_size: PositiveInt


class WaterPointsDataset(Dataset):
    path: str = Field(pattern=r"^/.+/MapServer/\d+/query$")
    kind_field: str = Field(min_length=1)
    exclude_kinds: list[str]
    page_size: PositiveInt


_MONTH_DAY = r"^(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$"


class Season(Section):
    """A stretch of each year, as month-day (inclusive)."""

    start: str = Field(pattern=_MONTH_DAY)
    end: str = Field(pattern=_MONTH_DAY)

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.end <= self.start:
            raise ValueError("a season ends after it starts, within one year")
        return self

    def dates(self, year: int) -> tuple[date, date]:
        return (
            date.fromisoformat(f"{year}-{self.start}"),
            date.fromisoformat(f"{year}-{self.end}"),
        )

    def summers(self, today: date, count: int) -> list[int]:
        """The ``count`` years whose season ended before ``today``, oldest first."""
        last = today.year if self.dates(today.year)[1] < today else today.year - 1
        return list(range(last - count + 1, last + 1))


class Bands(Section):
    """The STAC asset keys of the bands read."""

    red: str = Field(min_length=1)
    nir: str = Field(min_length=1)
    scene_class: str = Field(min_length=1)


class IrrigationMask(Section):
    """The enclosures whose irrigation coefficient marks them irrigated, from SIGPAC's
    vector tiles (docs/knowledge/sigpac.md)."""

    service: str
    # The tile path under the service, with {z}, {x} and {y}.
    path: str = Field(pattern=r"^/.*\{z\}.*\{x\}.*\{y\}.*$")
    zoom: int = Field(ge=12, le=15)
    # A tile answered 404 is asked again as its four children, down to this zoom.
    deepest_zoom: int = Field(ge=12, le=15)
    layer: str = Field(min_length=1)
    coefficient_field: str = Field(min_length=1)
    # An enclosure with at least this irrigation coefficient (percent) is irrigated.
    min_coefficient: PositiveFloat = Field(le=100)
    # Each tile's enclosures are burnt into a square raster this many pixels a side, then
    # averaged onto the grid; a cell this share irrigated or more is masked.
    raster_px: int = Field(ge=64, le=4096)
    masked_share: float = Field(gt=0, le=1)

    @model_validator(mode="after")
    def _zooms(self) -> Self:
        if self.deepest_zoom < self.zoom:
            raise ValueError("irrigation: deepest_zoom is above zoom")
        return self


class VegetationDataset(Dataset):
    """Sentinel-2 L2A scenes of late summer (docs/knowledge/copernicus.md): searched in
    ``service`` (STAC), their pixels read from ``pixels_service``."""

    collection: str = Field(min_length=1)
    pixels_service: str
    page_size: PositiveInt = Field(le=500)
    season: Season
    years: PositiveInt
    min_years: PositiveInt
    max_cloud_pct: float = Field(gt=0, le=100)
    scenes_per_year: PositiveInt
    bands: Bands
    valid_scene_classes: list[int] = Field(min_length=1)
    read_cell_m: PositiveFloat
    neighbourhood_m: PositiveFloat
    irrigation: IrrigationMask

    @model_validator(mode="after")
    def _years(self) -> Self:
        if self.min_years > self.years:
            raise ValueError("vegetation: min_years exceeds years")
        return self


class Datasets(Section):
    permeability: PermeabilityDataset
    terrain: TerrainDataset
    soil: SoilDataset
    groundwater_bodies: GroundwaterBodiesDataset
    water_points: WaterPointsDataset
    vegetation: VegetationDataset

    def all(self) -> dict[str, Dataset]:
        return {
            "permeability": self.permeability,
            "terrain": self.terrain,
            "soil": self.soil,
            "groundwater_bodies": self.groundwater_bodies,
            "water_points": self.water_points,
            "vegetation": self.vegetation,
        }


class GroundMotion(Section):
    """The EGMS Ortho vertical-velocity GeoTIFFs the owner downloads (EU Login) and copies
    into ``directory``: context for the map, not a model input."""

    service: str
    # Relative to the repository root unless absolute; data/ is git-ignored.
    directory: Path
    # The vertical component's files (U), not the east-west one (E).
    pattern: str = Field(min_length=1)

    def path(self, root: Path) -> Path:
        return self.directory if self.directory.is_absolute() else root / self.directory


class ContextLayers(Section):
    ground_motion: GroundMotion


# The dataset each input variable is made from (the build's mechanics).
VARIABLE_DATASET: dict[Variable, str] = {
    Variable.PERMEABILITY_CLASS: "permeability",
    Variable.ELEVATION_M: "terrain",
    Variable.SLOPE_DEG: "terrain",
    Variable.TWI: "terrain",
    Variable.DRAINAGE_DISTANCE_M: "terrain",
    Variable.CLAY_PCT: "soil",
    Variable.GROUNDWATER_STATUS: "groundwater_bodies",
    Variable.WATER_POINT_DISTANCE_M: "water_points",
    Variable.VEGETATION_ANOMALY: "vegetation",
}


class BuildSettings(Section):
    # Worker processes for the grids and tiles; 0 is one per CPU.
    workers: int = Field(ge=0)
    # Relative to the repository root unless absolute.
    output_dir: Path

    def output_path(self, root: Path) -> Path:
        return self.output_dir if self.output_dir.is_absolute() else root / self.output_dir


class TileLayer(Section):
    id: str = Field(pattern=_ID)
    variable: Variable
    visible: bool
    opacity: float = Field(ge=0, le=1)
    unit: str = Field(min_length=1)
    breaks: list[float] = Field(min_length=1)
    colours: list[str]

    @model_validator(mode="after")
    def _classes(self) -> Self:
        if self.variable in CATEGORICAL:
            raise ValueError(f"layer {self.id}: a categorical variable is not coloured by breaks")
        if any(later <= earlier for earlier, later in pairwise(self.breaks)):
            raise ValueError(f"layer {self.id}: breaks must rise strictly")
        if len(self.colours) != len(self.breaks) + 1:
            raise ValueError(f"layer {self.id}: one more colour than breaks")
        bad = [c for c in self.colours if not re.match(_COLOUR, c)]
        if bad:
            raise ValueError(f"layer {self.id}: {bad} are not #rrggbb colours")
        return self


class TilesSettings(Section):
    min_zoom: int = _ZOOM
    max_zoom: int = _ZOOM
    tile_size: PositiveInt
    browser_cache_s: int = Field(ge=0)
    layers: list[TileLayer] = Field(min_length=1)

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.min_zoom > self.max_zoom:
            raise ValueError("tiles: min_zoom is above max_zoom")
        ids = [layer.id for layer in self.layers]
        if len(set(ids)) != len(ids):
            raise ValueError("tile layer ids must be unique")
        return self

    def layer(self, layer_id: str) -> TileLayer:
        for layer in self.layers:
            if layer.id == layer_id:
                return layer
        raise KeyError(layer_id)


class NationalSettings(Section):
    resolution_m: PositiveFloat
    buffer_m: float = Field(ge=0)
    grids: list[GridSettings] = Field(min_length=1)
    datasets: Datasets
    context: ContextLayers
    build: BuildSettings
    tiles: TilesSettings

    @model_validator(mode="after")
    def _grids(self) -> Self:
        ids = [grid.id for grid in self.grids]
        if len(set(ids)) != len(ids):
            raise ValueError("grid ids must be unique")
        defaults = [grid.id for grid in self.grids if not grid.regions]
        if len(defaults) != 1:
            raise ValueError("exactly one grid lists no regions: it takes every other region")
        regions = [r for grid in self.grids for r in grid.regions]
        if len(set(regions)) != len(regions):
            raise ValueError("a region is on one grid only")
        territories = [t for grid in self.grids for t in grid.territories]
        if len(set(territories)) != len(territories):
            raise ValueError("a territory is on one grid only")
        return self

    def grid_of_region(self, region: str) -> GridSettings:
        """The grid that holds an ISO region."""
        for grid in self.grids:
            if region in grid.regions:
                return grid
        return next(grid for grid in self.grids if not grid.regions)

    def grid(self, grid_id: str) -> GridSettings:
        for grid in self.grids:
            if grid.id == grid_id:
                return grid
        raise KeyError(grid_id)
