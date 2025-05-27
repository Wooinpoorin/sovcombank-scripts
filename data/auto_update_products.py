# data/auto_update_products.py

import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime

# Три целевых URL
URLS = {
    "prime_plus":              "https://sovcombank.ru/apply/credit/kredit-na-kartu/",
    "car_pledge_loan":         "https://sovcombank.ru/credits/cash/pod-zalog-avto-",
    "real_estate_pledge_loan": "https://sovcombank.ru/credits/cash/alternativa"
}

# Заголовки, имитирующие настоящий браузер
HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Referer": "https://sovcombank.ru/",
    "Connection": "keep-alive"
}


def extract_rate_term(url: str):
    """
    1) GET-страница через requests
    2) Ищем <script id="__NEXT_DATA__"> — в нём весь JSON от Next.js
    3) Извлекаем props.pageProps.tariffs
    4) Собираем minRate/maxRate → minimal rate, minTermMonths/maxTermMonths → maximal term
    """
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()

    page = BeautifulSoup(resp.text, "html.parser")
    script = page.find("script", {"id": "__NEXT_DATA__"})
    if not script or not script.string:
        # JSON не нашли — возвращаем пустые
        return None, 0

    data = json.loads(script.string)
    # путь к тарифам
    tariffs = data \
        .get("props", {}) \
        .get("pageProps", {}) \
        .get("tariffs", [])

    rates = []
    terms = []

    for t in tariffs:
        # ставки
        for key in ("minRate", "maxRate", "rate"):
            val = t.get(key)
            if val is None:
                continue
            # берём все числа из строки
            for num in re.findall(r"[\d.,]+", str(val)):
                try:
                    rates.append(float(num.replace(",", ".")))
                except:
                    pass

        # сроки
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
    timestamp = datetime.utcnow().isoformat() + "Z"

    for key, url in URLS.items():
        rate, term = extract_rate_term(url)
        products[key] = {
            "Ставка":    rate,
            "Срок":      term,
            "Обновлено": timestamp
        }

    # Сохраняем в JSON
    with open("data/products.json", "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)

    # И выводим для CI
    print(json.dumps(products, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
