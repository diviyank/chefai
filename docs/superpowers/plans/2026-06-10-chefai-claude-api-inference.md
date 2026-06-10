# Direct Claude API Inference — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an optional, key-gated mode where chefai calls Claude itself (parsing the reply and integrating it directly), with the existing copy-paste workflow kept as a fallback.

**Architecture:** One new impure module `app/llm_client.py` is the only thing that imports the Anthropic SDK. `prompt_builder` and `response_parser` stay pure and are reused by both paths: `prompt_builder` output → `llm_client.complete()` → `response_parser`. Routers gain a "configured? → call Claude → parse → render cards / else fall back to the prompt" dispatch. Cook flows are reshaped to return 3 full recipes as one JSON array; a re-roll button re-calls Claude with the already-shown titles excluded.

**Tech Stack:** FastAPI, SQLModel/SQLite, Jinja2 + HTMX, Pydantic, `anthropic` Python SDK, pytest + FastAPI `TestClient`.

**Reference spec:** `docs/superpowers/specs/2026-06-10-chefai-claude-api-design.md`

---

## File Structure

**Create:**
- `app/llm_client.py` — `is_configured()`, `get_model()`, `complete(prompt)`, `LLMError`. Only SDK-touching module.
- `app/templates/partials/_recipe_cards.html` — renders N recipe cards (save form + re-roll button).
- `app/templates/partials/_plan_proposals_cards.html` — proposal cards + validate/cancel/re-roll (extracted so both the full page and the direct path reuse it).
- `tests/test_llm_client.py` — unit tests with the SDK faked.

**Modify:**
- `pyproject.toml` — add `anthropic` dependency.
- `app/schemas.py` — add `RecipeListResponse`.
- `app/response_parser.py` — add `parse_recipe_list_response`.
- `app/prompt_builder.py` — add `RECIPE_LIST_JSON_SCHEMA`, `_exclude_clause`, `build_cook_with_have_json`, `build_cook_with_shop_json`, `build_use_it_up_json`, and an `exclude` param on `build_plan`.
- `app/models.py` — add `Settings.use_llm_directly: bool = True`.
- `app/routers/generate.py` — `respond_with_recipes` helper, `_split_titles`/`_join_titles`, `FALLBACK_NOTICE`, `notice` on `_prompt_response`; direct path on `/cook/have` and `/cook/shop`.
- `app/routers/home.py` — direct path on `/use-it-up`.
- `app/routers/plan.py` — direct path on `/plan/generate` + `/plan/meal/{id}/prompt`; new `/plan/{ps_id}/regenerate`.
- `app/routers/settings.py` — persist `use_llm_directly`; expose `api_configured` to the page.
- `app/templates/partials/_prompt_result.html` — optional `notice` banner.
- `app/templates/plan_proposals.html` — include the new cards partial.
- `app/templates/cook.html` — `hx-indicator` spinner on the forms.
- `app/templates/settings.html` — direct-mode toggle + "clé API détectée" indicator.
- `tests/conftest.py` — `fake_llm` fixture.
- `tests/test_schemas.py`, `tests/test_response_parser.py`, `tests/test_prompt_builder.py`, `tests/test_models.py`, `tests/test_generate_routes.py`, `tests/test_home_routes.py`, `tests/test_plan_routes.py`, `tests/test_settings_routes.py` — new tests.
- `CLAUDE.md`, the 2026-06-09 spec — amend the "never calls an LLM" non-goal.

---

## Task 1: Add the `anthropic` dependency

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add `anthropic` to dependencies**

In `pyproject.toml`, change the `dependencies` list to include `anthropic`:

```toml
dependencies = [
    "fastapi>=0.110,<0.116",
    "uvicorn[standard]>=0.29",
    "sqlmodel>=0.0.16",
    "jinja2>=3.1",
    "python-multipart>=0.0.9",
    "anthropic>=0.40",
]
```

- [ ] **Step 2: Install it**

Run: `pip install -e '.[dev]'`
Expected: installs `anthropic` and its deps with no errors.

- [ ] **Step 3: Verify the import works**

Run: `python -c "import anthropic; print(anthropic.__version__)"`
Expected: prints a version string (e.g. `0.40.0` or newer).

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "build: add anthropic SDK dependency"
```

---

## Task 2: `RecipeListResponse` schema

**Files:**
- Modify: `app/schemas.py`
- Test: `tests/test_schemas.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_schemas.py`:

```python
def test_recipe_list_response_parses_multiple_recipes():
    from app.schemas import RecipeListResponse
    data = {"recipes": [
        {"title": "Curry", "ingredients": [{"name": "Riz"}], "steps": [{"text": "Cuire"}]},
        {"title": "Salade", "ingredients": [], "steps": []},
    ]}
    parsed = RecipeListResponse.model_validate(data)
    assert len(parsed.recipes) == 2
    assert parsed.recipes[0].title == "Curry"
    assert parsed.recipes[0].ingredients[0].name == "Riz"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_schemas.py::test_recipe_list_response_parses_multiple_recipes -v`
Expected: FAIL with `ImportError: cannot import name 'RecipeListResponse'`.

- [ ] **Step 3: Add the schema**

In `app/schemas.py`, after the `RecipeResponse` class, add:

```python
class RecipeListResponse(BaseModel):
    recipes: list[RecipeResponse] = Field(default_factory=list)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_schemas.py::test_recipe_list_response_parses_multiple_recipes -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/schemas.py tests/test_schemas.py
git commit -m "feat: add RecipeListResponse schema"
```

---

## Task 3: `parse_recipe_list_response` parser

**Files:**
- Modify: `app/response_parser.py`
- Test: `tests/test_response_parser.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_response_parser.py`:

```python
RECIPE_LIST_OK = '''Voici 3 idées :
```json
{"recipes":[
  {"title":"Curry","ingredients":[{"name":"Riz","qty":"200 g"}],"steps":[{"text":"Cuire"}]},
  {"title":"Soupe","ingredients":[],"steps":[]},
  {"title":"Salade","ingredients":[],"steps":[]}
]}
```'''

def test_parse_recipe_list_response_ok():
    parsed = rp.parse_recipe_list_response(RECIPE_LIST_OK)
    assert [r.title for r in parsed.recipes] == ["Curry", "Soupe", "Salade"]

