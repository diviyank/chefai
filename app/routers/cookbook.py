from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select
from ..db import get_session
from ..models import Recipe, PantryItem
from .. import response_parser as rp
from .. import decrement as dec
from ..main import templates

router = APIRouter()


@router.get("/cookbook", response_class=HTMLResponse)
def cookbook_page(request: Request, session: Session = Depends(get_session)):
    return templates.TemplateResponse("cookbook.html",
                                      {"request": request, "recipes": _filter_recipes(session, "")})


@router.post("/cookbook/save")
def save_recipe(request: Request, session: Session = Depends(get_session), raw: str = Form(...)):
    is_htmx = bool(request.headers.get("HX-Request"))
    try:
        parsed = rp.parse_recipe_response(raw)
    except rp.ParseError as exc:
        if is_htmx:  # re-render the box with the message + preserved text so the user can retry
            return templates.TemplateResponse(
                "partials/_recipe_save_box.html",
                {"request": request, "error": str(exc), "raw": raw})
        return templates.TemplateResponse("partials/_parse_error.html",
                                          {"request": request, "message": str(exc)})
    recipe = Recipe(
        title=parsed.title,
        ingredients_json=[i.model_dump() for i in parsed.ingredients],
        steps_json=[s.model_dump() for s in parsed.steps],
        source=parsed.source, tags_json=parsed.tags)
    session.add(recipe); session.commit(); session.refresh(recipe)
    if is_htmx:  # saved inline from the cook page → replace the form with a confirmation
        return templates.TemplateResponse("partials/_recipe_saved.html",
                                          {"request": request, "recipe": recipe})
    return RedirectResponse("/cookbook", status_code=303)


@router.get("/cookbook/search", response_class=HTMLResponse)
def search_recipes(request: Request, q: str = "", session: Session = Depends(get_session)):
    recipes = _filter_recipes(session, q)
    return templates.TemplateResponse("partials/_recipe_list.html",
                                      {"request": request, "recipes": recipes})


@router.post("/cookbook/{recipe_id}/delete")
def delete_recipe(recipe_id: int, request: Request, session: Session = Depends(get_session)):
    recipe = session.get(Recipe, recipe_id)
    if recipe is not None:
        session.delete(recipe); session.commit()
    if request.headers.get("HX-Request"):  # remove just the row from the list
        return HTMLResponse("")
    return RedirectResponse("/cookbook", status_code=303)


def _filter_recipes(session: Session, q: str) -> list[Recipe]:
    """Recipes newest-first, optionally filtered by a case-insensitive title/tag match."""
    recipes = session.exec(select(Recipe).order_by(Recipe.created_at.desc())).all()
    needle = q.strip().lower()
    if not needle:
        return list(recipes)
    return [r for r in recipes
            if needle in r.title.lower()
            or any(needle in str(tag).lower() for tag in (r.tags_json or []))]


@router.get("/cookbook/{recipe_id}", response_class=HTMLResponse)
def recipe_detail(recipe_id: int, request: Request, session: Session = Depends(get_session)):
    recipe = session.get(Recipe, recipe_id)
    return templates.TemplateResponse("recipe_detail.html", {"request": request, "recipe": recipe})


@router.get("/cookbook/{recipe_id}/cook", response_class=HTMLResponse)
def cook_mode(recipe_id: int, request: Request, session: Session = Depends(get_session)):
    recipe = session.get(Recipe, recipe_id)
    return templates.TemplateResponse("cook_mode.html", {"request": request, "recipe": recipe})


@router.get("/cookbook/{recipe_id}/finish", response_class=HTMLResponse)
def finish_cooking(recipe_id: int, request: Request, session: Session = Depends(get_session)):
    recipe = session.get(Recipe, recipe_id)
    pantry = [{"id": i.id, "name": i.name, "quantity_text": i.quantity_text, "is_staple": i.is_staple}
              for i in session.exec(select(PantryItem)).all()]
    proposals = dec.compute_decrement(pantry, recipe.ingredients_json)
    return templates.TemplateResponse("decrement_review.html",
                                      {"request": request, "recipe": recipe, "proposals": proposals})


@router.post("/cookbook/decrement/apply")
async def apply_decrement(request: Request, session: Session = Depends(get_session)):
    form = await request.form()
    for key, action in form.items():
        if not key.startswith("action_"):
            continue
        item_id = int(key.removeprefix("action_"))
        item = session.get(PantryItem, item_id)
        if item is None:
            continue
        if action == "remove":
            session.delete(item)
        elif action == "subtract":
            item.quantity_text = form.get(f"qty_{item_id}") or item.quantity_text
            session.add(item)
        # action == "keep": no change
    session.commit()
    return RedirectResponse("/pantry", status_code=303)
