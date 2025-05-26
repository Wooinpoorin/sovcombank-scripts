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

  function pick(arr) {
    return arr[Math.floor(Math.random() * arr.length)] || '';
  }

  const TARGET_PRODUCT_MAP = {
    premium_loan:            'prime_plus',
    car_loan:                'car_pledge_loan',
    real_estate_pledge_loan: 'real_estate_pledge_loan'
  };

  const PRODUCT_TITLES = {
    prime_plus:            'Кредит Прайм Плюс',
    car_pledge_loan:       'Автокредит под залог авто',
    real_estate_pledge_loan:'Кредит под залог недвижимости'
  };

  function formatConditions(prod) {
    const parts = [];
    // ставка всегда
    const rate = prod.Ставка != null ? `${prod.Ставка}%` : '—%';
    parts.push(`ставка ${rate}`);
    if (prod.Срок) parts.push(`срок ${prod.Срок} мес.`);
    return `Предварительные условия: ${parts.join(', ')}.`;
  }

  function fillPlaceholders(text, vals) {
    return text.replace(/{{(ФИО|Имя|Отчество|credit_remaining_months|ставка|срок)}}/g, (m, key) => {
      switch (key) {
        case 'ФИО': return vals.fullName;
        case 'Имя': return vals.firstName;
        case 'Отчество': return vals.patronymic;
        case 'credit_remaining_months': return String(vals.credit_remaining_months);
        case 'ставка': return vals.rate;
        case 'срок': return vals.term;
      }
      return m;
    });
  }

  document.getElementById('generate').addEventListener('click', async () => {
    try {
      // 1. Получаем клиента
      const [{ result: client }] = await chrome.scripting.executeScript({
        target: { tabId: (await chrome.tabs.query({ active:true, currentWindow:true }))[0].id },
        func: extractClient
      });

      // 2. Загружаем данные
      const [phrases, rules, productsRaw] = await Promise.all([
        loadJSON('phrases.json'),
        loadJSON('rules.json'),
        loadJSON('products.json')
      ]);

      // 3. Подготовим продукты: только наши три из products.json
      const products = productsRaw;

      // 4. Фильтруем правила и сопоставляем продукт
      const matched = Object.values(rules)
        .map(rule => {
          const key = TARGET_PRODUCT_MAP[rule.target_product];
          if (!key || !products[key]) return null;
          return { rule, prodKey: key };
        })
        .filter(Boolean)
        .filter(({ rule }) => matchesRule(rule.trigger, client))
        .sort((a, b) => a.rule.priority - b.rule.priority);

      // 5. Если нет совпадений — пробуем default
      if (matched.length === 0 && rules.default) {
        const def = rules.default;
        const key = TARGET_PRODUCT_MAP[def.target_product];
        if (key && products[key]) matched.push({ rule: def, prodKey: key });
      }

      // 6. Рендерим скрипты
      const container = document.getElementById('scriptsContainer');
      container.innerHTML = '';
      let idx = 1;
      matched.forEach(({ rule, prodKey }) => {
        const prod = products[prodKey];
        const title = PRODUCT_TITLES[prodKey] || prodKey;
        const prelim = formatConditions(prod);

        // готовим значения для плейсхолдеров
        const vals = {
          fullName: client.fullName,
          firstName: client.firstName,
          patronymic: client.patronymic,
          credit_remaining_months: client.credit_remaining_months,
          rate: prod.Ставка != null ? `${prod.Ставка}%` : '—%',
          term: prod.Срок   != null ? `${prod.Срок} мес.` : '— мес.'
        };

        // собираем скрипт
        const lines = rule.phrase_blocks.map(block => {
          const arr = phrases[block === 'intro' ? 'greeting' : block] || [];
          return fillPlaceholders(pick(arr), vals);
        }).filter(t => t);

        const scriptText = lines
          .map(s => s.trim())
          .join(' ')
          .replace(/\s+/g, ' ')
          .replace(/^\w/, c => c.toUpperCase());

        const card = document.createElement('div');
        card.className = 'script-card';
        card.innerHTML = `
          <strong>Скрипт #${idx++}: ${title}</strong>
          <p>${prelim} ${scriptText}</p>
        `;
        container.appendChild(card);
      });
    } catch (e) {
      console.error(e);
      alert('Ошибка генерации скриптов: ' + e.message);
    }
  });
})();
