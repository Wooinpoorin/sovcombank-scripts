#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import re
from datetime import datetime

from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

# Заголовки «как из браузера»
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/115.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8",
    "Referer": "https://sovcombank.ru/",
}

URLS = {
    "online_cash_loan":        "https://sovcombank.ru/apply/credit/onlajn-zayavka-na-kredit-nalichnymi/",
    "car_pledge_loan":         "https://sovcombank.ru/credits/cash/pod-zalog-avto/",
    "real_estate_pledge_loan": "https://sovcombank.ru/credits/pod-zalog/",
}

OUTPUT_PATH = os.getenv("OUTPUT_PATH", "data/products.json")


def render_page_source(url: str) -> str:
    """Подгружаем страницу в headless-браузере и ждём появления ключевого селектора."""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(extra_http_headers=HEADERS)
        page.goto(url, wait_until="networkidle")
        # ждём, пока в DOM появится секция «Полезная информация»
        page.wait_for_selector("h2:has-text('Полезная информация')", timeout=15000)
        content = page.content()
        browser.close()
        return content


def parse_conditions(rendered_html: str, url: str) -> dict:
    """
    Из отрендеренной страницы вытаскиваем:
      1) строго «Процентная ставка X%»
      2) строго «Срок кредита от A года до B лет»
      3) фоллбэк на «Полная стоимость кредита От X% - Y%»
      4) последний фоллбэк на «от X%» и «до Y мес»
    """
    text = BeautifulSoup(rendered_html, "html.parser").get_text(" ")

    # 1) Процентная ставка X%
    m_rate = re.search(r"Процентная\s+ставка\s*([0-9]+[.,]?[0-9]*)\s*%", text, re.IGNORECASE)
    # 2) Срок кредита от A года до B лет
    m_term = re.search(
        r"Срок(?:\s+кредита)?\s*от\s*([0-9]{1,2})\s*года?\s*до\s*([0-9]{1,2})\s*лет",
        text, re.IGNORECASE
    )

    if m_rate and m_term:
        rate = float(m_rate.group(1).replace(",", "."))
        term = int(m_term.group(2))
    else:
        # 3) Полная стоимость кредита От X% - Y%
        m_full = re.search(
            r"Полная\s+стоимость\s+кредита\s+От\s*([0-9]+[.,]?[0-9]*)\s*%\s*-\s*([0-9]+[.,]?[0-9]*)\s*%",
            text, re.IGNORECASE
        )
        if m_full:
            rate = float(m_full.group(1).replace(",", "."))
            term = None
        else:
            # 4) Фоллбэк на «от X%» и «до Y мес»
            rates = re.findall(r"от\s*([0-9]+[.,]?[0-9]*)\s*%", text, re.IGNORECASE)
            terms = re.findall(r"до\s*([0-9]{1,3})\s*мес", text, re.IGNORECASE)
            if not rates or not terms:
                raise RuntimeError(f"Не найдены ставки/сроки на {url}")
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

    for key, url in URLS.items():
        try:
            html = render_page_source(url)
            updated[key] = parse_conditions(html, url)
            print(f"✔ Parsed {key}: {updated[key]}")
        except Exception as e:
            print(f"❌ Ошибка при парсинге {key}: {e}")

    # мердж с существующим файлом
    if os.path.exists(OUTPUT_PATH):
        with open(OUTPUT_PATH, encoding="utf-8") as f:
            current = json.load(f)
    else:
        current = {}

    current.update(updated)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(current, f, ensure_ascii=False, indent=2)

    print(f"✅ Сохранено {len(updated)} продуктов в {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
