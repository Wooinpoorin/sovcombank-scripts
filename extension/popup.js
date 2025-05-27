(async () => {
  const BASE = 'https://raw.githubusercontent.com/Wooinpoorin/sovcombank-scripts/main/data/';

  async function loadJSON(name) {
    const res = await fetch(`${BASE}${name}`);
    if (!res.ok) throw new Error(`${name} загрузка: ${res.status}`);
    return res.json();
  }

  function extractClient() {
    const fioEl = document.querySelector('#fio');
    const fullName = fioEl ? fioEl.textContent.trim() : '';
    const parts = fullName.split(/\s+/);
    const mccs = Array.from(document.querySelectorAll('#ops-table tr'))
      .map(tr => Number(tr.cells[4]?.textContent.trim()) || null);

    return {
      fullName,
      firstName: parts[1] || '',
      patronymic: parts[2] || '',
      category: document.querySelector('.client-category')?.textContent.trim() || '',
      credit_remaining_months: Number(document.querySelector('.credit-remaining')?.textContent.trim()) || 0,
      operations: mccs
    };
  }

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

  function formatConditions(prod) {
    const parts = [];
    // Ставка: диапазон мин–макс
    const minRate = prod["Ставка мин"], maxRate = prod["Ставка макс"];
    const rateStr = (minRate != null && maxRate != null)
      ? (minRate === maxRate ? `${minRate}%` : `${minRate}%–${maxRate}%`)
      : '—%';
    parts.push(`ставка ${rateStr}`);

    // Срок: диапазон мин–макс
    const minTerm = prod["Срок мин"], maxTerm = prod["Срок макс"];
    if (minTerm != null && maxTerm != null) {
      const termStr = (minTerm === maxTerm ? `${minTerm}` : `${minTerm}–${maxTerm}`);
      parts.push(`срок ${termStr} мес.`);
    }

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

  // Функция для декартова произведения всех массивов вариантов фраз
  function cartesian(arrays) {
    if (!arrays.length) return [];
    return arrays.reduce((acc, curr) =>
      acc.flatMap(a => curr.map(b => a.concat([b]))), [[]]);
  }

  document.getElementById('generate').addEventListener('click', async () => {
    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (!tab?.id) throw new Error('Не удалось получить текущую вкладку.');

      // Инъектим extractClient
      const [{ result: client }] = await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        func: extractClient
      });

      if (!client) throw new Error('Не найден блок клиента на странице.');

      // Загружаем JSON-данные
      const [phrases, rules, products] = await Promise.all([
        loadJSON('phrases.json'),
        loadJSON('rules.json'),
        loadJSON('products.json')
      ]);

      // Ищем совпадения
      let matched = Object.values(rules)
        .map(rule => {
          const key = TARGET_PRODUCT_MAP[rule.target_product];
          return key && products[key] ? { rule, prodKey: key } : null;
        })
        .filter(Boolean)
        .filter(({ rule }) => matchesRule(rule.trigger, client))
        .sort((a, b) => a.rule.priority - b.rule.priority);

      // Дефолт
      if (!matched.length && rules.default) {
        const def = rules.default;
        const key = TARGET_PRODUCT_MAP[def.target_product];
        if (key && products[key]) matched.push({ rule: def, prodKey: key });
      }

      const container = document.getElementById('scriptsContainer');
      container.innerHTML = '';

      let idx = 1;

      matched.forEach(({ rule, prodKey }) => {
        const prod = products[prodKey];
        const title = PRODUCT_TITLES[prodKey] || prodKey;
        const prelim = formatConditions(prod);

        // Подстановочные значения
        const minR = prod["Ставка мин"], maxR = prod["Ставка макс"];
        const rateVal = (minR != null && maxR != null)
          ? (minR === maxR ? `${minR}%` : `${minR}%–${maxR}%`)
          : '—%';

        const minT = prod["Срок мин"], maxT = prod["Срок макс"];
        const termVal = (minT != null && maxT != null)
          ? (minT === maxT ? `${minT} мес.` : `${minT}–${maxT} мес.`)
          : '— мес.';

        const vals = {
          fullName: client.fullName,
          firstName: client.firstName,
          patronymic: client.patronymic,
          credit_remaining_months: client.credit_remaining_months,
          rate: rateVal,
          term: termVal
        };

        // Массивы всех вариантов для каждого блока
        const allPhraseVariants = rule.phrase_blocks.map(block => {
          const key = block === 'intro' ? 'greeting' : block;
          return (phrases[key] || []).map(phrase => fillPlaceholders(phrase, vals)).filter(Boolean);
        });

        // Декартово произведение (все комбинации)
        const combos = cartesian(allPhraseVariants);

        combos.forEach(combo => {
          let scriptText = combo.join(' ');
          if (scriptText) scriptText = scriptText[0].toUpperCase() + scriptText.slice(1);

          const card = document.createElement('div');
          card.className = 'script-card';
          card.innerHTML = `
            <strong>Скрипт #${idx++}: ${title}</strong>
            <p>${prelim} ${scriptText}</p>
          `;
          container.appendChild(card);
        });
      });

    } catch (e) {
      console.error(e);
      alert('Ошибка генерации скриптов: ' + e.message);
    }
  });
})();
