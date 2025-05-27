# data/auto_update_products.py

import requests
from bs4 import BeautifulSoup
import re
import json
from datetime import datetime

# Повторяем заголовки из SovcombankParser#create_driver
HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:138.0) '
                  'Gecko/20100101 Firefox/138.0',
    'Referer': 'https://sovcombank.ru/',
    'Connection': 'keep-alive',
    'DNT': '1'
}

session = requests.Session()
session.headers.update(HEADERS)


def extract_rate_term(url: str) -> tuple[float | None, int]:
    """
    Делает GET-запрос к url, парсит <td data-type="value">:
      - минимальную процентную ставку
      - максимальный срок в месяцах
    """
    resp = session.get(url, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'html.parser')

    rates = []
    terms = []

    for td in soup.find_all('td', attrs={'data-type': 'value'}):
        text = td.get_text(' ', strip=True).replace('\u00A0', ' ')
        if not text:
            continue

        low = text.lower()

        # 1) Ставки — все числа перед %
        if '%' in text:
            for num in re.findall(r'[\d\.,]+', text):
                try:
                    rates.append(float(num.replace(',', '.')))
                except:
                    pass

        # 2) Срок: из лет → месяцы
        for match in re.findall(r'(\d+)\s*(?:лет|год[ау]?)', low):
            terms.append(int(match) * 12)
        # Месяцы
        for match in re.findall(r'(\d+)\s*(?:мес(?:\.|яц[ея]в?)?)', low):
            terms.append(int(match))
        # Дни → месяцы (примерно)
        for match in re.findall(r'(\d+)\s*дн[ея]?', low):
            n = int(match)
            terms.append(max(1, n // 30))

    rate = min(rates) if rates else None
    term = max(terms) if terms else 0
    return rate, term


def main():
    urls = {
        "car_pledge_loan":         "https://sovcombank.ru/credits/cash/pod-zalog-avto-",
        "prime_plus":              "https://sovcombank.ru/apply/credit/kredit-na-kartu/",
        "real_estate_pledge_loan": "https://sovcombank.ru/credits/cash/alternativa"
    }

    products = {}
    for key, url in urls.items():
        rate, term = extract_rate_term(url)
        products[key] = {
            "Ставка": rate,
            "Срок": term,
            "Обновлено": datetime.utcnow().isoformat() + "Z"
        }

    with open("data/products.json", "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
