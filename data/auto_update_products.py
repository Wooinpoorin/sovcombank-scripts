#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import re
from datetime import datetime
from bs4 import BeautifulSoup

# Папка с HTML-файлами в репозитории
HTML_DIR = "data/html_pages"
OUTPUT_PATH = os.getenv("OUTPUT_PATH", "data/products.json")

def parse_html_file(file_path: str) -> dict:
    """
    Парсит HTML-файл и извлекает ставку и срок кредита
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'html.parser')

    text = soup.get_text(" ", strip=True)

    # 1) Находим ставку — "от 12.5%" и т.д.
    m_rate = re.search(r"от\s*([0-9]+[.,]?[0-9]*)\s*%", text, re.IGNORECASE)
    rate = float(m_rate.group(1).replace(",", ".")) if m_rate else None

    # 2) Находим срок — "до 60 месяцев"
    m_term = re.search(r"до\s*([0-9]{1,3})\s*мес", text, re.IGNORECASE)
    term = int(m_term.group(1)) if m_term else None

    # Фолбэк, если ничего не найдено
    if rate is None and term is None:
        raise RuntimeError(f"Не удалось найти ставку и срок в: {file_path}")

    return {
        "Ставка": rate if rate is not None else 0.0,
        "Срок": term if term is not None else 0,
        "Обновлено": datetime.utcnow().isoformat() + "Z"
    }

def main():
    if not os.path.exists(HTML_DIR):
        print(f"❌ Папка {HTML_DIR} не найдена.")
        return

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    updated = {}

    for filename in os.listdir(HTML_DIR):
        if filename.endswith(".html"):
            key = os.path.splitext(filename)[0].lower().replace(" ", "_")
            try:
                full_path = os.path.join(HTML_DIR, filename)
                updated[key] = parse_html_file(full_path)
                print(f"✔ Parsed {key}: {updated[key]}")
            except Exception as e:
                print(f"❌ Ошибка при парсинге {filename}: {e}")

    # Мёржим с текущим products.json
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
