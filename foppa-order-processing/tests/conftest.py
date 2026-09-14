"""
conftest.py — patch the catalog with deterministic demo data during tests.

Why this matters:
    - Prevents tests from loading the real Excel files (20–40 s per run)
    - Makes assertions predictable regardless of the production dataset
    - Ensures tests pass even without USE_REAL_DATA=true or the actual .xlsx files

The fixture is autouse=True so it applies to every test automatically.
"""
from __future__ import annotations

import pytest
from app.schemas import Product


# ─── Deterministic mini-catalog for tests ─────────────────────────────────────
_TEST_CATALOG = [
    Product(
        code="FPN1T",
        description="FRUCHTPUREE MANGO 1kg GEFR. FRUITIERE",
        unit="BEG",
        package_size="1 kg",
        aliases=["mango puree", "mango piree", "fruchtpueree mango"],
    ),
    Product(
        code="OEG25",
        description="SONNENBLUMENOEL 10l BIG CHEF",
        unit="KAN",
        package_size="10 l",
        aliases=["sonnenblumenoel big chef", "sunflower oil big chef", "oel big chef"],
    ),
    Product(
        code="EI35F",
        description="EIER SPEZIAL 180er OX (L) 63-73g",
        unit="KRT",
        package_size="180 pcs",
        aliases=["180er eier l", "eggs l", "large eggs", "eier spezial l"],
    ),
    Product(
        code="KART02",
        description="KARTOFFELSALAT 2kg HAUSGEMACHT",
        unit="KRT",
        package_size="2 kg",
        aliases=["kartoffelsalat", "potato salad", "patate insalata"],
    ),
    Product(
        code="TOM10",
        description="TOMATENSAUCE PASSIERT 10kg",
        unit="EIM",
        package_size="10 kg",
        aliases=["tomatensauce", "passata", "tomato sauce"],
    ),
    Product(
        code="KON05",
        description="KONFITUERE ERDBEER 2kg",
        unit="EIM",
        package_size="2 kg",
        aliases=["konfituere erdbeer", "strawberry jam", "marmelade erdbeer"],
    ),
]

_TEST_HISTORY: dict[str, list[str]] = {
    "CUST-DEMO":     ["FPN1T", "OEG25", "EI35F"],
    "CUST-PIZZA":    ["TOM10", "OEG25"],
    "CUST-CATERING": ["KART02", "EI35F", "FPN1T"],
}


@pytest.fixture(autouse=True)
def patch_catalog(monkeypatch):
    """
    Replace CATALOG and CUSTOMER_HISTORY in matching.py for every test.
    monkeypatch restores the originals automatically after each test.
    """
    import app.matching as m
    monkeypatch.setattr(m, "CATALOG", _TEST_CATALOG)
    monkeypatch.setattr(m, "CUSTOMER_HISTORY", _TEST_HISTORY)
