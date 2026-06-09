# chefai — Design Spec

**Date:** 2026-06-09
**Status:** Approved for planning

## 1. Summary

chefai is a single-user (household), **phone-first local web app**, hosted on a DietPi and served on the home LAN. It manages a cooking-related **state** — pantry/groceries, household & dietary profile, owned tools, and cooking skills — and turns that state into **copy-paste LLM prompts** for recipes and meal plans.

chefai **never calls an LLM itself**. It builds a complete context + prompt that the user copies into the LLM of their choice. For meal plans (and optionally saved recipes), the user pastes the LLM's **structured reply back** into chefai, which parses and stores it so the app can offer per-meal actions, shopping lists, and a cookbook.

The UI is in **French by default**, with a language selector for future locales.

## 2. Goals & non-goals

**Goals**
- Low-friction pantry management on a phone (optional quantity, optional expiry).
- Generate tailored LLM prompts for: cook-with-what-I-have, cook-with-small-shop, and multi-day meal planning.
- Round-trip meal plans back into the app: validate one of 3 proposals → per-meal cooking prompts + a store-grouped shopping list.
- Reduce food waste via an expiry-driven "à consommer bientôt" view.
- An offline-capable shopping mode usable at the store (off the home network).
- A cookbook with a guided cooking mode (step checklist + timers).

**Non-goals (v1)**
- No direct LLM API integration (pure copy-paste).
- No precise quantity bookkeeping. (Completing cooking mode does a **best-effort, confirmation-based** pantry decrement — see §5.6 — but the app does not maintain exact running inventory.)
- No multi-user accounts / auth (trusted home LAN, single household). Multiple phones on the LAN may use the app **concurrently against one shared dataset** (one pantry, profile, cookbook, plan); concurrent edits are last-write-wins, acceptable for low household traffic. The only per-device state is the offline shopping tick-state in `localStorage`, which does not sync between phones.
- No barcode scanning, nutrition tracking, or prompt-history (possible later — see §12).

## 3. Architecture

One lightweight service on the DietPi:

```
Browser (phone)
  │  HTML + HTMX partials + Alpine.js (clipboard/paste/timers) + Tailwind (precompiled)
  ▼
FastAPI  ──  Jinja2 templates (server-rendered)
  ├── prompt_builder/   pure functions: (pantry, profile, tools, skills, params, lang) → prompt text
  ├── response_parser/  pure functions: pasted LLM text → validated Pydantic objects
  ├── routers/          home, pantry, generate, plan, shopping, cookbook, settings
  ├── i18n/             translation catalogs (FR default), Settings.language selects locale
  └── db                SQLite via SQLModel
```

- `prompt_builder` and `response_parser` are **pure and isolated** (no DB, no web) → trivially unit-testable. Each generation flow is a function asserting its required context/constraints are present.
- Everything else is thin CRUD + template rendering + HTMX partial swaps.
- Tailwind is **precompiled at build time** (no runtime CDN dependency).

### Deployment
- `Dockerfile` + `docker-compose.yml`; `uvicorn` serving FastAPI.
- **SQLite database on a named volume / bind-mount** plus a small `data/` dir for backups → data persists across container rebuilds and DietPi reboots.
- Binds `0.0.0.0:<port>` for LAN access. `docker compose up -d` is the entire deploy; restarts on reboot.
- Served over plain HTTP on the LAN (see §8 offline caveat). HTTPS-PWA is a documented future upgrade.

## 4. Data model (SQLite)

- **PantryItem** — `name`, `category`, `quantity_text?` (free text: "low" / "500 g" / "3"), `expiry_date?`, `is_staple` (bool; excluded from shopping lists, decrement, and rendered in the compact staples line — see §5; **defaults to true** for the spices & condiments / oils & vinegars categories, user-overridable), `created_at`, `updated_at`.
- **Settings** (singleton) — `household_size`, `default_cook_time`, `language` (default `fr`); free-text fields: `restrictions`, `allergies`, `dislikes`, `consumption_habits` (diet goals / general habits), `tools_notes`, `skills_notes`.
- **Tool** — `name`, `enabled`. Seeded with a curated starter list.
- **Skill** — `name`, `enabled`. Seeded with a curated starter list.
- **PlanningSession** — `params_json` (n_days, lunch/dinner toggles, leftover-reuse, servings, cravings), `proposals_json` (the 3 returned plans, stored verbatim until one is chosen), `status` (`proposed` / `validated` / `cancelled`), `created_at`.
- **Meal** — belongs to a validated `PlanningSession`: `day_index`, `slot` (lunch/dinner), `title`, `ingredients_json`, `leftover_link?`, `notes`. Drives a per-meal "generate cooking prompt" button.
- **Recipe** (cookbook) — `title`, `ingredients_json`, `steps_json` (ordered steps, each with optional `duration_seconds` for timers), `source`, `tags`, `created_at`.
- **ShoppingItem** — `name`, `qty_text?`, `category`, `store_type` (boucherie / poissonnerie / primeur / boulangerie / fromagerie / épicerie-supermarché / autre), `checked` (bool), `source` (plan / recipe / manual). Checking an item creates/updates a `PantryItem`.

