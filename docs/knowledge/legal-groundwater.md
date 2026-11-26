# Legal knowledge: drilling for groundwater

The texts behind the rules of `config/legal/es/` (decision 0034). Every rule has its
official source, article and the date it was read. **Uncertain** marks what the text does not
settle; the filter shows those as a condition with the open question, never as a verdict.
Nothing here is legal advice. First read on 2026-11-24; every source re-read, and the rest
read, on 2026-11-26.

**Coverage:** the national law and the mining-safety rules; the water law of every region;
the plans of 17 of the 25 river-basin districts in full, four Canary island plans in part
(`areas.yaml` says what is missing in each).

## Not read (2026-11-26)

- **ES014 Galicia-Costa:** the Xunta's hosts (`www.xunta.gal`, `augasdegalicia.xunta.gal`,
  `www.xunta.gal/dog`) reset every connection from the cloud (curl error 35); the copies
  that could be read (hispagua, a mirror of the DOG text) end at art. 30.4 and art. 31.3,
  before the articles on distances (38) and groundwater bodies (40). `(GET, 2026-11-26)`
- **ES122 Fuerteventura:** Decreto 139/2024 is published through a download service of the
  Gobierno de Canarias the session did not reach. **ES125 La Palma:** Decreto 6/2025 is a
  scanned image at the BOC, without a text layer. **ES126 La Gomera:** the BOC entry of
  Decreto 102/2023 holds the decree, not the plan's normative articles.
- **Partial:** ES120 Gran Canaria and ES124 Tenerife (their protection spaces around existing
  galleries and wells: no layer maps them); ES123 Lanzarote and ES127 El Hierro (searched for
  wells, distances and small-use volumes, none found beyond the Canary Water Law; not read in
  full).
- **Not mapped, shown as open questions:** distances to the monitoring networks (Duero art.
  20.5, Tajo art. 22.3, Segura art. 46), the Tajo's appendix 11 sub-basins, the Catalan
  safeguard of art. 43, coastal strips; no official layer gives them.

## Live layers: the body and its status

- MITECO's WMS `estado_masas_aguasub_2027` and `masas_aguasub_riesgo_2027` answer
  GetFeatureInfo (WMS 1.3.0, EPSG:4258) with the fields `legal.yaml` reads: "Cód. Masa de
  agua", "Nombre masa de agua", "Estado cuantitativo"; "Código de masa", "Declaración de
  riesgo". Madrid: ES030MSBT030-010, "Bueno"; Mancha Occidental I: declared at risk.
  VERIFY-LIVE(legal-taps) closed. `(GetFeatureInfo, 2026-11-26)`
- The layer writes the plans' codes its own way: the Tajo with a hyphen (ES030MSBT030-010
  where the plan writes 030.010), Catalonia with MSBT and a split suffix (ES100MSBT18_01 for
  the plan's MAS 18), the Guadiana padded (ES040MSBT000030606), the Canaries with the island
  (ES120MSBTES70GC003). A rule's `where.bodies` lists the layer's form.

## National: Water Law and Public Water Domain Regulation

Re-read 2026-11-26: the consolidated texts are unchanged since the dates below.

- **TRLA** — Real Decreto Legislativo 1/2001, texto refundido de la Ley de Aguas,
  `https://www.boe.es/buscar/act.php?id=BOE-A-2001-14276` (consolidated, last update
  published 28/12/2023).
  - Art. 54.2: on one estate (predio) the owner may use springs inside it and abstract
    groundwater "cuando el volumen total anual no sobrepase los 7.000 metros cúbicos", under
    the conditions the regulation sets. "En los acuíferos que hayan sido declarados como
    sobreexplotados, o en riesgo de estarlo, no podrán realizarse nuevas obras de las
    amparadas por este apartado sin la correspondiente autorización." (text as corrected,
    BOE 30/11/2001). `(TRLA art. 54.2, 2026-11-24)`
  - Art. 6.1: the banks of public channels carry a 5 m easement zone and a **100 m zona de
    policía** "en la que se condicionará el uso del suelo y las actividades". `(TRLA art. 6, 2026-11-24)`
  - Art. 56: a body declared at risk of not reaching good quantitative or chemical status
    gets a users' community and an action programme that orders abstractions; until then
    precautionary limits may apply. `(TRLA art. 56, 2026-11-24)`
