# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The water-potential model (MASTER_PLAN §4.3): suitability lookups, the weighted score
renormalised over the inputs present, confidence, the explanation of a cell, and an area's
candidate spots and means.

The model receives grids and never fetches anything: it imports neither ``sources`` nor
``store`` (an import-linter contract), so it is tested on synthetic grids.
"""

from subphora.model.candidates import AreaMeans, CriterionMeans, area_means, select_candidates
from subphora.model.evaluate import Category, Evaluation, InputGrids, Quality, evaluate
from subphora.model.explain import confidence_of, explain_cell
from subphora.model.quality import dataset_quality

__all__ = [
    "AreaMeans",
    "Category",
    "CriterionMeans",
    "Evaluation",
    "InputGrids",
    "Quality",
    "area_means",
    "confidence_of",
    "dataset_quality",
    "evaluate",
    "explain_cell",
    "select_candidates",
]
