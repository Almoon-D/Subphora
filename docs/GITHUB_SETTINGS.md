# Ajustes de GitHub

GitHub **no copia los ajustes** al crear un repositorio con *Use this template*: solo copia
los archivos. Esta guía se repasa una vez en cada proyecto nuevo, sección por sección del
menú *Settings*, en el mismo orden. Está escrita para un proyecto **privado con el plan
Free**; si el proyecto es público, aplica además la última sección. Lo que esta guía no
menciona se deja como viene. "—" = no aparece en un repo privado con el plan Free.

## Lo que hay que cambiar (el resto de la guía explica cada opción)

1. *General → Releases*: **Enable release immutability** ✅.
2. *General → Features*: **Wikis**, **Projects** ❌ (Discussions y Sponsorships ya vienen ❌).
3. *General → Pull Requests*: **Allow merge commits** ❌ y **Allow rebase merging** ❌; squash
   con **Pull request title and description**; **Automatically delete head branches** ✅.
4. *Actions → General*: solo las acciones permitidas (lista abajo), **Require actions to be
   pinned to a full-length commit SHA** ✅, *Workflow permissions* de solo lectura.
5. *Advanced Security*: **Dependency graph**, **Dependabot alerts**, **Malware alerts**,
   **Dependabot security updates**, **Grouped security updates** ✅; **Automatic dependency
   submission** ❌; **Push protection** ✅ si aparece.
6. *Settings → Applications → Claude* (de tu cuenta): acceso al repo nuevo.
7. Si es público: la última sección.
8. La tarea mensual de mantenimiento: pídesela a Claude en cualquier chat o sesión, por
   ejemplo *"Crea una tarea programada el día 2 de cada mes en el repo `<repo>` con el prompt:
   Ejecuta la sesión de mantenimiento: make prompt S=maintenance"* (el día 2, para que el lote
   de Dependabot del día 1 ya esté abierto).
9. Una sola vez para todos tus repos: el presupuesto de Actions de 0 € de tu cuenta (al
   final de esta guía), si aún no lo tienes.

## General

| Opción | Valor | Por qué |
|---|---|---|
| Template repository | ❌ | Solo la plantilla es plantilla. |
| Default branch | `main` | Los workflows y AGENTS.md cuentan con `main`. |
| Releases → Enable release immutability | ✅ | Una release publicada no se puede alterar; el workflow nunca la modifica. |
| Wikis | ❌ | Ver nota 1. |
| Issues | ✅ | Para apuntar fallos o ideas desde el móvil; la planificación vive en `docs/`. |
| Sponsorships | ❌ | Necesita un perfil de GitHub Sponsors (alta con datos bancarios y fiscales). |
| Discussions | ❌ | Foro para comunidades; no la hay. |
| Projects | ❌ | Ver nota 2. |
| Pull requests | ✅ | Todo entra por PR. |
| Allow merge commits | ❌ | Un solo método: squash. |
| Allow squash merging | ✅ | Un commit por sesión en `main`. |
| → Default commit message | Pull request title and description | El commit guarda el plan y el checklist del PR. |
| Allow rebase merging | ❌ | Un solo método. |
| Always suggest updating pull request branches | ❌ | Cada actualización vuelve a pasar CI. |
| Allow auto-merge | — (gris) | No hace falta: el agente mergea sus PRs y CI mergea los de Dependabot. |
| Automatically delete head branches | ✅ | Borra la rama al mergear, también las de Dependabot. |
| Require contributors to sign off on web-based commits | ❌ | Requisito legal (DCO) de proyectos con muchos contribuidores. |
| Allow comments on individual commits | ✅ | Como viene. |
| Archives → Include Git LFS objects in archives | ❌ | No usamos LFS. |
| Pushes → Limit how many branches and tags can be updated in a single push | ❌ | Freno para repos con muchos usuarios; las sesiones empujan una rama cada vez. |
| Issues → Auto-close issues with merged linked pull requests | ✅ | "Fixes #12" en un PR cierra el issue 12. |
| Danger Zone | nada | |

**Nota 1 — Wikis.** Son páginas de documentación fuera del código, editables desde la web y
guardadas en un repositorio aparte. Los agentes no las ven al clonar, no se revisan en los PRs
y se desincronizan del código. Toda la documentación va en `docs/`, versionada con el código.
En repos privados con el plan Free, además, no existen.

**Nota 2 — Projects o `docs/ROADMAP.md`.** ROADMAP. Projects es un tablero tipo Trello sobre
issues, útil para equipos de personas. Para un dueño con sesiones de IA pierde en todo:
- *Organización*: ROADMAP se actualiza en el mismo PR que el código, así que nunca dice algo
  distinto de lo que hay en `main`; un tablero se actualiza aparte y se queda atrás.
- *Calidad para la IA*: la sesión lee ROADMAP al clonar, sin permisos extra; Projects exige la
  API GraphQL con un permiso (`project`) que las sesiones no suelen tener, y su contenido no
  pasa por la revisión del PR.
- *Tokens*: el agente lee de ROADMAP solo la sección que necesita (`grep` + rango de líneas);
  la API de Projects devuelve JSON con todos los campos de cada tarjeta.

## Access

| Opción | Valor | Por qué |
|---|---|---|
| Collaborators | solo tú | Quien tenga acceso de escritura puede mergear. |

## Code and automation

