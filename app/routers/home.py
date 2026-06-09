from datetime import date, timedelta
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select
from ..db import get_session
from ..models import PantryItem, PlanningSession
from .. import prompt_builder as pb
from .generate import load_state
from ..main import templates

router = APIRouter()
EXPIRY_WINDOW_DAYS = 4


def _expiring(session: Session) -> list[PantryItem]:
    cutoff = date.today() + timedelta(days=EXPIRY_WINDOW_DAYS)
    return session.exec(
        select(PantryItem).where(PantryItem.expiry_date != None)  # noqa: E711
        .where(PantryItem.expiry_date <= cutoff)
        .order_by(PantryItem.expiry_date)).all()


@router.get("/", response_class=HTMLResponse)
def home(request: Request, session: Session = Depends(get_session)):
    active_plan = session.exec(
        select(PlanningSession).where(PlanningSession.status == "validated")
        .order_by(PlanningSession.created_at.desc())).first()
    return templates.TemplateResponse("home.html", {
        "request": request, "expiring": _expiring(session), "active_plan": active_plan,
    })


@router.post("/use-it-up", response_class=HTMLResponse)
def use_it_up(request: Request, session: Session = Depends(get_session)):
    profile, tools, skills, pantry = load_state(session)
    names = [i.name for i in _expiring(session)]
    prompt = pb.build_use_it_up(profile, tools, skills, pantry, names,
                                {"max_time": profile["default_cook_time"]})
    return templates.TemplateResponse(
        "partials/_prompt_result.html",
        {"request": request, "prompt": prompt, "show_recipe_save": True})
