from app import enums

def test_staple_categories_are_subset_of_categories():
    assert set(enums.STAPLE_CATEGORIES).issubset(set(enums.DEFAULT_CATEGORIES))

def test_defaults_present():
    assert "Frigo" in enums.DEFAULT_CATEGORIES
    assert "Boucherie" in enums.DEFAULT_STORE_TYPES
    assert len(enums.DEFAULT_TOOLS) >= 5
    assert len(enums.DEFAULT_SKILLS) >= 3
