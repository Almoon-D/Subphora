# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Schema of ``config/defaults/national.yaml``: the national grids, the nationwide inputs
the batch build downloads, and the map layers it publishes as tiles (MASTER_PLAN §4.3).

Whether each dataset's service is catalogued, and each ageing profile defined, is checked
against the other sections by ``Settings``.
"""

import re
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


class Datasets(Section):
    permeability: PermeabilityDataset
    terrain: TerrainDataset
    soil: SoilDataset
    groundwater_bodies: GroundwaterBodiesDataset
    water_points: WaterPointsDataset

    def all(self) -> dict[str, Dataset]:
        return {
            "permeability": self.permeability,
            "terrain": self.terrain,
            "soil": self.soil,
            "groundwater_bodies": self.groundwater_bodies,
            "water_points": self.water_points,
        }


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
