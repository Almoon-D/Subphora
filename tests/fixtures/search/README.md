# Search fixtures

Real responses from SIGPAC (`sigpac-hubcloud.es/servicioconsultassigpac/query`) and
CartoCiudad (`www.cartociudad.es/geocoder/api/geocoder`), fetched on 2026-11-25, untrimmed
unless stated. Every place is public: farmland in Tierra de Campos and Málaga, a square in
Daimiel, a doorway on Zaragoza's Calle Mayor, the centre of Lisbon, a hillside on
Lanzarote. Third-party data: exempt from the copyright notice.

| File | Request |
|---|---|
| `sigpac_enclosure_campos.geojson` | `/recinfo/34/48/0/0/13/12/1.geojson`: one enclosure, 6.2744 ha |
| `sigpac_parcel_malaga.geojson` | `/recinfoparc/29/15/0/0/167/21.geojson`: a parcel of 13 enclosures |
| `sigpac_not_found.geojson` | `/recinfo/29/15/0/0/167/99999/1.geojson`: no feature, `"crs": ""` |
| `sigpac_point_daimiel.json` | `/recinfobypoint/4258/-3.6115/39.0675.json`: province 13; the enclosure's 76 KB WKT outline replaced by a square (unused) |
| `sigpac_point_lanzarote.json` | `/recinfobypoint/4258/-13.63/29.03.json`: province 35 |
| `sigpac_point_lisbon.json` | `/recinfobypoint/4258/-9.14/38.72.json`: an empty list |
| `cand_daimiel.json` | `/candidates?q=Daimiel&limit=8`: towns, the municipality, streets |
| `cand_mayor_zaragoza.json` | `/candidates?q=calle mayor 1 zaragoza&limit=8`: doorways |
| `cand_empty.json` | `/candidates?q=xqzzyvw&limit=5`: an empty list |
| `find_daimiel_muni.json` | `/find?id=13039&type=Municipio`: the municipality's MULTIPOLYGON |
| `find_portal_zaragoza.json` | `/find?id=02.50.G50_502970206939&type=portal`: a POINT |
| `find_street.json` | `/find?id=130390004129&type=callejero`: a MULTILINESTRING |
