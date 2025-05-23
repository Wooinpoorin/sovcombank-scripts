#!/usr/bin/env python3
import os, sys, json, requests, re
from datetime import datetime
from bs4 import BeautifulSoup
import fitz  # PyMuPDF

# Источники: URL PDF и output path
PDF_URL = os.getenv('SOURCE_URL') or sys.argv[1]
OUTPUT_PATH = os.getenv('OUTPUT_PATH') or sys.argv[2]
HALVA_URL = 'https://halvacard.ru/'
PDF_URL = PDF_URL or 'https://sovcombank.ru/document/11218'

# Парсинг PDF с условиями кредитов
def parse_pdf(url):
    resp = requests.get(url); resp.raise_for_status()
    doc = fitz.open(stream=resp.content, filetype='pdf')
    text = ''.join([page.get_text() for page in doc])
    pattern = re.compile(r"(\w+_loan)\s+ставка\s+(\d+\.?\d*)%\s+срок\s+(\d{1,2})")
    result = {}
    for key, rate, term in pattern.findall(text):
        result[key] = {
            'Ставка': float(rate),
            'Срок': int(term),
            'Обновлено': datetime.utcnow().isoformat()
        }
    return result

# Парсинг сайта HalvaCard
def parse_halva(url):
    resp = requests.get(url); resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'html.parser')
    # Пример CSS-селекторов
    inst = soup.select_one('.installment-months')
    disc = soup.select_one('.partner-discount')
    months = int(inst.text.split()[0]) if inst else 0
    discount = int(disc.text.strip().replace('%','')) if disc else 0
    return {'halva_card': {
        'installment_months': months,
        'discount': discount,
        'Описание': 'Карточка рассрочки Halva',
        'Обновлено': datetime.utcnow().isoformat()
    }}

# Собираем итоговый словарь и сохраняем
products = {}
products.update(parse_pdf(PDF_URL))
products.update(parse_halva(HALVA_URL))
with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
    json.dump(products, f, ensure_ascii=False, indent=2)
print(f"Обновлено продуктов: {len(products)} в {OUTPUT_PATH}")