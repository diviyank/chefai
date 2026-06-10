# chefai

Single-household, **phone-first local web app** served on the home LAN (DietPi). It manages a cooking
**state** — pantry/groceries, dietary profile, owned tools, cooking skills — and turns that state into
**copy-paste LLM prompts** for recipes and meal plans.

**chefai builds copy-paste LLM prompts by default, and can optionally call Claude directly** when
`ANTHROPIC_API_KEY` is set and the Settings "Générer directement avec Claude" toggle is on. The direct
path (`app/llm_client.py`, Sonnet 4.6) parses the reply and integrates it; on any failure it falls back
to the copy-paste prompt. In copy-paste mode the user pastes the LLM's **structured reply back**, which
chefai parses and stores so it can offer per-meal actions, shopping lists, and a cookbook. See
`docs/superpowers/specs/2026-06-10-chefai-claude-api-design.md`. UI is **French by default**
(`app/locales/fr.json`), with a language selector for future locales.

Full design rationale lives in `docs/superpowers/specs/2026-06-09-chefai-design.md`. Read it before
changing behavior — this file is the working summary, the spec is the source of truth.

## Architecture

One FastAPI service, server-rendered Jinja2 + HTMX partials + Alpine.js, Tailwind precompiled at build.

```
app/
  main.py            FastAPI app, startup (init_db + seed), router auto-registration
  config.py          REPO_ROOT, DB_PATH (CHEFAI_DB_PATH env), APP_TITLE
  db.py              SQLite engine + init via SQLModel
  models.py          SQLModel tables (PantryItem, Settings, Tool, Skill, PlanningSession, Meal, Recipe, ShoppingItem)
  schemas.py         Pydantic schemas for parsed LLM responses
  enums.py           categories, store types, meal slots, etc.
  seed.py            seeds Settings singleton + curated Tool/Skill starter lists
  prompt_builder.py  PURE: (pantry, profile, tools, skills, params, lang) -> prompt text
  response_parser.py PURE: pasted LLM text -> validated Pydantic objects
  decrement.py       PURE: pantry-decrement matcher (cooking-mode completion)
  i18n.py            t() translation lookup, registered as a Jinja global
  routers/           home, pantry, generate, plan, shopping, cookbook, settings
  templates/         Jinja2; partials/ are HTMX swap fragments (leading _ )
  static/            css (Tailwind), js/app.js, vendor/ (htmx, alpine), manifest
```

### Core invariant — keep the pure modules pure
`prompt_builder`, `response_parser`, and `decrement` have **no DB and no web imports**. They are the
heart of the app and are trivially unit-testable. Everything in `routers/` is thin CRUD + template
rendering + HTMX partial swaps that calls into these pure functions. Do not push business logic into
routers or pull DB access into the pure modules.

### Key behaviors
- **Pantry split in prompts**: non-staple "Ingrédients principaux" listed with qty + expiry; `is_staple`
  items rendered as one compact names-only "Épices, huiles & condiments" line. `is_staple` defaults true
  for spices/condiments and oils/vinegars categories.
- **Base context** is injected into every generated prompt (household size, restrictions, allergies,
  dislikes, habits, enabled tools, skills, language).
- **Paste-back parsing** is lenient (find the fenced JSON block in surrounding prose) → Pydantic validate
  → on failure show a clear French message + re-paste box. **Never half-saves** — transactional.
- **Plan flow**: prompt asks for 3 plans as fenced JSON → parse → store 3 proposals verbatim → user
  validates one → materializes `Meal` rows + `ShoppingItem` set.
- **Shopping mode** is offline-capable: client-side render, tick-state in `localStorage` (per-device,
  does not sync). Checking an item upserts a `PantryItem`.
- **Cooking-mode completion** runs `decrement.py`: numeric+compatible-unit → propose subtraction (≤0 →
  removal); free-text / unit-mismatch / fuzzy matches → flagged for confirmation; `is_staple` skipped.
  Applied transactionally on confirm; cancelling applies nothing.

### Non-goals (v1)
Optional direct Claude API calls are key-gated; copy-paste remains the default-capable fallback. No auth
(trusted LAN, single shared dataset, last-write-wins), no exact inventory bookkeeping, no
barcode/nutrition/prompt-history. See spec §2 and §12.

## Development

```bash
pip install -e '.[dev]'                                  # install with dev extras
uvicorn app.main:app --reload --port 1212                # run locally (DB at ./data/chefai.db)
pytest                                                    # full unit + integration suite
pytest tests/test_prompt_builder.py                       # single file
```

- Python 3.11+. Tests use FastAPI `TestClient` (one file per router) plus unit tests for the pure modules.
- **TDD**: write the failing test first. The pure modules (`prompt_builder`, `response_parser`,
  `decrement`) are where most logic lives and where tests give the most leverage.
- User-facing strings go through `i18n.t()` and `app/locales/fr.json`, never hardcoded in templates.
- Style: self-documenting code over comments. Use `rg`/`fd` over grep/find.

## Build & deploy

- **Docker**: multi-stage `Dockerfile` (Tailwind standalone CSS build → python:3.11-slim runtime).
  Tailwind is **pinned to v3.4.17** — v4 silently drops the theme color utilities this app uses.
  htmx/alpine are vendored at build time so the image is CDN-free. Serves on `0.0.0.0:1212`.
- **Compose**: `docker-compose.yml` pulls the GHCR image; `docker-compose.build.yml` is a build override.
  SQLite lives on the `chefai-data` named volume at `/data`.
- **CI** (`.github/workflows/build.yml`): lint + pytest, then buildx multi-arch (`linux/amd64`,
  `linux/arm64`) → push to GHCR. `arm/v7` was dropped (no uvloop/httptools wheels).
- **Packaging gotcha**: `pyproject.toml` pins `packages = ["app"]` — the runtime-created `data/` dir
  otherwise breaks setuptools flat-layout discovery ("Multiple top-level packages").
