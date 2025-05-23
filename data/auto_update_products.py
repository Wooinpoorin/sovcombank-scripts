#!/usr/bin/env python3
import os
import sys
import json
import re
from datetime import datetime

import requests
import fitz  # PyMuPDF

# ——————————————————————————————————————————————
# Настройка HTTP-сессии с User-Agent
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
})

# ——————————————————————————————————————————————
# 1) URL PDF (из env/SOURCE_URL или аргумента, иначе дефолт)
PDF_URL = os.getenv("SOURCE_URL") or (
    sys.argv[1] if len(sys.argv) > 1 else
    "https://prod-api.sovcombank.ru/document/index?id=6335"
)

# 2) Куда сохранять JSON
OUTPUT_PATH = os.getenv("OUTPUT_PATH") or (
    sys.argv[2] if len(sys.argv) > 2 else
    "data/products.json"
)

print(f"Parsing PDF from: {PDF_URL}")
print(f"Will write output to: {OUTPUT_PATH}")

# ——————————————————————————————————————————————
def parse_pdf(url: str) -> dict:
    """
    Скачиваем PDF и по регуляркам вытягиваем условия кредитов.
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

# ——————————————————————————————————————————————
# Основной код: только PDF
products = parse_pdf(PDF_URL)

# Сохраняем результат
os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
    json.dump(products, f, ensure_ascii=False, indent=2)

print(f"Successfully updated {len(products)} products")
