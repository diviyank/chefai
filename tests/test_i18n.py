from app import i18n

def test_returns_french_string_for_known_key():
    assert i18n.t("nav.pantry") == "Garde-manger"

def test_unknown_key_returns_key():
    assert i18n.t("does.not.exist") == "does.not.exist"
