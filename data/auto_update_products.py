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

# Три целевых страницы с обязательным слэшем на конце
PAGES = {
    "prime_plus":              "https://sovcombank.ru/apply/credit/kredit-na-kartu/",
    "car_pledge_loan":         "https://sovcombank.ru/credits/cash/pod-zalog-avto-/",
    "real_estate_pledge_loan": "https://sovcombank.ru/credits/cash/alternativa/"
}

# Универсальный селектор для всех трёх страниц
UNIVERSAL_TD = "td[data-type='value']"

def create_driver():
    chrome_bin = "/usr/bin/chromium-browser"
    driver_bin = "/usr/bin/chromedriver"
    opts = Options()
    opts.binary_location = chrome_bin
    opts.add_argument("--headless")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    # не грузим картинки для скорости
    opts.add_experimental_option("prefs", {"profile.managed_default_content_settings.images": 2})
    svc = Service(driver_bin)
    return webdriver.Chrome(service=svc, options=opts)

def extract_rate_term(driver, url):
    driver.get(url)
    wait = WebDriverWait(driver, 15)
    # ждём, что страница загрузится
    wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    time.sleep(1)

    # ждём появление нужных ячеек
    wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, UNIVERSAL_TD)))

    elems = driver.find_elements(By.CSS_SELECTOR, UNIVERSAL_TD)
    texts = [e.text.replace("\u00A0", " ").strip() for e in elems if e.text.strip()]

    rates = []
    terms = []

    for t in texts:
        # 1) Ставки: все числа перед '%'
        if "%" in t:
            for num in re.findall(r"[\d\.,]+", t):
                try:
                    rates.append(float(num.replace(",", ".")))
                except:
                    pass
        # 2) Сроки: годы → месяцы
        for m in re.findall(r"(\d+)\s*(лет|год[ау]?)", t, flags=re.IGNORECASE):
            terms.append(int(m[0]) * 12)
        #    месяцы
        for m in re.findall(r"(\d+)\s*(мес(?:\.|яц[ея]в?)?)", t, flags=re.IGNORECASE):
            terms.append(int(m[0]))
        #    дни → месяцы
        for m in re.findall(r"(\d+)\s*дн[ея]?", t, flags=re.IGNORECASE):
            days = int(m[0])
            terms.append(max(1, days // 30))

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
