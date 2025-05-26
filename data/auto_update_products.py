#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import re
from datetime import datetime
from bs4 import BeautifulSoup

# Папка с вашими свежесохранёнными HTML
HTML_DIR    = "data/html_pages"
OUTPUT_PATH = os.getenv("OUTPUT_PATH", "data/products.json")

def parse_html_file(path: str) -> dict:
    """
    Парсит один HTML-файл и возвращает:
      - Ставку (первое упоминание % в разделе «Процентная ставка»)
      - Срок (максимальное число месяцев в разделе «Срок кредита»)
    """
    with open(path, encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")

    # Убираем стили и скрипты, чтобы не мешались
    for tag in soup(["style", "script"]):
        tag.decompose()

    # Общий текст секций
    sections = {sec.find("h2").get_text(strip=True).lower(): sec
                for sec in soup.select("div.section")
                if sec.find("h2")}

    # 1) Ставка
    rate = None
    for title in sections:
        if "процентная ставка" in title:
            text = sections[title].get_text(" ", strip=True)
            all_rates = re.findall(r"([0-9]+(?:[.,][0-9]+)?)\s*%", text)
            if all_rates:
                # Берём первое (базовую) ставку
                rate = float(all_rates[0].replace(",", "."))
            break

    # fallback — если раздел не распознался, ищем везде
    if rate is None:
        m = re.search(r"(?:от\s*)?([0-9]+(?:[.,][0-9]+)?)\s*%", soup.get_text(" ", strip=True))
        rate = float(m.group(1).replace(",", ".")) if m else 0.0

    # 2) Срок
    term = None
    for title in sections:
        if "срок кредита" in title or title.startswith("срок"):
            text = sections[title].get_text(" ", strip=True)
            # Ищем все числа
            nums = re.findall(r"(\d{1,3})", text)
            months = [int(n) for n in nums]
            if months:
                term = max(months)
            break

    # fallback — если не нашли раздел, ищем "до N мес."
    if term is None:
        m = re.search(r"до\s*([0-9]{1,3})\s*(?:мес\.?|месяц[а-я]*)", soup.get_text(" ", strip=True), re.IGNORECASE)
        term = int(m.group(1)) if m else 0

    return {
        "Ставка":    rate,
        "Срок":      term,
        "Обновлено": datetime.utcnow().isoformat() + "Z"
    }


def main():
    if not os.path.isdir(HTML_DIR):
        print(f"❌ Папка с HTML не найдена: {HTML_DIR}")
        return

    updated = {}
    for fn in sorted(os.listdir(HTML_DIR)):
        if not fn.lower().endswith(".html"):
            continue
        key = os.path.splitext(fn)[0]
        path = os.path.join(HTML_DIR, fn)
        try:
            updated[key] = parse_html_file(path)
            print(f"✔ {key}: {updated[key]}")
        except Exception as e:
            print(f"❌ Ошибка в {fn}: {e}")

    # Мержим с существующим products.json
    current = {}
    if os.path.exists(OUTPUT_PATH):
        with open(OUTPUT_PATH, encoding="utf-8") as f:
            current = json.load(f)

    current.update(updated)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(current, f, ensure_ascii=False, indent=2)

    print(f"✅ Обновлено {len(updated)} товаров в {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
