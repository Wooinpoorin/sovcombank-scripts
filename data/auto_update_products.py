# data/auto_update_products.py

import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime

def extract_rate_term(url):
    """
    Делает GET-запрос к url, парсит td[data-type="value"]:
      - минимальная ставка (из всех %-значений)
      - максимальный срок в месяцах (из всех «до N <unit>»)
    """
    resp = requests.get(url, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'html.parser')

    rates = []
    terms = []

    for td in soup.find_all('td', attrs={'data-type': 'value'}):
        txt = td.get_text(strip=True).replace('\u00A0', ' ')
        if not txt:
            continue

        # 1) проценты
        if '%' in txt:
            for num in re.findall(r'[\d\.,]+', txt):
                try:
                    rates.append(float(num.replace(',', '.')))
                except:
                    pass

        # 2) срок: «до N <unit>»
        m = re.search(
            r'до\s*(\d+)\s*(дн[ея]?|мес(?:\.|яц[ея]в?)?|лет|год[ау]?)',
            txt, flags=re.IGNORECASE
        )
        if m:
            n = int(m.group(1))
            unit = m.group(2).lower()
            if 'дн' in unit:
                months = max(1, n // 30)
            elif 'лет' in unit or 'год' in unit:
                months = n * 12
            else:
                months = n
            terms.append(months)

    rate = min(rates) if rates else None
    term = max(terms) if terms else 0
    return rate, term


def main():
    urls = {
        "car_pledge_loan":        "https://sovcombank.ru/credits/cash/pod-zalog-avto-",
        "prime_plus":             "https://sovcombank.ru/apply/credit/kredit-na-kartu/",
        "real_estate_pledge_loan":"https://sovcombank.ru/credits/cash/alternativa"
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
