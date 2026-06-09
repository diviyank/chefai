from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select
from ..db import get_session
from ..models import PantryItem, Settings, Tool, Skill
from .. import prompt_builder as pb
from ..main import templates

router = APIRouter()


def load_state(session: Session):
    """Load user profile, tools, skills, and pantry into a structured format."""
    s = session.get(Settings, 1)
    profile = {
        "household_size": s.household_size, "default_cook_time": s.default_cook_time,
        "restrictions": s.restrictions, "allergies": s.allergies, "dislikes": s.dislikes,
        "consumption_habits": s.consumption_habits, "tools_notes": s.tools_notes,
        "skills_notes": s.skills_notes,
    }
    tools = [t.name for t in session.exec(select(Tool).where(Tool.enabled == True)).all()]  # noqa: E712
    skills = [k.name for k in session.exec(select(Skill).where(Skill.enabled == True)).all()]  # noqa: E712
    pantry = [{
        "name": i.name, "category": i.category, "quantity_text": i.quantity_text,
        "expiry_date": str(i.expiry_date) if i.expiry_date else None, "is_staple": i.is_staple,
    } for i in session.exec(select(PantryItem)).all()]
    return profile, tools, skills, pantry


def _prompt_response(request: Request, prompt: str):
    """Return a rendered prompt result partial."""
    return templates.TemplateResponse("partials/_prompt_result.html",
                                      {"request": request, "prompt": prompt})


@router.get("/cook", response_class=HTMLResponse)
def cook_page(request: Request, session: Session = Depends(get_session)):
    """Display the main cook page with three tabs."""
    return templates.TemplateResponse("cook.html", {
        "request": request, "default_time": session.get(Settings, 1).default_cook_time,
        "servings": session.get(Settings, 1).household_size,
    })


@router.post("/cook/have", response_class=HTMLResponse)
def gen_have(request: Request, session: Session = Depends(get_session),
             max_time: int = Form(30), cravings: str = Form(""),
             servings: int = Form(2), meal: str = Form("indifférent")):
    """Generate a prompt for cooking with what you have."""
    profile, tools, skills, pantry = load_state(session)
    prompt = pb.build_cook_with_have(profile, tools, skills, pantry,
                                     {"max_time": max_time, "cravings": cravings,
                                      "servings": servings, "meal": meal})
    return _prompt_response(request, prompt)


@router.post("/cook/shop", response_class=HTMLResponse)
def gen_shop(request: Request, session: Session = Depends(get_session),
             max_time: int = Form(30), cravings: str = Form(""),
             servings: int = Form(2), max_extra: int = Form(5)):
    """Generate a prompt for cooking with a small shopping list."""
    profile, tools, skills, pantry = load_state(session)
    prompt = pb.build_cook_with_shop(profile, tools, skills, pantry,
                                     {"max_time": max_time, "cravings": cravings,
                                      "servings": servings, "max_extra": max_extra})
    return _prompt_response(request, prompt)
