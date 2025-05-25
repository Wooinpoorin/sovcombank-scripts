#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import re
from datetime import datetime
import cloudscraper
from bs4 import BeautifulSoup

# Собираем Cloudflare-scraper-сессию
scraper = cloudscraper.create_scraper(
    browser={'custom': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                      'AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/115.0.0.0 Safari/537.36'}
)

# Словарь URL для трёх продуктов
URLS = {
    "online_cash_loan":       "https://sovcombank.ru/apply/credit/onlajn-zayavka-na-kredit-nalichnymi/",
    "car_pledge_loan":        "https://sovcombank.ru/credits/cash/pod-zalog-avto",
    "real_estate_pledge_loan":"https://sovcombank.ru/credits/pod-zalog"
}

OUTPUT_PATH = os.getenv("OUTPUT_PATH", "data/products.json")

def parse_conditions(url: str) -> dict:
    """
    Универсально парсим любую страницу:
    — вытягиваем из текста минимальную ставку «от X%»
    — максимальный срок «до Y мес»
    """
    resp = scraper.get(url)
    resp.raise_for_status()

    text = BeautifulSoup(resp.text, "html.parser") \
             .get_text(separator=" ")

    # регулярки «от 12,5%» и «до 60 мес»
    rates = re.findall(r"от\s*([0-9]+[.,]?[0-9]*)\s*%", text)
    terms = re.findall(r"до\s*([0-9]{1,3})\s*мес", text)

    if not rates or not terms:
        raise RuntimeError(f"Не найдены ставки/сроки на странице {url}")

    # минимальная ставка, максимальный срок
    rate = float(min(rates).replace(",", "."))
    term = int(max(terms))

    return {
        "Ставка":   rate,
        "Срок":     term,
        "Обновлено": datetime.utcnow().isoformat() + "Z"
    }

def main():
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    updated = {}

    for key, url in URLS.items():
        try:
            updated[key] = parse_conditions(url)
            print(f"Parsed {key}: {updated[key]}")
        except Exception as e:
            print(f"Ошибка при парсинге {key}: {e}")

    # читаем старый products.json (если есть) и мёрджим
    if os.path.exists(OUTPUT_PATH):
        with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
            current = json.load(f)
    else:
        current = {}

    current.update(updated)

    # сохраняем назад
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(current, f, ensure_ascii=False, indent=2)

    print(f"✅ Сохранено {len(updated)} продуктов в {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
