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
    Загружает страницу по URL и извлекает минимальную процентную ставку и максимальный срок в месяцах.
    Возвращает кортеж (rate: float | None, term: int).
    """
    driver.get(url)
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.TAG_NAME, "body"))
    )
    time.sleep(1)

    # Для страницы 'kredit-na-kartu' селектор отличается
    if "kredit-na-kartu" in url:
        tds = driver.find_elements(
            By.CSS_SELECTOR,
            "td.Tariffs-module--tableDataDescr--KbfG1.Tariffs-module--seoRedesign--OwzVi"
        )
    else:
        # Селектор для остальных двух страниц
        tds = driver.find_elements(
            By.CSS_SELECTOR,
            "td.max-w-xs.font-semibold.sm\\:max-w-none.lg\\:text-lg[data-type='value']"
        )

    texts = [td.text.strip() for td in tds]

    # Процентная ставка — первый текст, содержащий '%'
    rate_text = next((t for t in texts if '%' in t), None)
    # Срок — остальные поля без '%'
    term_texts = [t for t in texts if '%' not in t]

    # Извлечение и парсинг чисел для ставки
    rate = None
    if rate_text:
        rate_nums = re.findall(r"[\d.,]+", rate_text)
        rate_floats = [float(num.replace(',', '.')) for num in rate_nums]
        if rate_floats:
            rate = min(rate_floats)

    # Извлечение и парсинг сроков (берем максимальный), конвертируем годы в месяцы
    term = 0
    for txt in term_texts:
        nums = re.findall(r"\d+", txt)
        ints = [int(n) for n in nums]
        if not ints:
            continue
        max_int = max(ints)
        if 'год' in txt or 'лет' in txt:
            months = max_int * 12
        else:
            months = max_int
        term = max(term, months)

    return rate, term


def update_products_json(products, filepath):
    """Записывает словарь products в JSON-файл по указанному пути."""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(products, f, ensure_ascii=False, indent=2)


def main():
    # Соответствие ключей и URL-ов
    urls = {
        "car_pledge_loan": "https://sovcombank.ru/credits/cash/pod-zalog-avto-",
        "prime_plus": "https://sovcombank.ru/apply/credit/kredit-na-kartu/",
        "real_estate_pledge_loan": "https://sovcombank.ru/credits/cash/alternativa"
    }

    # Настройка драйвера
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

    # Сохраняем результаты в файл репозитория
    update_products_json(products, 'data/products.json')


if __name__ == '__main__':
    main()