- **RDPH** — Real Decreto 849/1986, Reglamento del Dominio Público Hidráulico,
  `https://www.boe.es/buscar/act.php?id=BOE-A-1986-10638` (last update published 03/06/2026).
  - Art. 84.2 (as amended by RD 665/2023): the 7,000 m³/year use; "No se podrán realizar
    nuevas obras, sin la correspondiente autorización del organismo de cuenca, en las masas
    de agua subterránea que hayan sido declaradas como en riesgo de no alcanzar el buen
    estado cuantitativo o químico". Art. 84.3: the water may only be used on the estate where
    it rises. `(RDPH art. 84, 2026-11-24)`
  - Art. 85: the owner must **notify** (comunicar) the basin authority: maximum
    instantaneous flow, maximum annual and monthly volume, purpose, municipality and a
    description of the works, with proof of ownership; the entry date fixes precedence.
    Outside bodies declared at risk the 54.2 well is a notice, not an authorisation.
    `(RDPH art. 85, 2026-11-24)`
  - Art. 87.1: 7,000 m³/year per estate **in total**, however many wells or springs; above
    it a concession is needed. `(RDPH art. 87, 2026-11-24)`
  - Art. 87.2: minimum distances between wells, or a well and a spring, are those of the
    basin plan; failing that, for maximum instantaneous flows under 0.15 l/s, **10 m in
    urban land and 20 m in non-developable land, and 100 m for larger flows**; the same
    distances to the neighbours' unlined ponds and ditches and to the control points of the
    piezometric and quality networks. `(RDPH art. 87.2, 2026-11-24)`
  - Art. 87.3: the notice carries the cadastral certificate of each parcel, the works, the
    irrigable area, and the distances to other abstractions, channels, buildings, roads and
    control points. Art. 87.4: **a well in the zona de policía always needs the basin
    authority's authorisation.** `(RDPH art. 87.3–87.4, 2026-11-24)`
  - Art. 9: the zona de policía is 100 m measured horizontally from the channel and may be
    widened to include the preferential-flow zone. Art. 78: works in it need a responsible
    declaration or a prior authorisation of the basin authority. `(RDPH arts. 9, 78, 2026-11-24)`

## Andalusia: Water Law of Andalusia

- **LAA** — Ley 9/2010, de 30 de julio, de Aguas para Andalucía (BOJA 155, 09/08/2010;
  BOE-A-2010-13465), `https://www.boe.es/buscar/act.php?id=BOE-A-2010-13465` (last update
  published 20/03/2026).
  - Art. 51.1: no abstraction without concession or authorisation; abstractions **up to
    7,000 m³/year need an authorisation** when the body has been declared at risk of not
    reaching good status, or when the Consejería declares it subject to **preventive
    control**. `(LAA art. 51.1, 2026-11-24)`
  - Art. 51.2: **opening a well, enlarging its diameter or depth, or moving it needs the
    prior authorisation of the Consejería**, besides any other licence. `(LAA art. 51.2, 2026-11-24)`
  - Art. 41: the zona de policía includes the preferential-flow zone; uses there follow the
    TRLA, the RDPH and the basin and flood-risk plans. `(LAA art. 41, 2026-11-24)`
