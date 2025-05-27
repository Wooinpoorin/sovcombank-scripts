#!/usr/bin/env python3
# data/auto_update_products.py

import json
import re
import os
from bs4 import BeautifulSoup
from datetime import datetime

# Папка, где лежит этот скрипт (data/)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Папка с HTML-страницами
HTML_DIR = os.path.join(SCRIPT_DIR, "html_pages")

# Пути к HTML-файлам
files = {
    "prime_plus": os.path.join(HTML_DIR, "prime_plus.html"),
    "car_pledge_loan": os.path.join(HTML_DIR, "car_pledge_loan.html"),
    "real_estate_pledge_loan": os.path.join(HTML_DIR, "real_estate_pledge_loan.html"),
}

def extract_max_term(soup):
    """Ищет блок 'Срок кредита' и возвращает максимальный срок в месяцах."""
    h2 = soup.find("h2", string=re.compile(r"Срок кредита"))
    if not h2:
        return 0
    sec = h2.find_next_sibling(lambda tag: tag.name in ("p", "ul"))
    if not sec:
        return 0
    nums = re.findall(r"\b(\d+)\b", sec.get_text())
    months = [int(n) for n in nums]
    return max(months) if months else 0

def parse_page(key, path):
    """Парсит одну страницу, возвращает (rate, term)."""
    with open(path, encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")

    term = extract_max_term(soup)
    rate = None

    if key == "prime_plus":
        h2 = soup.find("h2", string=re.compile(r"Основная процентная ставка"))
        if h2:
            for p in h2.find_next_siblings("p"):
                strong = p.find("strong")
                text = strong.get_text() if strong else p.get_text()
                m = re.search(r"([\d,\.]+)%", text)
                if m:
                    rate = float(m.group(1).replace(",", "."))
                    break

    elif key == "car_pledge_loan":
        h2 = soup.find("h2", string=re.compile(r"Процентная ставка"))
        if h2:
            ul = h2.find_next_sibling("ul")
            if ul:
                vals = [
                    float(m.group(1).replace(",", "."))
                    for li in ul.find_all("li")
                    for m in [re.search(r"([\d,\.]+)%", li.get_text())]
                    if m
                ]
                if vals:
                    rate = min(vals)

    elif key == "real_estate_pledge_loan":
        h2 = soup.find("h2", string=re.compile(r"Процентная ставка"))
        if h2:
            p = h2.find_next_sibling("p")
            if p:
                nums = re.findall(r"([\d,\.]+)", p.get_text())
                nums = [float(x.replace(",", ".")) for x in nums]
                if nums:
                    rate = min(nums)

    return rate, term

def main():
    now_iso = datetime.utcnow().isoformat() + "Z"
    data = {}

    for key, filepath in files.items():
        rate, term = parse_page(key, filepath)
        data[key] = {
            "Ставка (%)": rate,
            "Срок (мес.)": term,
            "Обновлено": now_iso
        }

    # Путь до выходного JSON — data/products.json
    out_path = os.path.join(SCRIPT_DIR, "products.json")
    with open(out_path, "w", encoding="utf-8") as fw:
        json.dump(data, fw, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