def test_parse_recipe_list_response_empty_raises():
    with pytest.raises(rp.ParseError):
        rp.parse_recipe_list_response('```json\n{"recipes":[]}\n```')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_response_parser.py::test_parse_recipe_list_response_ok -v`
Expected: FAIL with `AttributeError: module 'app.response_parser' has no attribute 'parse_recipe_list_response'`.

- [ ] **Step 3: Add the parser**

In `app/response_parser.py`, update the import line and add the function. Change:

```python
from .schemas import PlanResponse, RecipeResponse, ShoppingResponse
```

to:

```python
from .schemas import PlanResponse, RecipeResponse, RecipeListResponse, ShoppingResponse
```

Then add at the end of the file:

```python
def parse_recipe_list_response(text: str) -> RecipeListResponse:
    parsed = _parse(text, RecipeListResponse)
    if not parsed.recipes:
        raise ParseError(ERROR_MSG)
    return parsed
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_response_parser.py -v`
Expected: PASS (all, including the two new ones).

- [ ] **Step 5: Commit**

```bash
git add app/response_parser.py tests/test_response_parser.py
git commit -m "feat: add parse_recipe_list_response"
```

---

## Task 4: One-shot cook JSON prompts + `exclude` clause

**Files:**
- Modify: `app/prompt_builder.py`
- Test: `tests/test_prompt_builder.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_prompt_builder.py`:

```python
def test_cook_have_json_asks_for_three_recipe_array():
    prompt = pb.build_cook_with_have_json(PROFILE, TOOLS, SKILLS, PANTRY,
                                          {"max_time": 25, "cravings": "", "servings": 2, "meal": "diner"})
    assert '"recipes"' in prompt        # array schema present
    assert '"steps"' in prompt and '"ingredients"' in prompt
    assert "uniquement" in prompt.lower()
    assert "3" in prompt or "trois" in prompt.lower()

def test_cook_shop_json_mentions_extra_limit():
    prompt = pb.build_cook_with_shop_json(PROFILE, TOOLS, SKILLS, PANTRY,
                                          {"max_time": 30, "cravings": "", "servings": 2, "max_extra": 4})
    assert '"recipes"' in prompt and "4" in prompt

def test_use_it_up_json_lists_expiring_and_array_schema():
    prompt = pb.build_use_it_up_json(PROFILE, TOOLS, SKILLS, PANTRY, ["Poulet"], {"max_time": 30})
    assert '"recipes"' in prompt and "Poulet" in prompt

def test_cook_have_json_excludes_seen_titles():
    prompt = pb.build_cook_with_have_json(PROFILE, TOOLS, SKILLS, PANTRY,
                                          {"max_time": 25, "cravings": "", "servings": 2, "meal": "diner"},
                                          exclude=["Curry de poulet", "Salade César"])
    assert "Curry de poulet" in prompt and "Salade César" in prompt
    assert "ne propose pas" in prompt.lower()

def test_build_plan_excludes_titles_when_given():
    prompt = pb.build_plan(PROFILE, TOOLS, SKILLS, PANTRY,
                           {"n_days": 3, "lunch": True, "dinner": True, "leftovers": True,
                            "servings": 2, "cravings": ""},
                           exclude=["Tarte aux poireaux"])
    assert "Tarte aux poireaux" in prompt and "ne propose pas" in prompt.lower()

def test_build_plan_without_exclude_has_no_exclusion_clause():
    prompt = pb.build_plan(PROFILE, TOOLS, SKILLS, PANTRY,
                           {"n_days": 3, "lunch": True, "dinner": True, "leftovers": True,
                            "servings": 2, "cravings": ""})
    assert "ne propose pas" not in prompt.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_prompt_builder.py -k "json or exclude" -v`
Expected: FAIL — `AttributeError` for `build_cook_with_have_json` (and `build_plan` rejects the `exclude` kwarg).

- [ ] **Step 3: Implement the schema constant, helper, and builders**

In `app/prompt_builder.py`, after the `RECIPE_JSON_SCHEMA` block (ends line ~29), add:

```python
RECIPE_LIST_JSON_SCHEMA = (
    '{\n'
    '  "recipes": [\n'
    '    {\n'
    '      "title": "...",\n'
    '      "ingredients": [{"name": "...", "qty": "... ou null"}],\n'
    '      "steps": [{"text": "...", "duration_seconds": null}],\n'
    '      "source": null,\n'
    '      "tags": ["..."]\n'
    '    }\n'
    '  ]\n'
    '}'
)


def _exclude_clause(exclude) -> str:
    """Optional 'do not repeat these' line appended to one-shot prompts (re-roll)."""
    names = [n for n in (exclude or []) if n and n.strip()]
    if not names:
        return ""
    return f"\nNe propose pas à nouveau ces recettes : {', '.join(names)}.\n"


def _recipes_json_request() -> str:
    return (
        "\n## Format de réponse OBLIGATOIRE\n"
        "Réponds avec un seul bloc ```json``` contenant 3 recettes COMPLÈTES "
        "(titre, ingrédients avec quantités, étapes), respectant EXACTEMENT ce schéma "
        "(3 entrées dans \"recipes\") :\n"
        f"```json\n{RECIPE_LIST_JSON_SCHEMA}\n```"
    )
```

Then add the three one-shot builders at the end of the file:

```python
def build_cook_with_have_json(profile, tools, skills, pantry, params, exclude=None) -> str:
    return (
        f"{base_context(profile, tools, skills)}\n"
        f"{_pantry_section(pantry)}\n"
        "## Demande\n"
        "Propose-moi 3 recettes complètes en utilisant **uniquement** les ingrédients "
        "disponibles ci-dessus (les épices/condiments sont supposés toujours disponibles).\n"
        f"- Temps de cuisson maximum : {params.get('max_time', 30)} minutes\n"
        f"- Pour {params.get('servings', profile.get('household_size', 2))} personnes\n"
        f"- Repas : {params.get('meal', 'indifférent')}\n"
        f"- Envies / précisions : {params.get('cravings') or 'aucune'}\n"
        f"{_exclude_clause(exclude)}"
        f"{_recipes_json_request()}"
    )


def build_cook_with_shop_json(profile, tools, skills, pantry, params, exclude=None) -> str:
    return (
        f"{base_context(profile, tools, skills)}\n"
        f"{_pantry_section(pantry)}\n"
        "## Demande\n"
        "Propose-moi 3 recettes complètes basées sur mes ingrédients, en autorisant "
        f"au maximum {params.get('max_extra', 5)} ingrédients à acheter en plus.\n"
        "Pour chaque recette, inclus les ingrédients à acheter dans sa liste d'ingrédients.\n"
        f"- Temps de cuisson maximum : {params.get('max_time', 30)} minutes\n"
        f"- Pour {params.get('servings', profile.get('household_size', 2))} personnes\n"
        f"- Envies / précisions : {params.get('cravings') or 'aucune'}\n"
        f"{_exclude_clause(exclude)}"
        f"{_recipes_json_request()}"
    )


def build_use_it_up_json(profile, tools, skills, pantry, expiring_names, params, exclude=None) -> str:
    return (
        f"{base_context(profile, tools, skills)}\n"
        f"{_pantry_section(pantry)}\n"
        "## Demande\n"
        "Propose-moi 3 recettes complètes qui utilisent **en priorité** ces ingrédients "
        f"bientôt périmés / à consommer : {', '.join(expiring_names)}.\n"
        f"- Temps de cuisson maximum : {params.get('max_time', 30)} minutes\n"
        "Tu peux compléter avec les autres ingrédients disponibles.\n"
        f"{_exclude_clause(exclude)}"
        f"{_recipes_json_request()}"
    )
