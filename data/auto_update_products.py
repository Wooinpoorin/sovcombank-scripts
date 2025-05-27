import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import json
import re
from datetime import datetime


def extract_rate_term(driver, url):
    """
    Загружает страницу по URL и вытягивает минимальную процентную ставку и максимальный срок в месяцах
    «из текста страницы» с помощью регулярных выражений.
    Возвращает кортеж (rate: float | None, term: int).
    """
    driver.get(url)
    # Ждём, пока подгрузится <body>
    WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.TAG_NAME, "body"))
    )
    # Ждём ещё чуть-чуть, чтобы JS успел вставить текст
    time.sleep(1)

    # Берём весь HTML в одну строку
    html = driver.page_source.replace('\u00A0', ' ')

    # --- Ставка ---
    # Ищем все вхождения цифр с запятой/точкой перед знаком %
    rate_matches = re.findall(r'([\d\.,]+)\s*%', html)
    rates = [float(r.replace(',', '.')) for r in rate_matches]
    rate = min(rates) if rates else None

    # --- Срок ---
    # Ищем все «до N мес(яцев)» и «до M лет»
    term_matches = re.findall(r'до\s*(\d+)\s*(мес(?:яц[ея]в?)?|лет|год[ау]?)', html, flags=re.IGNORECASE)
    term_months = []
    for num_str, unit in term_matches:
        n = int(num_str)
        unit = unit.lower()
        if 'лет' in unit or 'год' in unit:
            term_months.append(n * 12)
        else:
            term_months.append(n)
    term = max(term_months) if term_months else 0

    return rate, term


def update_products_json(products, filepath):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(products, f, ensure_ascii=False, indent=2)


def main():
    urls = {
        "car_pledge_loan":   "https://sovcombank.ru/credits/cash/pod-zalog-avto-",
        "prime_plus":        "https://sovcombank.ru/apply/credit/kredit-na-kartu/",
        "real_estate_pledge_loan": "https://sovcombank.ru/credits/cash/alternativa"
    }

    options = uc.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    # Не грузим картинки
    options.add_experimental_option('prefs', {
        'profile.default_content_setting_values.images': 2
    })

    driver = uc.Chrome(options=options)
    driver.set_window_size(1200, 800)

    products = {}
    for key, url in urls.items():
        rate, term = extract_rate_term(driver, url)
        products[key] = {
            "Ставка": rate,
            "Срок": term,
            "Обновлено": datetime.utcnow().isoformat() + 'Z'
        }

    driver.quit()
    update_products_json(products, 'data/products.json')


if __name__ == '__main__':
    main()
