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
          .filter(([, cat]) => op.includes(cat))
          .map(([, cat]) => cat)
      )
    )];
  }

  function selectRule(rules, client, purchaseCats) {
    return Object.values(rules)
      .sort((a, b) => a.priority - b.priority)
      .find(rule => {
        const t = rule.trigger;
        if (t.client_category && client.category === t.client_category) return true;
        if (t.credit_remaining_months !== undefined &&
            client.credit_remaining_months <= t.credit_remaining_months) return true;
        if (t.purchase_categories && t.purchase_categories.length) {
          const matches = purchaseCats.filter(cat => t.purchase_categories.includes(cat));
          if (matches.length >= (t.min_count || 0)) return true;
        }
        return false;
      });
  }

  function generateScript(phrases, partners, products, client, rule) {
    // 1. Greeting
    const greeting = phrases.greeting[
      Math.floor(Math.random() * phrases.greeting.length)
    ];

    // 2. Interest-based line
    const cats = getPurchaseCategories(client.operations, partners);
    let interestLine = '';
    for (const cat of cats) {
      const key = `interest_${cat.toLowerCase()}`;
      if (phrases[key]) {
        const arr = phrases[key];
        interestLine = arr[Math.floor(Math.random() * arr.length)];
        break;
      }
    }

    // 3. Core blocks
    const hook = phrases.hook[
      Math.floor(Math.random() * phrases.hook.length)
    ];
    const offerIntro = phrases.offer_intro[
      Math.floor(Math.random() * phrases.offer_intro.length)
    ];
    const usp = phrases.usp[
      Math.floor(Math.random() * phrases.usp.length)
    ];
    const contextQ = phrases.context_question[
      Math.floor(Math.random() * phrases.context_question.length)
    ];
    const sumTermQ = phrases.sum_term_question[
      Math.floor(Math.random() * phrases.sum_term_question.length)
    ];
    const closing = phrases.closing[
      Math.floor(Math.random() * phrases.closing.length)
    ];

    // 4. Product data
    const prod = products[rule.target_product] || {};
    const rate = prod.Ставка != null ? `от ${prod.Ставка}%` : '';
    const term = prod.Срок != null ? `${prod.Срок} мес.` : '';

    // 5. Assemble and substitute
    let text = `${greeting} `;
    if (interestLine) text += `${interestLine} `;
    text += `${hook} ${offerIntro} ${rate}, ${usp} ${contextQ} ${sumTermQ} ${closing}`;

    text = text
      .replace(/{{ФИО}}/g, client.name)
      .replace(/{{credit_remaining_months}}/g, client.credit_remaining_months)
      .replace(/{{ставка}}/g, rate)
      .replace(/{{срок}}/g, term);

    return text;
  }

  document.getElementById('generate').addEventListener('click', async () => {
    try {
      // Extract client data from active tab
      const [{ result: client }] = await chrome.scripting.executeScript({
        target: { tabId: (await chrome.tabs.query({ active: true, currentWindow: true }))[0].id },
        func: extractClient
      });

      // Load JSON data
      const [phrases, rules, partners, products] = await Promise.all([
        loadJSON('phrases.json'),
        loadJSON('rules.json'),
        loadJSON('partners.json'),
        loadJSON('products.json')
      ]);

      const purchaseCats = getPurchaseCategories(client.operations, partners);
      const rule = selectRule(rules, client, purchaseCats);

      const container = document.getElementById('scriptsContainer');
      container.innerHTML = '';
      if (!rule) {
        container.innerHTML = '<p>Нет рекомендаций</p>';
        return;
      }

      // Generate 5 variations
      for (let i = 1; i <= 5; i++) {
        const script = generateScript(phrases, partners, products, client, rule);
        container.insertAdjacentHTML(
          'beforeend',
          `<div class="script"><strong>Вариант ${i}:</strong><p>${script}</p></div>`
        );
      }
    } catch (e) {
      console.error(e);
      alert('Ошибка генерации скрипта: ' + e.message);
    }
  });
})();
