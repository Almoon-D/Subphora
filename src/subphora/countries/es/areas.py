# Copyright (c) 2026 Almoon-D. All rights reserved.
"""Spanish provinces: the two-digit province code to its ISO 3166-2 province and region.

The two-digit code is the INE province code, which Catastro uses as the first two digits
of a rustic reference and returns as ``loine.cp``. The ISO codes key every area-dependent
rule (decision 0014). Ceuta and Melilla are autonomous cities: province and region alike.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Province:
    code: str
    iso: str
    region: str


_PROVINCES: tuple[tuple[str, str, str], ...] = (
    ("01", "ES-VI", "ES-PV"),  # Araba/Álava
    ("02", "ES-AB", "ES-CM"),  # Albacete
    ("03", "ES-A", "ES-VC"),  # Alicante/Alacant
    ("04", "ES-AL", "ES-AN"),  # Almería
    ("05", "ES-AV", "ES-CL"),  # Ávila
    ("06", "ES-BA", "ES-EX"),  # Badajoz
    ("07", "ES-PM", "ES-IB"),  # Illes Balears
    ("08", "ES-B", "ES-CT"),  # Barcelona
    ("09", "ES-BU", "ES-CL"),  # Burgos
    ("10", "ES-CC", "ES-EX"),  # Cáceres
    ("11", "ES-CA", "ES-AN"),  # Cádiz
    ("12", "ES-CS", "ES-VC"),  # Castellón/Castelló
    ("13", "ES-CR", "ES-CM"),  # Ciudad Real
    ("14", "ES-CO", "ES-AN"),  # Córdoba
    ("15", "ES-C", "ES-GA"),  # A Coruña
    ("16", "ES-CU", "ES-CM"),  # Cuenca
    ("17", "ES-GI", "ES-CT"),  # Girona
    ("18", "ES-GR", "ES-AN"),  # Granada
    ("19", "ES-GU", "ES-CM"),  # Guadalajara
    ("20", "ES-SS", "ES-PV"),  # Gipuzkoa
    ("21", "ES-H", "ES-AN"),  # Huelva
    ("22", "ES-HU", "ES-AR"),  # Huesca
    ("23", "ES-J", "ES-AN"),  # Jaén
    ("24", "ES-LE", "ES-CL"),  # León
    ("25", "ES-L", "ES-CT"),  # Lleida
    ("26", "ES-LO", "ES-RI"),  # La Rioja
    ("27", "ES-LU", "ES-GA"),  # Lugo
    ("28", "ES-M", "ES-MD"),  # Madrid
    ("29", "ES-MA", "ES-AN"),  # Málaga
    ("30", "ES-MU", "ES-MC"),  # Murcia
    ("31", "ES-NA", "ES-NC"),  # Navarra
    ("32", "ES-OR", "ES-GA"),  # Ourense
    ("33", "ES-O", "ES-AS"),  # Asturias
    ("34", "ES-P", "ES-CL"),  # Palencia
    ("35", "ES-GC", "ES-CN"),  # Las Palmas
    ("36", "ES-PO", "ES-GA"),  # Pontevedra
    ("37", "ES-SA", "ES-CL"),  # Salamanca
    ("38", "ES-TF", "ES-CN"),  # Santa Cruz de Tenerife
    ("39", "ES-S", "ES-CB"),  # Cantabria
    ("40", "ES-SG", "ES-CL"),  # Segovia
    ("41", "ES-SE", "ES-AN"),  # Sevilla
    ("42", "ES-SO", "ES-CL"),  # Soria
    ("43", "ES-T", "ES-CT"),  # Tarragona
    ("44", "ES-TE", "ES-AR"),  # Teruel
    ("45", "ES-TO", "ES-CM"),  # Toledo
    ("46", "ES-V", "ES-VC"),  # Valencia/València
    ("47", "ES-VA", "ES-CL"),  # Valladolid
    ("48", "ES-BI", "ES-PV"),  # Bizkaia
    ("49", "ES-ZA", "ES-CL"),  # Zamora
    ("50", "ES-Z", "ES-AR"),  # Zaragoza
    ("51", "ES-CE", "ES-CE"),  # Ceuta
    ("52", "ES-ML", "ES-ML"),  # Melilla
)


def province_by_code(code: str) -> Province | None:
    """The province with this two-digit code, or None when Spain has no such province."""
    for province_code, iso, region in _PROVINCES:
        if province_code == code:
            return Province(code=province_code, iso=iso, region=region)
    return None


def all_provinces() -> tuple[Province, ...]:
    return tuple(Province(code=c, iso=i, region=r) for c, i, r in _PROVINCES)
