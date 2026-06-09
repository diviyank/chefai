import pytest
from app import response_parser as rp

PLAN_OK = '''Bien sûr ! Voici vos plans :
```json
{"plans":[{"label":"A","days":[{"day":1,"meals":[{"slot":"diner","title":"Curry","ingredients":["riz"]}]}],"shopping_list":[{"name":"Riz","qty":"500 g","store_type":"Épicerie / Supermarché"}]}]}
```
Bon appétit !'''

RECIPE_RAW = '{"title":"Omelette","ingredients":[{"name":"Oeufs","qty":"3"}],"steps":[{"text":"Battre","duration_seconds":60}]}'

def test_extract_json_from_fenced_block():
    data = rp.extract_json_block(PLAN_OK)
    assert data["plans"][0]["label"] == "A"

def test_extract_json_from_raw_object():
    data = rp.extract_json_block("préambule " + RECIPE_RAW + " fin")
    assert data["title"] == "Omelette"

def test_parse_plan_response_ok():
    parsed = rp.parse_plan_response(PLAN_OK)
    assert parsed.plans[0].days[0].meals[0].title == "Curry"

def test_parse_recipe_response_ok():
    parsed = rp.parse_recipe_response(RECIPE_RAW)
    assert parsed.steps[0].duration_seconds == 60

def test_parse_failure_raises_french_parse_error():
    with pytest.raises(rp.ParseError) as exc:
        rp.parse_plan_response("désolé, pas de json ici")
    assert "réponse non reconnue" in str(exc.value).lower()
