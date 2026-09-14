from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ExtractedItem(BaseModel):
    raw_text: str = Field(description="Item phrase as recognized in the input.")
    quantity: Optional[float] = Field(default=None, description="Requested quantity if visible.")
    unit_hint: Optional[str] = Field(default=None, description="Unit or package hint from the input.")
    notes: Optional[str] = Field(default=None, description="Any item-specific comment.")


class ExtractedOrder(BaseModel):
    customer_hint: Optional[str] = Field(default=None, description="Customer name or hint if present.")
    delivery_note: Optional[str] = Field(default=None, description="Delivery note, e.g. deliver tomorrow.")
    raw_text: str = Field(description="Best recognized text or transcript.")
    items: List[ExtractedItem] = Field(default_factory=list)


class Product(BaseModel):
    code: str
    description: str
    unit: str
    package_size: str
    aliases: List[str] = Field(default_factory=list)


class ProductCandidate(BaseModel):
    code: str
    description: str
    unit: str
    package_size: str
    score: int
    stage: str
    explanation: str


class MatchedItem(BaseModel):
    raw_text: str
    requested_quantity: Optional[float]
    requested_unit_hint: Optional[str]
    selected: ProductCandidate
    alternatives: List[ProductCandidate] = Field(default_factory=list)


class MatchedOrder(BaseModel):
    customer_code: str
    delivery_note: Optional[str]
    items: List[MatchedItem]


class ExtractResponse(BaseModel):
    live_gemini: bool
    model: str
    customer_code: str
    extracted: ExtractedOrder
    matched: MatchedOrder


class FeedbackPayload(BaseModel):
    customer_code: str
    finalized_order: Dict[str, Any]
    reviewer_note: Optional[str] = None
