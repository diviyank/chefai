"""Per-kind extra template context for panels (reroll targets, form defaults).
Pure-ish view helper: dict in, dict out."""

_REROLL = {"cook_have": "/cook/have", "cook_shop": "/cook/shop"}


def _titles(recipes):
    return "||".join(r["title"] for r in recipes) if recipes else ""


def extra_context(kind: str, params: dict, result: dict | None) -> dict:
    if kind in ("cook_have", "cook_shop"):
        recipes = (result or {}).get("recipes", [])
        return {
            "recipes": recipes,
            "reroll_to": _REROLL[kind],
            "reroll_fields": {k: v for k, v in params.items() if k != "exclude_titles"},
            "exclude_value": _titles(recipes),
            "panel_target": f"panel-{kind}",
            # On the copy-paste fallback (job error -> _prompt_result.html) the user
            # still needs the paste-back box to save a recipe from the LLM reply.
            "show_recipe_save": True,
        }
    if kind == "plan":
        return {}
    return {}
