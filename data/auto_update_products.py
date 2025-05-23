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

# — Set up HTTP session with browser-like headers —
session = requests.Session()
session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/117.0.0.0 Safari/537.36"
    ),
    "Referer": "https://sovcombank.ru/",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
})

def resolve_pdf_url(page_url: str) -> str:
    """
    If the URL ends with .pdf, return it; otherwise fetch the page
    and extract the first PDF link.
    """
    if page_url.lower().endswith(".pdf"):
        return page_url

    resp = session.get(page_url)
    resp.raise_for_status()
    html = resp.text

    # look for href="...pdf"
    m = re.search(r'href=["\']([^"\']+\.pdf)', html, re.IGNORECASE)
    if not m:
        raise RuntimeError(f"PDF link not found on page: {page_url}")
    return urljoin(page_url, m.group(1))

# 1) Determine PDF source
PDF_PAGE = os.getenv("SOURCE_URL") or (sys.argv[1] if len(sys.argv) > 1 else None)
if not PDF_PAGE:
    raise RuntimeError("Please set SOURCE_URL or pass the PDF URL as an argument")
PDF_URL = resolve_pdf_url(PDF_PAGE)

# 2) Determine output path
OUTPUT_PATH = os.getenv("OUTPUT_PATH") or (sys.argv[2] if len(sys.argv) > 2 else "data/products.json")

# 3) HalvaCard URL
HALVA_URL = "https://halvacard.ru/"

print(f"Parsing PDF from: {PDF_URL}")
print(f"Saving to: {OUTPUT_PATH}")

def parse_pdf(url: str) -> dict:
    """
    Download PDF, extract text, and match known loan products
    by Russian-language patterns.
    """
    resp = session.get(url)
    resp.raise_for_status()

    doc = fitz.open(stream=resp.content, filetype="pdf")
    text = "\n".join(page.get_text() for page in doc)

    patterns = {
        "premium_loan":   r"Премиальный кредит[^\d%]*(\d+,\d*)%[^\d]*(\d{1,3})\s*мес",
        "car_loan":       r"Автокредит[^\d%]*(\d+,\d*)%[^\d]*(\d{1,3})\s*мес",
        "consumer_loan":  r"Потребительский кредит без обеспечения[^\d%]*(\d+,\d*)%[^\d]*(\d{1,3})\s*мес",
        "refinance_loan": r"[Рр]ефинансирование[^\d%]*(\d+,\d*)%[^\d]*(\d{1,3})\s*мес",
        "grocery_loan":   r"Кредит для покупок продуктов[^\d%]*(\d+,\d*)%[^\d]*(\d{1,3})\s*мес",
        "travel_loan":    r"Кредит на путешествия[^\d%]*(\d+,\d*)%[^\d]*(\d{1,3})\s*мес"
    }

    out = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            rate = float(match.group(1).replace(",", "."))
            term = int(match.group(2))
            out[key] = {
                "Ставка": rate,
                "Срок": term,
                "Обновлено": datetime.utcnow().isoformat()
            }
    return out

def parse_halva(url: str) -> dict:
    """
    Download HalvaCard page and extract installment months and discount.
    """
    resp = session.get(url)
    resp.raise_for_status()
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

# Build final products dictionary
products = {}
products.update(parse_pdf(PDF_URL))
products.update(parse_halva(HALVA_URL))

# Ensure directory exists and write JSON
os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
    json.dump(products, f, ensure_ascii=False, indent=2)

print(f"Successfully updated {len(products)} products")
