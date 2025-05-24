(async () => {
  const BASE = 'https://raw.githubusercontent.com/Wooinpoorin/sovcombank-scripts/main/data/';

  async function loadJSON(filename) {
    const res = await fetch(BASE + filename);
    if (!res.ok) throw new Error(`${filename} загрузка: ${res.status}`);
    return res.json();
  }

  function extractClient() {
    const fullName = document.querySelector('.full-name')?.innerText.trim() || '';
    const parts = fullName.split(/\s+/);
    return {
      fullName,
      firstName: parts[1] || '',
      patronymic: parts[2] || '',
      category: document.querySelector('.client-category')?.innerText.trim() || '',
      credit_remaining_months:
        Number(document.querySelector('.credit-remaining')?.innerText.trim()) || 0,
      operations: Array.from(document.querySelectorAll('.client-operations li')).map(li => ({
        text: li.innerText.trim(),
        mcc: li.dataset.mcc ? Number(li.dataset.mcc) : null
      }))
    };
  }

  function getPurchaseCategories(operations, partners) {
    return [...new Set(
      operations.flatMap(op =>
        Object.entries(partners)
          .filter(([, cat]) => op.text.includes(cat))
          .map(([, cat]) => cat)
      )
    )];
  }

  function selectRules(rules, client, purchaseCats) {
    return Object.values(rules)
      .sort((a, b) => a.priority - b.priority)
      .filter(rule => {
        const t = rule.trigger;
        // 1) MCC-based trigger
        if (Array.isArray(t.mcc_codes) && t.mcc_codes.length) {
          const count = client.operations.filter(op => t.mcc_codes.includes(op.mcc)).length;
          if (count >= (t.min_count || 0)) return true;
        }
        // 2) Purchase-category fallback (text-based)
        if (Array.isArray(t.purchase_categories) && t.purchase_categories.length) {
          const matchCount = purchaseCats.filter(cat => t.purchase_categories.includes(cat)).length;
          if (matchCount >= (t.min_count || 0)) return true;
        }
        // 3) Client-category trigger
        if (t.client_category && client.category === t.client_category) return true;
        // 4) Soon-expiring credit
        if (t.credit_remaining_months != null
            && client.credit_remaining_months <= t.credit_remaining_months) return true;
        return false;
      });
  }

  function generateScript(phrases, products, client, rule) {
    const parts = rule.phrase_blocks.map(block => {
      const arr = phrases[block] || [];
      return arr[Math.floor(Math.random() * arr.length)] || '';
    });
    let text = parts.join(' ');

    const prod = products[rule.target_product] || {};
    const rate = prod.Ставка != null ? `${prod.Ставка}%` : '';
    const term = prod.Срок   != null ? `${prod.Срок} мес.` : '';

    return text
      .replace(/{{ФИО}}/g, client.fullName)
      .replace(/{{Имя}}/g, client.firstName)
      .replace(/{{Отчество}}/g, client.patronymic)
      .replace(/{{credit_remaining_months}}/g, client.credit_remaining_months)
      .replace(/{{ставка}}/g, rate)
      .replace(/{{срок}}/g, term);
  }

  document.getElementById('generate').addEventListener('click', async () => {
    try {
      // Считываем информацию о клиенте
      const [{ result: client }] = await chrome.scripting.executeScript({
        target: {
          tabId: (await chrome.tabs.query({ active: true, currentWindow: true }))[0].id
        },
        func: extractClient
      });

      // Загружаем словари
      const [phrases, rules, partners, products] = await Promise.all([
        loadJSON('phrases.json'),
        loadJSON('rules.json'),
        loadJSON('partners.json'),
        loadJSON('products.json')
      ]);

      // Определяем текстовые категории по операциям
      const purchaseCats = getPurchaseCategories(client.operations, partners);
      // Выбираем все подходящие правила
      let matched = selectRules(rules, client, purchaseCats);
      // Если нет ни одного — вариант default
      if (!matched.length && rules.default) matched = [rules.default];

      const container = document.getElementById('scriptsContainer');
      container.innerHTML = '';

      // Для каждого правила выводим по одному скрипту
      matched.forEach((rule, idx) => {
        const script = generateScript(phrases, products, client, rule);
        container.insertAdjacentHTML('beforeend',
          `<div class="script-card"><strong>Предложение ${idx+1}: ${rule.target_product}</strong><p>${script}</p></div>`
        );
      });
    } catch (e) {
      console.error(e);
      alert('Ошибка генерации скриптов: ' + e.message);
    }
  });
})();
