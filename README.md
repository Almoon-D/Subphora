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
| `.github/workflows/ci.yml` | `make check` en cada PR (en segundos si solo cambian docs) |
| `.github/workflows/release.yml` | Publica la release cuando cambia la versión (la 0.0.0 no) |
| `.github/dependabot.yml` | Una tanda al mes, agrupada; CI mergea sola lo que no es major |

## Comandos

```
make setup     # entorno + hooks
make check     # todo lo que corre CI
uv run subphora --help
```

Copyright (c) 2026 Almoon-D. All rights reserved.
