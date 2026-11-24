# Junta de Andalucía (REDIAM and the water administration)

Host `www.juntadeandalucia.es` (WMS under `/medioambiente/mapwms/<service>`). Catalogue
ids: `rediam-water-bodies` (here) and `rediam-soils` (see `soil.md`). Findings observed on
2026-11-24.

## REDIAM WMS

- `REDIAM_masas_agua_andalucia_phc_2022_27`: layers `red_hidrografica`,
  `masas_supf_linea_and`, `masas_supf_polig_and`, `masas_subt_polig_and` (the groundwater
  bodies of every Andalusian district in the 2022-2027 plans); EPSG:3857 offered.
  `(GetCapabilities, 2026-11-24)`
- `AccessConstraints`: "Este servicio se puede usar de modo libre y gratuito siempre que se
  mencione a los autores y propietarios de la información". `(GetCapabilities, 2026-11-24)`
- **No `Access-Control-Allow-Origin`** on these services: a browser cannot call them
  directly; the server's proxy (session 03) must. `(GetCapabilities with Origin, 2026-11-24)`
- `REDIAM_redes_control_andalucia_phc_2022_27` (a name found in REDIAM bulletins) returns an
  HTML page, not capabilities: the name is wrong or retired. `(GetCapabilities, 2026-11-24)`
- IDEAndalucía services (`https://www.ideandalucia.es/services/…`, e.g. `toporaster10`)
  answer with CORS `*`. Not catalogued: nothing needs them yet. `(GetCapabilities, 2026-11-24)`

## The Andalusian Mediterranean basins (ES060)

- The Junta de Andalucía is the water authority for the intra-community districts
  (Cuencas Mediterráneas Andaluzas, Guadalete-Barbate, Tinto-Odiel-Piedras). Its plan for
  2022-2027 was approved by Real Decreto 689/2023; the normative content was published in
  BOJA no. 199 of 17 October 2023 (details in `legal-groundwater.md`).
- The plan's Apéndice 15 lists ES060MSBT060.033 Llanos de Antequera-Vega de Archidona and
  ES060MSBT060.034 Fuente de Piedra among the bodies "identified at risk of not reaching good
  status and subject to preventive control" (art. 54 of the Andalusian Water Law).
  `(BOJA 199/2023, 2026-11-24)`
- A hydrogeological presentation of Llanos de Antequera with a 3D geological model (2024):
  `https://juntadeandalucia.es/sites/default/files/inline-files/2024/09/Presentacion_hidrogeo_ES060MSBT060_033_Llanos.pdf`.

Copyright (c) 2026 Almoon-D. All rights reserved.
