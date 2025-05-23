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
      operations: Array.from(document.querySelectorAll('.client-operations li')).map(li => li.innerText.trim())
    };
  }

  function getPurchaseCategories(operations, partners) {
    return [...new Set(
      operations.flatMap(op =>
        Object.entries(partners)
          .filter(([merchant, category]) => op.includes(merchant))
          .map(([, category]) => category)
      )
    )];
  }

  function selectRule(rules, client, purchaseCats) {
    return Object.values(rules)
      .sort((a, b) => a.priority - b.priority)
      .find(rule => {
        const t = rule.trigger;
        // 1. VIP by category
        if (t.client_category && client.category === t.client_category) {
          return true;
        }
        // 2. Soon expiring credit
        if (t.credit_remaining_months !== undefined &&
            client.credit_remaining_months <= t.credit_remaining_months) {
          return true;
        }
        // 3. Purchase-based triggers
        if (t.purchase_categories && t.purchase_categories.length) {
          const matchCount = purchaseCats.filter(cat => t.purchase_categories.includes(cat)).length;
          if (matchCount >= (t.min_count || 0)) {
            return true;
          }
        }
        return false;
      });
  }

  function generateScript(phrases, rule, products, client) {
    // assemble phrase blocks
    let text = rule.phrase_blocks
      .map(block => {
        const arr = phrases[block] || [];
        return arr[Math.floor(Math.random() * arr.length)] || '';
      })
      .join(' ');

    const product = products[rule.target_product] || {};
    text = text
      .replace('{{ФИО}}', client.name)
      .replace('{{ставка}}', product.Ставка ?? '')
      .replace('{{срок}}', product.Срок ?? '')
      .replace('{{discount}}', product.discount ?? '')
      .replace('{{cashback}}', product.cashback ?? '')
      .replace('{{installment_months}}', product.installment_months ?? '')
      .replace('{{credit_remaining_months}}', client.credit_remaining_months);

    return text;
  }

  document.getElementById('generate').addEventListener('click', async () => {
    try {
      // Получаем данные клиента из активной вкладки
      const [{ result: client }] = await chrome.scripting.executeScript({
        target: { tabId: (await chrome.tabs.query({ active: true, currentWindow: true }))[0].id },
        func: extractClient
      });

      // Загружаем все JSON-данные
      const [phrases, rules, partners, products] = await Promise.all([
        loadJSON('phrases.json'),
        loadJSON('rules.json'),
        loadJSON('partners.json'),
        loadJSON('products.json')
      ]);

      // Определяем категории покупок клиента
      const purchaseCats = getPurchaseCategories(client.operations, partners);

      // Выбираем первичное правило
      const rule = selectRule(rules, client, purchaseCats);

      const container = document.getElementById('scriptsContainer');
      container.innerHTML = '';

      if (!rule) {
        container.innerHTML = '<p>Нет рекомендаций</p>';
        return;
      }

      // Генерируем 5 вариантов
      for (let i = 1; i <= 5; i++) {
        const script = generateScript(phrases, rule, products, client);
        container.insertAdjacentHTML('beforeend',
          `<div class="script"><strong>Вариант ${i}:</strong><p>${script}</p></div>`
        );
      }

    } catch (e) {
      console.error(e);
      alert('Ошибка генерации скрипта: ' + e.message);
    }
  });
})();
