"""
sample_data.py

Loads real Foppa data when USE_REAL_DATA=true is set in the environment,
otherwise falls back to the demo catalog for local development and testing.

Production / real data:
    export USE_REAL_DATA=true
    python app.py

Development / testing (default):
    python app.py          # or: pytest
"""
from __future__ import annotations

import os
from pathlib import Path

from .schemas import Product


# ─── Demo catalog ─────────────────────────────────────────────────────────────
# Used in development and tests. Matches the product codes expected by tests.
_DEMO_CATALOG: list[Product] = [
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

_DEMO_HISTORY: dict[str, list[str]] = {
    "CUST-DEMO": ["FPN1T", "OEG25", "EI35F"],
    "CUST-PIZZA": ["TOM10", "OEG25"],
    "CUST-CATERING": ["KART02", "EI35F", "FPN1T"],
}


# ─── Real data loaders ─────────────────────────────────────────────────────────
def _load_real_catalog() -> list[Product]:
    import pandas as pd

    _masterdata = Path(__file__).resolve().parents[2] / "data" / "masterdata"

    # Prefer the version with product groups (more complete)
    archive = _masterdata / "CompleteItemArchivewithProductgroup.xlsx"
    if not archive.exists():
        archive = _masterdata / "CompleteItemArchive.xlsx"

    df = pd.read_excel(archive)
    df.columns = [c.strip() for c in df.columns]

    products: list[Product] = []
    for _, row in df.iterrows():
        code = str(row.get("ItemCode", "")).strip()
        if not code or code == "nan":
            continue

        desc_de = str(row.get("DescriptionGerman", "") or "").strip()
        desc_it = str(row.get("DescriptionItalian", "") or "").strip()
        unit    = str(row.get("UnitofMeasurement", "") or "").strip()
        pcper   = row.get("PCPerUnit", "")

        description = desc_de or desc_it or code
        aliases: list[str] = []
        if desc_it and desc_it != desc_de:
            aliases.append(desc_it.lower())

        products.append(
            Product(
                code=code,
                description=description,
                unit=unit or "Stk",
                package_size=str(pcper) if pd.notna(pcper) else "",
                aliases=aliases,
            )
        )
    return products


def _load_real_customer_history() -> dict[str, list[str]]:
    import pandas as pd

    _masterdata = Path(__file__).resolve().parents[2] / "data" / "masterdata"
    schablone = _masterdata / "Schablone.xlsx"

    df = pd.read_excel(schablone)
    df.columns = [c.strip() for c in df.columns]

    history: dict[str, list[str]] = {}
    for cust, group in df.groupby("Customercode"):
        codes = group["ItemCode"].dropna().astype(str).str.strip().tolist()
        history[str(cust).strip()] = codes
    return history


# ─── Switch: demo vs real ──────────────────────────────────────────────────────
if os.getenv("USE_REAL_DATA", "false").lower() == "true":
    print("Loading real Foppa catalog… (this may take 20–40 s)")
    CATALOG: list[Product] = _load_real_catalog()
    CUSTOMER_HISTORY: dict[str, list[str]] = _load_real_customer_history()
    print(f"  Loaded {len(CATALOG)} catalog items, {len(CUSTOMER_HISTORY)} customer templates")
else:
    CATALOG = _DEMO_CATALOG
    CUSTOMER_HISTORY = _DEMO_HISTORY

DEMO_TEXT = """Mango puree 1
Sonnenblumenoel Big Chef 2
180er Eier L 4
morgen liefern"""
