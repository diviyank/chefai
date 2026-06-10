from typing import Optional
from pydantic import BaseModel, Field


class ShoppingLine(BaseModel):
    name: str
    qty: Optional[str] = None
    store_type: str = "Autre"


class Ingredient(BaseModel):
    name: str
    qty: Optional[str] = None


class Step(BaseModel):
    text: str
    duration_seconds: Optional[int] = None


class RecipeResponse(BaseModel):
    title: str
    ingredients: list[Ingredient] = Field(default_factory=list)
    steps: list[Step] = Field(default_factory=list)
    source: Optional[str] = None
    tags: list[str] = Field(default_factory=list)


class RecipeListResponse(BaseModel):
    recipes: list[RecipeResponse] = Field(default_factory=list)


class PlanMeal(BaseModel):
    slot: str  # dejeuner | diner
    title: str
    ingredients: list[str] = Field(default_factory=list)
    uses_leftovers_from: Optional[str] = None


class PlanDay(BaseModel):
    day: int
    meals: list[PlanMeal] = Field(default_factory=list)


class Plan(BaseModel):
    label: str
    days: list[PlanDay] = Field(default_factory=list)
    shopping_list: list[ShoppingLine] = Field(default_factory=list)


class PlanResponse(BaseModel):
    plans: list[Plan] = Field(default_factory=list)


class ShoppingResponse(BaseModel):
    shopping_list: list[ShoppingLine] = Field(default_factory=list)
