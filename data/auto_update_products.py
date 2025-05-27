# data/auto_update_products.py
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time, json, re
from datetime import datetime
from bs4 import BeautifulSoup


def extract_rate_term(driver, url):
    driver.get(url)
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    time.sleep(1)  # пусть подгрузится JS
    
    # парсим через BS4
    html = driver.page_source
    soup = BeautifulSoup(html, 'html.parser')
    
    rates = []
    terms = []
    
    # ищем все ряды таблиц на странице
    for tr in soup.select('table tr'):
        tds = tr.find_all('td')
        if len(tds) < 2:
            continue
        
        label = tds[0].get_text(strip=True).lower()
        value = tds[1].get_text(strip=True).replace('\u00A0', ' ')
        
        # 1) процентная ставка
        if '%' in value:
            # вытаскиваем все числа с десятичными
            nums = re.findall(r'[\d\.,]+', value)
            floats = [float(n.replace(',', '.')) for n in nums]
            rates.extend(floats)
        
        # 2) срок
        # ищем фразу «до N <unit>»
        m = re.search(r'до\s*(\d+)\s*(дн[ея]?|мес(?:\.|яц[ея]в?)?|лет|год[ау]?)', value, flags=re.IGNORECASE)
        if m:
            n, unit = int(m.group(1)), m.group(2).lower()
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
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(products, f, ensure_ascii=False, indent=2)


def main():
    urls = {
        "car_pledge_loan":       "https://sovcombank.ru/credits/cash/pod-zalog-avto-",
        "prime_plus":            "https://sovcombank.ru/apply/credit/kredit-na-kartu/",
        "real_estate_pledge_loan":"https://sovcombank.ru/credits/cash/alternativa"
    }
    options = uc.ChromeOptions()
    options.add_argument('--headless')
    options.add_experimental_option('prefs', {'profile.default_content_setting_values.images': 2})
    driver = uc.Chrome(options=options)
    driver.set_window_size(1200, 800)
    
    products = {}
    for key, url in urls.items():
        rate, term = extract_rate_term(driver, url)
        products[key] = {
            "Ставка": rate,
            "Срок": term,
            "Обновлено": datetime.utcnow().isoformat() + "Z"
        }
    
    driver.quit()
    update_products_json(products, 'data/products.json')


if __name__ == '__main__':
    main()
