# subphora

Subphora: mapa de probabilidad de agua subterránea para cualquier parcela de España — dónde buscar, a qué profundidad, con qué certeza y si se permite perforar.

## Ajustes de GitHub

GitHub no copia los ajustes de la plantilla al repositorio nuevo. Repásalos con
[`docs/GITHUB_SETTINGS.md`](docs/GITHUB_SETTINGS.md): cada opción de *Settings*, activa o no,
y por qué.

## Qué trae

| Pieza | Para qué |
|---|---|
| `AGENTS.md` (+ `CLAUDE.md`, `GEMINI.md`) | Manual del agente: qué leer, reglas, protocolo de PR → revisión → merge |
| `docs/sessions/` | Un archivo por sesión, desde la 00 (planificación); `make prompt S=00` imprime el prompt |
| `docs/decisions/` | Una decisión por archivo, con índice |
| `docs/ROADMAP.md`, `docs/MASTER_PLAN.md`, `docs/knowledge/` | Plan, estado y lo observado de servicios externos |
| `docs/GITHUB_SETTINGS.md` | Todos los ajustes de GitHub, opción por opción |
| `.claude/settings.json` | Al abrir una sesión de Claude Code en la nube, prepara el entorno sola (`make setup`) |
| `config/defaults/` + `config/owner.yaml` | Nada hardcodeado: valores por defecto y tus cambios |
| `src/subphora/` | El servidor (API FastAPI) y la línea de comandos |
| `web/` | La aplicación web: React, MapLibre, TypeScript |
| `deploy/` | Tu servidor en casa: Docker Compose, Caddy (HTTPS) y la guía paso a paso |
| `.github/workflows/ci.yml` | `make check` en cada PR (en segundos si solo cambian docs) |
| `.github/workflows/release.yml` | Publica la release cuando cambia la versión (la 0.0.0 no) |
| `.github/dependabot.yml` | Una tanda al mes, agrupada; CI mergea sola lo que no es major |

## Probarlo en tu PC

Necesitas [uv](https://docs.astral.sh/uv/) y Node 26 (la versión de `.nvmrc`; con nvm:
`nvm install` dentro del repositorio).

```
make setup                       # entorno de Python y del front end
uv run subphora users add <tú>   # tu usuario (te pide la contraseña dos veces)
make dev                         # arranca la API y la web; abre http://localhost:5173
```

La aplicación pide nombre y contraseña (en local, con Chrome o Firefox). Para tenerla en el
móvil, en tu mini PC con HTTPS y copias cada noche, sigue la guía
[deploy/GUIA.md](deploy/GUIA.md).

En la caja de búsqueda escribe cualquiera de estas cosas y pulsa *Buscar*:

- una referencia catastral: `0910001QD3101S` (el teatro romano de Mérida);
- una referencia SIGPAC, de parcela o de recinto: `34:48:0:0:13:12:1` (también `34:48:13:12:1`);
- una dirección o un municipio: `calle mayor 1 zaragoza`, `Daimiel`;
- unas coordenadas: `39.0675, -3.6115`, `40°25'0"N 3°42'13"O` o UTM `30 440000 4474000`
  (sin huso, la aplicación prueba los de España y se queda con los que caen en tierra).

Si el texto admite varias lecturas, te pregunta cuál querías. También puedes **dibujar un
punto o un polígono** en el mapa con los botones de debajo de la caja, o **un corte**: toca
el inicio y el final de una línea recta (de 100 m a 5 km) y debajo del mapa aparece el
corte geológico interpretativo del terreno bajo ella, con su confianza; toca cualquier
parte del corte para saber qué es y de dónde sale. El lugar elegido
aparece en amarillo sobre la ortofoto PNOA, con su ficha (provincia, superficie, fuente y
fecha); las áreas de la sesión quedan en una lista para volver a ellas (solo en esa
pestaña del navegador).

**Modo campo.** El botón *Modo campo* (arriba, junto al título) cambia el panel a botones
grandes para usar al aire libre: tu posición con su precisión y rumbo, y, si eliges uno de
los puntos candidatos del mapa detallado, la distancia y la dirección hasta él; dice
"Estás en el punto" solo a menos de 10 m y con una precisión de ±10 m o mejor. Registra
notas, fotos, notas de voz y la ruta: todo se guarda primero en el navegador, se envía al
servidor cuando hay conexión (sin duplicar nada) y queda en `data/field/`. El panel cuenta
lo que falta por enviar y lo exporta a un archivo. Para probarlo sin conexión: en el
navegador, herramientas de desarrollo → Red → *Sin conexión*, registra algo, vuelve a
conectar y mira cómo baja el contador; `uv run subphora field summary` cuenta lo recibido.

