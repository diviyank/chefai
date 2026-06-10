"""Pure prompt-building functions. No DB, no web. All output is French."""

PLAN_JSON_SCHEMA = (
    '{\n'
    '  "plans": [\n'
    '    {\n'
    '      "label": "Plan A",\n'
    '      "days": [\n'
    '        {"day": 1, "meals": [\n'
    '          {"slot": "dejeuner|diner", "title": "...", "ingredients": ["..."], "uses_leftovers_from": null}\n'
    '        ]}\n'
    '      ],\n'
    '      "shopping_list": [\n'
    '        {"name": "...", "qty": "... ou null", "store_type": "Boucherie|Poissonnerie|Primeur|Boulangerie|Fromagerie|Épicerie / Supermarché|Autre"}\n'
    '      ]\n'
    '    }\n'
    '  ]\n'
    '}'
)

RECIPE_JSON_SCHEMA = (
    '{\n'
    '  "title": "...",\n'
    '  "ingredients": [{"name": "...", "qty": "... ou null"}],\n'
    '  "steps": [{"text": "...", "duration_seconds": null}],\n'
    '  "source": null,\n'
    '  "tags": ["..."]\n'
    '}'
)

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


def render_pantry(items: list[dict]) -> tuple[str, str]:
    """Return (main_block, staples_line)."""
    main_lines, staples = [], []
    for it in items:
        if it.get("is_staple"):
            staples.append(it["name"])
            continue
        parts = [it["name"]]
        if it.get("quantity_text"):
            parts.append(f"({it['quantity_text']})")
        if it.get("expiry_date"):
            parts.append(f"[périme le {it['expiry_date']}]")
        main_lines.append("- " + " ".join(parts))
    main = "\n".join(main_lines) if main_lines else "(aucun ingrédient principal)"
    staples_line = ", ".join(staples) if staples else "(aucun)"
    return main, staples_line


def base_context(profile: dict, tools: list[str], skills: list[str]) -> str:
    return (
        "## Contexte du foyer\n"
        f"- Nombre de personnes : {profile.get('household_size', 2)}\n"
        f"- Restrictions alimentaires : {profile.get('restrictions') or 'aucune'}\n"
        f"- Allergies : {profile.get('allergies') or 'aucune'}\n"
        f"- Aliments non appréciés : {profile.get('dislikes') or 'aucun'}\n"
        f"- Habitudes / objectifs : {profile.get('consumption_habits') or 'aucun'}\n"
        f"- Équipement disponible : {', '.join(tools) or 'standard'}"
        f"{('. ' + profile['tools_notes']) if profile.get('tools_notes') else ''}\n"
        f"- Compétences en cuisine : {', '.join(skills) or 'débutant'}"
        f"{('. ' + profile['skills_notes']) if profile.get('skills_notes') else ''}\n"
    )


def _choose_to_cook_section() -> str:
    """Asks the LLM to emit the recipe JSON once the user picks a recipe, so it can be
    saved to the cookbook and used in cooking mode (pantry decrement)."""
    return (
        "\n## Quand je choisis une recette à cuisiner\n"
        "Dis-moi simplement laquelle tu recommandes, puis quand je t'indique mon choix, "
        "termine ta réponse par un bloc ```json``` (pour l'enregistrer et activer le mode "
        "cuisine) respectant EXACTEMENT ce schéma :\n"
        f"```json\n{RECIPE_JSON_SCHEMA}\n```"
    )


def _pantry_section(pantry: list[dict]) -> str:
    main, staples = render_pantry(pantry)
    return (
        "## Ingrédients principaux disponibles\n"
        f"{main}\n\n"
        "## Épices, huiles & condiments disponibles\n"
        f"{staples}\n"
    )


