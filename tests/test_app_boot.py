def test_home_page_renders_nav(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Garde-manger" in r.text
    assert "Cuisiner" in r.text
