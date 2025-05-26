#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import re
from datetime import datetime
from bs4 import BeautifulSoup

# Маппинг имён html-файлов → ключи в products.json
KEY_ALIASES = {
    'кредит на карту под залог автомобиля _ совкомбанк — minervasoft': 'car_pledge_loan',
    'дк под залог недвижимости альтернатива (дкпзн) _ совкомбанк — minervasoft': 'real_estate_pledge_loan'
}

HTML_DIR = "data/html_pages"
OUTPUT_PATH = os.getenv("OUTPUT_PATH", "data/products.json")

def parse_html_file(file_path: str) -> dict:
    """
    Парсит HTML-файл и извлекает:
      - Ставку: захватывает "от 12.5%" или просто "12.5%"
      - Срок: захватывает "до 60 мес.", "до 60 месяцев" и т.п.
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'html.parser')

    text = soup.get_text(" ", strip=True)

    # Ставка: опциональное "от", затем число с . или , и знак "%"
    m_rate = re.search(r"(?:от\s*)?([0-9]+(?:[.,][0-9]+)?)\s*%", text, re.IGNORECASE)
    rate = float(m_rate.group(1).replace(",", ".")) if m_rate else None

    # Срок: "до <число> мес.", "до <число> месяцев", "до <число> месяца"
    m_term = re.search(r"до\s*([0-9]{1,3})\s*(?:мес\.?|месяц(?:[а-я]*)?)", text, re.IGNORECASE)
    term = int(m_term.group(1)) if m_term else None

    if rate is None and term is None:
        raise RuntimeError(f"Не удалось найти ставку и срок в: {file_path}")

    return {
        "Ставка": rate or 0.0,
        "Срок":   term or 0,
        "Обновлено": datetime.utcnow().isoformat() + "Z"
    }

def main():
    if not os.path.exists(HTML_DIR):
        print(f"❌ Папка {HTML_DIR} не найдена.")
        return

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    updated = {}

    for filename in os.listdir(HTML_DIR):
        if not filename.endswith(".html"):
            continue
        stem = os.path.splitext(filename)[0].lower()
        key = KEY_ALIASES.get(stem, stem.replace(" ", "_"))
        full_path = os.path.join(HTML_DIR, filename)
        try:
            updated[key] = parse_html_file(full_path)
            print(f"✔ Parsed {key}: {updated[key]}")
        except Exception as e:
            print(f"❌ Ошибка при парсинге {filename}: {e}")

    # Мержим с текущим products.json
    if os.path.exists(OUTPUT_PATH):
        with open(OUTPUT_PATH, encoding="utf-8") as f:
            current = json.load(f)
    else:
        current = {}

    current.update(updated)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(current, f, ensure_ascii=False, indent=2)

    print(f"✅ Всего обновлено {len(updated)} продуктов в {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
