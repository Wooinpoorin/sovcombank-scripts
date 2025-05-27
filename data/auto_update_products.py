#!/usr/bin/env python3
# data/auto_update_products.py

import requests
import json
import re
from datetime import datetime
from bs4 import BeautifulSoup

# Три ваших URL (без лишних слэшей!)
URLS = {
    "prime_plus":              "https://sovcombank.ru/apply/credit/kredit-на-кartu/",
    "car_pledge_loan":         "https://sovcombank.ru/credits/cash/pod-zalog-avto-",
    "real_estate_pledge_loan": "https://sovcombank.ru/credits/cash/alternativa"
}

# Заголовки для имитации браузера
HEADERS = {
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.8",
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Referer":         "https://sovcombank.ru/",
    "Connection":      "keep-alive"
}

session = requests.Session()
session.headers.update(HEADERS)

def extract_rate_term(url: str) -> tuple[float|None,int]:
    """
    1) Инициализация с куками через главную
    2) GET целевой URL
    3) Получение JSON из <script id="__NEXT_DATA__">
    4) Из props.pageProps.tariffs — minRate/maxRate → минимальная ставка;
       minTermMonths/maxTermMonths → максимальный срок.
    """
    # 1) Для куки
    session.get("https://sovcombank.ru/", timeout=15).raise_for_status()
    # 2) Целевая страница
    resp = session.get(url, timeout=15)
    resp.raise_for_status()

    # 3) Ищем JSON
    soup = BeautifulSoup(resp.text, "html.parser")
    tag = soup.find("script", id="__NEXT_DATA__")
    if not tag or not tag.string:
        return None, 0

    data = json.loads(tag.string)
    tariffs = (data.get("props", {})
                   .get("pageProps", {})
                   .get("tariffs", []))

    rates, terms = [], []

    for t in tariffs:
        # Ставки
        for fld in ("minRate", "maxRate", "rate"):
            v = t.get(fld)
            if v is None: 
                continue
            for num in re.findall(r"[\d.,]+", str(v)):
                try:
                    rates.append(float(num.replace(",", ".")))
                except:
                    pass

        # Сроки
        mn = t.get("minTermMonths")
        mx = t.get("maxTermMonths")
        if isinstance(mn, int):
            terms.append(mn)
        if isinstance(mx, int):
            terms.append(mx)

    return (
        min(rates) if rates else None,
        max(terms) if terms else 0
    )

def main():
    products = {}
    ts = datetime.utcnow().isoformat() + "Z"

    for key, url in URLS.items():
        rate, term = extract_rate_term(url)
        products[key] = {"Ставка": rate, "Срок": term, "Обновлено": ts}

    with open("data/products.json", "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)

    print(json.dumps(products, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
