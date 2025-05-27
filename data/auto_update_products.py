import requests
import openai
import json
import time

# ==== КОНФИГ ====
OPENAI_API_KEY = "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"  # <-- ВСТАВЬ СВОЙ КЛЮЧ OpenAI API

URLS = {
    "car_pledge_loan": "https://sovcombank.ru/credits/cash/pod-zalog-avto-",
    "real_estate_pledge_loan": "https://sovcombank.ru/credits/cash/alternativa",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "text/html,application/xhtml+xml,application/xml",
    "Referer": "https://sovcombank.ru/"
}

# ==== AI ПАРСИНГ ====
def ai_parse_conditions(html, product_name):
    system_prompt = (
        "Ты профессиональный банковский бот. "
        "Тебе даётся HTML страницы продукта Совкомбанка. "
        "Найди минимальную и максимальную процентные ставки по кредиту, "
        "минимальный и максимальный срок кредита (в месяцах или годах), "
        "выдавай только JSON: {\"min_rate\": <float>, \"max_rate\": <float>, "
        "\"min_term\": <int>, \"max_term\": <int>}.\n"
        "Если есть только одно значение — оно и min, и max.\n"
        "Если не нашёл что-то, укажи null."
    )
    prompt = f"""
Вот HTML для продукта '{product_name}' (https://sovcombank.ru). 
Найди значения, как указано выше, и выдай только JSON!
HTML:
<<<
{html[:35000]}  # GPT-4o видит большой контекст, но если что — можно сократить.
>>>
"""
    openai.api_key = OPENAI_API_KEY
    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        temperature=0.0,
        max_tokens=500
    )
    # Достаём чистый JSON из ответа
    text = response.choices[0].message.content
    json_start = text.find('{')
    json_end = text.rfind('}') + 1
    try:
        parsed = json.loads(text[json_start:json_end])
    except Exception:
        parsed = None
    return parsed

def main():
    results = {}
    now = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())

    for name, url in URLS.items():
        print(f"Парсим {name} ({url}) ...")
        try:
            html = requests.get(url, headers=HEADERS, timeout=20).text
            data = ai_parse_conditions(html, name)
        except Exception as e:
            print(f"❗ Ошибка при парсинге {name}: {e}")
            data = None
        # Формируем финальный словарь
        results[name] = {
            "Ставка мин": data["min_rate"] if data else None,
            "Ставка макс": data["max_rate"] if data else None,
            "Срок мин": data["min_term"] if data else None,
            "Срок макс": data["max_term"] if data else None,
            "Обновлено": now,
        }
        # OpenAI просит лимиты по токенам — если долго, делаем паузу между запросами
        time.sleep(2)

    # === СОХРАНЕНИЕ В JSON ===
    with open("data/products.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print("Выгружено в data/products.json")

if __name__ == "__main__":
    main()
