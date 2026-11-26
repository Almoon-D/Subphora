# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The water-potential model (MASTER_PLAN §4.3): suitability lookups, the weighted score
renormalised over the inputs present, confidence, the explanation of a cell, an area's
candidate spots and means, the validation and calibration per hydrogeological domain, and
the depth to water and drilling cost at a spot.

The model receives grids and never fetches anything: it imports neither ``sources`` nor
``store`` (an import-linter contract), so it is tested on synthetic grids.
"""

from subphora.model.candidates import AreaMeans, CriterionMeans, area_means, select_candidates
from subphora.model.depth import PiezometerPoint, depth_at, drilling_cost, water_table
from subphora.model.evaluate import Category, Evaluation, InputGrids, Quality, evaluate
from subphora.model.explain import confidence_of, explain_cell
from subphora.model.quality import dataset_quality
from subphora.model.validation import (
    Labelled,
    not_validated,
    probability_of,
    skill_of,
    validate_domain,
)

__all__ = [
    "AreaMeans",
    "Category",
    "CriterionMeans",
    "Evaluation",
    "InputGrids",
    "Labelled",
    "PiezometerPoint",
    "Quality",
    "area_means",
    "confidence_of",
    "dataset_quality",
    "depth_at",
    "drilling_cost",
    "evaluate",
    "explain_cell",
    "not_validated",
    "probability_of",
    "select_candidates",
    "skill_of",
    "validate_domain",
    "water_table",
]
