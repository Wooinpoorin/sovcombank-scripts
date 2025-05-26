#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import re
import requests
from datetime import datetime
from bs4 import BeautifulSoup

# Если вы уже скачали HTML-файлы локально в data/html_pages,
# можно закомментировать логику скачивания и раскомментировать чтение из файлов.
FETCH_PAGES = False  # <-- переключатель: True → качаем по сети, False → читаем из data/html_pages

# Для FETCH_PAGES=True: укажите тут реальные URL своих article-view страниц (showAll=true)
PAGE_URLS = {
    "car_pledge_loan":       "https://minerva.sovcombank.ru/content/space/7/page/10603?showAll=true",
    "prime_plus":            "https://minerva.sovcombank.ru/content/space/7/page/10601?showAll=true",
    "real_estate_pledge_loan":"https://minerva.sovcombank.ru/content/space/7/page/10605?showAll=true",
}

HTML_DIR     = "data/html_pages"
OUTPUT_PATH  = os.getenv("OUTPUT_PATH", "data/products.json")

def fetch_page(key: str, url: str) -> str:
    """Скачивает страницу по URL."""
    print(f"→ Fetching {key} from {url}")
    r = requests.get(url)
    r.raise_for_status()
    return r.text

def load_html_sources() -> dict[str,str]:
    """
    Возвращает словарь key→html:
      - либо из сети (если FETCH_PAGES=True)
      - либо из локальных файлов data/html_pages/*.html
    """
    htmls = {}

    if FETCH_PAGES:
        for key, url in PAGE_URLS.items():
            htmls[key] = fetch_page(key, url)
    else:
        for fn in os.listdir(HTML_DIR):
            if not fn.endswith(".html"):
                continue
            key = os.path.splitext(fn)[0]
            path = os.path.join(HTML_DIR, fn)
            with open(path, encoding="utf-8") as f:
                htmls[key] = f.read()

    return htmls

def parse_html(html: str, key: str) -> dict:
    """
    Ищет в теле статьи:
      - процент (от 0 до 100+) с "%" после числа
      - срок в месяцах ("до N мес.", "до N месяцев" и т.п.)
    Возвращает dict с 3 полями.
    """
    soup = BeautifulSoup(html, "html.parser")

    # сузим область поиска до тела статьи, если есть:
    article = (
        soup.select_one("section.m-titled-group__body") or
        soup.select_one("div.article-viewer__content") or
        soup
    )
    text = article.get_text(" ", strip=True)

    # 1) Ставка: опциональное "от", число с . или ,, затем "%"
    m_rate = re.search(r"(?:от\s*)?([0-9]+(?:[.,][0-9]+)?)\s*%", text, re.IGNORECASE)
    if m_rate:
        rate = float(m_rate.group(1).replace(",", "."))
    else:
        print(f"⚠️ [{key}] не найден параметр «%» → ставим 0")
        rate = 0.0

    # 2) Срок: "до N мес.", "до N месяцев", "до N месяца"
    m_term = re.search(
        r"до\s*([0-9]{1,3})\s*(?:мес\.?|месяц(?:[а-я]*)?)",
        text, re.IGNORECASE
    )
    if m_term:
        term = int(m_term.group(1))
    else:
        print(f"⚠️ [{key}] не найден параметр «месяцев» → ставим 0")
        term = 0

    return {
        "Ставка":    rate,
        "Срок":      term,
        "Обновлено": datetime.utcnow().isoformat() + "Z"
    }

def main():
    # 1) Собираем исходники
    if not FETCH_PAGES and not os.path.isdir(HTML_DIR):
        print(f"❌ Папка {HTML_DIR} не найдена. Скачайте/поместите туда HTML-файлы.")
        return

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    htmls   = load_html_sources()
    updated = {}

    # 2) Парсим каждую страницу
    for key, html in htmls.items():
        try:
            updated[key] = parse_html(html, key)
            print(f"✔ Parsed {key}: {updated[key]}")
        except Exception as e:
            print(f"❌ Ошибка [{key}]: {e}")

    # 3) Мёржим в существующий products.json
    current = {}
    if os.path.exists(OUTPUT_PATH):
        with open(OUTPUT_PATH, encoding="utf-8") as f:
            current = json.load(f)

    current.update(updated)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(current, f, ensure_ascii=False, indent=2)

    print(f"✅ Всего обновлено {len(updated)} продуктов → {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
