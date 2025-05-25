#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import re
from datetime import datetime

import cloudscraper
import requests
from bs4 import BeautifulSoup

# Заголовки как у настоящего браузера
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/115.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9",
    "Referer": "https://sovcombank.ru/",
}

# cloudscraper для обхода 401
scraper = cloudscraper.create_scraper()

# Лендинги трёх продуктов
URLS = {
    "online_cash_loan":        "https://sovcombank.ru/apply/credit/onlajn-zayavka-na-kredit-nalichnymi/",
    "car_pledge_loan":         "https://sovcombank.ru/credits/cash/pod-zalog-avto",
    "real_estate_pledge_loan": "https://sovcombank.ru/credits/pod-zalog"
}

OUTPUT_PATH = os.getenv("OUTPUT_PATH", "data/products.json")

def fetch_url(url: str):
    """Сначала cloudscraper, иначе requests."""
    try:
        r = scraper.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()
        return r
    except Exception:
        r = requests.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()
        return r

def parse_conditions(html: str, url: str):
    """
    1) Ищем <script type="application/ld+json"> с BankLoan
    2) fallback: regex «от X%» / «до Y мес»
    """
    soup = BeautifulSoup(html, "html.parser")

    # 1) LD-JSON
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string)
            if data.get("@type") == "BankLoan":
                rate = float(data["interestRate"].rstrip("%").replace(",", "."))
                term = int(re.match(r"(\d+)", data["loanTerm"]).group(1))
                return rate, term
        except Exception:
            continue

    # 2) fallback по тексту
    text = soup.get_text(" ")
    rates = re.findall(r"от\s*([0-9]+[.,]?[0-9]*)\s*%", text, flags=re.IGNORECASE)
    terms = re.findall(r"до\s*([0-9]{1,3})\s*мес", text, flags=re.IGNORECASE)

    if not rates or not terms:
        raise RuntimeError(f"Не найдены ставки/сроки на странице {url}")

    rate = float(min(rates).replace(",", "."))
    term = int(max(terms))
    return rate, term

def main():
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    # читаем старые данные (если есть)
    if os.path.exists(OUTPUT_PATH):
        with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
            products = json.load(f)
    else:
        products = {}

    updated = {}
    for key, url in URLS.items():
        try:
            resp = fetch_url(url)
            rate, term = parse_conditions(resp.text, url)
            updated[key] = {
                "Ставка": rate,
                "Срок": term,
                "Описание": products.get(key, {}).get("Описание", ""),
                "Обновлено": datetime.utcnow().isoformat() + "Z"
            }
            print(f"✔ Parsed {key}: {updated[key]}")
        except Exception as e:
            print(f"❌ Ошибка при парсинге {key}: {e}")

    # мёрджим: новые/обновлённые ключи
    products.update(updated)

    # сохраняем
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)

    print(f"✅ Всего обновлено {len(updated)} продуктов — записано в {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
