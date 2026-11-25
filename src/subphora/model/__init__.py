# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The water-potential model (MASTER_PLAN §4.3): suitability lookups, the weighted score
renormalised over the inputs present, confidence and the explanation of a cell.

The model receives grids and never fetches anything: it imports neither ``sources`` nor
``store`` (an import-linter contract), so it is tested on synthetic grids.
"""

from subphora.model.evaluate import Category, Evaluation, InputGrids, Quality, evaluate
from subphora.model.explain import explain_cell
from subphora.model.quality import dataset_quality

__all__ = [
    "Category",
    "Evaluation",
    "InputGrids",
    "Quality",
    "dataset_quality",
    "evaluate",
    "explain_cell",
]
