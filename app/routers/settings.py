from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from sqlmodel import Session, select
from ..db import get_session
from ..models import Settings, Tool, Skill
from ..main import templates  # templates configured in main
from .. import llm_client

router = APIRouter()


def _settings(session: Session) -> Settings:
    return session.get(Settings, 1)


@router.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request, session: Session = Depends(get_session)):
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "settings": _settings(session),
        "tools": session.exec(select(Tool)).all(),
        "skills": session.exec(select(Skill)).all(),
        "api_configured": llm_client.is_configured(),
    })


@router.post("/settings")
def update_settings(
    session: Session = Depends(get_session),
    household_size: int = Form(2),
    default_cook_time: int = Form(30),
    language: str = Form("fr"),
    restrictions: str = Form(""),
    allergies: str = Form(""),
    dislikes: str = Form(""),
    consumption_habits: str = Form(""),
    tools_notes: str = Form(""),
    skills_notes: str = Form(""),
    use_llm_directly: str = Form(None),
):
    s = _settings(session)
    s.household_size = household_size
    s.default_cook_time = default_cook_time
    s.language = language
    s.restrictions = restrictions
    s.allergies = allergies
    s.dislikes = dislikes
    s.consumption_habits = consumption_habits
    s.tools_notes = tools_notes
    s.skills_notes = skills_notes
    s.use_llm_directly = use_llm_directly is not None
    session.add(s); session.commit()
    return RedirectResponse("/settings", status_code=303)


@router.post("/settings/tools/{tool_id}/toggle", response_class=HTMLResponse)
def toggle_tool(tool_id: int, request: Request, session: Session = Depends(get_session)):
    tool = session.get(Tool, tool_id)
    tool.enabled = not tool.enabled
    session.add(tool); session.commit(); session.refresh(tool)
    return templates.TemplateResponse("partials/_toggle.html",
                                      {"request": request, "item": tool, "kind": "tools"})


@router.post("/settings/skills/{skill_id}/toggle", response_class=HTMLResponse)
def toggle_skill(skill_id: int, request: Request, session: Session = Depends(get_session)):
    skill = session.get(Skill, skill_id)
    skill.enabled = not skill.enabled
    session.add(skill); session.commit(); session.refresh(skill)
    return templates.TemplateResponse("partials/_toggle.html",
                                      {"request": request, "item": skill, "kind": "skills"})
