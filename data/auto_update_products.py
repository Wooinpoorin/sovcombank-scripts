#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import re
from datetime import datetime

import cloudscraper
import requests
from bs4 import BeautifulSoup

# Заголовки, максимально приближённые к настоящему браузеру
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/115.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8",
    "Referer": "https://sovcombank.ru/",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1"
}

scraper = cloudscraper.create_scraper()  # обход Cloudflare

URLS = {
    "online_cash_loan":        "https://sovcombank.ru/apply/credit/onlajn-zayavka-na-kredit-nalichnymi/",
    "car_pledge_loan":         "https://sovcombank.ru/credits/cash/pod-zalog-avto/",
    "real_estate_pledge_loan": "https://sovcombank.ru/credits/pod-zalog/"
}

OUTPUT_PATH = os.getenv("OUTPUT_PATH", "data/products.json")


def fetch_url(url: str) -> requests.Response:
    """Пробуем cloudscraper, при любых ошибках — Requests."""
    try:
        r = scraper.get(url, headers=HEADERS, timeout=30, allow_redirects=True)
        r.raise_for_status()
        return r
    except Exception:
        r = requests.get(url, headers=HEADERS, timeout=30, allow_redirects=True)
        r.raise_for_status()
        return r


def parse_conditions(url: str) -> dict:
    """
    Парсим страницу кредита:
    1) Ищем "Процентная ставка X%" и "Срок кредита от A года до B лет"
    2) Если нет — стандартные regex "от X%" / "до Y мес."
    """
    resp = fetch_url(url)
    text = BeautifulSoup(resp.text, "html.parser").get_text(" ")

    # 1) строгие паттерны
    rate_m = re.search(r"Процентная\s+ставка\s*([0-9]+[.,]?[0-9]*)\s*%", text, re.IGNORECASE)
    term_m = re.search(
        r"Срок(?:\s+кредита)?\s*от\s*([0-9]{1,2})\s*года\s*до\s*([0-9]{1,2})\s*лет",
        text, re.IGNORECASE
    )
    if rate_m and term_m:
        rate = float(rate_m.group(1).replace(",", "."))
        term = int(term_m.group(2))
    else:
        # fallback на месяцы
        rates = re.findall(r"от\s*([0-9]+[.,]?[0-9]*)\s*%", text, re.IGNORECASE)
        terms = re.findall(r"до\s*([0-9]{1,3})\s*мес", text, re.IGNORECASE)
        if not rates or not terms:
            raise RuntimeError(f"Не найдены ставки/сроки на странице {url}")
        rate = float(min(rates).replace(",", "."))
        term = int(max(terms))

    return {
        "Ставка": rate,
        "Срок": term,
        "Обновлено": datetime.utcnow().isoformat() + "Z"
    }


def main():
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    updated = {}

    for key, url in URLS.items():
        try:
            updated[key] = parse_conditions(url)
            print(f"✔ Parsed {key}: {updated[key]}")
        except Exception as e:
            print(f"❌ Ошибка при парсинге {key}: {e}")

    # читаем старое, если есть
    if os.path.exists(OUTPUT_PATH):
        with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
            current = json.load(f)
    else:
        current = {}

    current.update(updated)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(current, f, ensure_ascii=False, indent=2)

    print(f"✅ Сохранено {len(updated)} продуктов в {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
