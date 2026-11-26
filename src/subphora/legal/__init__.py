# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The legal filter: rules held as data, evaluated at a place (MASTER_PLAN §4.5).

It imports only ``domain`` and ``config`` (import-linter contract): what it evaluates is
handed to it, so every branch is tested without network.
"""

from subphora.legal.engine import (
    Distance,
    LayerAnswer,
    PlaceFacts,
    assess,
    body_class,
    district_of,
    layers_read,
)

__all__ = [
    "Distance",
    "LayerAnswer",
    "PlaceFacts",
    "assess",
    "body_class",
    "district_of",
    "layers_read",
]
