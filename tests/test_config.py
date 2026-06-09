import importlib
from app import config

def test_default_db_path_under_data_dir():
    cfg = importlib.reload(config)
    assert str(cfg.DB_PATH).endswith("data/chefai.db")

def test_db_path_env_override(monkeypatch):
    monkeypatch.setenv("CHEFAI_DB_PATH", "/tmp/custom.db")
    cfg = importlib.reload(config)
    assert str(cfg.DB_PATH) == "/tmp/custom.db"
