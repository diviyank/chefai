from app import prompt_builder as pb

PROFILE = {
    "household_size": 2, "default_cook_time": 30, "restrictions": "végétarien",
    "allergies": "arachides", "dislikes": "coriandre", "consumption_habits": "peu de sucre",
    "tools_notes": "", "skills_notes": "",
}
TOOLS = ["Four", "Air fryer"]
SKILLS = ["Découpe au couteau"]
PANTRY = [
    {"name": "Poulet", "category": "Frigo", "quantity_text": "500 g", "expiry_date": "2026-06-20", "is_staple": False},
    {"name": "Cumin", "category": "Épices & condiments", "quantity_text": None, "expiry_date": None, "is_staple": True},
]

def test_render_pantry_splits_main_and_staples():
    main, staples = pb.render_pantry(PANTRY)
    assert "Poulet" in main and "500 g" in main
    assert "Cumin" in staples
    assert "Cumin" not in main  # staple not itemized

def test_base_context_includes_profile_and_tools():
    ctx = pb.base_context(PROFILE, TOOLS, SKILLS)
    for needle in ["végétarien", "arachides", "coriandre", "Four", "Air fryer", "Découpe au couteau"]:
        assert needle in ctx

def test_cook_with_have_constrains_to_pantry_and_params():
    prompt = pb.build_cook_with_have(PROFILE, TOOLS, SKILLS, PANTRY,
                                     {"max_time": 25, "cravings": "épicé", "servings": 2, "meal": "diner"})
    assert "uniquement" in prompt.lower()      # use only what's available
    assert "25" in prompt and "épicé" in prompt
    assert "3 " in prompt or "trois" in prompt.lower()  # asks for 3 ideas

def test_cook_with_shop_mentions_extra_items_limit():
    prompt = pb.build_cook_with_shop(PROFILE, TOOLS, SKILLS, PANTRY,
                                     {"max_time": 30, "cravings": "", "servings": 2, "max_extra": 4})
    assert "4" in prompt
    assert "liste" in prompt.lower()           # asks to list extras separately

def test_build_plan_requests_json_schema():
    prompt = pb.build_plan(PROFILE, TOOLS, SKILLS, PANTRY,
                           {"n_days": 3, "lunch": True, "dinner": True, "leftovers": True, "servings": 2, "cravings": ""})
    assert "json" in prompt.lower()
    assert '"plans"' in prompt              # schema field present
    assert "3" in prompt

def test_use_it_up_lists_expiring_items():
    prompt = pb.build_use_it_up(PROFILE, TOOLS, SKILLS, PANTRY, ["Poulet"], {"max_time": 30})
    assert "Poulet" in prompt
    assert "périm" in prompt.lower() or "consommer" in prompt.lower()

def test_meal_cooking_prompt_includes_title_and_servings():
    prompt = pb.build_meal_cooking(PROFILE, TOOLS, SKILLS,
                                   {"title": "Curry de lentilles", "ingredients": ["lentilles", "lait de coco"]}, servings=2)
    assert "Curry de lentilles" in prompt
    assert "2" in prompt