**Editable enumerations** (in Settings): pantry **categories** (default: fridge, freezer, fresh produce, dry/pantry, spices & condiments, oils & vinegars, other) and shopping **store types**.

## 5. Features & flows

A **base context** is always injected into every generated prompt: household size, dietary restrictions, allergies, dislikes, consumption habits/diet goals, enabled tools, skill level/notes, and language.

**Pantry rendering in prompts (two groups).** To keep prompts focused, `prompt_builder` splits the pantry:
- **Ingrédients principaux** — non-staple items (proteins, produce, dairy, leftovers): listed individually *with* quantity + expiry, since these constrain what can be cooked.
- **Épices, huiles & condiments** — `is_staple` items: rendered as a single **compact, names-only line** (no quantity, no expiry), so the LLM knows the full seasoning shelf (including unusual items like miso, harissa, nuoc-mam) without clutter.

Token cost of the staples line is negligible; the split is purely to keep recipe suggestions focused on the constraining ingredients.

1. **Cuisiner — Avec mes ingrédients** ("cook with what I have")
   - Params: max cook-time, free-text cravings, meal type, servings.
   - Prompt instructs the LLM to use **only pantry items**. Output: 3 recipe ideas.
   - Action: green **"Générer le prompt"** CTA (visually distinct, anchored at the bottom of the screen) → copies prompt to clipboard.
   - *Optional:* paste a chosen recipe back → saved to **Cookbook**.

2. **Cuisiner — Avec petites courses** ("cook with a small shop")
   - Same params + a "max extra items" knob.
   - Prompt permits a handful of bought ingredients and asks the LLM to **list them separately**.
   - *Optional:* paste-back → those extras become a **shopping list** (store-tagged).

3. **Cuisiner — Planifier la semaine** ("plan my week")
   - Params: n days, lunch/dinner toggles, leftover-reuse on/off, servings, cravings.
   - Prompt instructs the LLM to return **3 plans as fenced JSON** in a defined schema (days → slots → meals + ingredients + leftover links + a consolidated, store-tagged shopping list).
   - Flow: copy prompt → paste reply back → `response_parser` validates & stores 3 proposals → user browses → **validate one** (or cancel).
   - Validation materializes `Meal` rows + a `ShoppingItem` set. Each meal exposes a **"générer le prompt de cuisine"** button → a detailed single-meal recipe prompt (full method, scaled servings, leftover notes).

4. **À consommer bientôt** (home)
   - Surfaces items nearing expiry; one-tap builds a *"prioritize these expiring items"* prompt (otherwise like flow 1).

5. **Mode courses** (shopping mode)
   - Big tick-boxes, items **grouped by store type** (boucherie, poissonnerie, …).
   - **Offline-capable**: rendered fully client-side; tick-state persisted in `localStorage`, so it works at the store with no LAN connection. Checking an item flows it into the pantry on next sync.

6. **Recettes — mode cuisine** (cooking mode)
   - Full-screen guided cooking: ingredient checklist, step-by-step list with **tick-boxes per step**, and **tap-to-start timers** on steps that carry a duration; screen stays awake.
   - **Pantry decrement on completion**: finishing cooking mode (not cancelling) opens a *"mettre à jour le garde-manger"* review screen. chefai matches the recipe's ingredients to pantry items by normalized name and **pre-fills proposed changes**:
     - both sides parse to a number + compatible unit → propose subtraction; if the result ≤ 0, propose removal.
     - free-text / unit-mismatch / fuzzy-matched items → flagged with quick **épuisé** (remove) / **il en reste** (keep) toggles.
     - `is_staple` items are skipped entirely.
   - The user confirms (one tap) or tweaks, then changes are applied transactionally. Cancelling cooking mode applies nothing.

## 6. UI / navigation (layout A, French)

