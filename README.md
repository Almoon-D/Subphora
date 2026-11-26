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
| `.github/workflows/ci.yml` | `make check` en cada PR (en segundos si solo cambian docs) |
| `.github/workflows/release.yml` | Publica la release cuando cambia la versión (la 0.0.0 no) |
| `.github/dependabot.yml` | Una tanda al mes, agrupada; CI mergea sola lo que no es major |

## Probarlo en tu PC

Necesitas [uv](https://docs.astral.sh/uv/) y Node 26 (la versión de `.nvmrc`; con nvm:
`nvm install` dentro del repositorio).

```
make setup     # entorno de Python y del front end
make dev       # arranca la API y la web; abre http://localhost:5173
```

En la caja de búsqueda escribe cualquiera de estas cosas y pulsa *Buscar*:

- una referencia catastral: `0910001QD3101S` (el teatro romano de Mérida);
- una referencia SIGPAC, de parcela o de recinto: `34:48:0:0:13:12:1` (también `34:48:13:12:1`);
- una dirección o un municipio: `calle mayor 1 zaragoza`, `Daimiel`;
- unas coordenadas: `39.0675, -3.6115`, `40°25'0"N 3°42'13"O` o UTM `30 440000 4474000`
  (sin huso, la aplicación prueba los de España y se queda con los que caen en tierra).

Si el texto admite varias lecturas, te pregunta cuál querías. También puedes **dibujar un
punto o un polígono** en el mapa con los botones de debajo de la caja. El lugar elegido
aparece en amarillo sobre la ortofoto PNOA, con su ficha (provincia, superficie, fuente y
fecha); las áreas de la sesión quedan en una lista para volver a ellas (solo en esa
pestaña del navegador). `Ctrl-C` para ambos servidores. Las respuestas de Catastro, SIGPAC
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

La primera vez, `make check` descarga el Chromium de Playwright para los tests en
navegador.

Copyright (c) 2026 Almoon-D. All rights reserved.
