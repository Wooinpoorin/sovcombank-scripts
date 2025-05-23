#!/usr/bin/env python3
import os
import sys
import json
import requests
import re
from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup
import fitz  # PyMuPDF

def resolve_pdf_url(maybe_url: str) -> str:
    """
    Если нам передали страницу (не .pdf), дойдём до прямой ссылки на PDF.
    """
    if maybe_url.lower().endswith('.pdf'):
        return maybe_url
    resp = requests.get(maybe_url)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'html.parser')
    link = soup.find('a', href=re.compile(r'\.pdf($|\?)'))
    if not link or not link.get('href'):
        raise RuntimeError(f"Не удалось найти PDF-ссылку на странице: {maybe_url}")
    return urljoin(maybe_url, link['href'])

# 1) Источник PDF (страница или прямой .pdf)
PDF_PAGE = os.getenv('SOURCE_URL') or (sys.argv[1] if len(sys.argv)>1 else None)
if not PDF_PAGE:
    raise RuntimeError("Не указан SOURCE_URL или аргумент с URL PDF")
PDF_URL = resolve_pdf_url(PDF_PAGE)

# 2) Куда писать
OUTPUT_PATH = os.getenv('OUTPUT_PATH') or (sys.argv[2] if len(sys.argv)>2 else 'data/products.json')

# 3) URL для HalvaCard
HALVA_URL = 'https://halvacard.ru/'

print(f"Парсим PDF по адресу: {PDF_URL}")

def parse_pdf(url: str) -> dict:
    """
    Скачиваем PDF, достаём текст и по набору русскоязычных паттернов вытаскиваем продукты.
    """
    resp = requests.get(url)
    resp.raise_for_status()
    doc = fitz.open(stream=resp.content, filetype='pdf')
    text = "\n".join(page.get_text() for page in doc)

    # Список продуктов: ключ в JSON и regexp для ставки и срока
    mapping = {
        "premium_loan":      r"Премиальный кредит[^\d%]*(\d+,\d*)%[^\d]*(\d{1,3})\s*мес",
        "car_loan":          r"Автокредит[^\d%]*(\d+,\d*)%[^\d]*(\d{1,3})\s*мес",
        "consumer_loan":     r"Потребительский кредит без обеспечения[^\d%]*(\d+,\d*)%[^\d]*(\d{1,3})\s*мес",
        "refinance_loan":    r"Потребительский кредит на рефинансирование[^\d%]*(\d+,\d*)%[^\d]*(\d{1,3})\s*мес",
        "grocery_loan":      r"Кредит для покупок продуктов[^\d%]*(\d+,\d*)%[^\d]*(\d{1,3})\s*мес",
        "travel_loan":       r"Кредит на путешествия[^\d%]*(\d+,\d*)%[^\d]*(\d{1,3})\s*мес"
    }

    out = {}
    for key, rx in mapping.items():
        m = re.search(rx, text, re.IGNORECASE)
        if m:
            rate = float(m.group(1).replace(',', '.'))
            term = int(m.group(2))
            out[key] = {
                "Ставка": rate,
                "Срок": term,
                "Обновлено": datetime.utcnow().isoformat()
            }
    return out

def parse_halva(url: str) -> dict:
    """
    Парсим halvacard.ru по CSS-селекторам.
    """
    resp = requests.get(url)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'html.parser')
    inst = soup.select_one('.installment-months')
    disc = soup.select_one('.partner-discount')
    months = int(inst.text.split()[0]) if inst else 0
    discount = int(re.sub(r'\D','', disc.text)) if disc else 0
    return {
        "halva_card": {
            "installment_months": months,
            "discount": discount,
            "Описание": "Карточка рассрочки Halva",
            "Обновлено": datetime.utcnow().isoformat()
        }
    }

# Собираем и записываем
products = {}
products.update(parse_pdf(PDF_URL))
products.update(parse_halva(HALVA_URL))

os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
    json.dump(products, f, ensure_ascii=False, indent=2)

print(f"Успешно обновлено {len(products)} продуктов в {OUTPUT_PATH}")
