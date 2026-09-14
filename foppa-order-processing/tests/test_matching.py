"""
test_matching.py

Tests for the three-stage matching pipeline and normalisation helpers.

The catalog is replaced with a fast demo dataset via conftest.py (autouse fixture),
so every test runs in milliseconds regardless of the real Excel file size.

Test coverage:
  - Stage 1/2: customer-template matching and history boost
  - Stage 3: fallback to full catalog
  - Synonym mapping (Student Exercise 1 — marmelade → konfituere)
  - Multilingual input (English synonym: sunflower oil)
  - Alternative suggestions
  - normalize() helper: umlauts, punctuation
  - text_similarity() helper: symmetry, perfect match
"""
from __future__ import annotations

import pytest
from app.matching import match_order, normalize, text_similarity, tokens
from app.schemas import ExtractedItem, ExtractedOrder


# ─── Helper ───────────────────────────────────────────────────────────────────
def make_order(raw_text: str) -> ExtractedOrder:
    return ExtractedOrder(
        raw_text=raw_text,
        delivery_note=None,
        items=[ExtractedItem(raw_text=raw_text, quantity=2, unit_hint=None)],
    )


# ─── Stage 1 / 2: customer template ───────────────────────────────────────────
def test_matches_customer_template_product():
    """A product in the customer's template should be found with high confidence."""
    matched = match_order(make_order("Sonnenblumenoel Big Chef"), "CUST-DEMO")
    item = matched.items[0]
    assert item.selected.code == "OEG25"
    assert item.selected.stage == "customer_template"
    assert item.selected.score >= 85


def test_template_match_uses_history_boost():
    """A template product should outscore a catalog-only product for the same query."""
    matched = match_order(make_order("Mango puree"), "CUST-DEMO")
    item = matched.items[0]
    assert item.selected.code == "FPN1T"
    assert item.selected.stage == "customer_template"


# ─── Stage 3: fallback to full catalog ────────────────────────────────────────
def test_falls_back_to_catalog_for_product_outside_template():
    """KART02 is not in CUST-DEMO's template, so the fallback stage must fire."""
    matched = match_order(make_order("Kartoffelsalat 2kg"), "CUST-DEMO")
    item = matched.items[0]
    assert item.selected.code == "KART02"
    assert item.selected.stage == "fallback_catalog"


def test_fallback_triggered_when_threshold_not_met():
    """Setting an impossibly high threshold forces every match into fallback."""
    matched = match_order(make_order("sauce"), "CUST-DEMO", threshold=95)
    item = matched.items[0]
    assert item.selected.stage == "fallback_catalog"


# ─── Alternatives ─────────────────────────────────────────────────────────────
def test_returns_alternatives():
    matched = match_order(make_order("sauce"), "CUST-DEMO", threshold=95)
    assert len(matched.items[0].alternatives) > 0


def test_alternatives_differ_from_selected():
    """Every alternative must have a different code from the selected item."""
    matched = match_order(make_order("sauce"), "CUST-DEMO", threshold=95)
    selected_code = matched.items[0].selected.code
    for alt in matched.items[0].alternatives:
        assert alt.code != selected_code


# ─── Multilingual / synonym handling ──────────────────────────────────────────
def test_handles_english_synonym_sunflower_oil():
    """English 'sunflower oil big chef' should resolve to OEG25 via SYNONYMS."""
    matched = match_order(make_order("sunflower oil big chef"), "CUST-DEMO")
    assert matched.items[0].selected.code == "OEG25"


# ─── Student Exercise 1: new synonym + proof via test ─────────────────────────
def test_marmelade_synonym_maps_to_konfituere():
    """
    'marmelade' was added to SYNONYMS as a new term mapping to 'konfituere'.
    This test proves the synonym works at the token level.
    """
    result = tokens("Marmelade Erdbeer 1kg")
    assert "konfituere" in result, (
        f"Expected 'konfituere' in tokens, but got: {result}\n"
        f"Check that SYNONYMS['marmelade'] = 'konfituere' is present in matching.py."
    )


def test_marmellata_synonym_maps_to_konfituere():
    """Italian 'marmellata' should also map to 'konfituere'."""
    result = tokens("marmellata fragole")
    assert "konfituere" in result


def test_marmelade_matches_konfituere_product_end_to_end():
    """
    End-to-end: a 'Marmelade Erdbeer' query must find the KON05 product.
    This validates that the synonym flows all the way through the pipeline.
    """
    matched = match_order(make_order("Marmelade Erdbeer"), "CUST-DEMO")
    assert matched.items[0].selected.code == "KON05", (
        f"Expected KON05 but got {matched.items[0].selected.code} "
        f"(score={matched.items[0].selected.score})"
    )


# ─── normalize() helper ───────────────────────────────────────────────────────
def test_normalize_unicode_umlauts():
    """Unicode umlauts should be collapsed to plain ASCII."""
    assert normalize("Käse") == "kase"
    assert normalize("Öl") == "ol"
    assert normalize("Müsli") == "musli"
    assert normalize("Grüße") == "grusse"


def test_normalize_removes_punctuation():
    """Punctuation and special characters should be stripped."""
    assert normalize("3x Big-Chef!") == "3x big chef"


def test_normalize_collapses_whitespace():
    assert normalize("  Mango   Puree  ") == "mango puree"


# ─── text_similarity() helper ─────────────────────────────────────────────────
def test_text_similarity_perfect_match():
    assert text_similarity("Mango puree", "Mango puree") == 100


def test_text_similarity_is_symmetric():
    a = "Sonnenblumenoel"
    b = "sunflower oil"
    assert text_similarity(a, b) == text_similarity(b, a)


def test_text_similarity_unrelated_strings_score_low():
    score = text_similarity("Mango puree", "Kartoffelsalat 2kg")
    assert score < 50
