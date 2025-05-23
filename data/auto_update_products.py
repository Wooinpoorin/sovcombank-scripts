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
    Если нам передали не прямой PDF, а страницу описания,
    дойдём до ссылки на PDF.
    """
    if maybe_url.lower().endswith('.pdf'):
        return maybe_url
    resp = requests.get(maybe_url)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'html.parser')
    # ищем первый <a href="...pdf">
    link = soup.find('a', href=re.compile(r'\.pdf($|\?)'))
    if not link or not link.get('href'):
        raise RuntimeError(f"Не удалось найти PDF-ссылку на странице: {maybe_url}")
    return urljoin(maybe_url, link['href'])

# 1) Получаем URL PDF: из переменной окружения SOURCE_URL или из аргументов
PDF_PAGE = os.getenv('SOURCE_URL') or (sys.argv[1] if len(sys.argv) > 1 else None)
if not PDF_PAGE:
    raise RuntimeError("Не указан SOURCE_URL или аргумент с URL PDF")

# 2) Разрешаем до прямого PDF
PDF_URL = resolve_pdf_url(PDF_PAGE)

# 3) Куда сохранять результат
OUTPUT_PATH = os.getenv('OUTPUT_PATH') or (sys.argv[2] if len(sys.argv) > 2 else 'data/products.json')

# 4) Статический источник HalvaCard
HALVA_URL = 'https://halvacard.ru/'

print(f"Используем PDF для парсинга: {PDF_URL}")

def parse_pdf(url: str) -> dict:
    """Скачиваем PDF, парсим текст и выдираем продукты по паттерну."""
    resp = requests.get(url)
    resp.raise_for_status()
    doc = fitz.open(stream=resp.content, filetype='pdf')
    full_text = "".join(page.get_text() for page in doc)
    # Ожидаем, что продукты имеют ключ вида <name>_loan, далее 'ставка <rate>% срок <term>'
    pattern = re.compile(r"(\w+_loan)\s+ставка\s+(\d+\.?\d*)%\s+срок\s+(\d{1,2})")
    out = {}
    for key, rate, term in pattern.findall(full_text):
        out[key] = {
            "Ставка": float(rate),
            "Срок": int(term),
            "Обновлено": datetime.utcnow().isoformat()
        }
    return out

def parse_halva(url: str) -> dict:
    """Парсим сайт HalvaCard для данных по карте рассрочки."""
    resp = requests.get(url)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'html.parser')
    inst_el = soup.select_one('.installment-months')
    disc_el = soup.select_one('.partner-discount')
    months = int(inst_el.text.split()[0]) if inst_el else 0
    # Очищаем всё нецифровое из теkста
    discount = int(re.sub(r'\D', '', disc_el.text)) if disc_el else 0
    return {
        "halva_card": {
            "installment_months": months,
            "discount": discount,
            "Описание": "Карточка рассрочки Halva",
            "Обновлено": datetime.utcnow().isoformat()
        }
    }

# Собираем все продукты
products = {}
products.update(parse_pdf(PDF_URL))
products.update(parse_halva(HALVA_URL))

# Записываем в JSON
os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
    json.dump(products, f, ensure_ascii=False, indent=2)

print(f"Обновлено продуктов: {len(products)} в файле {OUTPUT_PATH}")
