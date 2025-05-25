#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import re
from datetime import datetime

import cloudscraper
import requests
from bs4 import BeautifulSoup

# Заголовки из браузера
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

scraper = cloudscraper.create_scraper()

URLS = {
    "online_cash_loan":        "https://sovcombank.ru/apply/credit/onlajn-zayavka-na-kredit-nalichnymi/",
    "car_pledge_loan":         "https://sovcombank.ru/credits/cash/pod-zalog-avto/",
    "real_estate_pledge_loan": "https://sovcombank.ru/credits/pod-zalog/"
}

OUTPUT_PATH = os.getenv("OUTPUT_PATH", "data/products.json")


def fetch_url(url: str) -> requests.Response:
    """
    Попытаем cloudscraper, а при любой ошибке — fallback на requests.
    Пробуем два варианта: с trailingslash и без.
    """
    errs = []
    for u in (url, url.rstrip("/") + "/"):
        try:
            resp = scraper.get(u, headers=HEADERS, timeout=30, allow_redirects=True)
            resp.raise_for_status()
            return resp
        except Exception as e1:
            try:
                resp2 = requests.get(u, headers=HEADERS, timeout=30, allow_redirects=True)
                resp2.raise_for_status()
                return resp2
            except Exception as e2:
                errs.append(f"{u} → cloudscraper: {e1} | requests: {e2}")
    raise RuntimeError("Все попытки fetch_url провалились:\n" + "\n".join(errs))


def parse_conditions(url: str) -> dict:
    """
    1) Жёстко ищем «Процентная ставка X%» и «Срок кредита от A года до B лет»
    2) Если не нашли — «Полная стоимость кредита От X% - Y%»
    3) Иначе — fallback «от X%» & «до Y мес»
    """
    resp = fetch_url(url)
    text = BeautifulSoup(resp.text, "html.parser").get_text(" ")

    # 1) ставка и срок «год»…«лет»
    m_rate = re.search(r"Процентная\s+ставка\s*([0-9]+[.,]?[0-9]*)\s*%", text, re.IGNORECASE)
    m_term = re.search(
        r"Срок(?:\s+кредита)?\s*от\s*(\d{1,2})\s*года?\s*до\s*(\d{1,2})\s*лет",
        text, re.IGNORECASE
    )
    if m_rate and m_term:
        rate = float(m_rate.group(1).replace(",", "."))
        term = int(m_term.group(2))
    else:
        # 2) Полная стоимость
        m_full = re.search(
            r"Полная\s+стоимость\s+кредита\s+От\s*([0-9]+[.,]?[0-9]*)\s*%\s*-\s*([0-9]+[.,]?[0-9]*)\s*%",
            text, re.IGNORECASE
        )
        if m_full:
            rate = float(m_full.group(1).replace(",", "."))
            term = None
        else:
            # 3) fallback на месяцы
            rates = re.findall(r"от\s*([0-9]+[.,]?[0-9]*)\s*%", text, re.IGNORECASE)
            terms = re.findall(r"до\s*([0-9]{1,3})\s*мес", text, re.IGNORECASE)
            if not rates or not terms:
                raise RuntimeError(f"Не найдены ставки/сроки на странице {url}")
            rate = float(min(rates).replace(",", "."))
            term = int(max(terms))

    return {
        "Ставка": rate,
        "Срок": term or 0,
        "Обновлено": datetime.utcnow().isoformat() + "Z"
    }


def main():
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    updated = {}

    for key, u in URLS.items():
        try:
            updated[key] = parse_conditions(u)
            print(f"✔ Parsed {key}: {updated[key]}")
        except Exception as e:
            print(f"❌ Ошибка при парсинге {key}: {e}")

    # мёржим с тем, что было
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
