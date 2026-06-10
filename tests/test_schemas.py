import pytest
from pydantic import ValidationError
from app import schemas

def test_plan_response_requires_three_plans_shape():
    data = {"plans": [{"label": "A", "days": [
        {"day": 1, "meals": [{"slot": "diner", "title": "Curry", "ingredients": ["riz"]}]}
    ], "shopping_list": [{"name": "Riz", "qty": "500 g", "store_type": "Épicerie / Supermarché"}]}]}
    parsed = schemas.PlanResponse.model_validate(data)
    assert parsed.plans[0].days[0].meals[0].title == "Curry"

def test_recipe_response_step_duration_optional():
    data = {"title": "Omelette", "ingredients": [{"name": "Oeufs", "qty": "3"}],
            "steps": [{"text": "Battre les oeufs"}]}
    parsed = schemas.RecipeResponse.model_validate(data)
    assert parsed.steps[0].duration_seconds is None

def test_recipe_response_missing_title_raises():
    with pytest.raises(ValidationError):
        schemas.RecipeResponse.model_validate({"ingredients": []})

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
