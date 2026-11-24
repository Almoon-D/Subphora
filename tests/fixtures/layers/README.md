# Official-layer fixtures

Real responses fetched on 2026-11-24 with the `subphora/0.2.1` or `0.3.0` User-Agent, untrimmed
unless the table says so. Each GetFeatureInfo asked for an image centred on a public place, at its
centre pixel.
Third-party data: exempt from the copyright notice.

| File | Request |
|---|---|
| `miteco_piezometer.json` | MITECO `RedPiezometrica` GetFeatureInfo, `application/json`, at piezometer 04.04.207 (Villarta de San Juan) |
| `igme_magna_dip.json` | IGME MAGNA WMS layer `6` GetFeatureInfo, `application/geo+json`, at a bedding measurement of sheet 610 (Cuenca) |
| `igme_permeability.xml` | IGME permeability 1:200,000 GetFeatureInfo, `text/xml` (ArcGIS `FeatureInfoResponse`), near the Ciudad Encantada (Cuenca) |
| `igme_exception.xml` | IGME MAGNA layer `0` GetFeatureInfo asked for `text/xml`: HTTP 200, `ServiceExceptionReport` "InvalidXslTemplate" |
| `igme_geode_tenerife.json` | IGME GEODE WMS layer `1` GetFeatureInfo, `application/geo+json`, near La Orotava (Tenerife), where MAGNA has no lithology |
| `igme_geode_sea.json` | the same off the coast of Málaga: an empty FeatureCollection |
| `igme_lithostrat_export.png` | IGME lithostratigraphic map, ArcGIS REST `export` in EPSG:3857, 16 pixels square, near the Ciudad Encantada (Cuenca) |
| `idena_soils_tafalla.json` | IDENA `EDAFOL_Pol_Suelos25m` GetFeatureInfo, `application/json`, near Tafalla (Navarra); trimmed to its first feature, geometry removed |
| `icgc_hydrogeology_manresa.xml` | ICGC `unitats_hidrogeologiques_tipus` GetFeatureInfo, `text/xml`, near Manresa (Catalonia) |
| `rediam_preventive_dalias.gml` | REDIAM `masas_agua_subt_intracom` GetFeatureInfo, `application/vnd.ogc.gml`, in the Campo de Dalías (Almería) |
| `rediam_preventive_empty.gml` | the same in Málaga, outside any body under preventive control: an empty `msGMLOutput` |
| `miteco_at_risk_daimiel.json` | MITECO `masas_aguasub_riesgo_2027` GetFeatureInfo, `application/json`, near Daimiel; trimmed to its first feature, geometry removed |
