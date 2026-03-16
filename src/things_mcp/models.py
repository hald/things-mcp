from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ItemListResult(BaseModel):
    success: bool = True
    message: str
    count: int
    items: list[dict[str, Any]] = Field(default_factory=list)
    error: str | None = None


class ActionResult(BaseModel):
    success: bool = True
    action: Literal["create", "update", "show", "search"]
    message: str
    title: str | None = None
    target_id: str | None = None


class EnvelopeBase(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class ListEnvelope(EnvelopeBase):
    payload: ItemListResult = Field(alias="json")


class ActionEnvelope(EnvelopeBase):
    payload: ActionResult = Field(alias="json")
