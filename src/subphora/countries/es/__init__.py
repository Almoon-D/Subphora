# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Spain: cadastral references, ISO 3166-2 areas and the CRS chosen by location."""

from subphora.countries.es.areas import Province, province_by_code
from subphora.countries.es.crs import local_crs
from subphora.countries.es.references import control_letters, parse_reference

__all__ = ["Province", "control_letters", "local_crs", "parse_reference", "province_by_code"]
