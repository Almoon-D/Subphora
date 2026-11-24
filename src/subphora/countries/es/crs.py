# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The projected CRS for measurements at a place in Spain (MASTER_PLAN §3, Coordinates).

- The Canary Islands: REGCAN95 / UTM zone 28N (EPSG:4083), whatever the island.
- Everywhere else (mainland, Balearics, Ceuta, Melilla): ETRS89 / UTM, the zone of the
  longitude (EPSG:25829, 25830 or 25831).
"""

import math

CANARIES_REGION = "ES-CN"
CANARIES_CRS = "EPSG:4083"
# ETRS89 / UTM zone N north is EPSG:258NN.
_ETRS89_UTM_BASE = 25800
_UTM_ZONE_WIDTH_DEG = 6
# The UTM zones that hold Spanish territory outside the Canaries.
UTM_ZONES = (29, 30, 31)


def utm_zone(longitude: float) -> int:
    """The standard UTM zone of a longitude (no Norway or Svalbard exceptions in Spain)."""
    if not -180 <= longitude <= 180 or math.isnan(longitude):
        raise ValueError(f"longitude {longitude} is out of range")
    zone = int((longitude + 180) // _UTM_ZONE_WIDTH_DEG) + 1
    return min(zone, 60)


def local_crs(region_code: str, longitude: float) -> str:
    """The EPSG code of the CRS for measurements at a place in this ISO region."""
    if region_code == CANARIES_REGION:
        return CANARIES_CRS
    zone = utm_zone(longitude)
    if zone not in UTM_ZONES:
        raise ValueError(f"longitude {longitude} (UTM zone {zone}) is outside Spain's zones")
    return f"EPSG:{_ETRS89_UTM_BASE + zone}"
