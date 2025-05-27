// popup.js
// Данные подгружаются из публичного репозитория:
// https://github.com/Wooinpoorin/sovcombank-scripts/tree/main/data/

(async () => {
  const BASE = 'https://raw.githubusercontent.com/Wooinpoorin/sovcombank-scripts/main/data/';

  async function loadJSON(name) {
    const res = await fetch(`${BASE}${name}`);
    if (!res.ok) throw new Error(`${name} загрузка: ${res.status}`);
    return res.json();
  }

  // Считываем данные из cl2.html — ФИО, имя, отчество, MCC, кредиты
  function extractClient() {
    // ФИО
    const fioEl = document.getElementById('fio');
    const fullName = fioEl ? fioEl.textContent.trim() : '';
    const parts = fullName.split(/\s+/);
    const firstName = parts[1] || '';
    const patronymic = parts[2] || '';

    // Категория клиента (напр. VIP если есть слово "VIP" в ФИО, можно заменить логику)
    let category = '';
    if (/VIP/i.test(fullName)) category = 'VIP';

    // Месяцы до конца кредита (по минимальному сроку любого кредита)
    let credit_remaining_months = 0;
    const creditsTable = document.querySelector('#credits-table tbody');
    if (creditsTable && creditsTable.rows.length) {
      let minMonths = Infinity;
      for (const row of creditsTable.rows) {
        const closeDate = row.cells[5]?.textContent.trim();
        if (closeDate) {
          const [d, m, y] = closeDate.split('.');
          const end = new Date(`${y}-${m}-${d}`);
          const now = new Date();
          let months = (end.getFullYear() - now.getFullYear()) * 12 + (end.getMonth() - now.getMonth());
          if (months < minMonths) minMonths = months;
        }
      }
      credit_remaining_months = minMonths !== Infinity ? minMonths : 0;
    }

    // Список операций (MCC-коды)
    const opsTable = document.getElementById('ops-table');
    const operations = [];
    if (opsTable) {
      for (const row of opsTable.rows) {
        const mcc = Number(row.cells[4]?.textContent.trim());
        if (mcc) operations.push(mcc);
      }
    }

    return {
      fullName,
      firstName,
      patronymic,
      category,
      credit_remaining_months,
      operations
    };
  }

  // Проверка совпадения клиента с триггером правила
  function matchesRule(trigger, client) {
    if (Array.isArray(trigger.mcc_codes) && trigger.mcc_codes.length) {
      const count = client.operations.filter(mcc => trigger.mcc_codes.includes(mcc)).length;
      if (count >= (trigger.min_count || 1)) return true;
    }
    if (trigger.client_category && client.category === trigger.client_category) return true;
    if (trigger.credit_remaining_months != null && client.credit_remaining_months <= trigger.credit_remaining_months) return true;
    return false;
  }

  const TARGET_PRODUCT_MAP = {
    premium_loan:            'prime_plus',
    car_loan:                'car_pledge_loan',
    real_estate_pledge_loan: 'real_estate_pledge_loan'
  };

  const PRODUCT_TITLES = {
    prime_plus:              'Кредит Прайм Плюс',
    car_pledge_loan:         'Автокредит под залог авто',
    real_estate_pledge_loan: 'Кредит под залог недвижимости'
  };

  function getProductRateTerm(prod) {
    let rateStr = '—%';
    let termStr = '— мес.';
    if ('Ставка (%)' in prod && prod['Ставка (%)'] != null) {
      rateStr = prod['Ставка (%)'] + '%';
    }
    if ('Срок (мес.)' in prod && prod['Срок (мес.)'] != null && prod['Срок (мес.)'] > 0) {
      termStr = prod['Срок (мес.)'] + ' мес.';
    }
    return { rateStr, termStr };
  }

  function formatConditions(prod) {
    const { rateStr, termStr } = getProductRateTerm(prod);
    const parts = [];
    parts.push(`ставка ${rateStr}`);
    if (termStr !== '— мес.') parts.push(`срок ${termStr}`);
    return `Предварительные условия: ${parts.join(', ')}.`;
  }

  function fillPlaceholders(text, vals) {
    return text.replace(/{{(ФИО|Имя|Отчество|credit_remaining_months|ставка|срок)}}/g, (_, key) => {
      switch (key) {
        case 'ФИО': return vals.fullName;
        case 'Имя': return vals.firstName;
        case 'Отчество': return vals.patronymic;
        case 'credit_remaining_months': return String(vals.credit_remaining_months);
        case 'ставка': return vals.rate;
        case 'срок': return vals.term;
      }
      return _;
    });
  }

  // Случайный выбор из массива с исключением ранее использованных (для разнообразия)
  function pick(arr, used = []) {
    const filtered = arr.filter(e => !used.includes(e));
    if (filtered.length === 0) return arr[Math.floor(Math.random() * arr.length)] || '';
    return filtered[Math.floor(Math.random() * filtered.length)] || '';
  }

  document.getElementById('generate').addEventListener('click', async () => {
    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (!tab?.id) throw new Error('Не удалось получить текущую вкладку.');

      const [{ result: client }] = await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        func: extractClient
      });

      if (!client) throw new Error('Не найден блок клиента на странице.');

      const [phrases, rules, products] = await Promise.all([
        loadJSON('phrases.json'),
        loadJSON('rules.json'),
        loadJSON('products.json')
      ]);

      // Собираем правила по каждому продукту (не только по одному совпавшему!)
      const allProductKeys = ['prime_plus', 'car_pledge_loan', 'real_estate_pledge_loan'];

      // Для каждого продукта собираем подходящие правила
      let offers = [];
      for (const prodKey of allProductKeys) {
        const prodRules = Object.values(rules)
          .filter(rule => {
            const mapKey = TARGET_PRODUCT_MAP[rule.target_product];
            return mapKey === prodKey && matchesRule(rule.trigger, client);
          })
          .sort((a, b) => a.priority - b.priority);

        // Если не нашлось по этому продукту, подставляем дефолтное правило если оно на него
        if (!prodRules.length && rules.default) {
          const mapKey = TARGET_PRODUCT_MAP[rules.default.target_product];
          if (mapKey === prodKey) prodRules.push(rules.default);
        }
        // Добавляем
        for (const rule of prodRules) {
          offers.push({ rule, prodKey });
        }
      }

      // Если совсем ничего не нашлось (нет дефолта под продукты), добавим по одному дефолтному предложению на продукт
      if (!offers.length && rules.default) {
        for (const prodKey of allProductKeys) {
          const mapKey = TARGET_PRODUCT_MAP[rules.default.target_product];
          if (mapKey === prodKey) offers.push({ rule: rules.default, prodKey });
        }
      }

      // Ограничим 1-2 шаблона на продукт для наглядности, но покажем по каждому продукту!
      const container = document.getElementById('scriptsContainer');
      container.innerHTML = '';

      let idx = 1;

      for (const { rule, prodKey } of offers) {
        const prod = products[prodKey];
        const title = PRODUCT_TITLES[prodKey] || prodKey;
        const prelim = formatConditions(prod);

        const { rateStr, termStr } = getProductRateTerm(prod);

        const vals = {
          fullName: client.fullName,
          firstName: client.firstName,
          patronymic: client.patronymic,
          credit_remaining_months: client.credit_remaining_months,
          rate: rateStr,
          term: termStr
        };

        // Сгенерируем по 1-2 скрипта для каждого оффера для разнообразия
        const usedBlocks = {};
        for (let v = 0; v < 2; v++) {
          const lines = rule.phrase_blocks.map(block => {
            const key = block === 'intro' ? 'greeting' : block;
            const arr = phrases[key] || [];
            if (!usedBlocks[key]) usedBlocks[key] = [];
            const phrase = fillPlaceholders(pick(arr, usedBlocks[key]), vals);
            usedBlocks[key].push(phrase);
            return phrase;
          }).filter(Boolean);

          let scriptText = lines.join(' ');
          if (scriptText) scriptText = scriptText[0].toUpperCase() + scriptText.slice(1);

          const card = document.createElement('div');
          card.className = 'script-card';
          card.innerHTML = `
            <strong>Скрипт #${idx++}: ${title}</strong>
            <p>${prelim} ${scriptText}</p>
          `;
          container.appendChild(card);
        }
      }

    } catch (e) {
      console.error(e);
      alert('Ошибка генерации скриптов: ' + e.message);
    }
  });
})();
