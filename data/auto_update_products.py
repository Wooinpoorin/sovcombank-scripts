#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, json, re
from datetime import datetime
from bs4 import BeautifulSoup

# Для чистых HTML из data/html_pages_clean
HTML_DIR    = "data/html_pages_clean"
OUTPUT_PATH = os.getenv("OUTPUT_PATH", "data/products.json")

def parse_html_file(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")

    # Считаем, что весь нужный текст теперь в <body>
    text = soup.get_text(" ", strip=True)

    # Ищем процент: число(.,)число + %
    m_rate = re.search(r"([0-9]+(?:[.,][0-9]+)?)\s*%", text)
    rate = float(m_rate.group(1).replace(",", ".")) if m_rate else 0.0

    # Ищем срок: "до N мес.", "до N месяцев" и т.п.
    m_term = re.search(
        r"до\s*([0-9]{1,3})\s*(?:мес(?:\.|яц[а-я]*)?)",
        text, re.IGNORECASE
    )
    term = int(m_term.group(1)) if m_term else 0

    return {
        "Ставка":    rate,
        "Срок":      term,
        "Обновлено": datetime.utcnow().isoformat() + "Z"
    }

def main():
    if not os.path.isdir(HTML_DIR):
        print(f"❌ Папка {HTML_DIR} не найдена. Запустите сначала clean_html_pages.py")
        return

    updated = {}
    for fn in sorted(os.listdir(HTML_DIR)):
        if not fn.lower().endswith(".html"):
            continue
        key = os.path.splitext(fn)[0]
        full = os.path.join(HTML_DIR, fn)
        updated[key] = parse_html_file(full)
        print(f"✔ {key}: {updated[key]}")

    # Мёржим с existing products.json
    current = {}
    if os.path.exists(OUTPUT_PATH):
        with open(OUTPUT_PATH, encoding="utf-8") as f:
            current = json.load(f)

    current.update(updated)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(current, f, ensure_ascii=False, indent=2)

    print(f"✅ Всего {len(updated)} обновлено → {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
