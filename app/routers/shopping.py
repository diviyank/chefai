from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select
from ..db import get_session
from ..models import ShoppingItem, PantryItem, Settings
from ..main import templates

router = APIRouter()


@router.get("/shopping", response_class=HTMLResponse)
def shopping_page(request: Request, session: Session = Depends(get_session)):
    items = session.exec(select(ShoppingItem).order_by(ShoppingItem.store_type)).all()
    store_types = session.get(Settings, 1).store_types_json
    return templates.TemplateResponse("shopping.html",
                                      {"request": request, "items": items, "store_types": store_types})


@router.post("/shopping/add", response_class=HTMLResponse)
def add_shopping(request: Request, session: Session = Depends(get_session),
                 name: str = Form(...), qty_text: str = Form(""), store_type: str = Form("Autre")):
    item = ShoppingItem(name=name.strip(), qty_text=qty_text.strip() or None,
                        store_type=store_type, source="manual")
    session.add(item); session.commit(); session.refresh(item)
    return templates.TemplateResponse("partials/_shopping_item.html",
                                      {"request": request, "item": item})


@router.post("/shopping/{item_id}/check", response_class=HTMLResponse)
def check_item(item_id: int, request: Request, session: Session = Depends(get_session)):
    item = session.get(ShoppingItem, item_id)
    item.checked = True
    # Flow into pantry (idempotent upsert by name).
    existing = session.exec(select(PantryItem).where(PantryItem.name == item.name)).first()
    if existing is None:
        session.add(PantryItem(name=item.name, category="Autre", quantity_text=item.qty_text))
    else:
        existing.quantity_text = item.qty_text or existing.quantity_text
        session.add(existing)
    session.add(item); session.commit(); session.refresh(item)
    return templates.TemplateResponse("partials/_shopping_item.html",
                                      {"request": request, "item": item})


@router.get("/shopping/mode", response_class=HTMLResponse)
def shop_mode(request: Request, session: Session = Depends(get_session)):
    items = session.exec(select(ShoppingItem).where(ShoppingItem.checked == False)).all()  # noqa: E712
    grouped: dict[str, list] = {}
    for it in items:
        grouped.setdefault(it.store_type, []).append(it)
    return templates.TemplateResponse("shop_mode.html", {"request": request, "grouped": grouped})
