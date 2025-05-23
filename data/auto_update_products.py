#!/usr/bin/env python3
import os
import json
import re
from datetime import datetime

import requests
from bs4 import BeautifulSoup

# User-Agent to emulate a real browser
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

# URLs to scrape static conditions from
URLS = {
    "online_cash_loan": "https://sovcombank.ru/apply/credit/onlajn-zayavka-na-kredit-nalichnymi/",
    "car_pledge_loan":  "https://sovcombank.ru/credits/cash/pod-zalog-avto",
    "pod_zalog":        "https://sovcombank.ru/credits/pod-zalog"
}

# Where to write the results
OUTPUT_PATH = os.getenv("OUTPUT_PATH", "data/products.json")

def parse_conditions(url: str) -> dict:
    """
    Fetch the page at `url` and extract all percent-and-month pairs,
    returning the minimum rate and maximum term.
    """
    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()
    text = BeautifulSoup(resp.text, "html.parser").get_text(separator="\n")

    # find all percentages, e.g. "12,5%"
    rates = [float(r.replace(",", ".")) for r in re.findall(r"(\d+[,\.]\d*)\s*%", text)]
    # find all terms in months, e.g. "24 мес."
    terms = [int(m) for m in re.findall(r"(\d{1,3})\s*мес", text)]

    if not rates or not terms:
        raise RuntimeError(f"Не удалось найти ставку или срок на странице {url}")

    return {
        "Ставка": min(rates),
        "Срок":   max(terms),
        "Обновлено": datetime.utcnow().isoformat()
    }

def main():
    products = {}
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    for key, url in URLS.items():
        try:
            products[key] = parse_conditions(url)
            print(f"Parsed {key}: {products[key]}")
        except Exception as e:
            print(f"Warning: не удалось обработать {key} ({url}): {e}")

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)

    print(f"Updated {len(products)} products in {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
