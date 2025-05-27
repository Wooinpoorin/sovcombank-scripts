import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import time
import json
import re
from datetime import datetime


def extract_rate_term(driver, url):
    """
    Загружает страницу по URL и извлекает минимальную процентную ставку и максимальный срок в месяцах.
    Теперь берём все <td data-type="value"> и парсим из них и %-ставки, и сроки.
    Возвращает кортеж (rate: float | None, term: int).
    """
    driver.get(url)
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    time.sleep(1)  # даём JS подгрузиться

    html = driver.page_source
    soup = BeautifulSoup(html, 'html.parser')

    rates = []
    terms = []

    # перебираем все ячейки, где лежат и ставки, и сроки
    for td in soup.find_all('td', attrs={'data-type': 'value'}):
        text = td.get_text(strip=True).replace('\u00A0', ' ')

        # 1) процентная ставка
        if '%' in text:
            nums = re.findall(r'[\d\.,]+', text)
            floats = [float(n.replace(',', '.')) for n in nums]
            rates.extend(floats)

        # 2) срок — ищем «до N <единица>»
        m = re.search(
            r'до\s*(\d+)\s*(дн[ея]?|мес(?:\.|яц[ея]в?)?|лет|год[ау]?)',
            text, flags=re.IGNORECASE
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


def update_products_json(products, filepath):
    """Записывает словарь products в JSON-файл по указанному пути."""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(products, f, ensure_ascii=False, indent=2)


def main():
    urls = {
        "car_pledge_loan":        "https://sovcombank.ru/credits/cash/pod-zalog-avto-",
        "prime_plus":             "https://sovcombank.ru/apply/credit/kredit-na-kartu/",
        "real_estate_pledge_loan":"https://sovcombank.ru/credits/cash/alternativa"
    }

    options = uc.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_experimental_option('prefs', {
        'profile.default_content_setting_values.images': 2
    })

    driver = uc.Chrome(options=options)
    driver.set_window_size(1200, 800)

    products = {}
    for key, url in urls.items():
        rate, term = extract_rate_term(driver, url)
        products[key] = {
            'Ставка': rate,
            'Срок': term,
            'Обновлено': datetime.utcnow().isoformat() + 'Z'
        }

    driver.quit()
    update_products_json(products, 'data/products.json')


if __name__ == '__main__':
    main()
