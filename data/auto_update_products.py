#!/usr/bin/env python3
import os
import json
import sys                  # <-- добавлено
import re
import time
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Три целевых страницы
PAGES = {
    "prime_plus":              "https://sovcombank.ru/apply/credit/kredit-na-kartu/",
    "car_pledge_loan":         "https://sovcombank.ru/credits/cash/pod-zalog-avto-",
    "real_estate_pledge_loan": "https://sovcombank.ru/credits/cash/alternativa"
}

# Селекторы из ваших парсеров
SEL_KREDIT = "td.Tariffs-module--tableDataDescr--KbfG1.Tariffs-module--seoRedesign--OwzVi"
SEL_COMMON = "td.max-w-xs.font-semibold.sm\\:max-w-none.lg\\:text-lg[data-type='value']"

def create_driver():
    """Создаёт headless Selenium ChromeDriver на CI без патчей."""
    chrome_bin = "/usr/bin/chromium-browser"
    driver_bin = "/usr/bin/chromedriver"
    opts = Options()
    opts.binary_location = chrome_bin
    opts.add_argument("--headless")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    # Отключаем картинки для скорости
    opts.add_experimental_option("prefs", {"profile.managed_default_content_settings.images": 2})
    svc = Service(driver_bin)
    return webdriver.Chrome(service=svc, options=opts)

def extract_rate_term(driver, url):
    driver.get(url)
    wait = WebDriverWait(driver, 15)
    # ждём тело
    wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    time.sleep(1)

    # выбираем правильный селектор
    sel = SEL_KREDIT if "kredit-na-kartu" in url else SEL_COMMON
    wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, sel)))

    # прокрутка для ленивых элементов
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(0.5)
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(0.5)

    elems = driver.find_elements(By.CSS_SELECTOR, sel)
    texts = [e.text.replace("\u00A0", " ").strip() for e in elems if e.text.strip()]

    rates = []
    terms = []

    # минимальная ставка
    for t in texts:
        if "%" in t:
            for num in re.findall(r"[\d\.,]+", t):
                try:
                    rates.append(float(num.replace(",", ".")))
                except:
                    pass

    # максимальный срок
    for t in texts:
        # годы → месяцы
        for m in re.findall(r"(\d+)\s*(лет|год[ау]?)", t, flags=re.IGNORECASE):
            terms.append(int(m[0])*12)
        # месяцы
        for m in re.findall(r"(\d+)\s*(мес(?:\.|яц[ея]в?)?)", t, flags=re.IGNORECASE):
            terms.append(int(m[0]))
        # дни → месяцы
        for m in re.findall(r"(\d+)\s*дн[ея]?", t, flags=re.IGNORECASE):
            days = int(m[0]); terms.append(max(1, days//30))

    return (min(rates) if rates else None, max(terms) if terms else 0)


def main():
    driver = create_driver()
    results = {}
    now = datetime.utcnow().isoformat() + "Z"

    for key, url in PAGES.items():
        try:
            rate, term = extract_rate_term(driver, url)
        except Exception as e:
            print(f"Error parsing {key}: {e}", file=sys.stderr)
            rate, term = None, 0
        results[key] = {"Ставка": rate, "Срок": term, "Обновлено": now}

    driver.quit()

    os.makedirs("data", exist_ok=True)
    out = "data/products.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
