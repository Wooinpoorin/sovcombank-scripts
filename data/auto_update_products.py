import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time, json, re
from datetime import datetime

def patch_uc_chrome():
    """Патч для безопасного __del__ в undetected_chromedriver.Chrome"""
    original = uc.Chrome.__del__
    def safe_del(self):
        try:
            if hasattr(self, 'service') and self.service.is_connectable():
                self.quit()
        except:
            pass
    uc.Chrome.__del__ = safe_del
    uc.Chrome._original_del = original

patch_uc_chrome()

def create_driver():
    """
    Кастомный Chrome для CI:
    - headless + no-sandbox + disable-dev-shm-usage  
    - stealth-флаги и отключение картинок  
    - вбрасываем HTTP-заголовки через CDP
    """
    options = uc.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--disable-features=IsolateOrigins,site-per-process')
    options.add_argument('--disable-automation')
    options.add_experimental_option('prefs', {
        'profile.managed_default_content_settings.images': 2
    })

    driver = uc.Chrome(options=options)
    driver.set_window_size(1200, 800)

    # инжектим заголовки как в SovcombankParser#create_driver :contentReference[oaicite:0]{index=0}
    driver.execute_cdp_cmd('Network.setExtraHTTPHeaders', {
        'headers': {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:138.0) Gecko/20100101 Firefox/138.0',
            'Referer': 'https://sovcombank.ru/',
            'DNT': '1',
            'Connection': 'keep-alive'
        }
    })
    return driver

def extract_rate_term(driver, url):
    driver.get(url)
    WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    # дождаться, что ячейки появились
    WebDriverWait(driver, 15).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "td[data-type='value']")))

    # прокрутка для ленивой подгрузки
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(0.5)
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(0.5)

    rates, terms = [], []
    for td in driver.find_elements(By.CSS_SELECTOR, "td[data-type='value']"):
        txt = td.text.replace('\u00A0', ' ').strip()
        if not txt:
            continue

        # собираем все числа перед %
        if '%' in txt:
            for num in re.findall(r'[\d\.,]+', txt):
                try:
                    rates.append(float(num.replace(',', '.')))
                except:
                    pass

        # ищем «до N <unit>»
        m = re.search(r'до\s*(\d+)\s*(дн[ея]?|мес(?:\.|яц[ея]в?)?|лет|год[ау]?)',
                      txt, flags=re.IGNORECASE)
        if m:
            n, unit = int(m.group(1)), m.group(2).lower()
            if 'дн' in unit:
                months = max(1, n // 30)
            elif 'лет' in unit or 'год' in unit:
                months = n * 12
            else:
                months = n
            terms.append(months)

    return (min(rates) if rates else None,
            max(terms) if terms else 0)


def update_products_json(products, filepath):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(products, f, ensure_ascii=False, indent=2)


def main():
    urls = {
        "car_pledge_loan":        "https://sovcombank.ru/credits/cash/pod-zalog-avto-",
        "prime_plus":             "https://sovcombank.ru/apply/credit/kredit-na-kartu/",
        "real_estate_pledge_loan":"https://sovcombank.ru/credits/cash/alternativa"
    }

    driver = create_driver()
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
