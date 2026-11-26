<!-- Copyright (c) 2026 Almoon-D. All rights reserved. -->

# Piezometry fixtures

Excerpts of MITECO's national piezometry database (`basedatospiezometria.zip`, the file
`Piezo_GEOportal_2024_descargas_20260220.accdb`, downloaded by hand by the owner on
2026-11-25), exported with `mdb-export -D '%Y-%m-%d' -T '%Y-%m-%d'` (mdbtools 1.0) on
2026-11-26. Public monitoring-network data; no owner data. Third-party data: exempt from
the copyright notice.

| File | Content |
|---|---|
| `01_Piezometros.csv` | six piezometers: two in Sierra de Altomira (zone 30), one in Catalonia (zone 31), one removed with levels only before 2008, one with no monitored body, one in Bullaque |
| `02_Niveles.csv` | the last 30 levels of each (3 of the removed one), and one row without a level |
| `basins/F71_Puntos_de_control_piezometrico.zip` | CH Júcar's download (hand-downloaded by the owner on 2026-11-26), cut to three control points (two with a body, one with neither body nor level) and their measurements since 2021, one per month, split over the two measurement workbooks |
| `basins/Red Oficial Guadiana OCTUBRE 2026.xlsx` | CH Guadiana's October 2026 sheet (same date), cut to four piezometers and the months from 2022: two in the national excerpt, one in Bullaque only it holds, one in Rus-Valdelobos (a body the excerpt does not name) |
