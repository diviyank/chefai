from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .db import init_db
from .i18n import t

BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
templates.env.globals["t"] = t

app = FastAPI(title="chefai")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.on_event("startup")
def _startup() -> None:
    init_db()
    from . import jobs
    jobs.mark_stale_running()
    from sqlmodel import Session
    from .db import get_engine
    from .seed import seed
    with Session(get_engine()) as s:
        seed(s)


def register_routers() -> None:
    from importlib import import_module
    for name in ("home", "pantry", "generate", "plan", "shopping", "cookbook", "settings"):
        if not (BASE_DIR / "routers" / f"{name}.py").exists():
            continue
        module = import_module(f"app.routers.{name}")
        app.include_router(module.router)


register_routers()