```

- [ ] **Step 4: Add the `exclude` param to `build_plan`**

In `app/prompt_builder.py`, change the `build_plan` signature and insert the exclusion clause before the JSON format section. Change the signature line:

```python
def build_plan(profile, tools, skills, pantry, params) -> str:
```

to:

```python
def build_plan(profile, tools, skills, pantry, params, exclude=None) -> str:
```

and inside the returned string, change this fragment:

```python
        "Utilise en priorité mes ingrédients, et ajoute une liste de courses consolidée.\n\n"
        "## Format de réponse OBLIGATOIRE\n"
```

to:

```python
        "Utilise en priorité mes ingrédients, et ajoute une liste de courses consolidée.\n"
        f"{_exclude_clause(exclude)}\n"
        "## Format de réponse OBLIGATOIRE\n"
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_prompt_builder.py -v`
Expected: PASS (all, including the prior prose-prompt tests which are unchanged).

- [ ] **Step 6: Commit**

```bash
git add app/prompt_builder.py tests/test_prompt_builder.py
git commit -m "feat: one-shot cook JSON prompts + exclude clause"
```

---

## Task 5: `Settings.use_llm_directly` column

**Files:**
- Modify: `app/models.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_models.py`:

```python
def test_settings_defaults_to_direct_llm_enabled():
    from app.models import Settings
    assert Settings().use_llm_directly is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_models.py::test_settings_defaults_to_direct_llm_enabled -v`
Expected: FAIL with `AttributeError: 'Settings' object has no attribute 'use_llm_directly'`.

- [ ] **Step 3: Add the field**

In `app/models.py`, inside the `Settings` class, add this line after `skills_notes: str = ""`:

```python
    use_llm_directly: bool = True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_models.py::test_settings_defaults_to_direct_llm_enabled -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/models.py tests/test_models.py
git commit -m "feat: add Settings.use_llm_directly toggle"
```

---

## Task 6: `llm_client.py` (only SDK-touching module)

**Files:**
- Create: `app/llm_client.py`
- Test: `tests/test_llm_client.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_llm_client.py`:

```python
import pytest
from app import llm_client


