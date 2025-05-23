(async () => {
  const base = 'https://raw.githubusercontent.com/Wooinpoorin/sovcombank-scripts/main/data/';
  async function load(file) {
    const res = await fetch(base + file);
    if (!res.ok) throw new Error(file + ' загрузка: ' + res.status);
    return res.json();
  }

  function extractClient() {
    return {
      name: document.querySelector('.full-name')?.innerText || 'Клиент',
      category: document.querySelector('.client-category')?.innerText || '',
      credit_remaining_months: +document.querySelector('.credit-remaining')?.innerText || 0,
      operations: Array.from(document.querySelectorAll('.client-operations li')).map(li => li.innerText)
    };
  }

  function getCategories(ops, partners) {
    return [...new Set(
      ops.flatMap(op => Object.entries(partners)
        .filter(([name,cat]) => op.includes(name))
        .map(([,cat]) => cat)
      )
    )];
  }

  function selectRule(rules, client, cats) {
    return Object.values(rules)
      .sort((a,b) => a.priority - b.priority)
      .find(r => {
        const t = r.trigger;
        if (t.client_category && t.client_category === client.category) return true;
        if (t.purchase_categories) {
          const m = cats.filter(c => t.purchase_categories.includes(c));
          if (m.length >= t.min_count) return true;
        }
        return false;
      });
  }

  function generate(phrases, rule, products, client) {
    let text = rule.phrase_blocks.map(block => {
      const arr = phrases[block] || [];
      return arr[Math.floor(Math.random() * arr.length)];
    }).join(' ');
    const prod = products[rule.target_product] || {};
    text = text
      .replace('{{ФИО}}', client.name)
      .replace('{{ставка}}', prod.Ставка || '')
      .replace('{{срок}}', prod.Срок || '')
      .replace('{{installment_months}}', prod.installment_months || '')
      .replace('{{discount}}', prod.discount || '')
      .replace('{{название}}', rule.target_product);
    return text;
  }

  document.getElementById('generate').addEventListener('click', async () => {
    try {
      const [{result: client}] = await chrome.scripting.executeScript({
        target: { tabId: (await chrome.tabs.query({active: true, currentWindow: true}))[0].id },
        func: extractClient
      });

      const [phrases, rules, partners, products] = await Promise.all([
        load('phrases.json'), load('rules.json'),
        load('partners.json'), load('products.json')
      ]);
      const cats = getCategories(client.operations, partners);
      const rule = selectRule(rules, client, cats);
      const container = document.getElementById('scriptsContainer');
      container.innerHTML = '';
      if (!rule) { container.innerHTML = '<p>Нет рекомендаций</p>'; return; }
      for (let i = 1; i <= 5; i++) {
        const script = generate(phrases, rule, products, client);
        container.insertAdjacentHTML('beforeend', `<div class="script"><strong>Вариант ${i}:</strong><p>${script}</p></div>`);
      }
    } catch (e) {
      console.error(e);
      alert('Ошибка: ' + e.message);
    }
  });
})();