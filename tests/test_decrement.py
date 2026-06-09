from app import decrement as d

def test_normalize_name_strips_accents_case_plural():
    assert d.normalize_name("Oignons") == d.normalize_name("oignon")
    assert d.normalize_name("Épices") == "epice"

def test_parse_quantity_numeric_and_unit():
    assert d.parse_quantity("500 g") == (500.0, "g")
    assert d.parse_quantity("2") == (2.0, "")
    assert d.parse_quantity("1,5 l") == (1.5, "l")

def test_parse_quantity_freetext_returns_none():
    assert d.parse_quantity("un peu") is None
    assert d.parse_quantity(None) is None

def test_subtract_when_compatible_units():
    pantry = [{"id": 1, "name": "Farine", "quantity_text": "500 g", "is_staple": False}]
    recipe = [{"name": "farine", "qty": "200 g"}]
    props = d.compute_decrement(pantry, recipe)
    assert props[0]["action"] == "subtract"
    assert props[0]["new_quantity_text"] == "300 g"

def test_remove_when_result_non_positive():
    pantry = [{"id": 1, "name": "Oeufs", "quantity_text": "3", "is_staple": False}]
    recipe = [{"name": "oeufs", "qty": "3"}]
    props = d.compute_decrement(pantry, recipe)
    assert props[0]["action"] == "remove"

def test_freetext_or_mismatch_flagged_confirm():
    pantry = [{"id": 1, "name": "Lait", "quantity_text": "un peu", "is_staple": False}]
    recipe = [{"name": "lait", "qty": "200 ml"}]
    props = d.compute_decrement(pantry, recipe)
    assert props[0]["action"] == "confirm"

def test_staples_skipped():
    pantry = [{"id": 1, "name": "Sel", "quantity_text": "1 kg", "is_staple": True}]
    recipe = [{"name": "sel", "qty": "10 g"}]
    assert d.compute_decrement(pantry, recipe) == []

def test_unmatched_recipe_ingredient_ignored():
    pantry = [{"id": 1, "name": "Farine", "quantity_text": "500 g", "is_staple": False}]
    recipe = [{"name": "safran", "qty": "1 pincée"}]
    assert d.compute_decrement(pantry, recipe) == []
