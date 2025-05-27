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

# Базовые заголовки «как из браузера»
HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3",
    "Cache-Control": "max-age=0",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/114.0.0.0 Safari/537.36"
    ),
    "Connection": "keep-alive"
}

session = requests.Session()
session.headers.update(HEADERS)


def fetch_page(url: str) -> str:
    """
    Сначала заходим на главную, чтобы получить куки/токены,
    потом — на нужный URL; при 401 — повторяем с Referer.
    """
    # 1) Инициализируем сессию на главной
    if not session.cookies:
        session.get("https://sovcombank.ru/", timeout=30).raise_for_status()

    # 2) Запрашиваем целевую страницу
    resp = session.get(url, timeout=30)
    if resp.status_code == 401:
        # Повторяем с корректным Referer
        resp = session.get(url, headers={**HEADERS, "Referer": "https://sovcombank.ru/"}, timeout=30)
    resp.raise_for_status()
    return resp.text


def extract_rate_term(url: str) -> tuple[float | None, int]:
    """
    1) GET-страницу через fetch_page()
    2) Парсим BeautifulSoup и находим <script id="__NEXT_DATA__">
    3) Извлекаем JSON и смотрим props.pageProps.tariffs
    4) Собираем все minRate/maxRate → минимальная ставка
       и все minTermMonths/maxTermMonths → максимальный срок
    """
    html = fetch_page(url)
    soup = BeautifulSoup(html, "html.parser")

    script = soup.find("script", id="__NEXT_DATA__")
    if not script or not script.string:
        return None, 0

    payload = json.loads(script.string)
    tariffs = (
        payload.get("props", {})
               .get("pageProps", {})
               .get("tariffs", [])
    )

    rates, terms = [], []
    for t in tariffs:
        # процент
        for field in ("minRate", "maxRate", "rate"):
            val = t.get(field)
            if val is None:
                continue
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

    return (min(rates) if rates else None,
            max(terms) if terms else 0)


def main():
    products = {}
    ts = datetime.utcnow().isoformat() + "Z"

    for key, url in URLS.items():
        rate, term = extract_rate_term(url)
        products[key] = {
            "Ставка": rate,
            "Срок":   term,
            "Обновлено": ts
        }

    # Записываем в файл
    with open("data/products.json", "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)

    # Лог в CI
    print(json.dumps(products, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
