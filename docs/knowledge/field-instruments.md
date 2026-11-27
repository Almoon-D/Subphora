# Field instruments

The live survey behind decision 0042: what each instrument costs, how deep it sees, what it
can and cannot detect in the main Spanish settings, how hard it is to build, its electrical
safety and how mature its open sources are. Prices are as each page showed them, with the
currency and tax the page stated; "estimate" marks a figure not read from a page. Findings
observed on 2026-11-27 unless tagged otherwise.

## Sources read

| Topic | Page | What it gave |
|---|---|---|
| OhmPi | `https://ohmpi.gitlab.io/ohmpi/` (documentation v2024: overview, boards specifications, power supply, measurement board v2024, MUX v2024 and v2023 pages) | specifications, bills of materials, configurations, safety warnings |
| OhmPi | `https://gitlab.com/ohmpi/ohmpi/-/raw/master/CHANGELOG.txt` | current release v2024.1.0, field checklist added |
| OhmPi | `https://zenodo.org/records/18643763` (HardwareX paper, published 2026-02-14, version V2024) | "under €1500 for 16 electrodes"; licences |
| OhmPi | `https://github.com/ohmpi/ohmpi` (mirror; canonical repository on GitLab) | licence files |
| Inversion and HVSR software | PyPI JSON for `pygimli`, `resipy`, `hvsrpy`, `simpeg` | versions and licences |
| HVSR | `https://raspberryshake.org/shop/product/rs3d`, `https://raspberryshake.org/media/global-technical-specifications.pdf`, `https://community.raspberryshake.org/t/portable-rs3d-usage-for-hvsr/5111`, `https://www.epa.gov/environmental-geophysics/passive-seismic-hvsr` | prices, sensor band, field use, method limits |
| VLF | `https://www.epa.gov/environmental-geophysics/very-low-frequency-electromagnetic-vlf`, `https://geonics.com/html/vlfsystems.html`, `https://gi.copernicus.org/articles/11/279/2022/` | method, instruments, the nearest open design |
| Magnetic resonance | Uriarte Blanco et al. 2011, Boletín Geológico y Minero 122(3) 345-362, `https://info.igme.es/media/boletin/2011/122_3/Articulo_5.pdf` | MRS used in Spain (Duero basin, IGME and UPM, NumisLITE) |
| Contracted work | `https://www.habitissimo.es/presupuestos/realizar-estudio-hidrogeologico` (updated 2026-09-16), `https://www.rs-ingenieria.es/estudios-hidrogeologicos/`, `https://www.rs-ingenieria.es/estudio-geofisica-electrica/`, `https://www.rs-ingenieria.es/detector-de-agua/`, `https://www.igeas.es/cuanto-cuesta-hacer-un-pozo-de-agua/` (2026-07-24), `https://afincamundorural.com/mas-alla-de-las-varillas-del-zahori-tecnicas-geofisicas-modernas-sondeo-electrico-tomografia-para-encontrar-agua-subterranea/` (2026-11-12), `https://hidrosondeos.es/blog/sondeos/precio-sondeo-de-agua` (2026-05-17) | study, geophysics and drilling prices in Spain |
| Positioning | `https://www.ardusimple.com/?p=1766`, `https://www.ardusimple.com/?p=556`, `https://www.ign.es/resources/docs/IGNCnig/Condiciones-uso-SPTR-Spain.pdf`, `https://datos-geodesia.ign.es/Documentos/SPTR/SPTR_Revista_Tramos_2025.pdf`, `https://www.juntadeandalucia.es/institutodeestadisticaycartografia/rap/sites/default/files/public/101-rap-faq-sobre-la-rap.pdf` | receiver prices and accuracy; the public correction services |
| Level meters and loggers | `https://www.fondriest.com/solinst-model-101-p2-probe-water-level-meters.htm`, Amazon.es listing B0F5WXG16J, `https://reach.dog/shop/envirotech-services/products/solinst-model-3001-levelogger-5-junior`, `https://www.usabluebook.com/barologger-5-barometric-pressure-monitor-114608-53535`, `https://www.intercyprus.com/products/submersible-water-level-sensor-4-20ma-rs485-hydrostatic-liquid-level-sensor-0-10v-0-5m-liquid-water-level-transmitter`, `https://ie.rs-online.com/web/p/level-sensors/2690086`, `https://certification.oshwa.org/mx000038.html`, `https://github.com/rhpearce/waterdepthsensor` | prices, accuracy, open designs |

Pages that refused automated reads: the PMC copy of the OhmPi paper (a browser check),
Certicalia's price pages (client error), GeoSeek (robots file unreachable), Fondriest's
Levelogger pages (403), `ergnss-tr.ign.es` (robots file unreachable).

## Manual water-level meter (dipper)

- A probe on a graduated tape that beeps when it touches water; it reads depth to water in
  an existing well to the millimetre. It measures water directly, needs no current in the
  ground and has no safety risk beyond the well head.