- **Uncertain:** the Junta's water competence covers the intra-community districts
  (Cuencas Mediterráneas Andaluzas, Guadalete-Barbate, Tinto-Odiel-Piedras). Whether art.
  51.2 binds a well in the Andalusian part of the Guadalquivir (an inter-community basin
  managed by the State's CHG) is not settled by the text read. Session 09 shows it as an
  open condition there.

## Guadalquivir basin plan (ES050, CHG)

- Plan 2022-2027 approved by Real Decreto 35/2023 (24 January); its normative provisions
  are Annex VII, published in BOE no. 35 of 10/02/2023 (BOE-A-2023-3511); text used:
  `https://www.miteco.gob.es/content/dam/miteco/es/agua/temas/planificacion-hidrologica/normativa_ph_guadalquivir_tcm30-552976.pdf`.
  - Art. 38.1: in bodies declared at risk (quantitative or chemical) and those declared
    overexploited before RDL 17/2012, the measures of their action programmes apply.
    Art. 38.4: **in bodies in poor quantitative status no new concessions are admitted**,
    except replacements of existing ones or public supply without a viable alternative.
    `(Annex VII art. 38, 2026-11-24)`
  - Art. 50.1: the 54.2 right is incompatible with any other abstraction for the same use
    already granted to the estate. Art. 50.2: **in bodies declared at risk, 54.2 wells need
    an authorisation.** `(Annex VII art. 50.1–50.2, 2026-11-24)`
  - Art. 50.3: distances for 54.2 wells, as exclusion circles: urbanised land 10 m (under
    1,000 m³/year) or 100 m; rural land 50 m for ≤ 1,000 m³/year, growing with the volume to
    **500 m** (at 3,000 m³/year in bodies in poor quantitative status or Red Natura 2000; at
    7,000 m³/year elsewhere, one metre per 13.333 m³ above 1,000). **Uncertain:** the text
    has a "b) suelo rural" and a "c) resto del territorio" with overlapping rules; session 09
    applies the stricter where both could apply and flags it. `(Annex VII art. 50.3, 2026-11-24)`
  - Art. 44.3.h: between concession wells, 100 m minimum unless more specific limits apply;
    **500 m between a new well and an existing spring abstraction**. Art. 44.3.c: wells over
    5 m deep cement at least the first 4 m of annulus. `(Annex VII art. 44, 2026-11-24)`
  - Art. 45: "minor" concessions (escasa importancia) for irrigation: up to 4 l/s and
    7,000 m³/year. `(Annex VII art. 45, 2026-11-24)`
- The list of bodies in poor quantitative status is the plan's annex 5, appendix 1; the
  live status is in MITECO's `estado_masas_aguasub_2027` (`miteco-basins.md`).

## Andalusian Mediterranean basins plan (ES060, Junta de Andalucía)

- Plan 2022-2027 approved by Real Decreto 689/2023 (18 July, BOE-A-2023-16879); its
  normative content published by Orden de 9 de octubre de 2023, BOJA no. 199 of 17/10/2023,
  `https://www.juntadeandalucia.es/boja/2023/199/45`.
  - Art. 53.1: 54.2 abstractions (≤ 7,000 m³/year) **need the Consejería's prior
    authorisation** (LAA art. 51.1) when the water comes from aquifers declared
    overexploited, under preventive control or identified at risk. Art. 53.2: between 3,000
    and 7,000 m³/year the applicant justifies the allocation. Art. 53.3: the well must be on
    the estate where the water is used. `(Orden 9/10/2023 art. 53, 2026-11-24)`
  - Art. 53.5: distances for 54.2 wells (between wells, or to springs or channels): in
    bodies in **good** quantitative status 50 m (< 1,500 m³/year) or 100 m (> 1,500); outside
    groundwater bodies 100 m; stricter limits of protection perimeters prevail.
    **Uncertain:** the article gives no distance for bodies in poor status (there the
    authorisation of art. 53.1 decides). `(Orden 9/10/2023 art. 53.5, 2026-11-24)`
  - Art. 39: bodies in Apéndice 15 are under **preventive control**; any abstraction there
    needs a prior report of compatibility with the plan; Apéndice 15 lists 34 bodies.
    Art. 40: the procedure to declare a body at risk. `(Orden 9/10/2023 arts. 39–40, Apéndice 15, 2026-11-24)`
  - Art. 47: documentation for groundwater abstractions (location on the cadastral map and
    orthophoto at 1:5,000, borehole and casing profiles, water level and date, pump).
    `(Orden 9/10/2023 art. 47, 2026-11-24)`

## The other basin plans of RD 35/2023 (BOE-A-2023-3511, BOE no. 35, 10/02/2023)

All read at `https://www.boe.es/buscar/doc.php?id=BOE-A-2023-3511`, the annex of each plan.
The Supreme Court's annulments published since (BOE-A-2025-11326, Tajo appendix 10;
BOE-A-2026-11702 and BOE-A-2026-21528, Segura art. 13.13.d; BOE-A-2025-15242 and
BOE-A-2025-23548, appendices 13.4 and 7.8 and art. 26.1 of annexes V and VI) touch none of
the articles below. `(BOE, 2026-11-26)`

