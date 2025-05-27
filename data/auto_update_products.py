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
from selenium.common.exceptions import TimeoutException, NoSuchElementException

PAGES = {
    "prime_plus":              "https://sovcombank.ru/apply/credit/kredit-na-kartu/",
    "car_pledge_loan":         "https://sovcombank.ru/credits/cash/pod-zalog-avto-/",
    "real_estate_pledge_loan": "https://sovcombank.ru/credits/cash/alternativa/"
}

SELECTORS = {
    "prime_plus": [
        ("td.Tariffs-module--tableDataDescr--KbfG1", "table")
    ],
    "car_pledge_loan": [
        (".product-info-block__item-value", "dynamic"),
        ("body", "fulltext")
    ],
    "real_estate_pledge_loan": [
        (".scb-text__text", "dynamic"),
        ("body", "fulltext")
    ]
}

def create_driver():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,1080")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opts)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver

def extract_data(driver, url, selectors):
    driver.get(url)
    content = ""
    
    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH, "//*[contains(text(), '%') or contains(text(), 'мес')]"))
        )
        time.sleep(1)
        
        for selector, stype in selectors:
            try:
                if stype == "table":
                    elements = WebDriverWait(driver, 10).until(
                        EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector)))
                    content += "\n".join([e.text for e in elements]) + "\n"
                elif stype == "dynamic":
                    element = WebDriverWait(driver, 10).until(
                        EC.visibility_of_element_located((By.CSS_SELECTOR, selector)))
                    content += element.text + "\n"
            except (TimeoutException, NoSuchElementException):
                continue
        
        if not content:
            content = driver.find_element(By.TAG_NAME, "body").text
    
    except TimeoutException:
        content = driver.find_element(By.TAG_NAME, "body").text
    
    content = re.sub(r'\s+', ' ', content).lower()
    
    rates = []
    for match in re.finditer(r'(\d{1,3}(?:[.,]\d+)?)\s*%', content):
        try:
            rate = float(match.group(1).replace(',', '.'))
            rates.append(rate)
        except ValueError:
            continue
    
    terms = []
    term_patterns = [
        (r'до\s*(\d+)\s*(лет|год|мес|месяцев?)', 1),
        (r'срок\s*до\s*(\d+)\s*(лет|год|мес)', 1),
        (r'(\d+)\s*(лет|год|мес)', 1)
    ]
    
    for pattern, multiplier in term_patterns:
        for match in re.finditer(pattern, content):
            try:
                value = int(match.group(1))
                unit = match.group(2)
                if 'год' in unit or 'лет' in unit:
                    terms.append(value * 12)
                elif 'мес' in unit:
                    terms.append(value)
            except (ValueError, IndexError):
                continue
    
    min_rate = min(rates) if rates else None
    max_term = max(terms) if terms else 0
    
    return min_rate, max_term

def main():
    driver = create_driver()
    results = {}
    ts = datetime.utcnow().isoformat() + "Z"
    
    for key, url in PAGES.items():
        try:
            rate, term = extract_data(driver, url, SELECTORS[key])
        except Exception as e:
            print(f"\n❗ Ошибка при парсинге «{key}» ({url}): {str(e)}", file=sys.stderr)
            traceback.print_exc()
            rate, term = None, 0
        finally:
            results[key] = {
                "Ставка (%)": rate,
                "Срок (мес.)": term,
                "Обновлено": ts
            }
    
    driver.quit()
    
    os.makedirs("data", exist_ok=True)
    with open("data/products.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(json.dumps(results, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()