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

Escribe una referencia catastral (por ejemplo `0910001QD3101S`, el teatro romano de Mérida)
y pulsa *Buscar*: la parcela aparece perfilada en amarillo sobre la ortofoto PNOA, con el
plano catastral encima al acercarte. `Ctrl-C` para ambos servidores. Las respuestas de
Catastro se guardan una semana en `data/cache/` (no se sube al repositorio).

## Comandos

```
make setup     # entorno de Python y del front end
make dev       # API + web en local
make check     # todo lo que corre CI (Python y web, con tests en navegador)
uv run subphora --help
```

La primera vez, `make check` descarga el Chromium de Playwright para los tests en
navegador.

Copyright (c) 2026 Almoon-D. All rights reserved.
