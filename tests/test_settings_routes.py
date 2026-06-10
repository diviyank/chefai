from app.models import Settings, Tool


def test_get_settings_shows_profile_fields(client):
    r = client.get("/settings")
    assert r.status_code == 200
    assert "Réglages" in r.text

def test_post_settings_updates_profile(client, session):
    r = client.post("/settings", data={
        "household_size": "4", "default_cook_time": "45", "language": "fr",
        "restrictions": "végétarien", "allergies": "", "dislikes": "",
        "consumption_habits": "moins de sucre", "tools_notes": "", "skills_notes": "",
    }, follow_redirects=False)
    assert r.status_code in (200, 303)
    s = session.get(Settings, 1)
    assert s.household_size == 4 and s.restrictions == "végétarien"

def test_toggle_tool(client, session):
    tool = session.query(Tool).first()
    r = client.post(f"/settings/tools/{tool.id}/toggle")
    assert r.status_code == 200
    session.refresh(tool)
    assert tool.enabled is True


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
