# Copyright (c) 2026 Almoon-D. All rights reserved.
"""How well an input fits the grid: its resolution against the cell, its age against its
ageing profile. A resolution or edition the publisher does not state scores the
configured ``unknown_value``: unknown is never treated as good."""

from subphora.config.model import Ageing
from subphora.domain.layers import LayerDetail
from subphora.model.evaluate import Quality


def ground_resolution_m(detail: LayerDetail, metres_per_scale_unit: float) -> float | None:
    """The input's ground resolution: its grid cell, or what its map scale resolves
    (1:N resolves N x ``metres_per_scale_unit`` metres); None when neither is stated."""
    if detail.cell_m is not None:
        return detail.cell_m
    if detail.scale_denominator is not None:
        return detail.scale_denominator * metres_per_scale_unit
    return None


def age_fit(edition: int | None, build_year: int, ageing: Ageing, unknown_value: float) -> float:
    if edition is None:
        return unknown_value
    age = max(0, build_year - edition)
    if age <= ageing.full_years:
        return 1.0
    return max(0.0, (ageing.zero_years - age) / (ageing.zero_years - ageing.full_years))


def dataset_quality(
    detail: LayerDetail,
    cell_m: float,
    metres_per_scale_unit: float,
    build_year: int,
    ageing: Ageing,
    unknown_value: float,
) -> Quality:
    resolution = ground_resolution_m(detail, metres_per_scale_unit)
    fit = unknown_value if resolution is None else min(1.0, cell_m / resolution)
    return Quality(resolution=fit, age=age_fit(detail.edition, build_year, ageing, unknown_value))
