# Parcel lookup fixtures

Real responses from Catastro (`ovc.catastro.meh.es`), fetched on 2026-11-24 with the
`subphora/0.1.2` User-Agent, untrimmed. Every place is public: a cathedral square, a
volcano and a railway station. Third-party data: exempt from the copyright notice.

| File | Request |
|---|---|
| `wfs_santiago_4326.xml` | `/INSPIRE/wfsCP.aspx?service=WFS&version=2.0.0&request=GetFeature&STOREDQUERY_ID=GetParcel&refcat=7279701NH3477G&srsname=EPSG::4326` (Praza do Obradoiro, Santiago de Compostela): latitude, longitude order |
| `wfs_tinajo_4326.xml` | the same with `refcat=35029A03200314` (Volcán Montaña Tinga, Tinajo, Lanzarote): one polygon with 16 holes. Asking for `EPSG::4083` returned the same body, still in EPSG:4326 |
| `wfs_invalid_length.xml` | the same with `refcat=12345`: HTTP 200, `ExceptionReport` "Invalid length of REFCAT parameter" |
| `dnprc_santiago.json` | `/OVCServWeb/OVCWcfCallejero/COVCCallejero.svc/json/Consulta_DNPRC?RefCat=7279701NH3477G`: one property (`bico`) |
| `dnprc_tinajo.json` | the same with `RefCat=35029A03200314`: a rustic property |
| `dnprc_atocha_several.json` | the same with `RefCat=1532704VK4713C` (Estación Puerta de Atocha, Madrid): several properties (`lrcdnp`) |
| `dnprc_not_found.json` | the same with `RefCat=29015A16799999`: error code 5 |

The not-found WFS answer and a parcel in EPSG:25830 are in `../sources/`
(`catastro_wfs_not_found.xml`, `catastro_wfs_parcel.xml`).
