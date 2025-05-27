#!/usr/bin/env python3
# data/auto_update_products.py

import os
import sys
import json
import re
import time
from datetime import datetime

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- Конфигурация трёх страниц ---
PAGES = {
    "prime_plus":              "https://sovcombank.ru/apply/credit/kredit-na-kartu/",
    "car_pledge_loan":         "https://sovcombank.ru/credits/cash/pod-zalog-avto-",
    "real_estate_pledge_loan": "https://sovcombank.ru/credits/cash/alternativa"
}

# Селекторы: для kredit-na-kartu особый класс, для остальных — общий
SELECTOR_KREDIT = "td.Tariffs-module--tableDataDescr--KbfG1.Tariffs-module--seoRedesign--OwzVi"
SELECTOR_COMMON = "td.max-w-xs.font-semibold.sm\\:max-w-none.lg\\:text-lg[data-type='value']"

# Окружение (CI) выставляет пути
CHROME_BIN = os.getenv("CHROME_BIN", "/usr/bin/chromium-browser")
CHROMEDRIVER_PATH = os.getenv("CHROMEDRIVER_PATH", "/usr/bin/chromedriver")


def patch_uc():
    """Патч для безопасного завершения undetected_chromedriver.Chrome.__del__"""
    original = uc.Chrome.__del__

    def safe_del(self):
        try:
            if hasattr(self, "service") and self.service.is_connectable():
                self.quit()
        except Exception:
            pass

    uc.Chrome.__del__ = safe_del
    uc.Chrome._original_del = original


def create_driver():
    """Готовим headless undetected_chromedriver для CI"""
    patch_uc()
    options = uc.ChromeOptions()
    options.binary_location = CHROME_BIN
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-blink-features=AutomationControlled")
    # не грузим картинки
    prefs = {"profile.managed_default_content_settings.images": 2}
    options.add_experimental_option("prefs", prefs)
    # заводим драйвер
    driver = uc.Chrome(options=options, driver_executable_path=CHROMEDRIVER_PATH)
    driver.set_window_size(1200, 800)
    return driver


def extract_rate_term(driver, url):
    """
    1) Загружаем страницу
    2) Ждём body, ждём ячейки нужного селектора
    3) Парсим минимальную ставку и максимальный срок
    """
    driver.get(url)

    # 1. Ждём загрузки тела страницы
    WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.TAG_NAME, "body"))
    )
    time.sleep(1)

    # 2. Выбираем нужный селектор
    if "kredit-na-kartu" in url:
        sel = SELECTOR_KREDIT
    else:
        sel = SELECTOR_COMMON

    # 3. Ждём появления ячеек
    WebDriverWait(driver, 15).until(
        EC.presence_of_all_elements_located((By.CSS_SELECTOR, sel))
    )

    # 4. Пролистываем (для ленивой подгрузки)
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(0.5)
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(0.5)

    elements = driver.find_elements(By.CSS_SELECTOR, sel)
    texts = [el.text.replace("\u00A0", " ").strip() for el in elements if el.text.strip()]

    # 5. Ставка: минимальная из всех чисел с %
    rates = []
    for t in texts:
        if "%" in t:
            for num in re.findall(r"[\d\.,]+", t):
                try:
                    rates.append(float(num.replace(",", ".")))
                except:
                    pass

    # 6. Срок: из всех «N <unit>» — конвертируем и берём max
    terms = []
    for t in texts:
        # ищем два числа подряд (от … до …)
        # либо «до N <unit>», либо «N до M <unit>»
        # Но проще: все числа без % → год→мес, дни→мес
        for m in re.findall(r"(\d+)\s*(лет|год[ау]?)", t, flags=re.IGNORECASE):
            terms.append(int(m[0]) * 12)
        for m in re.findall(r"(\d+)\s*(мес(?:\.|яц[ея]в?)?)", t, flags=re.IGNORECASE):
            terms.append(int(m[0]))
        for m in re.findall(r"(\d+)\s*(дн[ея]?)", t, flags=re.IGNORECASE):
            days = int(m[0])
            terms.append(max(1, days // 30))

    return (min(rates) if rates else None, max(terms) if terms else 0)


def main():
    driver = create_driver()
    products = {}
    ts = datetime.utcnow().isoformat() + "Z"

    for key, url in PAGES.items():
        try:
            rate, term = extract_rate_term(driver, url)
        except Exception as e:
            print(f"❗ Ошибка при парсинге '{key}': {e}", file=sys.stderr)
            rate, term = None, 0

        products[key] = {"Ставка": rate, "Срок": term, "Обновлено": ts}

    driver.quit()

    # Гарантированное создание папки
    os.makedirs("data", exist_ok=True)
    with open("data/products.json", "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)

    # Лог для CI
    print(json.dumps(products, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
