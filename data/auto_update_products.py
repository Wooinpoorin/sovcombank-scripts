#!/usr/bin/env python3
import os
import json
import re
from datetime import datetime
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

URLS = {
    "online_cash_loan": "https://sovcombank.ru/apply/credit/onlajn-zayavka-na-kredit-nalichnymi/",
    "car_pledge_loan":  "https://sovcombank.ru/credits/cash/pod-zalog-avto",
    "real_estate_pledge_loan": "https://sovcombank.ru/credits/pod-zalog"
}

OUTPUT_PATH = os.getenv("OUTPUT_PATH", "data/products.json")

def parse_conditions(url, rate_pattern, term_pattern, description):
    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    content_text = soup.get_text(separator=" ")

    rates = re.findall(rate_pattern, content_text)
    terms = re.findall(term_pattern, content_text)

    if not rates or not terms:
        raise ValueError(f"Не найдены условия на странице: {url}")

    return {
        "Ставка": float(rates[0].replace(',', '.')),
        "Срок": int(terms[0]),
        "Описание": description,
        "Обновлено": datetime.utcnow().isoformat() + "Z"
    }

def main():
    products = {}
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    parsers = {
        "online_cash_loan": {
            "rate_pattern": r'от\s+(\d+[,.]?\d*)%',
            "term_pattern": r'до\s+(\d+)\s+мес',
            "description": "Кредит наличными онлайн"
        },
        "car_pledge_loan": {
            "rate_pattern": r'от\s+(\d+[,.]?\d*)%',
            "term_pattern": r'до\s+(\d+)\s+месяц',
            "description": "Кредит под залог авто"
        },
        "real_estate_pledge_loan": {
            "rate_pattern": r'от\s+(\d+[,.]?\d*)%',
            "term_pattern": r'до\s+(\d+)\s+месяц',
            "description": "Кредит под залог недвижимости"
        }
    }

    for product, settings in parsers.items():
        try:
            products[product] = parse_conditions(
                URLS[product],
                settings["rate_pattern"],
                settings["term_pattern"],
                settings["description"]
            )
            print(f"Parsed {product}: {products[product]}")
        except Exception as e:
            print(f"Ошибка при парсинге {product}: {e}")

    # Загрузка существующих данных и обновление
    if os.path.exists(OUTPUT_PATH):
        with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
            current_products = json.load(f)
    else:
        current_products = {}

    current_products.update(products)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(current_products, f, ensure_ascii=False, indent=2)

    print(f"✅ Данные продуктов успешно обновлены и сохранены в {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
