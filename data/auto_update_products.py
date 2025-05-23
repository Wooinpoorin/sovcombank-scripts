#!/usr/bin/env python3
import os, sys, json, re
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
import fitz  # PyMuPDF

# — эмулируем браузер во всех запросах —
session = requests.Session()
session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/117.0.0.0 Safari/537.36"
    ),
    "Referer": "https://sovcombank.ru/",
    "Accept": "*/*"
})

# 1) читаем SOURCE_URL — ОБЯЗАТЕЛЬНО ПРЯМОЙ .pdf
PDF_URL = os.getenv("SOURCE_URL") or (sys.argv[1] if len(sys.argv)>1 else None)
if not PDF_URL or not PDF_URL.lower().endswith(".pdf"):
    raise RuntimeError(
        "ERROR: SOURCE_URL должен указывать на прямой PDF-файл, например:\n"
        "  https://sovcombank.ru/upload/iblock/XYZ/conditions.pdf\n"
        "Нельзя передавать страницу описания."
    )

# 2) куда сохраняем
OUTPUT = os.getenv("OUTPUT_PATH") or (sys.argv[2] if len(sys.argv)>2 else "data/products.json")

HALVA_URL = "https://halvacard.ru/"

print("PDF_URL:", PDF_URL)
print("OUTPUT:", OUTPUT)

def parse_pdf(url):
    r = session.get(url); r.raise_for_status()
    doc = fitz.open(stream=r.content, filetype="pdf")
    text = "\n".join(p.get_text() for p in doc)
    # набор продуктов + русские шаблоны
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
        m = re.search(rx, text, re.IGNORECASE)
        if not m: continue
        rate = float(m.group(1).replace(",","."))
        term = int(m.group(2))
        out[key] = {"Ставка": rate, "Срок": term, "Обновлено": datetime.utcnow().isoformat()}
    return out

def parse_halva(url):
    r = session.get(url); r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    inst = soup.select_one(".installment-months")
    disc = soup.select_one(".partner-discount")
    months = int(inst.text.split()[0]) if inst else 0
    discount = int(re.sub(r"\D","",disc.text)) if disc else 0
    return {"halva_card": {
      "installment_months": months,
      "discount": discount,
      "Описание": "Карточка рассрочки Halva",
      "Обновлено": datetime.utcnow().isoformat()
    }}

# Собираем и сохраняем
products = {}
products.update(parse_pdf(PDF_URL))
products.update(parse_halva(HALVA_URL))

os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump(products, f, ensure_ascii=False, indent=2)

print("Updated products:", len(products))
