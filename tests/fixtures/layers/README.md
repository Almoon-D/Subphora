# Official-layer fixtures

Real responses fetched on 2026-11-24 with the `subphora/0.2.1` or `0.3.0` User-Agent, untrimmed. Each
GetFeatureInfo asked for a 101-pixel image centred on a public place, at its centre pixel.
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
