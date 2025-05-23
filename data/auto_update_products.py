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

# Заголовки, эмулирующие настоящий браузер
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/117.0.0.0 Safari/537.36'
}

# Используем сессию, чтобы заголовки применились ко всем запросам
session = requests.Session()
session.headers.update(HEADERS)

def resolve_pdf_url(maybe_url: str) -> str:
    """
    Если передали HTML-страницу, дойдём до прямой ссылки на PDF.
    Если уже .pdf — вернём URL как есть.
    """
    if maybe_url.lower().endswith('.pdf'):
        return maybe_url

    resp = session.get(maybe_url)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, 'html.parser')
    link = soup.find('a', href=re.compile(r'\.pdf($|\?)'))
    if not link or not link.get('href'):
        raise RuntimeError(f"Не удалось найти PDF-ссылку на странице: {maybe_url}")

    return urljoin(maybe_url, link['href'])

# 1) Источник PDF (страница или прямой .pdf)
PDF_PAGE = os.getenv('SOURCE_URL') or (sys.argv[1] if len(sys.argv) > 1 else None)
if not PDF_PAGE:
    raise RuntimeError("Не указан SOURCE_URL или аргумент с URL PDF")

PDF_URL = resolve_pdf_url(PDF_PAGE)

# 2) Куда писать результат
OUTPUT_PATH = os.getenv('OUTPUT_PATH') or (sys.argv[2] if len(sys.argv) > 2 else 'data/products.json')

# 3) Статический источник HalvaCard
HALVA_URL = 'https://halvacard.ru/'

print(f"PDF для парсинга: {PDF_URL}")
print(f"Записываем в: {OUTPUT_PATH}")

def parse_pdf(url: str) -> dict:
    """
    Скачиваем PDF, вытягиваем текст и по набору русскоязычных регулярок
    собираем словарь продуктов.
    """
    resp = session.get(url)
    resp.raise_for_status()

    doc = fitz.open(stream=resp.content, filetype='pdf')
    text = "\n".join(page.get_text() for page in doc)

    # Явный список продуктов и их regexp-паттерны по русским названиям
    mapping = {
        "premium_loan":   r"Премиальный кредит[^\d%]*(\d+,\d*)%[^\d]*(\d{1,3})\s*мес",
        "car_loan":       r"Автокредит[^\d%]*(\d+,\d*)%[^\d]*(\d{1,3})\s*мес",
        "consumer_loan":  r"Потребительский кредит без обеспечения[^\d%]*(\d+,\d*)%[^\d]*(\d{1,3})\s*мес",
        "refinance_loan": r"рефинансирование[^\d%]*(\d+,\d*)%[^\d]*(\d{1,3})\s*мес",
        "grocery_loan":   r"Кредит для покупок продуктов[^\d%]*(\d+,\d*)%[^\d]*(\d{1,3})\s*мес",
        "travel_loan":    r"Кредит на путешествия[^\d%]*(\d+,\d*)%[^\d]*(\d{1,3})\s*мес"
    }

    out = {}
    for key, pattern in mapping.items():
        m = re.search(pattern, text, flags=re.IGNORECASE)
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
    Получаем данные по HalvaCard с официального сайта.
    """
    resp = session.get(url)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, 'html.parser')
    inst_el = soup.select_one('.installment-months')
    disc_el = soup.select_one('.partner-discount')

    months = int(inst_el.text.split()[0]) if inst_el else 0
    discount = int(re.sub(r'\D', '', disc_el.text)) if disc_el else 0

    return {
        "halva_card": {
            "installment_months": months,
            "discount": discount,
            "Описание": "Карточка рассрочки Halva",
            "Обновлено": datetime.utcnow().isoformat()
        }
    }

# Собираем полный список продуктов
products = {}
products.update(parse_pdf(PDF_URL))
products.update(parse_halva(HALVA_URL))

# Сохраняем в JSON
os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
    json.dump(products, f, ensure_ascii=False, indent=2)

print(f"Готово: обновлено продуктов {len(products)}")```


