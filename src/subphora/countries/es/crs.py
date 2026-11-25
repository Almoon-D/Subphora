# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The projected CRS for measurements at a place in Spain (MASTER_PLAN §3, Coordinates).

- The Canary Islands: REGCAN95 / UTM zone 28N (EPSG:4083), whatever the island.
- Everywhere else (mainland, Balearics, Ceuta, Melilla): ETRS89 / UTM, the zone of the
  longitude (EPSG:25829, 25830 or 25831).

Typed UTM coordinates name their zone; ``utm_crs`` is the CRS Spain uses in it.
"""

import math

CANARIES_REGION = "ES-CN"
CANARIES_CRS = "EPSG:4083"
# ETRS89 / UTM zone N north is EPSG:258NN.
_ETRS89_UTM_BASE = 25800
_UTM_ZONE_WIDTH_DEG = 6
# The UTM zones that hold Spanish territory outside the Canaries.
UTM_ZONES = (29, 30, 31)
# The Canaries are measured in REGCAN95 / UTM zone 28 (EPSG:4083), every island alike.
CANARY_UTM_ZONE = 28
# The latitude bands from 80° S: 8° each, the last (X) up to 84° N.
UTM_BANDS = "CDEFGHJKLMNPQRSTUVWX"
_BAND_SOUTH = -80.0
_BAND_NORTH = 84.0
_BAND_HEIGHT_DEG = 8


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


def utm_crs(zone: int) -> str:
    """The CRS Spain uses for UTM coordinates in this zone: REGCAN95 in 28 (the Canaries),
    ETRS89 elsewhere."""
    if zone == CANARY_UTM_ZONE:
        return CANARIES_CRS
    if zone not in UTM_ZONES:
        raise ValueError(f"UTM zone {zone} holds no Spanish territory")
    return f"EPSG:{_ETRS89_UTM_BASE + zone}"


def latitude_band(latitude: float) -> str:
    """The UTM latitude band letter (C to X, 8° each, without I and O; X spans 12°)."""
    if not _BAND_SOUTH <= latitude <= _BAND_NORTH or math.isnan(latitude):
        raise ValueError(f"latitude {latitude} has no UTM band")
    index = min(int((latitude - _BAND_SOUTH) // _BAND_HEIGHT_DEG), len(UTM_BANDS) - 1)
    return UTM_BANDS[index]
