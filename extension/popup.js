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

  // Сопоставление ключей правил с реальными продуктами и человекочитаемыми названиями
  const PRODUCT_ALIASES = {
    prime_plus:            ['prime_plus', 'Кредит Прайм Плюс'],
    car_pledge_loan:       ['car_pledge_loan', 'Автокредит под залог авто'],
    real_estate_pledge_loan:['real_estate_pledge_loan', 'Кредит под залог недвижимости']
  };

  function generateScriptText(phrases, products, client, rule, actualKey) {
    const body = rule.phrase_blocks.map(block => {
      const arr = phrases[block] || [];
      return arr[Math.floor(Math.random() * arr.length)] || '';
    }).join(' ');
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

      // Отбор и сортировка правил
      const matched = Object.entries(rules)
        .sort(([,a],[,b]) => a.priority - b.priority)
        .filter(([,rule]) => matchesRule(rule, client));

      if (matched.length === 0 && rules.default) {
        matched.push(['default', rules.default]);
      }

      matched.forEach(([ruleKey, rule], idx) => {
        const [actualKey, humanName] = PRODUCT_ALIASES[rule.target_product] || [rule.target_product, rule.target_product];
        const rate = products[actualKey]?.Ставка != null ? `${products[actualKey].Ставка}%` : '—';
        const term = products[actualKey]?.Срок   != null ? `${products[actualKey].Срок} мес.`  : '—';
        const prelim = `Предварительные условия: ставка ${rate}, срок ${term}.`;
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
