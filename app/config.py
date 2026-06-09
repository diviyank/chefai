import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("CHEFAI_DB_PATH", REPO_ROOT / "data" / "chefai.db"))
APP_TITLE = "chefai"
