import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime
import time

HF_TOKEN = "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"  # <-- вставь свой токен
LLM_API_URL = "https://api-inference.huggingface.co/models/deepseek-ai/deepseek-llm-7b-chat"  # или другую бесплатную LLM

HEADERS = {
    "Authorization": f"Bearer {HF_TOKEN}",
    "Content-Type": "application/json"
}

URLS = {
    "car_pledge_loan": "https://sovcombank.ru/credits/cash/pod-zalog-avto-",
    "real_estate_pledge_loan": "https://sovcombank.ru/credits/cash/alternativa"
}

def ask_llm(prompt):
    payload = {
        "inputs": prompt,
        "parameters": {"max_new_tokens": 256, "temperature": 0.1},
        "options": {"wait_for_model": True}
    }
    response = requests.post(LLM_API_URL, headers=HEADERS, json=payload, timeout=60)
    response.raise_for_status()
    data = response.json()
    # DeepSeek, Llama и другие возвращают [{'generated_text': "..."}]
    if isinstance(data, list) and 'generated_text' in data[0]:
        return data[0]['generated_text']
    elif isinstance(data, dict) and "generated_text" in data:
        return data["generated_text"]
    else:
        return str(data)

def extract_conditions(text):
    prompt = (
        "Прочитай этот текст с сайта банка. "
        "Извлеки минимальную процентную ставку (если есть диапазон — возьми минимальную), и максимальный срок кредитования в месяцах. "
        "Верни результат строго в формате JSON: {'Ставка': число, 'Срок': число}.\n"
        "Текст:\n" + text
    )
    answer = ask_llm(prompt)
    # Ищем JSON в ответе
    match = re.search(r"\{[^\}]+\}", answer)
    if match:
        try:
            data = json.loads(match.group(0).replace("'", '"'))
            return data.get('Ставка'), data.get('Срок')
        except Exception:
            pass
    return None, 0

def main():
    products = {}
    ts = datetime.utcnow().isoformat() + "Z"
    for key, url in URLS.items():
        print(f"Парсим {key} ({url}) ...")
        resp = requests.get(url, timeout=30)
        soup = BeautifulSoup(resp.text, "html.parser")
        # Берём основной текст (можно расширить селектор)
        main_text = soup.get_text(separator="\n", strip=True)
        # Режем чтобы не было слишком длинно (лимиты)
        main_text = main_text[:3000]
        try:
            rate, term = extract_conditions(main_text)
            print(f"  Ставка: {rate}, Срок: {term}")
        except Exception as e:
            print(f"❗ Ошибка при парсинге {key}: {e}")
            rate, term = None, 0
        products[key] = {"Ставка": rate, "Срок": term, "Обновлено": ts}
        time.sleep(6)  # не спамить API HuggingFace

    with open("data/products.json", "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)
    print("Выгружено в data/products.json")

if __name__ == "__main__":
    main()
