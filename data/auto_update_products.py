#!/usr/bin/env python3
# data/auto_update_products.py

import os
import sys
import json
import re
import time
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# три целевые страницы
PAGES = {
    "prime_plus":              "https://sovcombank.ru/apply/credit/kredit-na-kartu/",
    "car_pledge_loan":         "https://sovcombank.ru/credits/cash/pod-zalog-avto-",
    "real_estate_pledge_loan": "https://sovcombank.ru/credits/cash/alternativa"
}

# селекторы для таблиц
SELECTOR_KREDIT = "td.Tariffs-module--tableDataDescr--KbfG1.Tariffs-module--seoRedesign--OwzVi"
SELECTOR_COMMON = "td.max-w-xs.font-semibold.sm\\:max-w-none.lg\\:text-lg[data-type='value']"

def create_driver():
    chrome_bin = "/usr/bin/chromium-browser"
    driver_bin = "/usr/bin/chromedriver"
    opts = Options()
    opts.binary_location = chrome_bin
    opts.add_argument("--headless")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_experimental_option("prefs", {"profile.managed_default_content_settings.images": 2})
    return webdriver.Chrome(service=Service(driver_bin), options=opts)

def extract_rate_term(driver, url):
    driver.get(url)

    wait = WebDriverWait(driver, 15)
    wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    time.sleep(1)

    # выбираем нужный селектор
    if "kredit-na-kartu" in url:
        sel = SELECTOR_KREDIT
    else:
        sel = SELECTOR_COMMON

    wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, sel)))
    # подгружаем ленивые элементы
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(0.5)
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(0.5)

    tds = driver.find_elements(By.CSS_SELECTOR, sel)
    texts = [td.text.replace("\u00A0"," ").strip() for td in tds if td.text.strip()]

    # ставка: минимальное число с '%'
    rates = []
    for t in texts:
        if "%" in t:
            for num in re.findall(r"[\d\.,]+", t):
                try:
                    rates.append(float(num.replace(",", ".")))
                except:
                    pass

    # срок: максимальный из упоминаний диапазонов
    terms = []
    for t in texts:
        # «от X до Y»
        m = re.search(r"до\s*(\d+)", t)
        if m:
            n = int(m.group(1))
            if "лет" in t or "год" in t:
                terms.append(n * 12)
            elif "дн" in t:
                terms.append(max(1, n // 30))
            else:
                terms.append(n)

    return (
        min(rates) if rates else None,
        max(terms) if terms else 0
    )

def main():
    driver = create_driver()
    products = {}
    ts = datetime.utcnow().isoformat() + "Z"

    for key, url in PAGES.items():
        try:
            rate, term = extract_rate_term(driver, url)
        except Exception as e:
            print(f"Error parsing {key}: {e}", file=sys.stderr)
            rate, term = None, 0
        products[key] = {"Ставка": rate, "Срок": term, "Обновлено": ts}

    driver.quit()

    os.makedirs("data", exist_ok=True)
    with open("data/products.json", "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)

    print(json.dumps(products, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
