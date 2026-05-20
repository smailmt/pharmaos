"""Schemas Pydantic communs."""
from typing import Generic, TypeVar
from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class PaginatedResponse(APIModel, Generic[T]):
    items: list[T]
    total: int
    page: int = 1
    page_size: int = 50