def build_cook_with_have(profile, tools, skills, pantry, params) -> str:
    return (
        f"{base_context(profile, tools, skills)}\n"
        f"{_pantry_section(pantry)}\n"
        "## Demande\n"
        "Propose-moi 3 idées de recettes en utilisant **uniquement** les ingrédients "
        "disponibles ci-dessus (les épices/condiments sont supposés toujours disponibles).\n"
        f"- Temps de cuisson maximum : {params.get('max_time', 30)} minutes\n"
        f"- Pour {params.get('servings', profile.get('household_size', 2))} personnes\n"
        f"- Repas : {params.get('meal', 'indifférent')}\n"
        f"- Envies / précisions : {params.get('cravings') or 'aucune'}\n"
        "Pour chaque idée : titre, ingrédients utilisés, et étapes principales."
        f"{_choose_to_cook_section()}"
    )


def build_cook_with_shop(profile, tools, skills, pantry, params) -> str:
    return (
        f"{base_context(profile, tools, skills)}\n"
        f"{_pantry_section(pantry)}\n"
        "## Demande\n"
        "Propose-moi 3 idées de recettes basées sur mes ingrédients, en autorisant "
        f"au maximum {params.get('max_extra', 5)} ingrédients à acheter en plus.\n"
        "Indique clairement, pour chaque recette, la **liste séparée** des ingrédients à acheter.\n"
        f"- Temps de cuisson maximum : {params.get('max_time', 30)} minutes\n"
        f"- Pour {params.get('servings', profile.get('household_size', 2))} personnes\n"
        f"- Envies / précisions : {params.get('cravings') or 'aucune'}\n"
        f"{_choose_to_cook_section()}"
    )


def build_plan(profile, tools, skills, pantry, params, exclude=None) -> str:
    slots = []
    if params.get("lunch"):
        slots.append("déjeuner")
    if params.get("dinner"):
        slots.append("dîner")
    return (
        f"{base_context(profile, tools, skills)}\n"
        f"{_pantry_section(pantry)}\n"
        "## Demande\n"
        f"Propose-moi 3 plans de repas différents sur {params.get('n_days', 3)} jours "
        f"({' et '.join(slots) or 'dîner'}), pour {params.get('servings', 2)} personnes.\n"
        f"- Réutilisation des restes : {'oui' if params.get('leftovers') else 'non'}\n"
        f"- Envies / précisions : {params.get('cravings') or 'aucune'}\n"
        "Utilise en priorité mes ingrédients, et ajoute une liste de courses consolidée.\n"
        f"{_exclude_clause(exclude)}\n"
        "## Format de réponse OBLIGATOIRE\n"
        "Réponds avec un bloc ```json``` respectant EXACTEMENT ce schéma "
        "(3 entrées dans \"plans\") :\n"
        f"```json\n{PLAN_JSON_SCHEMA}\n```"
    )


def build_use_it_up(profile, tools, skills, pantry, expiring_names, params) -> str:
    return (
        f"{base_context(profile, tools, skills)}\n"
        f"{_pantry_section(pantry)}\n"
        "## Demande\n"
        "Propose-moi 3 idées de recettes qui utilisent **en priorité** ces ingrédients "
        f"bientôt périmés / à consommer : {', '.join(expiring_names)}.\n"
        f"- Temps de cuisson maximum : {params.get('max_time', 30)} minutes\n"
        "Tu peux compléter avec les autres ingrédients disponibles."
        f"{_choose_to_cook_section()}"
    )


def build_meal_cooking(profile, tools, skills, meal: dict, servings: int) -> str:
    return (
        f"{base_context(profile, tools, skills)}\n\n"
        "## Demande\n"
        f"Donne-moi la recette détaillée de : **{meal['title']}**, pour {servings} personnes.\n"
        f"Ingrédients prévus : {', '.join(meal.get('ingredients', []))}.\n"
        "Inclus la liste d'ingrédients avec quantités et les étapes numérotées avec durées.\n\n"
        "Si possible, termine par un bloc ```json``` (pour l'enregistrer) au format :\n"
        f"```json\n{RECIPE_JSON_SCHEMA}\n```"
    )


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