- Solinst 101 with P2 probe, metric: 30 m $657.40, 60 m $809.40, 100 m $961.40, 150 m
  $1,257.80 (Fondriest, USD, no tax shown). The P2 probe is "not suitable for submergence to
  any significant depth"; the P7 probe is submersible to 300 m (RS Hydro, no price shown).
- Generic 20-100 m meters on Amazon.es: one listing at €559.67. Wellsquip (Spain) sells
  50-500 m meters on quote only (`equipozo.com/sondas`).
- A home-made dipper (two-wire probe, buzzer, a 100 m tape): estimate €60-100 in parts; less
  rugged, and the tape's marks become the accuracy.
- What it adds: the owner's own water levels, the one measurement that the well registry
  (decision 0040) and depth to water (0031) already know how to use.

## Resistivity: vertical electrical sounding (VES) and tomography (ERT)

- What it measures: the ground's electrical resistivity with depth. Gravel and clean sand
  with fresh water read higher than clay and marl; clay, marl and salty water all read low,
  so a low reading is ambiguous without geology or a well. It sees layers and contacts, not
  water itself. Depth reached, as a rule of thumb (not a page): VES about a quarter to a
  sixth of the current electrodes' spread AB; ERT about a fifth of the line's length.
- OhmPi (current release v2024.1.0, CHANGELOG): measurement board v2024.0.2 alone is a
  4-electrode meter (A, B, M, N); multiplexer boards add electrodes. Specifications page:
  max permissible Vab 200 V DC (2023 board: 24 V), 12 V supply, current 0.11-50 mA with the
  2 Ω shunt (48 mA limit; 1 Ω or 0.5 Ω for 100 or 200 mA), pulses 50 ms to 15 s, Vmn input
  1000 MΩ, ±5 V, operating -25 to 50 °C. The v2024 board isolates the Vmn side (Mikroe I2C
  isolator) and has a discharge relay since v2024.1.0.
- Power: a 12 V battery injects 12 V directly, or the DPH5005 boost converter "allows to
  inject up to 50 V" and regulates it, controlled by the Raspberry Pi over USB (power page).
- Bills of materials on the documentation (EUR excluding VAT): measurement board v2024
  **€461.08** (including a pack of 3 PCBs at €70 from Aisler); MUX v2024 board €120.36 (16
  electrodes in 2-role mode, two boards per 16-electrode system); MUX v2023 boards for 64
  electrodes (PCBs at €140 each). The paper: "under €1500 for 16 electrodes" for a system.
  The Raspberry Pi, the DPH5005, batteries, cables and electrodes are not in the board BOMs.
- Configurations the documentation recommends: field monitoring with 8-48 electrodes on
  MUX v2024 and a DPH5005; 4 electrodes with no MUX for laboratory samples. A 4-electrode
  field sounding is the measurement board alone with the electrodes moved by hand.
- Build: through-hole soldering, PCBs ordered from the KiCad files, IDC ribbon cables. The
  documentation warns: "it requires skills in electronics and to respect the safety rules",
  must be "assembled in a professional context and by people competent in electronics",
  and "Always check with a resistor board before going on the field". No assembled kit or
  vendor is listed. Help is on Discord and GitLab issues.
- Communication: Raspberry Pi with a web interface and MQTT (`run_http_interface.sh`,
  `start_mqtt_html.py`); readings saved as files on the Pi.
- Licences: hardware CERN-OHL-S-2.0 (strongly reciprocal), software GPL-3.0-or-later,
  documentation CERN-OHL-P v2 and CC BY-SA 4.0 (Zenodo record, repository, documentation).
- Inversion: pyGIMLi 1.6.1, Apache-2.0 (1D VES and 2D ERT); ResIPy 3.6.6, GPL-3.0 (OhmPi's
  installer offers it); SimPEG 0.26.0, MIT (PyPI).
- Other low-cost designs: Cruz Júnior et al. 2023, "Design and construction of an automated
  and programmable resistivity meter for shallow subsurface investigation" (GI 12, 15-23,
  CC BY 4.0); none has OhmPi's community, documentation or releases.

## Passive seismic (HVSR)

- What it measures: the resonance frequency f0 of soft sediment over hard bedrock, from
  ambient noise at one point; thickness h = Vs / (4 f0) for a simple two-layer ground, and
  it needs at least a 2:1 impedance contrast at the contact (EPA). It gives sediment
  thickness over bedrock, not water.
- Raspberry Shake 3D: $954.99-1,404.99 (DIY kit, indoor, outdoor; USD). Three 4.5 Hz
  geophones electronically extended below 1 Hz; -3 dB at 0.7 Hz on V7+ (specification PDF).
  At 0.7 Hz and Vs 400 m/s the deepest contact is about 140 m (h = Vs / 4 f0; the Vs is an
  assumption). Field use runs on a battery pack (a user's portable build: a little over
  5 hours; "about as portable and faster to deploy" than a commercial unit; a Tromino
  estimated at about 4 times the cost).
