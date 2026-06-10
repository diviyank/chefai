# chefai — Direct Claude API inference (design)

**Date:** 2026-06-10
**Status:** Approved (brainstorming)
**Supersedes (partially):** the "no LLM API calls" non-goal in
`docs/superpowers/specs/2026-06-09-chefai-design.md` §2 / §12.

## 1. Summary

chefai today builds copy-paste LLM prompts and parses the reply the user pastes
back. This design adds an **optional, key-gated direct inference mode**: when an
Anthropic API key is configured, the app calls Claude itself, parses the reply,
and integrates the result directly — eliminating the manual copy-paste hop. The
copy-paste workflow remains as a **fallback** whenever no key is configured, the
API errors, or the reply fails to parse.

Model: **Claude Sonnet 4.6** (`claude-sonnet-4-6`). At the expected volume
(~2–3 calls/day, ≈60–90/month) the estimated cost is **~$3–8/month** — cost is
not a deciding factor; Sonnet is chosen for quality on multi-constraint tasks
(allergies + restrictions + dislikes + leftover-linking + French).

## 2. Core principle — preserve the pure-module invariant

`prompt_builder` and `response_parser` remain pure (no DB, no web, no SDK). The
human transport hop between them is replaced by exactly one new impure module
that imports the Anthropic SDK. Nothing else gains a network/SDK import.

```
prompt_builder.build_*()  →  llm_client.complete(prompt)  →  response_parser.parse_*()
        (pure)                   (NEW — only impure bit)              (pure)
```

The API path and the copy-paste path share **one** parsing path: `llm_client`
returns raw reply text and hands off to the existing lenient `response_parser`.

## 3. New module: `app/llm_client.py`

The single place that touches `anthropic`.

- `is_configured() -> bool` — true when `ANTHROPIC_API_KEY` is set.
- `complete(prompt: str) -> str` — sends one user message, returns reply text.
  - Uses the SDK's **streaming** internally
    (`client.messages.stream(...).get_final_message()`) so large meal-plan
    outputs don't hit HTTP timeouts; presents a single synchronous result to the
    caller.
  - Model from `CHEFAI_LLM_MODEL` env (default `claude-sonnet-4-6`),
    `max_tokens ≈ 8000`, adaptive thinking (`thinking={"type": "adaptive"}`).
  - Raises a typed `LLMError` on auth / rate-limit / network / refusal so routers
    can fall back cleanly.
- Returns **raw text** → handed to the existing `response_parser.parse_*`.

Structured outputs (`client.messages.parse()` / `output_config.format`) are noted
as a **future hardening**, not used in v1 — the existing lenient parser is reused
to keep a single parsing path shared with the copy-paste flow.

## 4. Flow-by-flow integration

| Flow | Today | Direct-API path |
|---|---|---|
| **Meal plan** (`/plan/generate`) | build prompt → user pastes back → `parse_plan_response` | If configured: `complete()` → `parse_plan_response` → store proposals → render `plan_proposals.html` directly. Else: today's prompt partial. |
| **Meal recipe** (`/plan/meal/{id}/prompt`) | prose + trailing recipe JSON, paste-back save | If configured: `complete()` → `parse_recipe_response` → render recipe + save. Else: today's prompt. |
| **Cook-with-have / shop / use-it-up** | 2-turn prose-then-JSON | **New one-shot prompt variant** requesting **3 full recipes as a JSON array**; **new** `RecipeListResponse` schema + `parse_recipe_list_response`. API path renders 3 recipe cards (tap to save/cook). **Copy-paste fallback keeps today's prose prompt unchanged.** |

Pure additions (all unit-testable, no DB/web):

- `prompt_builder`: one-shot JSON variants for the three cook flows
  (e.g. `build_cook_with_have_json`, `build_cook_with_shop_json`,
  `build_use_it_up_json`), each accepting an optional `exclude: list[str] = None`.
- `prompt_builder.build_plan`: gains the same optional `exclude` param.
- `schemas`: `RecipeListResponse` (`recipes: list[RecipeResponse]`, expecting 3).
- `response_parser`: `parse_recipe_list_response`.

## 5. "Générer d'autres recettes / plans" button (re-roll)

- Rendered on every direct-API result (the 3 recipe cards, and the 3 plans).
- HTMX POST back to the same generate endpoint, carrying the already-shown titles
  in a hidden `exclude_titles` field.
- The matching `prompt_builder` function appends a
  *"Ne propose pas à nouveau ces recettes : X, Y, Z."* clause from `exclude`.
- Stays stateless (titles ride on the request) and keeps `prompt_builder` pure.
- Lives on the **API path only** (it re-calls Claude). The copy-paste fallback is
  unchanged (no re-roll button).

## 6. Config & secrets

- API key via `ANTHROPIC_API_KEY` env (standard SDK resolution; injected through
  docker-compose). **Never stored in SQLite** — it is a secret and matches the
  project's `.env` rule.
- `CHEFAI_LLM_MODEL` env override (default `claude-sonnet-4-6`).
- One new `Settings` boolean `use_llm_directly` (default `true`) to disable the
  direct path without removing the key. Because the app provisions schema via
  `create_all` (no migration tool), `init_db()` also runs an idempotent
  `_ensure_settings_columns()` backfill so a pre-existing `chefai.db` gains the
  column on startup rather than crashing.
- The UI shows the "Générer avec Claude" direct action only when
  `llm_client.is_configured() and settings.use_llm_directly`.

## 7. UX & error handling

- Synchronous HTMX POST with an `hx-indicator` spinner (meal plans ~5–20s). No
  streaming-to-browser in v1.
- **Any** failure — not configured, `LLMError`, or `ParseError` — falls back to
  rendering the existing copy-paste prompt partial **plus a short French note**
  (e.g. *"Génération directe indisponible — copiez le prompt ci-dessous."*).
- Storage stays transactional; **never half-saves** (unchanged invariant).

## 8. Testing

- `prompt_builder` / `response_parser` additions: pure unit tests (new JSON cook
  prompts, the `exclude` clause, `parse_recipe_list_response`).
- `llm_client`: the Anthropic call is **mocked** — no real network in the suite.
- Router tests via `TestClient` with a fake `complete` injected (dependency
  override), covering both the success path and the fall-back-to-prompt path
  (LLMError and ParseError).
- Add `anthropic` to `dependencies` in `pyproject.toml`.

## 9. Docs / spec changes

- Amend `2026-06-09-chefai-design.md` §2 / §12: the "never calls an LLM / no LLM
  API calls" non-goal is **reversed for an optional, key-gated direct mode**;
  copy-paste remains the default-capable fallback. This document is the source of
  truth for the API integration.
- Update `CLAUDE.md` working summary accordingly (the "chefai never calls an LLM
  itself" line gains the key-gated-direct-mode exception).

## 10. Non-goals (v1)

No streaming-to-browser, no structured-outputs enforcement, no conversation
history / multi-turn, no per-request model selection, no key-management UI, no
cost metering / usage dashboard, no re-roll on the copy-paste fallback.
