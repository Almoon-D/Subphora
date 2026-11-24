# Commercial use: whom to ask before selling

The owner tests Subphora on his own land first and sells nothing until then (decision 0015).
This list is for that later moment: every organisation whose terms a paid product would
need, what the term says, where it is written and what to ask. A session that finds a new
one adds a row; evidence and dates live in the knowledge file named.

## To contact

| Organisation | What a paid product needs | Term and source | Knowledge |
|---|---|---|---|
| IGME (CN IGME-CSIC) | Consent to use the MAGNA 1:50,000 WMS inside a paid service | MAGNA WMS `AccessConstraints`: "No está permitido implementar un servicio de valor añadido no gratuito sin establecer contacto con el IGME" | `docs/knowledge/igme.md` |
| IGME (CN IGME-CSIC) | Access to water levels and analyses per water point (needed by session 07 too) | Only in the BDAguas web application, no documented API or download | `docs/knowledge/igme.md` |
| Dirección General del Catastro | Confirmation that showing cadastral maps and parcel outlines to paying customers fits the licence (own use or transformed value-added products; no untransformed redistribution; not called "cartografía catastral"; no tiled requests, no massive downloads) | Licencia de acceso y uso INSPIRE, `https://www.catastro.hacienda.gob.es/webinspire/documentos/Licencia.pdf` | `docs/knowledge/catastro.md` |
| Junta de Andalucía (REDIAM) | Confirmation that "free and gratuitous use citing the authors" covers a paid product | REDIAM WMS `AccessConstraints` | `docs/knowledge/junta-andalucia.md` |
| Confederación Hidrográfica del Guadalquivir | Its public map services (IDE-CHG) were not reachable; ask for the current endpoints and terms | `idechg.chguadalquivir.es` redirects to an error page | `docs/knowledge/miteco-basins.md` |

## Cost, not permission

| Organisation | Why it matters when selling | Source | Knowledge |
|---|---|---|---|
| Google (Maps Platform) | Commercial use is allowed under its terms, but usage is billed per project: 100,000 free 2D map tiles a month, then about USD 0.60 per 1,000, so cost grows with customers | Map Tiles API policies and pricing | `docs/knowledge/google-maps.md` |

## Open licences: attribution only

IGN/CNIG (PNOA, base maps, MDT, CartoCiudad: CC BY 4.0), FEGA (SIGPAC: CC BY 4.0), MITECO
("sin limitaciones al acceso público", reuse citing the source), SoilGrids (CC BY 4.0),
Copernicus (free and open, with attribution), AEMET (use authorised citing AEMET). Each
keeps its attribution text from `config/defaults/sources.yaml`.

## Beyond data licences (for the decision that allows selling)

- Many customers instead of a few users: accounts, separation of each customer's private
  data, data-protection duties (MASTER_PLAN §4.9 is single-owner today).
- The legal guidance shown to customers stays "guidance, not legal advice" (hard rule 2).

Copyright (c) 2026 Almoon-D. All rights reserved.
