# Master plan

The design. Sessions build it; they do not relitigate it. A change of design is an owner
decision, recorded in `docs/decisions/` and then reflected here.

## 1. Goal

<!-- What the project must do, for whom, and what "done" looks like. -->

## 2. Non-goals

<!-- What it will never do. The hard rules in AGENTS.md come from here. -->

## 3. Constraints

<!-- Budget (free tiers, LLM spend), data sources, jurisdiction, runtime, deployment. -->

## 4. Architecture

<!-- Components and how data flows between them. Each boundary becomes an import-linter
     contract in pyproject.toml. -->

## 5. Layout

```
src/subphora/
  domain/     frozen models, imports nothing else of ours
  config/     settings schema and loader
```

## 6. Build path

<!-- The ordered sessions and what each delivers; the table itself lives in docs/ROADMAP.md. -->