def test_is_configured_reflects_env(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert llm_client.is_configured() is False
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    assert llm_client.is_configured() is True


def test_get_model_default_and_override(monkeypatch):
    monkeypatch.delenv("CHEFAI_LLM_MODEL", raising=False)
    assert llm_client.get_model() == "claude-sonnet-4-6"
    monkeypatch.setenv("CHEFAI_LLM_MODEL", "claude-haiku-4-5")
    assert llm_client.get_model() == "claude-haiku-4-5"


def test_complete_without_key_raises_llm_error(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(llm_client.LLMError):
        llm_client.complete("bonjour")


class _FakeBlock:
    type = "text"
    text = "réponse"


class _FakeMessage:
    content = [_FakeBlock()]


class _FakeStream:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_final_message(self):
        return _FakeMessage()


class _FakeMessages:
    def stream(self, **kwargs):
        return _FakeStream()


class _FakeClient:
    messages = _FakeMessages()


def test_complete_returns_text(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setattr(llm_client, "_client", lambda: _FakeClient())
    assert llm_client.complete("salut") == "réponse"


class _BoomMessages:
    def stream(self, **kwargs):
        raise RuntimeError("network down")


class _BoomClient:
    messages = _BoomMessages()


def test_complete_wraps_sdk_failure_as_llm_error(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setattr(llm_client, "_client", lambda: _BoomClient())
    with pytest.raises(llm_client.LLMError):
        llm_client.complete("salut")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_llm_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.llm_client'`.

- [ ] **Step 3: Implement the module**

Create `app/llm_client.py`:

```python
"""The ONLY module that talks to the Anthropic API. Keeps prompt_builder /
response_parser pure: build a prompt -> complete() -> parse the reply text."""
import os

DEFAULT_MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 8000


class LLMError(RuntimeError):
    """Any failure talking to Claude (missing key, network, API error, refusal)."""


def is_configured() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def get_model() -> str:
    return os.environ.get("CHEFAI_LLM_MODEL", DEFAULT_MODEL)


def _client():
    from anthropic import Anthropic
    return Anthropic()


def complete(prompt: str) -> str:
    """Send one user message, return the concatenated text reply. Raises LLMError."""
    if not is_configured():
        raise LLMError("ANTHROPIC_API_KEY non configurée")
    try:
        with _client().messages.stream(
            model=get_model(),
            max_tokens=MAX_TOKENS,
            thinking={"type": "adaptive"},
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            message = stream.get_final_message()
    except Exception as exc:  # SDK APIError, network, etc. -> uniform LLMError
        raise LLMError(str(exc)) from exc
    return "".join(
        block.text for block in message.content
        if getattr(block, "type", None) == "text"
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_llm_client.py -v`
Expected: PASS (all 6).

- [ ] **Step 5: Commit**

```bash
git add app/llm_client.py tests/test_llm_client.py
git commit -m "feat: add llm_client (Anthropic SDK wrapper)"
```

---

## Task 7: `fake_llm` fixture + `notice` banner

**Files:**
- Modify: `tests/conftest.py`
- Modify: `app/templates/partials/_prompt_result.html`

- [ ] **Step 1: Add the `fake_llm` fixture**

Append to `tests/conftest.py`:

```python
@pytest.fixture
def fake_llm(monkeypatch):
    """Force the direct-LLM path on and stub the Anthropic call.

    Set state['reply'] to a JSON string to simulate success, or to an
    LLMError instance to simulate a failure. state['prompts'] records every
    prompt sent (for asserting the exclude clause on re-roll)."""
    from app import llm_client
    state = {"reply": "", "prompts": []}

    def _complete(prompt):
        state["prompts"].append(prompt)
        if isinstance(state["reply"], Exception):
            raise state["reply"]
        return state["reply"]

    monkeypatch.setattr(llm_client, "is_configured", lambda: True)
    monkeypatch.setattr(llm_client, "complete", _complete)
    return state
```

- [ ] **Step 2: Add the `notice` banner to the prompt partial**

Replace the entire contents of `app/templates/partials/_prompt_result.html` with:

```html
<div class="mt-4">
  {% if notice %}
  <div class="mb-3 p-2 rounded bg-amber-50 text-amber-800 text-sm border border-amber-200">{{ notice }}</div>
  {% endif %}
  <textarea id="prompt-out" rows="12" readonly
            class="w-full border rounded p-2 text-sm font-mono bg-slate-50">{{ prompt }}</textarea>
  <button type="button" onclick="copyText('prompt-out', this)"
          class="mt-2 bg-green-600 text-white rounded px-4 py-2 w-full">Copier le prompt</button>

  {% if show_recipe_save %}
  <div id="recipe-save" class="mt-6 border-t pt-4">
    {% include "partials/_recipe_save_box.html" %}
  </div>
  {% endif %}
</div>
```

- [ ] **Step 3: Verify existing tests still pass (no behavior change yet)**

Run: `pytest tests/test_generate_routes.py tests/test_plan_routes.py -v`
Expected: PASS (the `notice` block is inert when `notice` is absent).

- [ ] **Step 4: Commit**

```bash
git add tests/conftest.py app/templates/partials/_prompt_result.html
git commit -m "test: fake_llm fixture; chore: notice banner on prompt partial"
```

---

## Task 8: `_recipe_cards.html` partial + cook direct path (have/shop)

**Files:**
- Create: `app/templates/partials/_recipe_cards.html`
- Modify: `app/routers/generate.py`
- Modify: `app/templates/cook.html`
- Test: `tests/test_generate_routes.py`

- [ ] **Step 1: Write the failing route tests**

Append to `tests/test_generate_routes.py`:

```python
import json
from app import llm_client

_THREE_RECIPES = json.dumps({"recipes": [
    {"title": "Poulet rôti", "ingredients": [{"name": "Poulet"}], "steps": [{"text": "Cuire"}]},
    {"title": "Salade verte", "ingredients": [], "steps": []},
    {"title": "Soupe", "ingredients": [], "steps": []},
]})


def test_cook_have_direct_renders_recipe_cards(client, fake_llm):
    fake_llm["reply"] = _THREE_RECIPES
    r = client.post("/cook/have", data={
        "max_time": "25", "cravings": "", "servings": "2", "meal": "diner"})
    assert r.status_code == 200
    assert "Poulet rôti" in r.text and "Salade verte" in r.text
    assert "/cookbook/save" in r.text          # per-card save
    assert "Générer d'autres" in r.text         # re-roll button


def test_cook_have_reroll_sends_seen_titles_as_exclude(client, fake_llm):
    fake_llm["reply"] = _THREE_RECIPES
    client.post("/cook/have", data={
        "max_time": "25", "cravings": "", "servings": "2", "meal": "diner",
        "exclude_titles": "Poulet rôti||Salade verte"})
    assert "Poulet rôti" in fake_llm["prompts"][-1]
    assert "ne propose pas" in fake_llm["prompts"][-1].lower()


def test_cook_have_llm_failure_falls_back_to_prompt(client, fake_llm):
    fake_llm["reply"] = llm_client.LLMError("boom")
    r = client.post("/cook/have", data={
        "max_time": "25", "cravings": "", "servings": "2", "meal": "diner"})
    assert r.status_code == 200
    assert "Copier le prompt" in r.text          # fallback prompt partial
    assert "indisponible" in r.text.lower()       # notice


def test_cook_shop_direct_renders_cards(client, fake_llm):
    fake_llm["reply"] = _THREE_RECIPES
    r = client.post("/cook/shop", data={
        "max_time": "30", "cravings": "", "servings": "2", "max_extra": "4"})
    assert "Poulet rôti" in r.text and "/cookbook/save" in r.text
```

Note: `test_generate_have_returns_prompt_text` and `test_cook_suggestions_offer_recipe_save_box` (existing) do NOT pass `fake_llm`, so `is_configured()` is real (no key in the test env) → they still hit the copy-paste path. They must keep passing unchanged.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_generate_routes.py -k "direct or reroll or fall_back or shop_direct" -v`
Expected: FAIL — cards/re-roll text not present (routes still return only the prompt).

- [ ] **Step 3: Create the recipe-cards partial**

Create `app/templates/partials/_recipe_cards.html`:

```html
<div class="space-y-4">
  {% for recipe in recipes %}
  <div class="bg-white border rounded p-3">
    <h3 class="font-semibold">{{ recipe.title }}</h3>
    {% if recipe.ingredients %}
    <p class="text-xs uppercase text-slate-400 mt-2">Ingrédients</p>
    <ul class="text-sm list-disc list-inside">
      {% for ing in recipe.ingredients %}
      <li>{{ ing.name }}{% if ing.qty %} — {{ ing.qty }}{% endif %}</li>
      {% endfor %}
    </ul>
    {% endif %}
    {% if recipe.steps %}
    <p class="text-xs uppercase text-slate-400 mt-2">Étapes</p>
    <ol class="text-sm list-decimal list-inside">
      {% for step in recipe.steps %}<li>{{ step.text }}</li>{% endfor %}
    </ol>
    {% endif %}
    <form hx-post="/cookbook/save" hx-target="#card-result-{{ loop.index0 }}" hx-swap="innerHTML" class="mt-2">
      <textarea name="raw" class="hidden">{{ recipe | tojson }}</textarea>
      <button class="bg-green-600 text-white rounded px-4 py-2 text-sm w-full">Enregistrer &amp; cuisiner</button>
    </form>
    <div id="card-result-{{ loop.index0 }}" class="mt-2"></div>
  </div>
  {% endfor %}

  {% if reroll_to %}
  <form hx-post="{{ reroll_to }}" hx-target="#result" hx-swap="innerHTML" hx-indicator="#llm-spinner">
    {% for name, value in reroll_fields.items() %}
    <input type="hidden" name="{{ name }}" value="{{ value }}">
    {% endfor %}
    <input type="hidden" name="exclude_titles" value="{{ exclude_value }}">
    <button class="bg-slate-200 rounded px-4 py-2 text-sm w-full">Générer d'autres recettes</button>
  </form>
  {% endif %}
</div>
```

- [ ] **Step 4: Add the dispatch helper + direct path to `generate.py`**

In `app/routers/generate.py`, update the imports block at the top to add `llm_client`, `response_parser`, and `Settings` (already imported):

```python
from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select
from ..db import get_session
from ..models import PantryItem, Settings, Tool, Skill
from .. import prompt_builder as pb
from .. import response_parser as rp
from .. import llm_client
from ..main import templates
```

Add these module-level helpers right after `router = APIRouter()`:

```python
FALLBACK_NOTICE = "Génération directe indisponible — copiez le prompt ci-dessous."


def _split_titles(value: str) -> list[str]:
    return [t.strip() for t in (value or "").split("||") if t.strip()]


def _join_titles(titles: list[str]) -> str:
    return "||".join(titles)
```

Change `_prompt_response` to accept an optional `notice`:

```python
def _prompt_response(request: Request, prompt: str, show_recipe_save: bool = False, notice: str = None):
    """Return a rendered prompt result partial (copy-paste path / fallback)."""
    return templates.TemplateResponse(
        "partials/_prompt_result.html",
        {"request": request, "prompt": prompt, "show_recipe_save": show_recipe_save, "notice": notice})
```

Add the shared dispatch helper (used by have/shop here and by use-it-up in Task 9):

```python
def respond_with_recipes(request: Request, session: Session, *, json_prompt: str,
                         prose_prompt: str, reroll_to: str, reroll_fields: dict):
    """Direct path if configured + enabled: call Claude, parse a 3-recipe array,
    render cards. On not-configured/disabled -> the prose prompt. On any LLM or
    parse failure -> the prose prompt + a French notice."""
    settings = session.get(Settings, 1)
    if not (llm_client.is_configured() and settings.use_llm_directly):
        return _prompt_response(request, prose_prompt, show_recipe_save=True)
    try:
        parsed = rp.parse_recipe_list_response(llm_client.complete(json_prompt))
    except (llm_client.LLMError, rp.ParseError):
        return _prompt_response(request, prose_prompt, show_recipe_save=True, notice=FALLBACK_NOTICE)
    recipes = [r.model_dump() for r in parsed.recipes]
    return templates.TemplateResponse("partials/_recipe_cards.html", {
        "request": request, "recipes": recipes,
        "reroll_to": reroll_to, "reroll_fields": reroll_fields,
        "exclude_value": _join_titles([r["title"] for r in recipes]),
    })
```

Replace the `gen_have` function body to use the dispatch helper (note the new `exclude_titles` form field):

```python
@router.post("/cook/have", response_class=HTMLResponse)
def gen_have(request: Request, session: Session = Depends(get_session),
             max_time: int = Form(30), cravings: str = Form(""),
             servings: int = Form(2), meal: str = Form("indifférent"),
             exclude_titles: str = Form("")):
    """Cook with what you have: direct 3-recipe cards, or copy-paste prompt."""
    profile, tools, skills, pantry = load_state(session)
    params = {"max_time": max_time, "cravings": cravings, "servings": servings, "meal": meal}
    return respond_with_recipes(
        request, session,
        json_prompt=pb.build_cook_with_have_json(profile, tools, skills, pantry, params,
                                                 exclude=_split_titles(exclude_titles)),
        prose_prompt=pb.build_cook_with_have(profile, tools, skills, pantry, params),
        reroll_to="/cook/have",
        reroll_fields={"max_time": max_time, "cravings": cravings, "servings": servings, "meal": meal})
```

Replace the `gen_shop` function body similarly:

```python
@router.post("/cook/shop", response_class=HTMLResponse)
def gen_shop(request: Request, session: Session = Depends(get_session),
             max_time: int = Form(30), cravings: str = Form(""),
             servings: int = Form(2), max_extra: int = Form(5),
             exclude_titles: str = Form("")):
    """Cook with a small shopping list: direct 3-recipe cards, or copy-paste prompt."""
    profile, tools, skills, pantry = load_state(session)
    params = {"max_time": max_time, "cravings": cravings, "servings": servings, "max_extra": max_extra}
    return respond_with_recipes(
        request, session,
        json_prompt=pb.build_cook_with_shop_json(profile, tools, skills, pantry, params,
                                                 exclude=_split_titles(exclude_titles)),
        prose_prompt=pb.build_cook_with_shop(profile, tools, skills, pantry, params),
        reroll_to="/cook/shop",
        reroll_fields={"max_time": max_time, "cravings": cravings, "servings": servings, "max_extra": max_extra})
```

- [ ] **Step 5: Add the spinner to `cook.html`**

In `app/templates/cook.html`, add `hx-indicator="#llm-spinner"` to the two cook forms and add a spinner element above `<div id="result">`. Change the HAVE form opening tag (line ~15):

```html
  <form x-show="tab==='have'" hx-post="/cook/have" hx-target="#result" hx-indicator="#llm-spinner" class="space-y-2 mt-4">
```

Change the SHOP form opening tag (line ~30):

```html
  <form x-show="tab==='shop'" hx-post="/cook/shop" hx-target="#result" hx-indicator="#llm-spinner" class="space-y-2 mt-4">
```

Replace `<div id="result"></div>` (line ~45) with:

```html
  <div id="llm-spinner" class="htmx-indicator text-center text-sm text-slate-500 mt-4">⏳ Claude réfléchit…</div>
  <div id="result"></div>
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_generate_routes.py -v`
Expected: PASS (new direct/reroll/fallback tests AND the original prose-path tests).

- [ ] **Step 7: Commit**

```bash
git add app/routers/generate.py app/templates/partials/_recipe_cards.html app/templates/cook.html tests/test_generate_routes.py
git commit -m "feat: direct Claude path for cook-with-have/shop with re-roll"
```

---

## Task 9: use-it-up direct path

**Files:**
- Modify: `app/routers/home.py`
- Test: `tests/test_home_routes.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_home_routes.py` (add the imports at the top of the file if not present):

```python
import json
from datetime import date, timedelta
from app import llm_client
from app.models import PantryItem

_RECIPES = json.dumps({"recipes": [
    {"title": "Gratin", "ingredients": [], "steps": []},
    {"title": "Poêlée", "ingredients": [], "steps": []},
    {"title": "Velouté", "ingredients": [], "steps": []},
]})


def test_use_it_up_direct_renders_cards(client, session, fake_llm):
    session.add(PantryItem(name="Courgette", category="Frigo",
                           expiry_date=date.today() + timedelta(days=1)))
    session.commit()
    fake_llm["reply"] = _RECIPES
    r = client.post("/use-it-up")
    assert r.status_code == 200
    assert "Gratin" in r.text and "/cookbook/save" in r.text


def test_use_it_up_fallback_on_failure(client, fake_llm):
    fake_llm["reply"] = llm_client.LLMError("boom")
    r = client.post("/use-it-up")
    assert "Copier le prompt" in r.text and "indisponible" in r.text.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_home_routes.py -k use_it_up -v`
Expected: FAIL — cards/notice text not present (route still returns only the prompt).

- [ ] **Step 3: Wire the direct path**

Replace the contents of `app/routers/home.py` `use_it_up` function. First update imports at the top of the file:

```python
from datetime import date, timedelta
from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select
from ..db import get_session
from ..models import PantryItem, PlanningSession
from .. import prompt_builder as pb
from .generate import load_state, respond_with_recipes, _split_titles
from ..main import templates
```

Then replace the `use_it_up` route:

```python
@router.post("/use-it-up", response_class=HTMLResponse)
def use_it_up(request: Request, session: Session = Depends(get_session),
              exclude_titles: str = Form("")):
    profile, tools, skills, pantry = load_state(session)
    names = [i.name for i in _expiring(session)]
    params = {"max_time": profile["default_cook_time"]}
    return respond_with_recipes(
        request, session,
        json_prompt=pb.build_use_it_up_json(profile, tools, skills, pantry, names, params,
                                            exclude=_split_titles(exclude_titles)),
        prose_prompt=pb.build_use_it_up(profile, tools, skills, pantry, names, params),
        reroll_to="/use-it-up",
        reroll_fields={})
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_home_routes.py -v`
Expected: PASS (new tests AND existing home tests).

- [ ] **Step 5: Commit**

```bash
git add app/routers/home.py tests/test_home_routes.py
git commit -m "feat: direct Claude path for use-it-up"
```

---

## Task 10: Meal-recipe direct path

**Files:**
- Modify: `app/routers/plan.py`
- Test: `tests/test_plan_routes.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_plan_routes.py` (add imports at the top if missing):

```python
import json
from app import llm_client
from app.models import PlanningSession, Meal

_ONE_RECIPE = json.dumps({
    "title": "Curry de lentilles",
    "ingredients": [{"name": "Lentilles", "qty": "200 g"}],
    "steps": [{"text": "Mijoter", "duration_seconds": 600}],
})


def _make_meal(session):
    ps = PlanningSession(params_json={}, proposals_json=[], status="validated")
    session.add(ps); session.commit(); session.refresh(ps)
    meal = Meal(planning_session_id=ps.id, day_index=1, slot="diner",
                title="Curry de lentilles", ingredients_json=["lentilles"])
    session.add(meal); session.commit(); session.refresh(meal)
    return meal


def test_meal_prompt_direct_renders_recipe(client, session, fake_llm):
    meal = _make_meal(session)
    fake_llm["reply"] = _ONE_RECIPE
    r = client.get(f"/plan/meal/{meal.id}/prompt")
    assert r.status_code == 200
    assert "Curry de lentilles" in r.text and "/cookbook/save" in r.text


def test_meal_prompt_fallback_on_failure(client, session, fake_llm):
    meal = _make_meal(session)
    fake_llm["reply"] = llm_client.LLMError("boom")
    r = client.get(f"/plan/meal/{meal.id}/prompt")
    assert "Copier le prompt" in r.text and "indisponible" in r.text.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_plan_routes.py -k meal_prompt -v`
Expected: FAIL — recipe card text not present.

- [ ] **Step 3: Wire the direct path into `meal_prompt`**

In `app/routers/plan.py`, update imports at the top to add `llm_client` and the generate helpers:

```python
from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select
from ..db import get_session
from ..models import PlanningSession, Meal, ShoppingItem, Settings
from .. import prompt_builder as pb
from .. import response_parser as rp
from .. import llm_client
from .generate import load_state, _prompt_response, FALLBACK_NOTICE
from ..main import templates
```

Replace the `meal_prompt` route with:

```python
@router.get("/plan/meal/{meal_id}/prompt", response_class=HTMLResponse)
def meal_prompt(meal_id: int, request: Request, session: Session = Depends(get_session)):
    meal = session.get(Meal, meal_id)
    profile, tools, skills, _ = load_state(session)
    prompt = pb.build_meal_cooking(
        profile, tools, skills,
        {"title": meal.title, "ingredients": meal.ingredients_json},
        servings=session.get(Settings, 1).household_size)
    settings = session.get(Settings, 1)
    if not (llm_client.is_configured() and settings.use_llm_directly):
        return _prompt_response(request, prompt, show_recipe_save=True)
    try:
        parsed = rp.parse_recipe_response(llm_client.complete(prompt))
    except (llm_client.LLMError, rp.ParseError):
        return _prompt_response(request, prompt, show_recipe_save=True, notice=FALLBACK_NOTICE)
    return templates.TemplateResponse("partials/_recipe_cards.html", {
        "request": request, "recipes": [parsed.model_dump()],
        "reroll_to": None, "reroll_fields": {}, "exclude_value": ""})
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_plan_routes.py -k meal_prompt -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/routers/plan.py tests/test_plan_routes.py
git commit -m "feat: direct Claude path for meal recipe"
```

---

## Task 11: Meal-plan direct path + re-roll

**Files:**
- Create: `app/templates/partials/_plan_proposals_cards.html`
- Modify: `app/templates/plan_proposals.html`
- Modify: `app/routers/plan.py`
- Test: `tests/test_plan_routes.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_plan_routes.py`:

```python
_TWO_PLANS = json.dumps({"plans": [
    {"label": "Plan A", "days": [{"day": 1, "meals": [
        {"slot": "diner", "title": "Risotto", "ingredients": ["riz"]}]}],
     "shopping_list": [{"name": "Riz", "qty": "300 g", "store_type": "Autre"}]},
    {"label": "Plan B", "days": [{"day": 1, "meals": [
        {"slot": "diner", "title": "Tajine", "ingredients": ["pois chiches"]}]}],
     "shopping_list": []},
]})


def test_plan_generate_direct_renders_proposal_cards(client, session, fake_llm):
    fake_llm["reply"] = _TWO_PLANS
    r = client.post("/plan/generate", data={
        "n_days": "3", "lunch": "on", "dinner": "on", "leftovers": "on",
        "servings": "2", "cravings": ""})
    assert r.status_code == 200
    assert "Risotto" in r.text and "Tajine" in r.text
    assert "Valider ce plan" in r.text and "Générer d'autres plans" in r.text


def test_plan_generate_fallback_on_failure(client, fake_llm):
    fake_llm["reply"] = llm_client.LLMError("boom")
    r = client.post("/plan/generate", data={
        "n_days": "3", "lunch": "on", "dinner": "on", "leftovers": "on",
        "servings": "2", "cravings": ""})
    assert "Copier le prompt" in r.text and "indisponible" in r.text.lower()


def test_plan_regenerate_excludes_prior_titles(client, session, fake_llm):
    fake_llm["reply"] = _TWO_PLANS
    client.post("/plan/generate", data={
        "n_days": "3", "lunch": "on", "dinner": "on", "leftovers": "on",
        "servings": "2", "cravings": ""})
    ps = session.exec(select(PlanningSession)
                      .order_by(PlanningSession.id.desc())).first()
    fake_llm["reply"] = _TWO_PLANS
    r = client.post(f"/plan/{ps.id}/regenerate")
    assert r.status_code == 200
    assert "Risotto" in fake_llm["prompts"][-1]      # prior title fed back as exclusion
    assert "ne propose pas" in fake_llm["prompts"][-1].lower()
```

Note: `select` is already imported in `tests/test_plan_routes.py` only if used; if not, add `from sqlmodel import select` at the top.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_plan_routes.py -k "direct or regenerate or plan_generate_fall" -v`
Expected: FAIL — proposal cards / `/plan/.../regenerate` route not present.

- [ ] **Step 3: Extract the proposals cards partial**

Create `app/templates/partials/_plan_proposals_cards.html`:

```html
<div class="space-y-4">
  {% if notice %}
  <div class="p-2 rounded bg-amber-50 text-amber-800 text-sm border border-amber-200">{{ notice }}</div>
  {% endif %}
  {% for plan in plans %}
  <div class="bg-white border rounded p-3">
    <h3 class="font-semibold">{{ plan.label }}</h3>
    {% for day in plan.days %}
      <p class="text-xs uppercase text-slate-400 mt-2">Jour {{ day.day }}</p>
      {% for meal in day.meals %}
        <p class="text-sm">• {{ meal.slot }} — {{ meal.title }}</p>
      {% endfor %}
    {% endfor %}
    <form method="post" action="/plan/{{ ps.id }}/validate" class="mt-2">
      <input type="hidden" name="choice" value="{{ loop.index0 }}">
      <button class="bg-green-600 text-white rounded px-4 py-2 text-sm">Valider ce plan</button>
    </form>
  </div>
  {% endfor %}
  {% if reroll %}
  <form method="post" action="/plan/{{ ps.id }}/regenerate">
    <button class="bg-slate-200 rounded px-4 py-2 text-sm w-full">Générer d'autres plans</button>
  </form>
  {% endif %}
  <form method="post" action="/plan/{{ ps.id }}/cancel">
    <button class="text-red-500 text-sm">Annuler le plan</button>
  </form>
</div>
```

- [ ] **Step 4: Make the full page reuse the partial**

Replace the contents of `app/templates/plan_proposals.html` with:

```html
{% extends "base.html" %}
{% block header %}Plans proposés{% endblock %}
{% block content %}
{% include "partials/_plan_proposals_cards.html" %}
{% endblock %}
```

(The existing `/plan/parse` paste-back route renders this page with `plans` + `ps`; `reroll` and `notice` are simply absent there, so the re-roll button doesn't show — matching the design's "API path only".)

- [ ] **Step 5: Wire the direct path + regenerate route in `plan.py`**

In `app/routers/plan.py`, replace the `plan_generate` route with:

```python
@router.post("/plan/generate", response_class=HTMLResponse)
def plan_generate(request: Request, session: Session = Depends(get_session),
                  n_days: int = Form(3), lunch: str = Form(None), dinner: str = Form(None),
                  leftovers: str = Form(None), servings: int = Form(2), cravings: str = Form("")):
    profile, tools, skills, pantry = load_state(session)
    params = {"n_days": n_days, "lunch": bool(lunch), "dinner": bool(dinner),
              "leftovers": bool(leftovers), "servings": servings, "cravings": cravings}
    settings = session.get(Settings, 1)
    if not (llm_client.is_configured() and settings.use_llm_directly):
        return _prompt_response(request, pb.build_plan(profile, tools, skills, pantry, params))
    try:
        parsed = rp.parse_plan_response(llm_client.complete(pb.build_plan(profile, tools, skills, pantry, params)))
    except (llm_client.LLMError, rp.ParseError):
        return _prompt_response(request, pb.build_plan(profile, tools, skills, pantry, params),
                                notice=FALLBACK_NOTICE)
    ps = PlanningSession(params_json=params,
                         proposals_json=[p.model_dump() for p in parsed.plans], status="proposed")
    session.add(ps); session.commit(); session.refresh(ps)
    return templates.TemplateResponse("partials/_plan_proposals_cards.html",
                                      {"request": request, "ps": ps, "plans": ps.proposals_json,
                                       "reroll": True})
```

Add a helper to collect prior meal titles and the regenerate route (place after `plan_generate`):

```python
def _plan_meal_titles(proposals: list) -> list[str]:
    titles = []
    for plan in proposals:
        for day in plan.get("days", []):
            for meal in day.get("meals", []):
                if meal.get("title"):
                    titles.append(meal["title"])
    return titles


@router.post("/plan/{ps_id}/regenerate", response_class=HTMLResponse)
def plan_regenerate(ps_id: int, request: Request, session: Session = Depends(get_session)):
    ps = session.get(PlanningSession, ps_id)
    profile, tools, skills, pantry = load_state(session)
    exclude = _plan_meal_titles(ps.proposals_json)
    prompt = pb.build_plan(profile, tools, skills, pantry, ps.params_json, exclude=exclude)
    try:
        parsed = rp.parse_plan_response(llm_client.complete(prompt))
    except (llm_client.LLMError, rp.ParseError):
        return templates.TemplateResponse("partials/_plan_proposals_cards.html",
                                          {"request": request, "ps": ps, "plans": ps.proposals_json,
                                           "reroll": True, "notice": FALLBACK_NOTICE})
    ps.proposals_json = [p.model_dump() for p in parsed.plans]
    session.add(ps); session.commit(); session.refresh(ps)
    return templates.TemplateResponse("partials/_plan_proposals_cards.html",
                                      {"request": request, "ps": ps, "plans": ps.proposals_json,
                                       "reroll": True})
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_plan_routes.py -v`
Expected: PASS (new tests AND the existing plan tests, including `/plan/parse` paste-back).

- [ ] **Step 7: Commit**

```bash
git add app/routers/plan.py app/templates/plan_proposals.html app/templates/partials/_plan_proposals_cards.html tests/test_plan_routes.py
git commit -m "feat: direct Claude path for meal plan with re-roll"
```

---

## Task 12: Settings toggle (UI + persistence)

**Files:**
- Modify: `app/routers/settings.py`
- Modify: `app/templates/settings.html`
- Test: `tests/test_settings_routes.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_settings_routes.py`:

```python
from app.models import Settings


def test_settings_page_shows_direct_mode_toggle(client):
    r = client.get("/settings")
    assert r.status_code == 200
    assert "use_llm_directly" in r.text


def test_settings_post_persists_direct_mode_off(client, session):
    # checkbox unchecked → field absent in the form payload → stored False
    client.post("/settings", data={
        "household_size": "2", "default_cook_time": "30", "language": "fr",
        "restrictions": "", "allergies": "", "dislikes": "",
        "consumption_habits": "", "tools_notes": "", "skills_notes": ""})
    assert session.get(Settings, 1).use_llm_directly is False


def test_settings_post_persists_direct_mode_on(client, session):
    client.post("/settings", data={
        "household_size": "2", "default_cook_time": "30", "language": "fr",
        "restrictions": "", "allergies": "", "dislikes": "",
        "consumption_habits": "", "tools_notes": "", "skills_notes": "",
        "use_llm_directly": "on"})
    assert session.get(Settings, 1).use_llm_directly is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_settings_routes.py -k direct_mode -v`
Expected: FAIL — `use_llm_directly` not in page; field not persisted.

- [ ] **Step 3: Persist the toggle + expose `api_configured`**

In `app/routers/settings.py`, add the import and update both routes. Add at the top:

```python
from .. import llm_client
```

Change `settings_page` to pass `api_configured`:

```python
@router.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request, session: Session = Depends(get_session)):
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "settings": _settings(session),
        "tools": session.exec(select(Tool)).all(),
        "skills": session.exec(select(Skill)).all(),
        "api_configured": llm_client.is_configured(),
    })
```

Change `update_settings` to accept and store the checkbox (an unchecked HTML checkbox sends no field, so default `None` → `False`):

```python
@router.post("/settings")
def update_settings(
    session: Session = Depends(get_session),
    household_size: int = Form(2),
    default_cook_time: int = Form(30),
    language: str = Form("fr"),
    restrictions: str = Form(""),
    allergies: str = Form(""),
    dislikes: str = Form(""),
    consumption_habits: str = Form(""),
    tools_notes: str = Form(""),
    skills_notes: str = Form(""),
    use_llm_directly: str = Form(None),
):
    s = _settings(session)
    s.household_size = household_size
    s.default_cook_time = default_cook_time
    s.language = language
    s.restrictions = restrictions
    s.allergies = allergies
    s.dislikes = dislikes
    s.consumption_habits = consumption_habits
    s.tools_notes = tools_notes
    s.skills_notes = skills_notes
    s.use_llm_directly = use_llm_directly is not None
    session.add(s); session.commit()
    return RedirectResponse("/settings", status_code=303)
```

- [ ] **Step 4: Add the toggle to the settings form**

In `app/templates/settings.html`, inside the `<form method="post" action="/settings" ...>` block and before its closing `</form>` (line ~36), add:

```html
  <label class="flex items-center gap-2 text-sm">
    <input type="checkbox" name="use_llm_directly" {{ 'checked' if settings.use_llm_directly }}>
    Générer directement avec Claude (sinon : prompt à copier-coller)
  </label>
  <p class="text-xs text-slate-500">
    {% if api_configured %}Clé API détectée.{% else %}Aucune clé API (ANTHROPIC_API_KEY) — mode copier-coller uniquement.{% endif %}
  </p>
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_settings_routes.py -v`
Expected: PASS (new tests AND existing settings tests).

- [ ] **Step 6: Commit**

```bash
git add app/routers/settings.py app/templates/settings.html tests/test_settings_routes.py
git commit -m "feat: settings toggle for direct-LLM mode"
```

---

## Task 13: Full suite + docs/spec amendment

**Files:**
- Modify: `CLAUDE.md`
- Modify: `docs/superpowers/specs/2026-06-09-chefai-design.md`

- [ ] **Step 1: Run the entire test suite**

Run: `pytest`
Expected: PASS — all tests green, no warnings about missing modules. If anything fails, fix before continuing.

- [ ] **Step 2: Amend `CLAUDE.md`**

In `CLAUDE.md`, find the opening summary sentence:

> **chefai never calls an LLM itself.** It builds a complete context + prompt the user copies into the LLM of their choice.

Replace it with:

> **chefai builds copy-paste LLM prompts by default, and can optionally call Claude directly** when `ANTHROPIC_API_KEY` is set and the Settings "Générer directement avec Claude" toggle is on. The direct path (`app/llm_client.py`, Sonnet 4.6) parses the reply and integrates it; on any failure it falls back to the copy-paste prompt. See `docs/superpowers/specs/2026-06-10-chefai-claude-api-design.md`.

Also update the **Non-goals (v1)** line in `CLAUDE.md` that reads `No LLM API calls` — change it to `Optional direct Claude API calls (key-gated); copy-paste remains the default-capable fallback`.

- [ ] **Step 3: Amend the 2026-06-09 spec**

In `docs/superpowers/specs/2026-06-09-chefai-design.md`, locate the §2 / §12 statements that say chefai makes "no LLM API calls" / "never calls an LLM." Append to each a pointer:

```markdown
> **Updated 2026-06-10:** This non-goal is reversed for an optional, key-gated
> direct-inference mode. Copy-paste remains the default-capable fallback. See
> `docs/superpowers/specs/2026-06-10-chefai-claude-api-design.md`.
```

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md docs/superpowers/specs/2026-06-09-chefai-design.md
git commit -m "docs: note optional direct Claude inference; reverse no-LLM non-goal"
```

---

## Deployment notes (not code tasks)

- **API key:** set `ANTHROPIC_API_KEY` in the environment (docker-compose `environment:` / a `.env` referenced by compose). Never commit it. Optional `CHEFAI_LLM_MODEL` overrides the model (default `claude-sonnet-4-6`).
- **Existing SQLite DB:** handled automatically. `init_db()` runs `SQLModel.metadata.create_all` (which does not ALTER existing tables) and then `_ensure_settings_columns()` (Task 14), which idempotently backfills the `Settings.use_llm_directly` column on a pre-existing `chefai.db`. Fresh installs and the test suite get the column from `create_all`; already-deployed DBs get it on the next startup. No manual migration needed.
- **Cost:** ~$3–8/month at 2–3 calls/day on Sonnet 4.6 (per the spec).

---

## Self-Review

**Spec coverage:**
- §2 pure-module invariant → Task 6 (`llm_client` is the only SDK module); `prompt_builder`/`response_parser` only gain pure functions (Tasks 2–4). ✓
- §3 `llm_client` (`is_configured`, `complete`, `LLMError`, model env, internal streaming) → Task 6. ✓
- §4 meal-plan direct → Task 11; meal-recipe direct → Task 10; cook flows one-shot 3-recipe JSON + new schema/parser → Tasks 2, 3, 4, 8, 9; copy-paste fallback unchanged → assertions in Tasks 8–11. ✓
- §5 re-roll button + `exclude_titles` + pure `exclude` param → Tasks 4, 8 (cook), 11 (plan). ✓
- §6 config: `ANTHROPIC_API_KEY`, `CHEFAI_LLM_MODEL`, `use_llm_directly` toggle, UI gating → Tasks 5, 6, 12 + deployment notes. ✓
- §7 spinner + fallback-with-notice + transactional storage → Tasks 7, 8, 12 (spinner in 8). ✓
- §8 tests mock the API; `anthropic` dependency → `fake_llm` fixture (Task 7), Task 6 unit tests, Task 1. ✓
- §9 docs/spec amendment → Task 13. ✓
- §10 non-goals respected (no streaming-to-browser, no structured-outputs, no multi-turn, no re-roll on fallback). ✓

**Placeholder scan:** No TBD/TODO; every code step shows complete code and exact paths. ✓

**Type/name consistency:** `respond_with_recipes`, `_split_titles`/`_join_titles`, `FALLBACK_NOTICE`, `_prompt_response(notice=...)` defined in Task 8 (generate.py) and imported by Tasks 9 (home) and 10/11 (plan). `build_cook_with_have_json`/`build_cook_with_shop_json`/`build_use_it_up_json`/`build_plan(exclude=)` defined in Task 4, used in Tasks 8–11. `parse_recipe_list_response` (Task 3) used in Task 8. `_recipe_cards.html` context keys (`recipes`, `reroll_to`, `reroll_fields`, `exclude_value`) consistent between Task 8 (have/shop), Task 9 (use-it-up via helper), and Task 10 (meal recipe passes `reroll_to=None`). `_plan_proposals_cards.html` keys (`ps`, `plans`, `reroll`, `notice`) consistent across Task 11 and the full-page include. ✓
