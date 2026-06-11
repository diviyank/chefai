from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select
from ..db import get_session
from ..models import PantryItem, Settings, Tool, Skill
from .. import prompt_builder as pb
from .. import response_parser as rp
from .. import llm_client
from .. import jobs, generation
from ..main import templates

router = APIRouter()

FALLBACK_NOTICE = "Génération directe indisponible — copiez le prompt ci-dessous."


def _split_titles(value: str) -> list[str]:
    return [t.strip() for t in (value or "").split("||") if t.strip()]


def _join_titles(titles: list[str]) -> str:
    return "||".join(titles)


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


def _prompt_response(request: Request, prompt: str, show_recipe_save: bool = False, notice: str = None):
    """Return a rendered prompt result partial.

    Suggestion flows set show_recipe_save so the user can paste a chosen recipe back
    and save it to the cookbook (enabling cook mode + pantry decrement)."""
    return templates.TemplateResponse(
        "partials/_prompt_result.html",
        {"request": request, "prompt": prompt, "show_recipe_save": show_recipe_save, "notice": notice})


def respond_with_recipes(request: Request, session: Session, *, json_prompt: str,
                         prose_prompt: str, reroll_to: str, reroll_fields: dict):
    """Direct path if configured + enabled: call Claude, parse a 3-recipe array,
    render cards. On not-configured/disabled -> the prose prompt. On any LLM or
    parse failure -> the prose prompt + a French notice."""
    settings = session.get(Settings, 1)
    if not (llm_client.is_configured() and settings.use_llm_directly):
        return _prompt_response(request, prose_prompt, show_recipe_save=True)
    try:
        parsed = rp.parse_recipe_list_response(llm_client.complete(json_prompt))
    except (llm_client.LLMError, rp.ParseError):
        return _prompt_response(request, prose_prompt, show_recipe_save=True, notice=FALLBACK_NOTICE)
    recipes = [r.model_dump() for r in parsed.recipes]
    return templates.TemplateResponse("partials/_recipe_cards.html", {
        "request": request, "recipes": recipes,
        "reroll_to": reroll_to, "reroll_fields": reroll_fields,
        "exclude_value": _join_titles([r["title"] for r in recipes]),
    })


@router.get("/cook", response_class=HTMLResponse)
def cook_page(request: Request, session: Session = Depends(get_session)):
    s = session.get(Settings, 1)
    from .jobs import render_panel
    defaults = {"default_time": s.default_cook_time, "servings_default": s.household_size}
    panels = {k: render_panel(request, k, jobs.latest(session, k), session=session, **defaults).body.decode()
              for k in ("cook_have", "cook_shop", "plan")}
    return templates.TemplateResponse("cook.html", {"request": request, "panels": panels})


@router.post("/cook/have", response_class=HTMLResponse)
def gen_have(request: Request, session: Session = Depends(get_session),
             max_time: int = Form(30), cravings: str = Form(""),
             servings: int = Form(2), meal: str = Form("indifférent"),
             exclude_titles: str = Form("")):
    profile, tools, skills, pantry = load_state(session)
    params = {"max_time": max_time, "cravings": cravings, "servings": servings, "meal": meal}
    settings = session.get(Settings, 1)
    prose = pb.build_cook_with_have(profile, tools, skills, pantry, params)
    if not (llm_client.is_configured() and settings.use_llm_directly):
        return _prompt_response(request, prose, show_recipe_save=True)
    titles = _split_titles(exclude_titles)
    json_prompt = pb.build_cook_with_have_json(profile, tools, skills, pantry, params, exclude=titles)
    work = generation.build_cook_work("cook_have", json_prompt=json_prompt)
    job = jobs.start("cook_have", params, prose, work)
    # Fetch the latest job from the database (work may have already completed if inlined in tests)
    latest_job = jobs.latest(session, "cook_have")
    from .jobs import render_panel
    return render_panel(request, "cook_have", latest_job)


@router.post("/cook/shop", response_class=HTMLResponse)
def gen_shop(request: Request, session: Session = Depends(get_session),
             max_time: int = Form(30), cravings: str = Form(""),
             servings: int = Form(2), max_extra: int = Form(5),
             exclude_titles: str = Form("")):
    profile, tools, skills, pantry = load_state(session)
    params = {"max_time": max_time, "cravings": cravings, "servings": servings,
              "max_extra": max_extra}
    settings = session.get(Settings, 1)
    prose = pb.build_cook_with_shop(profile, tools, skills, pantry, params)
    if not (llm_client.is_configured() and settings.use_llm_directly):
        return _prompt_response(request, prose, show_recipe_save=True)
    titles = _split_titles(exclude_titles)
    json_prompt = pb.build_cook_with_shop_json(profile, tools, skills, pantry, params, exclude=titles)
    work = generation.build_cook_work("cook_shop", json_prompt=json_prompt)
    jobs.start("cook_shop", params, prose, work)
    from .jobs import render_panel
    return render_panel(request, "cook_shop", jobs.latest(session, "cook_shop"))
