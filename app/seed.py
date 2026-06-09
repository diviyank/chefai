from sqlmodel import Session, select
from .models import Settings, Tool, Skill
from .enums import (
    DEFAULT_CATEGORIES, DEFAULT_STORE_TYPES, DEFAULT_TOOLS, DEFAULT_SKILLS,
)


def seed(session: Session) -> None:
    if session.get(Settings, 1) is None:
        session.add(Settings(
            id=1,
            categories_json=list(DEFAULT_CATEGORIES),
            store_types_json=list(DEFAULT_STORE_TYPES),
        ))
    existing_tools = {t.name for t in session.exec(select(Tool)).all()}
    for name in DEFAULT_TOOLS:
        if name not in existing_tools:
            session.add(Tool(name=name, enabled=False))
    existing_skills = {s.name for s in session.exec(select(Skill)).all()}
    for name in DEFAULT_SKILLS:
        if name not in existing_skills:
            session.add(Skill(name=name, enabled=False))
    session.commit()
