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
