# data/auto_update_products.py

import requests
import json
import re
from datetime import datetime
from bs4 import BeautifulSoup

# -------------------------------------------------------
#  Конфиг: три целевых URL и заголовки для запросов
# -------------------------------------------------------

URLS = {
    "prime_plus":              "https://sovcombank.ru/apply/credit/kredit-na-kartu/",
    "car_pledge_loan":         "https://sovcombank.ru/credits/cash/pod-zalog-avto-",
    "real_estate_pledge_loan": "https://sovcombank.ru/credits/cash/alternativa"
}

HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ru-RU,ru;q=0.8',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
    'Referer': 'https://sovcombank.ru/',
    'Connection': 'keep-alive'
}

session = requests.Session()
session.headers.update(HEADERS)


# -------------------------------------------------------
#  Функция: получить минимальную ставку и максимальный срок
# -------------------------------------------------------
def extract_rate_term(url: str) -> tuple[float|None,int]:
    """
    1. GET-страница через requests + HEADERS
    2. Поймать <script id="__NEXT_DATA__">, распарсить JSON
    3. Взять data['props']['pageProps']['tariffs']
    4. Из каждого элемента:
       - minRate/maxRate → числа → rates.append()
       - minTermMonths/maxTermMonths → terms.append()
    5. Вернуть (min(rates), max(terms))
    """
    resp = session.get(url, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, 'html.parser')
    tag = soup.find("script", id="__NEXT_DATA__")
    if not tag or not tag.string:
        return None, 0

    data = json.loads(tag.string)
    tariffs = (
        data.get("props", {})
            .get("pageProps", {})
            .get("tariffs", [])
    )

    rates = []
    terms = []

    for t in tariffs:
        # процентные ставки
        for key in ("minRate", "maxRate", "rate"):
            v = t.get(key)
            if v is None:
                continue
            for num in re.findall(r"[\d.,]+", str(v)):
                try:
                    rates.append(float(num.replace(",", ".")))
                except:
                    pass

        # сроки в месяцах
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


# -------------------------------------------------------
#  Основной запуск
# -------------------------------------------------------
def main():
    products = {}
    now = datetime.utcnow().isoformat() + "Z"

    for key, url in URLS.items():
        rate, term = extract_rate_term(url)
        products[key] = {
            "Ставка": rate,
            "Срок":   term,
            "Обновлено": now
        }

    # Сохраняем в файл
    with open("data/products.json", "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)

    # На всякий случай выводим в консоль
    print(json.dumps(products, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
