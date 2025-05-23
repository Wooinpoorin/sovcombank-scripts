(async () => {
  const BASE = 'https://raw.githubusercontent.com/Wooinpoorin/sovcombank-scripts/main/data/';

  async function loadJSON(filename) {
    const res = await fetch(BASE + filename);
    if (!res.ok) throw new Error(`${filename} загрузка: ${res.status}`);
    return res.json();
  }

  function extractClient() {
    return {
      name: document.querySelector('.full-name')?.innerText.trim() || 'Клиент',
      category: document.querySelector('.client-category')?.innerText.trim() || '',
      credit_remaining_months: Number(document.querySelector('.credit-remaining')?.innerText.trim()) || 0,
      operations: Array.from(document.querySelectorAll('.client-operations li')).map(li => ({
        text: li.innerText.trim(),
        mcc: li.dataset.mcc ? Number(li.dataset.mcc) : null
      }))
    };
  }

  function selectRule(rules, client) {
    return Object.values(rules)
      .sort((a, b) => a.priority - b.priority)
      .find(rule => {
        const t = rule.trigger;
        // MCC-based trigger
        if (Array.isArray(t.mcc_codes) && t.mcc_codes.length) {
          const count = client.operations.filter(op => t.mcc_codes.includes(op.mcc)).length;
          if (count >= (t.min_count || 0)) return true;
        }
        // Client category trigger
        if (t.client_category && client.category === t.client_category) return true;
        // Soon-expiring credit trigger
        if (t.credit_remaining_months != null &&
            client.credit_remaining_months <= t.credit_remaining_months) return true;
        return false;
      });
  }

  function generateScript(phrases, products, client, rule) {
    const blocks = rule.phrase_blocks || [];
    let text = blocks.map(block => {
      const arr = phrases[block] || [];
      return arr[Math.floor(Math.random() * arr.length)] || '';
    }).join(' ');

    const prod = products[rule.target_product] || {};
    const rate = prod.Ставка != null ? `от ${prod.Ставка}%` : '';
    const term = prod.Срок != null ? `${prod.Срок} мес.` : '';

    text = text
      .replace(/{{ФИО}}/g, client.name)
      .replace(/{{credit_remaining_months}}/g, client.credit_remaining_months)
      .replace(/{{ставка}}/g, rate)
      .replace(/{{срок}}/g, term);

    return text;
  }

  document.getElementById('generate').addEventListener('click', async () => {
    try {
      // Извлекаем данные клиента
      const [{ result: client }] = await chrome.scripting.executeScript({
        target: { tabId: (await chrome.tabs.query({ active: true, currentWindow: true }))[0].id },
        func: extractClient
      });

      // Загружаем все необходимые JSON
      const [phrases, rules, products] = await Promise.all([
        loadJSON('phrases.json'),
        loadJSON('rules.json'),
        loadJSON('products.json')
      ]);

      const rule = selectRule(rules, client);
      const container = document.getElementById('scriptsContainer');
      container.innerHTML = '';

      if (!rule) {
        container.innerHTML = '<p>Нет рекомендаций</p>';
        return;
      }

      // Генерируем 5 вариантов
      for (let i = 1; i <= 5; i++) {
        const script = generateScript(phrases, products, client, rule);
        container.insertAdjacentHTML(
          'beforeend',
          `<div class="script-card"><strong>Вариант ${i}:</strong><p>${script}</p></div>`
        );
      }
    } catch (e) {
      console.error(e);
      alert('Ошибка генерации скрипта: ' + e.message);
    }
  });
})();
