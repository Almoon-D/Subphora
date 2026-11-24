# Source-probe fixtures

Real responses, fetched on 2026-11-24 with the `subphora/0.1.0` User-Agent and trimmed only
by removing whole elements (styles, tile matrices, operations metadata, filter
capabilities). Third-party data: exempt from the copyright notice.

| File | Request | Trimmed |
|---|---|---|
| `catastro_wms_capabilities.xml` | `https://ovc.catastro.meh.es/cartografia/INSPIRE/spadgcwms.aspx?SERVICE=WMS&REQUEST=GetCapabilities&VERSION=1.3.0` | `Style`, INSPIRE extended capabilities, `Exception` |
| `catastro_rejected.html` | the same request with curl's default User-Agent: HTTP 400 | no |
| `catastro_wms_map.png` | GetMap `CP.CadastralParcel`, EPSG:3857, BBOX `-951500,5293500,-950900,5294100` (Santiago de Compostela), 256 px | no |
| `catastro_wfs_capabilities.xml` | `https://ovc.catastro.meh.es/INSPIRE/wfsCP.aspx?service=WFS&request=GetCapabilities` | operations metadata, filter capabilities |
| `catastro_wfs_parcel.xml` | `…/wfsCP.aspx?…&STOREDQUERY_ID=GetParcel&refcat=7279701NH3477G&srsname=EPSG::25830` (the public parcel of the Praza do Obradoiro, Santiago de Compostela) | no |
| `catastro_wfs_not_found.xml` | the same with `refcat=29015A16799999`: HTTP 200 with an `ExceptionReport` | no |
| `capabilities_truncated.xml` | the first 1,500 bytes of `catastro_wms_capabilities.xml` (a malformed document) | cut |
| `ign_pnoa_wmts_capabilities.xml` | `https://www.ign.es/wmts/pnoa-ma?request=GetCapabilities&service=WMTS` | `TileMatrix`, `TileMatrixSetLimits`, operations metadata |
| `ign_mdt_wcs_capabilities.xml` | `https://servicios.idee.es/wcs-inspire/mdt?request=GetCapabilities&service=WCS` | no |
| `igme_lithostrat_wms_capabilities.xml` | `https://mapas.igme.es/gis/services/Cartografia_Tematica/IGME_Litoestratigrafico_200/MapServer/WMSServer?request=GetCapabilities&service=WMS` (offers no EPSG:3857) | `Style` |
| `miteco_wfs_capabilities.xml` | `https://gis.miteco.gob.es/geoserver/agua/estado_masas_aguasub_2027/ows?SERVICE=WFS&REQUEST=GetCapabilities` | operations metadata, filter capabilities |
| `sigpac_ogcapi_collections.json` | `https://sigpac-hubcloud.es/ogcapi/collections?f=json` | no |
| `sigpac_recinfo.json` | `https://sigpac-hubcloud.es/servicioconsultassigpac/query/recinfo/34/48/0/0/13/12/1.json` (an enclosure in Tierra de Campos) | no |