Bottom tab bar (chosen layout A): **Accueil · Garde-manger · Cuisiner · Courses · Recettes**. **Réglages** via a ⚙️ icon in the header.

- **Accueil** — "à consommer bientôt" alerts, quick actions, active-plan summary.
- **Garde-manger** — pantry grouped by category; fast add (name + optional qty + optional expiry).
- **Cuisiner** — segmented control for the three generators; params above; green "Générer le prompt" CTA at the bottom (distinct, smaller, bottom-anchored).
- **Courses** — list builder + mode courses (offline, store-grouped tick-boxes).
- **Recettes** — cookbook list → recipe detail → mode cuisine.
- **Réglages** — profile & diet free-texts, tools & skills checklists, editable categories & store-types, language selector.

## 7. Error handling

- **Paste-back parsing**: lenient JSON extraction (locate the fenced block within surrounding prose) → Pydantic validation → on failure, a clear French message (e.g. *"réponse non reconnue — vérifiez que vous avez copié le bloc complet"*) with a re-paste box. **Never half-saves** (transactional).
- All quantity/expiry fields are **optional**; the only required field is an item name.
- Plan **validate / cancel** are explicit and reversible until validated.

## 8. Offline caveat (recorded)

Over plain LAN HTTP there is **no service worker** (secure-context requirement). Shopping mode therefore relies on a self-contained client-side render + `localStorage`. Normal lock/unlock at the store works; in the rare case the browser fully evicts the tab from memory, a one-time reload on home wifi is needed. The drop-in upgrade is to serve chefai over HTTPS (self-signed cert trusted once on the phone) and register a service worker, making the whole app reliably offline.

## 9. Testing (TDD)

- **Unit** — `prompt_builder` (assert each flow injects the correct base context + constraints), `response_parser` (well-formed and malformed LLM samples; store-type tagging; step/duration extraction), and the **pantry-decrement matcher** (name normalization, numeric+unit parse/subtract, zero→removal, free-text/unit-mismatch flagged for confirmation, staples skipped).
- **Integration** — FastAPI `TestClient` per router: pantry CRUD; plan validate → meals + shopping items; shopping-check → pantry upsert; cookbook paste-back → structured steps.
- **Fixtures** — seeded pantry/profile/tools/skills; sample LLM responses as test data files.

## 10. CI/CD & documentation

- **GitHub Actions CI** (`.github/workflows/build.yml`):
  - Triggers on push to the default branch and on version tags.
  - Lints + runs the pytest suite (unit + integration).
  - Builds the Docker image with `docker/build-push-action` + `buildx`/QEMU for **multi-arch** targets (`linux/amd64`, `linux/arm64`, `linux/arm/v7`) so the image runs on a DietPi (ARM SBC) as well as x86.
  - Publishes to **GHCR** (`ghcr.io/<owner>/chefai`), tagged with `latest` and the git SHA / version tag.
- **README.md** with a deployment tutorial:
  - What chefai is + the copy-paste LLM model in one paragraph.
  - Quick start: `docker compose up -d`, the published GHCR image, and the env/port/volume config.
  - DietPi deployment walkthrough: pulling the multi-arch image, the `docker-compose.yml`, the **persistent volume** for the SQLite DB, finding the LAN address, opening it on a phone, and "add to home screen".
  - Backup/restore of the SQLite database file.
  - The HTTPS-PWA upgrade path (from §8) as an optional advanced section.

## 11. Tech stack

- **Backend:** Python, FastAPI, SQLModel (SQLite).
- **Frontend:** Jinja2 server-rendered, HTMX for partial updates, Alpine.js for clipboard/paste/timers, Tailwind (precompiled).
- **Packaging:** Docker + docker-compose, SQLite on a persistent volume.
- **PWA:** manifest + "add to home screen"; full offline (service worker) deferred to an HTTPS deployment.

## 12. Deferred / follow-on features

- **Barcode scanning** — deferred. Requires a **secure context (HTTPS)** for camera access (`getUserMedia`), so it lands alongside the optional HTTPS deployment from §8. Implementation: `@zxing/browser` (or native `BarcodeDetector`) for EAN-13 capture, plus product resolution via either a **local barcode→name map** (offline, name-on-first-scan) or the **Open Food Facts API** (needs outbound internet; strong FR coverage). Only helps barcoded packaged goods, not loose produce/leftovers.
- Auto prompt/response history, recipe ratings, nutrition goals, custom prompt templates — possible later, out of v1 scope.
