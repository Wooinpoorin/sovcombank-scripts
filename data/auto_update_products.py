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
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

# Три целевых страницы (со слэшем)
PAGES = {
    "prime_plus":              "https://sovcombank.ru/apply/credit/kredit-na-kartu/",
    "car_pledge_loan":         "https://sovcombank.ru/credits/cash/pod-zalog-avto-/",
    "real_estate_pledge_loan": "https://sovcombank.ru/credits/cash/alternativa/"
}

def create_driver():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_experimental_option("prefs", {"profile.managed_default_content_settings.images": 2})
    path = ChromeDriverManager().install()
    service = Service(path)
    return webdriver.Chrome(service=service, options=opts)

def extract_rate_term(driver, url):
    driver.get(url)
    wait = WebDriverWait(driver, 15)
    # Ждём, что JSON будет вставлен
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "script#__NEXT_DATA__")))
    time.sleep(0.5)  # дать Next.js время

    # Парсим page_source для __NEXT_DATA__
    soup = BeautifulSoup(driver.page_source, "html.parser")
    script = soup.find("script", id="__NEXT_DATA__")
    if not script or not script.string:
        return None, 0

    data = json.loads(script.string)
    tariffs = data.get("props", {}) \
                   .get("pageProps", {}) \
                   .get("tariffs", []) or []

    rates = []
    terms = []

    for t in tariffs:
        # ставки
        for fld in ("minRate", "maxRate", "rate"):
            v = t.get(fld)
            if v is None: 
                continue
            for num in re.findall(r"[\d.,]+", str(v)):
                try:
                    rates.append(float(num.replace(",", ".")))
                except:
                    pass
        # сроки (месяцы)
        mn = t.get("minTermMonths")
        mx = t.get("maxTermMonths")
        if isinstance(mn, int):
            terms.append(mn)
        if isinstance(mx, int):
            terms.append(mx)

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
        results[key] = {"Ставка": rate, "Срок": term, "Обновлено": ts}

    driver.quit()

    os.makedirs("data", exist_ok=True)
    with open("data/products.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
