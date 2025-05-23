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
# Set up a requests session with browser-like headers
session = requests.Session()
session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/117.0.0.0 Safari/537.36"
    ),
    "Referer": "https://sovcombank.ru/",
    "Accept": "application/pdf,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
})

def resolve_pdf_url(page_url: str) -> str:
    """
    If the URL itself returns a PDF (checked by HEAD), return it.
    Otherwise, fetch the HTML and extract the first .pdf link.
    """
    # 1) HEAD to see if it's already a PDF
    try:
        head = session.head(page_url, allow_redirects=True)
        ctype = head.headers.get("content-type", "")
        if head.status_code == 200 and "application/pdf" in ctype:
            return page_url
    except requests.RequestException:
        pass

    # 2) Otherwise GET HTML and find a PDF link
    resp = session.get(page_url)
    resp.raise_for_status()
    html = resp.text

    # look for href="...pdf"
    m = re.search(r'href=["\']([^"\']+\.pdf)', html, re.IGNORECASE)
    if m:
        return urljoin(page_url, m.group(1))

    # try iframe src
    m = re.search(r'<iframe[^>]+src=["\']([^"\']+\.pdf)', html, re.IGNORECASE)
    if m:
        return urljoin(page_url, m.group(1))

    # fallback: raw PDF URL anywhere
    m = re.search(r'(https?://[^"\'>\s]+\.pdf)', html, re.IGNORECASE)
    if m:
        return m.group(1)

    raise RuntimeError(f"PDF link not found on page: {page_url}")

# ——————————————————————————————————————————————
# 1) PDF source: from env or CLI
PDF_PAGE = os.getenv("SOURCE_URL") or (sys.argv[1] if len(sys.argv) > 1 else None)
if not PDF_PAGE:
    raise RuntimeError("Please set SOURCE_URL or pass the PDF page/URL as first argument")

PDF_URL = resolve_pdf_url(PDF_PAGE)

# 2) Output path
OUTPUT_PATH = os.getenv("OUTPUT_PATH") or (sys.argv[2] if len(sys.argv) > 2 else "data/products.json")

# 3) HalvaCard URL
HALVA_URL = "https://halvacard.ru/"

print("Using PDF for parsing:", PDF_URL)
print("Output will be written to:", OUTPUT_PATH)

# ——————————————————————————————————————————————
def parse_pdf(url: str) -> dict:
    """
    Download the PDF and extract known loan products using regex.
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
    for key, rx in patterns.items():
        match = re.search(rx, text, flags=re.IGNORECASE)
        if not match:
            continue
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
    Fetch HalvaCard page and extract installment and discount.
    """
    resp = session.get(url)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    inst = soup.select_one(".installment-months")
    disc = soup.select_one(".partner-discount")

    months = int(inst.text.split()[0]) if inst else 0
    discount = int(re.sub(r"\D", "", disc.text)) if disc else 0

    return {
        "halva_card": {
            "installment_months": months,
            "discount": discount,
            "Описание": "Карточка рассрочки Halva",
            "Обновлено": datetime.utcnow().isoformat()
        }
    }

# ——————————————————————————————————————————————
# Build and write JSON
products = {}
products.update(parse_pdf(PDF_URL))
products.update(parse_halva(HALVA_URL))

os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
    json.dump(products, f, ensure_ascii=False, indent=2)

print(f"Successfully updated {len(products)} products")
