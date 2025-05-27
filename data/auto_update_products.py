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
    Загружает страницу, подгружает весь динамический контент,
    берёт все <td data-type="value"> и из них парсит:
     - минимальную процентную ставку
     - максимальный срок в месяцах
    """
    driver.get(url)
    # ждём, пока появится тело страницы
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

    # скроллим вниз/вверх, чтобы подгрузились ленивые элементы
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(0.5)
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(0.5)

    # ждём, пока появятся элементы с data-type="value"
    WebDriverWait(driver, 15).until(
        EC.presence_of_all_elements_located((By.CSS_SELECTOR, "td[data-type='value']"))
    )

    rates = []
    terms = []

    # берём текст всех ячеек
    tds = driver.find_elements(By.CSS_SELECTOR, "td[data-type='value']")
    for td in tds:
        text = td.text.replace('\u00A0', ' ').strip()
        if not text:
            continue

        # 1) процентная ставка
        if '%' in text:
            for num in re.findall(r'[\d\.,]+', text):
                try:
                    rates.append(float(num.replace(',', '.')))
                except:
                    continue

        # 2) срок (берём последнюю цифру для максимума)
        if 'до' in text:
            nums = re.findall(r'(\d+)', text)
            if nums:
                n = int(nums[-1])
                if 'год' in text or 'лет' in text:
                    terms.append(n * 12)
                elif 'мес' in text:
                    terms.append(n)
                elif 'дн' in text:
                    terms.append(max(1, n // 30))

    rate = min(rates) if rates else None
    term = max(terms) if terms else 0
    return rate, term


def update_products_json(products, filepath):
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