**Paquetes sin conexión.** Antes de ir al terreno, elige la zona (y calcula su mapa
detallado si quieres los candidatos) y pulsa *Descargar el paquete* en el apartado
*Paquetes sin conexión*: guarda en el navegador la ortofoto PNOA de la zona y 500 m
alrededor (zooms 10 a 18), el índice y su confianza, el contorno de la parcela y los
candidatos. Antes de descargar dice qué guarda, qué no (el mapa catastral nunca: sus
condiciones lo prohíben; se guarda el contorno de la parcela) y cuánto ocupará; rechaza
paquetes de más de 250 MB. Si la descarga se corta, *Reanudar* sigue donde quedó. Sin
cobertura, la página abre igualmente (aunque la recargues) y muestra la zona del paquete;
*Abrir* la vuelve a seleccionar y *Borrar* libera el espacio. Para probarlo: descarga un
paquete, pon el navegador *Sin conexión* y recarga.
**Tus pozos.** El apartado *Tus pozos* guarda tus pozos y sondeos: nombre, posición (toca
el mapa y pulsa *Usar el último punto tocado*), profundidad, caudal, fecha de perforación y
resultado (productivo, seco o sin saber), y sus lecturas de nivel con fecha. Si ya los
tienes en una hoja de cálculo, guárdala como CSV y súbela ahí mismo (o `uv run subphora
wells import pozos.csv`); vale el CSV de Excel en español, con `;` y coma decimal. En el
mapa detallado, la capa *Índice actualizado con tus pozos* sube el mapa alrededor de un
pozo productivo y lo baja alrededor de uno seco (cada pozo pesa la mitad a 150 m y nada a
más de 600 m, en `config/defaults/wells.yaml`); el índice original no cambia, para que
compares las dos capas. Tocar el mapa enseña los dos valores y qué pozos los separan.
*Comparar el mapa con mis pozos* mide si el mapa acierta con tus pozos, aparte de los del
IGME. Son datos privados: solo en tu servidor (`data/wells/`) y en su copia de cada noche;
no salen en el informe, y en el paquete solo si marcas la casilla.

`Ctrl-C` para ambos servidores. Las respuestas de Catastro, SIGPAC
y CartoCiudad se guardan en `data/cache/` (no se sube al repositorio).

## Comandos

```
make setup     # entorno de Python y del front end
make dev       # API + web en local
make check     # todo lo que corre CI (Python y web, con tests en navegador)
uv run subphora --help
uv run subphora national build --region ES-Z   # mapa nacional de una provincia
uv run subphora national build --all           # toda España (~5 GB libres, varias horas)
uv run subphora piezometry import              # niveles piezométricos (ver abajo)
uv run subphora field summary                  # lo registrado en campo que ha llegado
uv run subphora wells import|summary|validate  # tus pozos: importar un CSV, contarlos, medir el mapa
uv run subphora users add|password|remove|list # quién puede entrar
uv run subphora backup create|list|verify|restore  # copias de data/ (ver deploy/GUIA.md)
```

El mapa nacional se guarda en `data/national/` y `make dev` lo muestra al abrir el mapa.
Cada construcción compara el índice con los pozos públicos del IGME en cada masa de agua y
dice si acierta ("validado"), si no es mejor que el azar o si faltan pozos; ese acierto
entra en la confianza y tiene su propia capa.

**Profundidad y coste.** Descarga a mano la base de datos de piezometría del MITECO
(`basedatospiezometria.zip`, el formulario es para personas) y déjala en
`data/piezometry/`. Instala mdbtools (`brew install mdbtools` en macOS,
`apt install mdbtools` en Linux) y ejecuta `uv run subphora piezometry import`. Si además
dejas en `data/piezometry/basins/` las hojas del Júcar
(`F71_Puntos_de_control_piezometrico.zip`) y del Guadiana
(`Red Oficial Guadiana OCTUBRE 2026.xlsx`; si el nombre cambia, ajústalo en
`config/owner.yaml`), la importación añade sus niveles, que llegan hasta 2026. Desde
entonces cada punto candidato del mapa detallado muestra la profundidad estimada del agua
con su margen (o "desconocida" y por qué) y un rango de coste de perforación. Los precios
están en `config/defaults/drilling.yaml`; pon el presupuesto de tu pocero en
`config/owner.yaml` para sustituirlos.

**Informe y paquete profesional.** Con el mapa detallado de un área calculado, el panel
ofrece "Descargar el informe (PDF)" y "Descargar el paquete (ZIP)": el PDF es para un
hidrogeólogo o el organismo de cuenca; el ZIP añade las capas para un SIG (GeoPackage y
COG) y tablas CSV. Las fotos y notas de voz de campo solo entran si marcas la casilla. El
PDF necesita Pango y HarfBuzz: en macOS `brew install pango`; en Linux
`apt install libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0`.

La primera vez, `make check` descarga el Chromium de Playwright para los tests en
navegador.

Copyright (c) 2026 Almoon-D. All rights reserved.
