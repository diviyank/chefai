from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select
from ..db import get_session
from ..models import PlanningSession, Meal, ShoppingItem, Settings
from .. import prompt_builder as pb
from .. import response_parser as rp
from .. import llm_client
from .generate import load_state, _prompt_response, FALLBACK_NOTICE
from ..main import templates

router = APIRouter()


@router.post("/plan/generate", response_class=HTMLResponse)
def plan_generate(request: Request, session: Session = Depends(get_session),
                  n_days: int = Form(3), lunch: str = Form(None), dinner: str = Form(None),
                  leftovers: str = Form(None), servings: int = Form(2), cravings: str = Form("")):
    profile, tools, skills, pantry = load_state(session)
    prompt = pb.build_plan(profile, tools, skills, pantry, {
        "n_days": n_days, "lunch": bool(lunch), "dinner": bool(dinner),
        "leftovers": bool(leftovers), "servings": servings, "cravings": cravings,
    })
    return templates.TemplateResponse("partials/_prompt_result.html",
                                      {"request": request, "prompt": prompt})


@router.post("/plan/parse", response_class=HTMLResponse)
def plan_parse(request: Request, session: Session = Depends(get_session), raw: str = Form(...)):
    try:
        parsed = rp.parse_plan_response(raw)
    except rp.ParseError as exc:
        return templates.TemplateResponse(
            "partials/_parse_error.html",
            {"request": request, "message": str(exc)}, status_code=200)
    ps = PlanningSession(
        params_json={}, proposals_json=[p.model_dump() for p in parsed.plans], status="proposed")
    session.add(ps); session.commit(); session.refresh(ps)
    return templates.TemplateResponse("plan_proposals.html",
                                      {"request": request, "ps": ps, "plans": ps.proposals_json})


@router.post("/plan/{ps_id}/validate")
def plan_validate(ps_id: int, session: Session = Depends(get_session), choice: int = Form(0)):
    ps = session.get(PlanningSession, ps_id)
    chosen = ps.proposals_json[choice]
    for day in chosen.get("days", []):
        for meal in day.get("meals", []):
            session.add(Meal(
                planning_session_id=ps.id, day_index=day["day"], slot=meal["slot"],
                title=meal["title"], ingredients_json=meal.get("ingredients", []),
                leftover_link=meal.get("uses_leftovers_from")))
    for line in chosen.get("shopping_list", []):
        session.add(ShoppingItem(
            name=line["name"], qty_text=line.get("qty"),
            store_type=line.get("store_type", "Autre"), source="plan"))
    ps.status = "validated"
    session.add(ps); session.commit()
    return RedirectResponse(f"/plan/{ps.id}", status_code=303)


@router.post("/plan/{ps_id}/cancel")
def plan_cancel(ps_id: int, session: Session = Depends(get_session)):
    ps = session.get(PlanningSession, ps_id)
    ps.status = "cancelled"
    session.add(ps); session.commit()
    return RedirectResponse("/cook", status_code=303)


@router.get("/plan/{ps_id}", response_class=HTMLResponse)
def plan_detail(ps_id: int, request: Request, session: Session = Depends(get_session)):
    ps = session.get(PlanningSession, ps_id)
    meals = session.exec(select(Meal).where(Meal.planning_session_id == ps_id)
                         .order_by(Meal.day_index, Meal.slot)).all()
    return templates.TemplateResponse("plan_detail.html",
                                      {"request": request, "ps": ps, "meals": meals})


@router.get("/plan/meal/{meal_id}/prompt", response_class=HTMLResponse)
def meal_prompt(meal_id: int, request: Request, session: Session = Depends(get_session)):
    meal = session.get(Meal, meal_id)
    profile, tools, skills, _ = load_state(session)
    prompt = pb.build_meal_cooking(
        profile, tools, skills,
        {"title": meal.title, "ingredients": meal.ingredients_json},
        servings=session.get(Settings, 1).household_size)
    settings = session.get(Settings, 1)
    if not (llm_client.is_configured() and settings.use_llm_directly):
        return _prompt_response(request, prompt, show_recipe_save=True)
    try:
        parsed = rp.parse_recipe_response(llm_client.complete(prompt))
    except (llm_client.LLMError, rp.ParseError):
        return _prompt_response(request, prompt, show_recipe_save=True, notice=FALLBACK_NOTICE)
    return templates.TemplateResponse("partials/_recipe_cards.html", {
        "request": request, "recipes": [parsed.model_dump()],
        "reroll_to": None, "reroll_fields": {}, "exclude_value": ""})