- **Miño-Sil (ES010, Annex III).** Art. 32: distance to other wells and springs 100 m; under
  1 l/s and 3,650 m³/year 50 m; under 0.15 l/s and 3,650 m³/year 10 m in urban land and 20 m
  elsewhere (20 m used, the land class not known). Art. 34.2 restates RDPH 84.2.
- **Cantábrico Oriental and Occidental (ES017, ES018, Annexes I, II).** Art. 34.3: in bodies
  in poor quantitative status the authority may refuse or limit new abstractions, small ones
  included (shown as an authorisation).
- **Duero (ES020, Annex IV).** Arts. 33 and 34.1.b: the groundwater zoning closes or limits
  new **concessions** (above 7,000 m³/year); a 54.2 well is outside it. Art. 20.5: 400 m (or
  100 m) to piezometers, not mapped.
- **Tajo (ES030, Annex V).** Art. 22 and appendix 12: 100 m under 1,000 m³/year, 250 m up to
  7,000, then rising to 400 m at a rate per body (Torrelaguna 030.004: 1 m per 1,000 m³;
  Madrid 030.010–012: 3 m; 030.018, 025, 026: 6 m; elsewhere 4 m, the stricter of the
  basin's two scales). Art. 35.1 and appendices 15–16: concessions in the seven bodies at
  risk need the action programme's authorisation. Art. 35.2: in Madrid's three bodies a
  well is at most 200 m deep with a pump of at most 11 kW (open question).
- **Guadiana (ES040, Annex VI).** Art. 23.2: 100 m between wells. Art. 31.1 and appendix 5.4:
  no new concessions in the eleven bodies listed (Mancha Occidental, Campo de Montiel…);
  appendix 11.1, the closed perimeters (`regional-layers.md`).
- **Segura (ES070, Annex X).** Art. 46.1: 100 m; 500 m to piezometers above 15,000 m³/year
  (not mapped). Art. 45.3–45.4: no new groundwater volumes beyond 54.2 wells. Art. 49: 54.2
  wells in bodies at risk need an authorisation.
- **Júcar (ES080, Annex XI).** Art. 45.6: no new concessions in bodies in poor quantitative
  status. Art. 49.4: every 54.2 well needs the authority's authorisation. No distance of its
  own: the national one applies.
- **Ebro (ES091, Annex XII).** Art. 25.2.e: 100 m. Art. 45.4 and appendix 12.7: in 20 listed
  bodies 200 m for 54.2 wells, 400 m above. Art. 45.2 and appendix 12.5.1: no new
  concessions in ES091MSBT079.
- **Ceuta and Melilla (ES150, ES160, Annexes VIII, IX).** Art. 21: concessions give way to
  public supply and keep 100 m from other abstractions; nothing beyond the national rules
  for a 54.2 well.

## Plans published by their regions

- **Guadalete-Barbate and Tinto-Odiel-Piedras (ES063, ES064).** Orden de 9 de octubre de
  2023, BOJA no. 199 (`https://www.juntadeandalucia.es/boja/2023/199/43` and `/44`):
  arts. 39, 53.1 and 53.5 word for word as the Andalusian Mediterranean plan's; their
  preventive-control bodies are in Apéndice 14.
- **Catalonia (ES100).** RD 690/2023, normative part annexed to Decret 91/2023 (ACA, Spanish
  text, `https://info.aca.gencat.cat/ca/aca/informacio/geco/plans-programes/PDG/ES/01-00_Plan_gestion_2022-27.pdf`).
  Art. 42.5 and annex 1.6: in 18 bodies even a 54.2 well needs an authorisation. Arts.
  41.1–41.2: in bodies in poor status new abstractions are limited. Art. 43: a 300 m
  safeguard around supply wells (not mapped).
- **Balearics (ES110).** RD 49/2023, normative text in BOIB 2023/28
  (`https://www.caib.es/eboibfront/pdf/es/2023/28/1130905`, read through the CAIB's
  "Normativa" PDF because the BOIB annex's fonts do not extract). Arts. 113.1–113.3: every
  new well needs an authorisation. Art. 113.7, cuadro 20: 20 m up to 0.15 l/s, 100 m to
  0.5, 200 m to 1, 350 m to 2, 500 m to 5, a study above. Art. 123.4: no new abstractions
  in bodies in poor status.
- **Gran Canaria (ES120).** Decreto 370/2023, BOC 2023/191/001: art. 73, small abstraction
  up to 1,500 m³/year by authorisation; art. 76, above it a concession.
- **Tenerife (ES124).** Decreto 372/2023, BOC 2023/191/003: small abstraction up to 2,000
  m³/year by authorisation; above it a concession.

## Regional water laws

- **Canarias:** Ley 12/1990 de Aguas (BOE-A-1990-23087, consolidated 29/06/2026), art.
  73.2–73.3: any work to find or abstract groundwater needs the island water council's
  authorisation. Loaded as `lac-73-title`.
- **Andalusia:** above.
- **Every other region** read at the BOE's consolidated texts on 2026-11-26; none adds a
  condition to drilling a well, so each is loaded with no rules: Aragón (Ley 10/2014,
  BOE-A-2015-185), Asturias (Ley 1/1994, BOE-A-1994-10719), Cantabria (Ley 2/2014,
  BOE-A-2014-13624), Castilla-La Mancha (Ley 2/2022, BOE-A-2022-4920), Catalonia (Decreto
  Legislativo 3/2003, texto refundido de la legislación en materia de aguas), Valencia (Ley
  2/1992, BOE-A-1992-12147; its irrigation Ley 7/1986 was repealed in 2019), Extremadura
  (Ley 1/2023, BOE-A-2023-6662), Galicia (Ley 9/2010, BOE-A-2010-18559), Madrid (Ley
  17/1984, BOE-A-1985-2431), Murcia (Ley 3/2000, BOE-A-2001-542), Navarra (Ley Foral
  10/1988, BOE-A-1989-2954), País Vasco (Ley 1/2006, BOE-A-2011-17399), La Rioja (Ley
  5/2000, BOE-A-2000-20554), Illes Balears (Decreto Legislativo 1/2016, BOE-A-2016-4956).
  They set sanitation and water levies, metering and sanctions. Castilla y León has no
  water law; Ceuta and Melilla legislate none.

## Drilling permits beyond water law

- **Mining safety:** Real Decreto 863/1985, Reglamento General de Normas Básicas de Seguridad
  Minera (`https://www.boe.es/buscar/act.php?id=BOE-A-1985-10836`, consolidated 18/03/2010),
  arts. 108–109, and ITC 06.0.07 (Orden de 2 de octubre de 1985): a borehole for water
  needs a project signed by a competent technician and approved by the region's mining
  authority before drilling. Loaded as `rgnbsm-108-mining`, everywhere. `(BOE, 2026-11-26)`
- **Municipal licence:** needed for the works; not evaluated (MASTER_PLAN §4.5).

Copyright (c) 2026 Almoon-D. All rights reserved.