| Sección | Valor | Por qué |
|---|---|---|
| Branches (reglas clásicas) | nada | En privado con el plan Free no protegen nada; en público se usan Rulesets. |
| Tags | nada | La inmutabilidad de releases ya protege sus tags. |
| Rules → Rulesets | — | Los repos privados con el plan Free no los tienen. |
| Actions | ver abajo | |
| Models | nada | GitHub Models (IA de GitHub); usamos Claude. |
| Webhooks | nada | Avisan a otros servicios (Discord, un servidor…). Solo si el proyecto lo necesita, con una decisión en `docs/decisions/`. |
| Copilot | todo desactivado | Revisión y agente de Copilot gastan peticiones de pago y duplican la revisión que ya hace Claude. |
| Copilot → Dreaming | ❌ | Mejora la memoria de Copilot; no lo usamos (y pide un plan de pago de Copilot). |
| Environments | nada al empezar | Cuando el proyecto despliegue, un environment `production` guarda sus secretos y puede exigir tu aprobación. |
| Codespaces → Prebuild configuration | nada | Prepara entornos de Codespaces; trabajas con Claude Code. |
| Pages → Build and deployment | Source: *Deploy from a branch*, Branch: **None** | Así Pages queda desactivado; no publicamos una web. |

**Actions → General.**
- *Actions permissions*: **Allow Almoon-D, and select non-Almoon-D, actions and
  reusable workflows**, con **Allow actions created by GitHub** y, en la lista,
  `astral-sh/setup-uv@*, dependabot/fetch-metadata@*`. Una acción nueva en un workflow se
  añade aquí en el mismo momento.
- **Require actions to be pinned to a full-length commit SHA**: ✅ (todas lo están).
- *Workflow permissions*: **Read repository contents and packages permissions**; **Allow
  GitHub Actions to create and approve pull requests**: ❌. Los workflows que escriben
  (release, el merge de Dependabot) piden su propio permiso.
- *Runners*, *Caches*: nada.

## Security → Advanced Security

**Dependabot**

| Opción | Valor | Por qué |
|---|---|---|
| Dependency graph | ✅ | Base de las alertas. |
| Automatic dependency submission | ❌ | uv no la necesita; gasta ejecuciones. |
| Dependabot alerts | ✅ | |
| Malware alerts | ✅ | Avisa si una dependencia resulta ser malware. |
| Dependabot auto-triage rules → Dismiss low-impact alerts for development-scoped dependencies | ✅ (como viene) | Descarta avisos de poco riesgo en herramientas de desarrollo (pytest, ruff…), que no corren en producción. |
| Dependabot auto-triage rules → Dismiss package malware alerts | ❌ (como viene) | Un aviso de malware nunca se descarta solo. |
| Dependabot security updates | ✅ | Abre el arreglo en cuanto sale un aviso; CI lo mergea si no es major. |
| Grouped security updates | ✅ | Un PR por ecosistema en lugar de uno por paquete. |
| Dependabot version updates | ya configurado | Lo define `.github/dependabot.yml`; no se toca desde aquí. |
| Dependabot on Actions runners | ✅ (como viene) | Sus trabajos son gratis. |

**Code security**

| Opción | Valor | Por qué |
|---|---|---|
| CodeQL analysis | — | En privado con el plan Free no está disponible. |
| Other tools | nada | |
| AI Scan (for repositories, for pull requests, for AI applications) | ❌ | Gastan créditos de IA de pago. |
| Copilot Autofix | como viene | Sin CodeQL no hace nada. |
| Agentic autofix | ❌ | Gasta créditos de IA y abre PRs de Copilot. |
| Protection rules → Check runs failure threshold | como viene | Solo actúa con CodeQL y un ruleset. |

**Secrets y otros**

| Opción | Valor | Por qué |
|---|---|---|
| Secret Protection / Push protection | ✅ si aparece | Bloquea un push que contenga una clave. |
| Deploy keys | nada | |
| Secrets and variables → Actions | solo lo que pida un workflow | Nunca credenciales de producción (AGENTS.md). |
| Secrets and variables → Dependabot / Codespaces | nada | |

## Integrations

| Opción | Valor | Por qué |
|---|---|---|
| GitHub Apps | Claude | La app de Claude necesita acceso al repo para las sesiones. |
| Email notifications | nada | |
| Autolink references | nada | Enlaza referencias a gestores externos (Jira…). |

## Tu cuenta (una sola vez, vale para todos los repos)

- *Settings → Billing and licensing → Budgets and alerts*: presupuesto de **Actions** de 0 €
  con **Stop usage when budget limit is reached**. Nunca pagas por error.
- *Settings → Planning* (Issue types, Issue fields): nada. Clasifican issues para equipos;
  aquí la planificación vive en `docs/`.
- *Settings → Applications → Claude*: acceso al repositorio nuevo (o a todos).

## Si el proyecto es público

Los minutos de Actions son gratis y aparecen opciones que en privado no existen:

- *General → Features*: en **Issues** y **Pull requests**, *Creation allowed by:*
  **Collaborators only**.
- *Actions → General → Approval for running fork pull request workflows*: **Require approval
  for all external contributors**.
- *Rules → Rulesets → New branch ruleset*: nombre `main`; *Enforcement status*: **Active**;
  *Bypass list* vacía; *Target branches*: **Include default branch**; marca **Restrict
  deletions**, **Block force pushes**, **Require a pull request before merging** (0
  aprobaciones) y **Require status checks to pass** → `ci`. El check `ci` siempre informa,
  también en PRs de solo documentación, así que no bloquea nada que deba pasar.
- *Advanced Security*: **CodeQL analysis → Set up → Default** si el proyecto tiene código
  propio; **Private vulnerability reporting** solo si tiene usuarios que puedan avisarte.
