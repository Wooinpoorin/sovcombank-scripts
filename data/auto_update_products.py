#!/usr/bin/env python3
# data/auto_update_products.py

import os
import sys
import json
import re
import time
import traceback
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException

PAGES = {
    "prime_plus":              "https://sovcombank.ru/apply/credit/kredit-na-kartu/",
    "car_pledge_loan":         "https://sovcombank.ru/credits/cash/pod-zalog-avto-/",
    "real_estate_pledge_loan": "https://sovcombank.ru/credits/cash/alternativa/"
}

SELECTOR_KREDIT = r"td.Tariffs-module--tableDataDescr--KbfG1"
SELECTOR_COMMON = r"td[data-type='value']"

def create_driver():
    opts = Options()
    opts.add_argument("--headless")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_experimental_option("prefs", {"profile.managed_default_content_settings.images": 2})
    driver_path = ChromeDriverManager().install()
    service = Service(driver_path)
    return webdriver.Chrome(service=service, options=opts)

def extract_rate_term(driver, url):
    driver.get(url)
    wait = WebDriverWait(driver, 20)
    wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    time.sleep(2)

    # сначала пробуем «родной» селектор
    sel = SELECTOR_KREDIT if "kredit-na-kartu" in url else SELECTOR_COMMON
    try:
        wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, sel)))
        elems = driver.find_elements(By.CSS_SELECTOR, sel)
        texts = [e.text.replace("\u00A0", " ").strip() for e in elems if e.text.strip()]
    except TimeoutException:
        # если ничего не нашли за 20 секунд — уходим в full-text
        body_text = driver.find_element(By.TAG_NAME, "body").text
        texts = [line.strip() for line in body_text.splitlines() if line.strip()]

    rates = []
    terms = []

    # собираем все процентные ставки
    for t in texts:
        for num in re.findall(r"([\d\.,]+)\s*%", t):
            try:
                rates.append(float(num.replace(",", ".")))
            except ValueError:
                continue

    # ищем упоминания «до N лет/год/мес/дн»
    for t in texts:
        m = re.search(r"до\s*(\d+)\s*(лет|год|мес|дн)", t, flags=re.IGNORECASE)
        if m:
            n = int(m.group(1))
            unit = m.group(2).lower()
            if unit in ("лет", "год"):
                terms.append(n * 12)
            elif unit == "мес":
                terms.append(n)
            elif unit == "дн":
                terms.append(max(1, n // 30))

    return (min(rates) if rates else None, max(terms) if terms else 0)

def main():
    driver = create_driver()
    results = {}
    ts = datetime.utcnow().isoformat() + "Z"

    for key, url in PAGES.items():
        try:
            rate, term = extract_rate_term(driver, url)
        except Exception:
            print(f"\n❗ Ошибка при парсинге «{key}» ({url}):", file=sys.stderr)
            traceback.print_exc()
            rate, term = None, 0
        results[key] = {"Ставка (%)": rate, "Срок (мес.)": term, "Обновлено": ts}

    driver.quit()

    os.makedirs("data", exist_ok=True)
    with open("data/products.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(json.dumps(results, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
