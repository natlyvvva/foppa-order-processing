from __future__ import annotations

import os
from typing import Optional

from .sample_data import DEMO_TEXT
from .schemas import ExtractedItem, ExtractedOrder


# ─── Base extraction prompt ────────────────────────────────────────────────────
EXTRACTION_PROMPT = """You are an intelligent data extraction assistant for a food-wholesale ERP system.

Your task: extract structured order data from the provided input (text, PDF, or image).

Return ONLY valid JSON matching the ExtractedOrder schema. Do not invent article codes.

Extraction rules:
- Each ordered item → separate entry in the items list
- Quantities: numbers immediately before or after item names
- Unit hints: packaging units like KAN, KRT, BEG, SAC, DOS, BRI, STK, EIM
- Delivery notes (e.g. "morgen liefern", "deliver tomorrow", "consegna domani") → delivery_note field, NOT items
- Customer name or code → customer_hint if visible
- Preserve the original spelling exactly in raw_text, even if it seems misspelled
- If a value is uncertain, include it anyway and flag uncertainty in the notes field
"""

# ─── Input-type-specific prompt additions ─────────────────────────────────────
_PDF_INSTRUCTIONS = """
PDF-specific instructions:
- Extract ALL line items from every page of the document.
- Tables: treat each row as a separate item; use column headers to identify
  quantity and unit columns.
- Page headers, footers, and company logos are NOT order items — ignore them.
- Handwritten annotations: include in raw_text with a "(handwritten)" note if
  they differ from printed text.
- Multiple pages: treat as a single order and collect all items across pages.
- If text is partially illegible, preserve what you can and flag it in notes.
"""

_IMAGE_INSTRUCTIONS = """
Image/scan-specific instructions:
- This is a photo or scan of a handwritten or printed order list.
- Each line on the list is typically a separate item.
- Numbers at the start or end of a line are usually quantities.
- Preserve the original spelling exactly in raw_text — even if misspelled.
- If handwriting is unclear, write your best guess and add "(unclear)" in notes.
- Crossed-out items should be omitted entirely.
"""

_TEXT_INSTRUCTIONS = """
Plain-text instructions:
- Each line or comma-separated entry is typically a separate item.
- Lines containing only logistics info ("deliver tomorrow", "urgent") → delivery_note.
"""


def _build_prompt(mime_type: Optional[str], extra_text: Optional[str]) -> str:
    """Assemble a context-aware prompt based on the input media type."""
    prompt = EXTRACTION_PROMPT

    if mime_type:
        if "pdf" in mime_type.lower():
            prompt += _PDF_INSTRUCTIONS
        elif mime_type.lower().startswith("image/"):
            prompt += _IMAGE_INSTRUCTIONS
        else:
            prompt += _TEXT_INSTRUCTIONS
    else:
        prompt += _TEXT_INSTRUCTIONS

    if extra_text and extra_text.strip():
        prompt += f"\n\nAdditional context from the user:\n{extra_text.strip()}"

    return prompt


def parse_order_json(raw_json: str) -> ExtractedOrder:
    if hasattr(ExtractedOrder, "model_validate_json"):
        return ExtractedOrder.model_validate_json(raw_json)
    return ExtractedOrder.parse_raw(raw_json)


def demo_extraction(text: Optional[str] = None) -> ExtractedOrder:
    raw_text = text.strip() if text and text.strip() else DEMO_TEXT
    return ExtractedOrder(
        customer_hint=None,
        delivery_note="morgen liefern" if "morgen" in raw_text.lower() else None,
        raw_text=raw_text,
        items=[
            ExtractedItem(raw_text="Mango puree", quantity=1, unit_hint="BEG"),
            ExtractedItem(raw_text="Sonnenblumenoel Big Chef", quantity=2, unit_hint="KAN"),
            ExtractedItem(raw_text="180er Eier L", quantity=4, unit_hint="KRT"),
        ],
    )


class GeminiOrderExtractor:
    def __init__(self) -> None:
        # gemini-2.0-flash is the current stable model (3-flash-preview was renamed)
        self.model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-preview-05-20")
        self.api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

    @property
    def live_enabled(self) -> bool:
        return bool(self.api_key)

    def extract(
        self,
        *,
        text: Optional[str] = None,
        file_bytes: Optional[bytes] = None,
        mime_type: Optional[str] = None,
    ) -> ExtractedOrder:
        if not self.live_enabled:
            return demo_extraction(text)

        from google import genai
        from google.genai import types

        client = genai.Client(api_key=self.api_key)
        contents = []

        # File goes first so Gemini sees it before the prompt
        if file_bytes and mime_type:
            contents.append(types.Part.from_bytes(data=file_bytes, mime_type=mime_type))

        # Build a context-aware prompt based on input type
        prompt = _build_prompt(mime_type=mime_type, extra_text=text)
        contents.append(prompt)

        response = client.models.generate_content(
            model=self.model,
            contents=contents,
            config=types.GenerateContentConfig(
                temperature=0,
                response_mime_type="application/json",
                response_schema=ExtractedOrder,
            ),
        )

        return parse_order_json(response.text)
