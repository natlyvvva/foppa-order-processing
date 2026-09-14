from __future__ import annotations

import re
import unicodedata
from typing import Iterable, List

from rapidfuzz import fuzz

from .sample_data import CATALOG, CUSTOMER_HISTORY
from .schemas import ExtractedOrder, MatchedItem, MatchedOrder, Product, ProductCandidate


# ─── Synonyms: map informal/short words to catalog vocabulary ─────────────────
SYNONYMS = {
    "oil": "oel", "ol": "oel", "oele": "oel", "oleo": "oel",
    "sunflower": "sonnenblumenoel", "sunfloweroil": "sonnenblumenoel",
    "egg": "eier", "eggs": "eier", "ei": "eier",
    "large": "l", "gross": "l", "grosse": "l",
    "puree": "puree", "piree": "puree", "pueree": "puree",
    "fruchtpueree": "fruchtpuree",
    "potato": "kartoffel", "salad": "salat",
    "marmelade": "konfituere", "marmellata": "konfituere",  # jam → catalog term
    "naturjoghurt": "joghurt natur", "naturjogurt": "joghurt natur",
    "joghurt": "joghurt", "jogurt": "joghurt", "yogurt": "joghurt",
    "kuebl": "kuebel", "kübl": "kuebel",
}

# German compound-word splits: help match "Naturjoghurt" → "natur joghurt"
COMPOUND_HINTS = ["joghurt", "jogurt", "oel", "salat", "brot", "milch",
                  "sauce", "creme", "konfituere", "marmelade", "kartoffel",
                  "tomaten", "zucker", "mehl", "kaese", "schinken"]


def normalize(value: str) -> str:
    value = value.lower()
    # German umlaut normalization
    value = (value.replace("ä", "a").replace("ö", "o").replace("ü", "u")
                  .replace("ae", "a").replace("oe", "o").replace("ue", "u")
                  .replace("ß", "ss"))
    value = unicodedata.normalize("NFKD", value)
    value = value.encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def split_compounds(text: str) -> str:
    """Insert spaces inside German compounds so tokens match better."""
    words = text.split()
    out = []
    for w in words:
        added = False
        for hint in COMPOUND_HINTS:
            if hint in w and w != hint and len(w) > len(hint) + 2:
                # split around the hint: "naturjoghurt" -> "natur joghurt"
                idx = w.find(hint)
                before = w[:idx]
                after = w[idx + len(hint):]
                parts = [p for p in (before, hint, after) if p]
                out.extend(parts)
                added = True
                break
        if not added:
            out.append(w)
    return " ".join(out)


def tokens(value: str) -> List[str]:
    norm = split_compounds(normalize(value))
    result = []
    for token in norm.split():
        result.append(SYNONYMS.get(token, token))
    return result


def product_search_text(product: Product) -> str:
    return " ".join(
        [product.code, product.description, product.unit,
         product.package_size, *product.aliases]
    )


def text_similarity(left: str, right: str) -> int:
    """
    Improved similarity using rapidfuzz token_set_ratio.
    token_set_ratio ignores word order and extra words — ideal for
    matching 'Naturjoghurt Brimi' against 'JOGHURT GEZUCKERT NATUR BRIMI'.
    """
    left_norm = " ".join(tokens(left))
    right_norm = " ".join(tokens(right))
    if not left_norm or not right_norm:
        return 0

    # token_set_ratio: best for partial / reordered matches
    set_ratio = fuzz.token_set_ratio(left_norm, right_norm)
    # token_sort_ratio: handles word-order differences
    sort_ratio = fuzz.token_sort_ratio(left_norm, right_norm)
    # partial_ratio: catches substring matches
    partial = fuzz.partial_ratio(left_norm, right_norm)

    # Weighted blend; token_set is the strongest signal here
    score = max(set_ratio, sort_ratio, partial * 0.9)
    return round(score)


def history_products(customer_code: str) -> List[Product]:
    history_codes = set(CUSTOMER_HISTORY.get(customer_code, []))
    return [product for product in CATALOG if product.code in history_codes]


def score_product(raw_text: str, product: Product, customer_code: str) -> ProductCandidate:
    base = text_similarity(raw_text, product_search_text(product))
    history_boost = 8 if product.code in CUSTOMER_HISTORY.get(customer_code, []) else 0
    score = min(100, base + history_boost)
    stage = "customer_template" if history_boost else "catalog"
    explanation = (
        f"Matched '{raw_text}' against {product.code}; base score {base}"
        f"{' plus customer-history boost' if history_boost else ''}."
    )
    return ProductCandidate(
        code=product.code,
        description=product.description,
        unit=product.unit,
        package_size=product.package_size,
        score=score,
        stage=stage,
        explanation=explanation,
    )


def rank_products(raw_text: str, products: List[Product], customer_code: str) -> List[ProductCandidate]:
    ranked = [score_product(raw_text, product, customer_code) for product in products]
    return sorted(ranked, key=lambda candidate: candidate.score, reverse=True)


def match_order(order: ExtractedOrder, customer_code: str, threshold: int = 85) -> MatchedOrder:
    matched_items: List[MatchedItem] = []
    template_products = history_products(customer_code)

    for item in order.items:
        # Stage 1+2: search customer template first
        template_ranked = rank_products(item.raw_text, template_products, customer_code)
        selected = template_ranked[0] if template_ranked else None
        alternatives: List[ProductCandidate] = template_ranked[1:4]

        # Stage 3: fallback to full catalog if below threshold
        if selected is None or selected.score < threshold:
            full_ranked = rank_products(item.raw_text, CATALOG, customer_code)
            # Only override if catalog finds something better
            if not selected or (full_ranked and full_ranked[0].score > selected.score):
                selected = full_ranked[0]
                selected.stage = "fallback_catalog"
                alternatives = [c for c in full_ranked[1:4] if c.code != selected.code]

        matched_items.append(
            MatchedItem(
                raw_text=item.raw_text,
                requested_quantity=item.quantity,
                requested_unit_hint=item.unit_hint,
                selected=selected,
                alternatives=alternatives,
            )
        )

    return MatchedOrder(
        customer_code=customer_code,
        delivery_note=order.delivery_note,
        items=matched_items,
    )
