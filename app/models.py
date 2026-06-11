from datetime import date, datetime
from typing import Optional
from sqlalchemy import JSON
from sqlmodel import SQLModel, Field, Column


class PantryItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    category: str
    quantity_text: Optional[str] = None
    expiry_date: Optional[date] = None
    is_staple: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Settings(SQLModel, table=True):
    id: Optional[int] = Field(default=1, primary_key=True)
    household_size: int = 2
    default_cook_time: int = 30
    language: str = "fr"
    restrictions: str = ""
    allergies: str = ""
    dislikes: str = ""
    consumption_habits: str = ""
    tools_notes: str = ""
    skills_notes: str = ""
    use_llm_directly: bool = False  # copy-paste is the default; direct Claude is opt-in
    categories_json: list = Field(default_factory=list, sa_column=Column(JSON))
    store_types_json: list = Field(default_factory=list, sa_column=Column(JSON))


class Tool(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    enabled: bool = False


class Skill(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    enabled: bool = False


class PlanningSession(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    params_json: dict = Field(default_factory=dict, sa_column=Column(JSON))
    proposals_json: list = Field(default_factory=list, sa_column=Column(JSON))
    status: str = "proposed"  # proposed | validated | cancelled
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Meal(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    planning_session_id: int = Field(foreign_key="planningsession.id")
    day_index: int
    slot: str  # dejeuner | diner
    title: str
    ingredients_json: list = Field(default_factory=list, sa_column=Column(JSON))
    leftover_link: Optional[str] = None
    notes: str = ""


class Recipe(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    ingredients_json: list = Field(default_factory=list, sa_column=Column(JSON))
    steps_json: list = Field(default_factory=list, sa_column=Column(JSON))
    source: Optional[str] = None
    tags_json: list = Field(default_factory=list, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ShoppingItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    qty_text: Optional[str] = None
    category: Optional[str] = None
    store_type: str = "Autre"
    checked: bool = False
    source: str = "manual"  # plan | recipe | manual


class GenerationJob(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    kind: str = Field(index=True)
    status: str = "running"  # running | done | error
    params_json: str = "{}"
    prompt: str = ""
    result_json: Optional[str] = None
    notice: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
