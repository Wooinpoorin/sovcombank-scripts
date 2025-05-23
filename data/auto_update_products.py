#!/usr/bin/env python3
import os
import sys
import json
import re
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
import fitz  # PyMuPDF

# ——————————————————————————————————————————————
# HTTP session with browser-like headers
session = requests.Session()
session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/117.0.0.0 Safari/537.36"
    ),
    "Referer": "https://sovcombank.ru/",
    "Accept": "application/pdf,application/octet-stream;q=0.9,*/*;q=0.8"
})

# ——————————————————————————————————————————————
# 1) PDF source (prod-api or env/CLI override)
PDF_URL = os.getenv("SOURCE_URL") or (
    sys.argv[1] if len(sys.argv) > 1 else
    "https://prod-api.sovcombank.ru/document/index?id=6335"
)

# 2) Output path
OUTPUT_PATH = os.getenv("OUTPUT_PATH") or (
    sys.argv[2] if len(sys.argv) > 2 else
    "data/products.json"
)

print(f"Parsing PDF from: {PDF_URL}")
print(f"Will write output to: {OUTPUT_PATH}")

# ——————————————————————————————————————————————
def parse_pdf(url: str) -> dict:
    """Download PDF and extract known products via regex."""
    resp = session.get(url)
    resp.raise_for_status()
    doc = fitz.open(stream=resp.content, filetype="pdf")
    text = "\n".join(p.get_text() for p in doc)

    patterns = {
        "premium_loan":   r"Премиальный кредит[^\d%]*(\d+,\d*)%[^\d]*(\d{1,3})\s*мес",
        "car_loan":       r"Автокредит[^\d%]*(\d+,\d*)%[^\d]*(\d{1,3})\s*мес",
        "consumer_loan":  r"Потребительский кредит без обеспечения[^\d%]*(\d+,\d*)%[^\d]*(\d{1,3})\s*мес",
        "refinance_loan": r"[Рр]ефинансирование[^\d%]*(\d+,\d*)%[^\d]*(\d{1,3})\s*мес",
        "grocery_loan":   r"Кредит для покупок продуктов[^\d%]*(\d+,\d*)%[^\d]*(\d{1,3})\s*мес",
        "travel_loan":    r"Кредит на путешествия[^\d%]*(\d+,\d*)%[^\d]*(\d{1,3})\s*мес"
    }

    out = {}
    for key, rx in patterns.items():
        m = re.search(rx, text, flags=re.IGNORECASE)
        if not m: 
            continue
        rate = float(m.group(1).replace(",", "."))
        term = int(m.group(2))
        out[key] = {
            "Ставка": rate,
            "Срок": term,
            "Обновлено": datetime.utcnow().isoformat()
        }
    return out

# ——————————————————————————————————————————————
def parse_halva(url: str) -> dict:
    """
    Attempt to fetch HalvaCard page. On 401/403, return empty dict
    so the Action doesn't fail.
    """
    try:
        resp = session.get(url)
        resp.raise_for_status()
    except requests.exceptions.HTTPError as e:
        print(f"Warning: HalvaCard fetch failed ({e}), skipping Halva data.")
        return {}

    soup = BeautifulSoup(resp.text, "html.parser")
    inst_el = soup.select_one(".installment-months")
    disc_el = soup.select_one(".partner-discount")

    months = int(inst_el.text.split()[0]) if inst_el else 0
    discount = int(re.sub(r"\D", "", disc_el.text)) if disc_el else 0

    return {
        "halva_card": {
            "installment_months": months,
            "discount": discount,
            "Описание": "Карточка рассрочки Halva",
            "Обновлено": datetime.utcnow().isoformat()
        }
    }

# ——————————————————————————————————————————————
# Build products dict and write JSON
products = {}
products.update(parse_pdf(PDF_URL))
products.update(parse_halva("https://halvacard.ru/"))

os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
    json.dump(products, f, ensure_ascii=False, indent=2)

print(f"Successfully updated {len(products)} products")
