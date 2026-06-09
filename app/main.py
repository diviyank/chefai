from pathlib import Path
from fastapi import FastAPI, Request
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
    from sqlmodel import Session
    from .db import get_engine
    from .seed import seed
    with Session(get_engine()) as s:
        seed(s)


def register_routers() -> None:
    from .routers import home, pantry, generate, plan, shopping, cookbook, settings
    for module in (home, pantry, generate, plan, shopping, cookbook, settings):
        app.include_router(module.router)


@app.get("/")
def root(request: Request):
    # Temporary placeholder until home router (Task 20) replaces it.
    return templates.TemplateResponse("base.html", {"request": request})
