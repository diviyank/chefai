from datetime import date, datetime
from typing import Optional
from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select
from ..db import get_session
from ..models import PantryItem, Settings
from ..enums import STAPLE_CATEGORIES
from ..main import templates

router = APIRouter()


def _categories(session: Session) -> list[str]:
    return session.get(Settings, 1).categories_json


@router.get("/pantry", response_class=HTMLResponse)
def pantry_page(request: Request, session: Session = Depends(get_session)):
    items = session.exec(select(PantryItem).order_by(PantryItem.category, PantryItem.name)).all()
    grouped: dict[str, list] = {}
    for it in items:
        grouped.setdefault(it.category, []).append(it)
    return templates.TemplateResponse("pantry.html", {
        "request": request, "grouped": grouped, "categories": _categories(session),
    })


@router.post("/pantry/add", response_class=HTMLResponse)
def add_item(
    request: Request,
    session: Session = Depends(get_session),
    name: str = Form(...),
    category: str = Form(...),
    quantity_text: str = Form(""),
    expiry_date: str = Form(""),
):
    parsed_expiry: Optional[date] = None
    if expiry_date:
        parsed_expiry = datetime.strptime(expiry_date, "%Y-%m-%d").date()
    item = PantryItem(
        name=name.strip(),
        category=category,
        quantity_text=quantity_text.strip() or None,
        expiry_date=parsed_expiry,
        is_staple=category in STAPLE_CATEGORIES,
    )
    session.add(item); session.commit(); session.refresh(item)
    return templates.TemplateResponse("partials/_pantry_item.html",
                                      {"request": request, "item": item})


@router.delete("/pantry/{item_id}", response_class=HTMLResponse)
def delete_item(item_id: int, session: Session = Depends(get_session)):
    item = session.get(PantryItem, item_id)
    if item:
        session.delete(item); session.commit()
    return HTMLResponse("")
