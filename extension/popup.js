(async () => {
  const BASE = 'https://raw.githubusercontent.com/Wooinpoorin/sovcombank-scripts/main/data/';

  async function loadJSON(filename) {
    const res = await fetch(BASE + filename);
    if (!res.ok) throw new Error(`${filename} загрузка: ${res.status}`);
    return res.json();
  }

  function extractClient() {
    const fioEl = document.querySelector('#fio') || document.querySelector('.full-name');
    const fullName = fioEl ? fioEl.innerText.trim() : '';
    const parts = fullName.split(/\s+/);
    return {
      fullName,
      firstName: parts[1] || '',
      patronymic: parts[2] || '',
      category: document.querySelector('.client-category')?.innerText.trim() || '',
      credit_remaining_months: Number(document.querySelector('.credit-remaining')?.innerText.trim()) || 0,
      operations: Array.from(document.querySelectorAll('#ops-table tr')).map(tr => ({
        mcc: Number(tr.cells[4]?.innerText.trim()) || null
      }))
    };
  }

  function matchesRule(rule, client) {
    const t = rule.trigger;
    if (Array.isArray(t.mcc_codes) && t.mcc_codes.length) {
      const cnt = client.operations.filter(op => t.mcc_codes.includes(op.mcc)).length;
      if (cnt >= (t.min_count || 1)) return true;
    }
    if (t.client_category && client.category === t.client_category) return true;
    if (t.credit_remaining_months != null && client.credit_remaining_months <= t.credit_remaining_months) return true;
    return false;
  }

  // Алиасы для человекочитаемых названий и корректного поиска данных
  const PRODUCT_ALIASES = {
    // ключ в rules.json      →  [ключ в products.json,            русское название]
    consumer_loan:         ['online_cash_loan',      'Кредит наличными онлайн'],
    refinance_loan:        ['refinance_offer',       'Рефинансирование кредитов'],
    premium_loan:          ['premium_loan',          'Премиальный кредит для VIP'],
    car_loan:              ['car_loan',              'Автокредит на выгодных условиях'],
    travel_loan:           ['travel_loan',           'Кредит на путешествия'],
    grocery_loan:          ['grocery_loan',          'Кредит для покупок продуктов'],
    halva_card:            ['halva_card',            'Карта рассрочки Halva'],
    installment_card:      ['installment_card',      'Карта рассрочки до 24 мес.'],
  };

  function generateScriptText(phrases, products, client, rule, actualKey) {
    // генерируем основной текст
    const body = rule.phrase_blocks.map(block => {
      const arr = phrases[block] || [];
      return arr[Math.floor(Math.random() * arr.length)] || '';
    }).join(' ');

    // подставляем все плейсхолдеры
    return body
      .replace(/{{ФИО}}/g, client.fullName)
      .replace(/{{Имя}}/g, client.firstName)
      .replace(/{{Отчество}}/g, client.patronymic)
      .replace(/{{credit_remaining_months}}/g, client.credit_remaining_months)
      .replace(/{{ставка}}/g, products[actualKey]?.Ставка != null ? `${products[actualKey].Ставка}%` : '—')
      .replace(/{{срок}}/g, products[actualKey]?.Срок != null   ? `${products[actualKey].Срок} мес.`  : '—');
  }

  document.getElementById('generate').addEventListener('click', async () => {
    try {
      const [{ result: client }] = await chrome.scripting.executeScript({
        target: { tabId: (await chrome.tabs.query({ active:true, currentWindow:true }))[0].id },
        func: extractClient
      });

      const [phrases, rules, products] = await Promise.all([
        loadJSON('phrases.json'),
        loadJSON('rules.json'),
        loadJSON('products.json')
      ]);

      const container = document.getElementById('scriptsContainer');
      container.innerHTML = '';

      // отфильтровываем правила
      const matched = Object.entries(rules)
        .sort(([,a],[,b]) => a.priority - b.priority)
        .filter(([,rule]) => matchesRule(rule, client));

      if (matched.length === 0 && rules.default) matched.push(['default', rules.default]);

      matched.forEach(([ruleKey, rule], idx) => {
        // решаем, из какого ключа products брать данные и как назвать
        const [actualKey, humanName] = PRODUCT_ALIASES[rule.target_product] 
                                       || [rule.target_product, rule.target_product];

        // предварительные условия
        const rate = products[actualKey]?.Ставка != null ? `${products[actualKey].Ставка}%` : '—';
        const term = products[actualKey]?.Срок   != null ? `${products[actualKey].Срок} мес.`  : '—';
        const prelim = `Предварительные условия: ставка ${rate}, срок ${term}.`;

        // основной текст
        const text = generateScriptText(phrases, products, client, rule, actualKey);

        container.insertAdjacentHTML('beforeend', `
          <div class="script-card">
            <strong>Скрипт #${idx+1}: ${humanName}</strong>
            <p>${prelim} ${text}</p>
          </div>
        `);
      });
    } catch (e) {
      console.error(e);
      alert('Ошибка генерации скриптов: ' + e.message);
    }
  });
})();
