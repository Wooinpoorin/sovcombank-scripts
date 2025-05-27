// popup.js
// Данные подгружаются из репозитория:
// https://github.com/Wooinpoorin/sovcombank-scripts/tree/main/data/

(async () => {
  const BASE = 'https://raw.githubusercontent.com/Wooinpoorin/sovcombank-scripts/main/data/';

  async function loadJSON(name) {
    const res = await fetch(`${BASE}${name}`);
    if (!res.ok) throw new Error(`${name} загрузка: ${res.status}`);
    return res.json();
  }

  // Считывание ФИО, MCC, кредитов из cl2.html
  function extractClient() {
    // ФИО, имя, отчество
    const fioEl = document.getElementById('fio');
    const fullName = fioEl ? fioEl.textContent.trim() : '';
    const parts = fullName.split(/\s+/);
    const firstName = parts[1] || '';
    const patronymic = parts[2] || '';

    // Категория клиента (напр. VIP если есть "VIP" в ФИО)
    let category = '';
    if (/VIP/i.test(fullName)) category = 'VIP';

    // Месяцы до конца кредита (по минимальному сроку)
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

    // Все уникальные MCC (только числа)
    const opsTable = document.getElementById('ops-table');
    const operations = [];
    if (opsTable) {
      for (const row of opsTable.rows) {
        const mcc = Number(row.cells[4]?.textContent.trim());
        if (mcc && !operations.includes(mcc)) operations.push(mcc);
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

  // Логика совпадения правила и клиента
  function matchesRule(trigger, client) {
    if (Array.isArray(trigger.mcc_codes) && trigger.mcc_codes.length) {
      const count = client.operations.filter(mcc => trigger.mcc_codes.includes(mcc)).length;
      if (count >= (trigger.min_count || 1)) return true;
    }
    if (trigger.client_category && client.category === trigger.client_category) return true;
    if (trigger.credit_remaining_months != null && client.credit_remaining_months <= trigger.credit_remaining_months) return true;
    // Если нет триггеров, подходит всем (например, default)
    if (
      (!trigger.mcc_codes || !trigger.mcc_codes.length) &&
      !trigger.client_category &&
      trigger.credit_remaining_months == null
    ) return true;
    return false;
  }

  // Привязки для отображения
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

  // Случайный выбор из массива с исключением использованных
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

      // --- Отладка: выводим MCC-коды клиента и сработавшие правила ---
      console.log("MCC клиента:", client.operations);

      const allProductKeys = ['prime_plus', 'car_pledge_loan', 'real_estate_pledge_loan'];
      const container = document.getElementById('scriptsContainer');
      container.innerHTML = '';
      let idx = 1;

      // Для каждого продукта собираем все совпавшие правила (и дефолт если нужно)
      for (const prodKey of allProductKeys) {
        const matchedRules = Object.values(rules)
          .filter(rule => {
            const mapKey = TARGET_PRODUCT_MAP[rule.target_product];
            return mapKey === prodKey && matchesRule(rule.trigger, client);
          })
          .sort((a, b) => a.priority - b.priority);

        // Отладка: какие rules сработали для этого продукта?
        console.log(`Для продукта ${PRODUCT_TITLES[prodKey]} найдены правила:`,
          matchedRules.map(r => r && r.phrase_blocks && r.phrase_blocks.join(', ')));

        // Если ни одного не нашли — добавим дефолт
        if (!matchedRules.length && rules.default) {
          matchedRules.push({
            ...rules.default,
            target_product: Object.keys(TARGET_PRODUCT_MAP).find(key => TARGET_PRODUCT_MAP[key] === prodKey) || 'prime_plus'
          });
        }

        // Для каждого сработавшего правила генерируем 2 шаблона (можно больше/меньше)
        for (const rule of matchedRules) {
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

          // Выводим два уникальных варианта скрипта для каждого rules+продукт
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
      }
    } catch (e) {
      console.error(e);
      alert('Ошибка генерации скриптов: ' + e.message);
    }
  });
})();
