# myproject

Una frase: qué hace y para quién.

## Cómo usar esta plantilla (borra esta sección después)

1. En GitHub, en la plantilla: **Use this template → Create a new repository**, público o
   privado. Sin marcar *Include all branches*: el proyecto nuevo empieza sin historial y en
   la versión 0.0.0.
2. Ajustes del repositorio nuevo: la lista corta al principio de
   [`docs/GITHUB_SETTINGS.md`](docs/GITHUB_SETTINGS.md).
3. Abre una sesión de Claude Code (Opus 5.5) en el repositorio nuevo con este prompt:
   `Ejecuta la sesión 00: make prompt S=00`. Te entrevista, renombra el proyecto, escribe el
   plan y los prompts de las sesiones siguientes. Cada sesión deja preparada la siguiente.
4. Revisa la licencia: por defecto es AGPL-3.0 (`LICENSE` y `license` en `pyproject.toml`).
   Si el proyecto necesita otra, díselo a la sesión 00.

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
uv run myproject --help
```

Copyright (c) 2027 AlmoonD. All rights reserved.