- Processing: hvsrpy 2.1.0, GPL-3.0-or-later (PyPI); the SESAME guidelines for practice.

## VLF electromagnetics

- Passive; uses military radio transmitters at 15-30 kHz; suits "near-vertical planar
  contacts and/or conductive bodies" such as fracture zones in resistive rock, to about
  200 m in "highly resistive country rock", far less in conductive ground; topography gives
  false positives and negatives; qualitative without modelling (EPA).
- Instruments: Geonics EM16 and EM16R (no price on the maker's page), with a portable
  transmitter (TX27, a grounded wire about 1 km long) for when broadcasts are weak.
- No open VLF receiver found. The nearest open design (Wilson et al. 2022, GI 11, 279-291,
  CC BY 4.0) is an active 0.4/1.6 kHz induction instrument, "under USD 400" to build, read
  with a multimeter; its data on request, no repository.
- Which European transmitters are on air now was not verified.

## Contracted surveys and studies in Spain

- Hydrogeological study: €800 rural, €1,000 urban, €1,300 for a well, €1,600 with
  geotechnics; travel from €200 (Habitissimo, 2026-09-16); €300-1,200 (IGEAS); desk study
  without a visit from €220 + VAT (RS-Ingeniería).
- VES (SEV): "desde unos pocos cientos de euros" per point, cheaper per point for several;
  ERT: "en el rango de miles de euros" for several hundred metres (Afinca Mundo Rural). Firms
  quote per site (RS-Ingeniería: SEV, ERT, self-potential, Schlumberger, Wenner,
  dipole-dipole; report 3 days after the field day).
- TEM and magnetic resonance (MRS): no Spanish price found. MRS has been used in Spain by
  IGME and UPM (NumisLITE, Duero basin, 2011); it is the one method sensitive to water
  itself (water content and an estimate of transmissivity) and needs low electromagnetic
  noise, so it is research-grade, not a contractor's catalogue item.
- Drilling: €25-60/m (IGEAS), €35-40/m at 220 mm (RS-Ingeniería: a dry 100 m hole costs
  €3,500-4,000), €60-150/m and €7,000-12,000 for 100 m (Hidrosondeos, 2026-05-17).
- "Water detectors": RS-Ingeniería's page says antenna and frequency devices "no miden
  ninguna propiedad física conocida del agua"; the non-goals already exclude them.

## Positioning

- Phone GPS: a few metres. A VES is one point; its centre a few metres off changes nothing,
  and the electrode spacings come from a tape. An ERT line needs spacings to centimetres
  (tape) and its elevations, which the IGN elevation model already gives the app.
- RTK: ArduSimple simpleRTK2B Basic Starter Kit (ZED-F9P with a multiband antenna) 211,00
  (currency not shown; ships from Spain); "<1cm with NTRIP up to 35km", "<1.5m in
  standalone mode"; USB-C, Bluetooth only through an add-on.
- Corrections: IGN's Servicio de Posicionamiento en Tiempo Real is public and free, built
  from the national ERGNSS stations and the regional networks under agreement, a few
  centimetres, after a registration form; Andalusia's RAP gives NTRIP after asking for a
  user by e-mail.

## Level loggers

- Solinst Levelogger 5 Junior $534.56 (0.1 % FS); Barologger 5 $384 excluding tax (USD).
  Levelogger 5: ±0.05 % FS, 10-year battery, no price shown.
- Industrial submersible transmitter: WIKA LF-1, 0-1 bar, €809.86 excluding VAT. Generic
  0-5 m 4-20 mA / RS485 sensor: €107.89 on sale (no VAT note).
- Open designs: ESPiezometer (ESP32-C3 for RS485 piezometric sensors, OSHWA MX000038,
  certified 2025-10-24; CERN-OHL-W-2.0, GPL-3.0-only); King's College's Arduino depth logger
  (CC BY 4.0, tested 6 months against a Levelogger Junior; Sensors 24(8) 2488, 2024).
- A vented-cable sensor reads depth directly; an absolute one needs a barometer at the
  well (a Barologger serves wells within about 30 km).

## Fit by setting

| | Karst limestone | Sedimentary basin with marls | Hard-rock massif |
|---|---|---|---|
| Dipper in a well | levels, any depth | levels | levels |
| VES (4 electrodes) | weak: caves and fractures break the layered assumption | good: sand and gravel against clay and marl, to tens of metres | good for the weathered mantle's thickness |
| ERT (16-32 electrodes) | shallow fractures and clay-filled pockets, tens of metres | good: lateral changes, channel deposits | good: fracture zones as low-resistivity bands |
| HVSR | poor: no soft cover over hard rock | good: basin fill thickness | good: mantle thickness over fresh rock |
| VLF | some, for fracture zones | poor: conductive ground | classic for fracture zones |
| Contracted deep ERT, TEM | for a deep water table | for deep aquifers below 60 m | rarely needed |

Copyright (c) 2026 Almoon-D. All rights reserved.
