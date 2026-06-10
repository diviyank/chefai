from datetime import date, timedelta
from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select
from ..db import get_session
from ..models import PantryItem, PlanningSession
from .. import prompt_builder as pb
from .generate import load_state, respond_with_recipes, _split_titles
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
def use_it_up(request: Request, session: Session = Depends(get_session),
              exclude_titles: str = Form("")):
    profile, tools, skills, pantry = load_state(session)
    names = [i.name for i in _expiring(session)]
    params = {"max_time": profile["default_cook_time"]}
    return respond_with_recipes(
        request, session,
        json_prompt=pb.build_use_it_up_json(profile, tools, skills, pantry, names, params,
                                            exclude=_split_titles(exclude_titles)),
        prose_prompt=pb.build_use_it_up(profile, tools, skills, pantry, names, params),
        reroll_to="/use-it-up",
        reroll_fields={})
