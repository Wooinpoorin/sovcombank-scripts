import os
import json
import re
import time
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Три целевых страницы
URLS = {
    "prime_plus":              "https://sovcombank.ru/apply/credit/kredit-na-kartu/",
    "car_pledge_loan":         "https://sovcombank.ru/credits/cash/pod-zalog-avto-",
    "real_estate_pledge_loan": "https://sovcombank.ru/credits/cash/alternativa"
}

def create_driver():
    chrome_bin = os.getenv("CHROME_BIN", "/usr/bin/chromium-browser")
    driver_path = os.getenv("CHROMEDRIVER_PATH", "/usr/bin/chromedriver")

    chrome_opts = Options()
    chrome_opts.binary_location = chrome_bin
    chrome_opts.add_argument("--headless")
    chrome_opts.add_argument("--no-sandbox")
    chrome_opts.add_argument("--disable-gpu")
    chrome_opts.add_argument("--disable-dev-shm-usage")
    chrome_opts.add_argument("--disable-extensions")
    chrome_opts.add_argument("--window-size=1200,800")

    # отключаем загрузку картинок
    prefs = {"profile.managed_default_content_settings.images": 2}
    chrome_opts.add_experimental_option("prefs", prefs)

    service = Service(driver_path)
    driver = webdriver.Chrome(service=service, options=chrome_opts)
    return driver

def extract_rate_term(driver, url):
    """
    1) Загружаем страницу
    2) Ждём <td data-type='value'>
    3) Сбор минимальной ставки и максимального срока
    """
    driver.get(url)
    wait = WebDriverWait(driver, 15)
    wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "td[data-type='value']")))

    # небольшая прокрутка для ленивых загрузок
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(0.5)
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(0.5)

    rates = []
    terms = []

    elems = driver.find_elements(By.CSS_SELECTOR, "td[data-type='value']")
    for td in elems:
        txt = td.text.replace('\u00A0', ' ').strip()
        if not txt:
            continue

        # проценты
        if '%' in txt:
            for num in re.findall(r'[\d\.,]+', txt):
                try:
                    rates.append(float(num.replace(',', '.')))
                except:
                    pass

        # «до N <unit>»
        m = re.search(r'до\s*(\d+)\s*(дн[ея]?|мес(?:\.|яц[ея]в?)?|лет|год[ау]?)', txt, flags=re.IGNORECASE)
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
    driver = create_driver()
    products = {}
    ts = datetime.utcnow().isoformat() + "Z"

    for key, url in URLS.items():
        try:
            rate, term = extract_rate_term(driver, url)
        except Exception as e:
            print(f"❗ Ошибка при парсинге {key}: {e}")
            rate, term = None, 0

        products[key] = {
            "Ставка":    rate,
            "Срок":      term,
            "Обновлено": ts
        }

    driver.quit()

    # Запись в JSON
    os.makedirs("data", exist_ok=True)
    with open("data/products.json", "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)

    # Печать для CI
    print(json.dumps(products, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
