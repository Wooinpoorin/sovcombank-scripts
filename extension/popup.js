(async () => {
  const BASE = 'https://raw.githubusercontent.com/Wooinpoorin/sovcombank-scripts/main/data/';

  async function loadJSON(filename) {
    const res = await fetch(BASE + filename);
    if (!res.ok) throw new Error(`${filename} загрузка: ${res.status}`);
    return res.json();
  }

  function extractClient() {
    const fullName = document.querySelector('#fio')?.innerText.trim()
                   || document.querySelector('.full-name')?.innerText.trim()
                   || '';
    const parts = fullName.split(/\s+/);
    return {
      fullName,
      firstName: parts[1] || '',
      patronymic: parts[2] || '',
      category: document.querySelector('.client-category')?.innerText.trim() || '',
      credit_remaining_months:
        Number(document.querySelector('.credit-remaining')?.innerText.trim()) || 0,
      operations: Array.from(document.querySelectorAll('#ops-table tr')).map(tr => {
        const mccCell = tr.cells[4];
        return { mcc: mccCell ? Number(mccCell.innerText.trim()) : null };
      })
    };
  }

  function matchesRule(rule, client) {
    const t = rule.trigger;
    if (Array.isArray(t.mcc_codes) && t.mcc_codes.length) {
      const cnt = client.operations.filter(op => t.mcc_codes.includes(op.mcc)).length;
      if (cnt >= (t.min_count || 1)) return true;
    }
    if (t.client_category && client.category === t.client_category) return true;
    if (t.credit_remaining_months != null
        && client.credit_remaining_months <= t.credit_remaining_months) return true;
    return false;
  }

  function generateScript(phrases, products, client, rule) {
    const text = rule.phrase_blocks.map(block => {
      const arr = phrases[block] || [];
      return arr[Math.floor(Math.random() * arr.length)] || '';
    }).join(' ');
    return text
      .replace(/{{ФИО}}/g, client.fullName)
      .replace(/{{Имя}}/g, client.firstName)
      .replace(/{{Отчество}}/g, client.patronymic)
      .replace(/{{credit_remaining_months}}/g, client.credit_remaining_months)
      .replace(/{{ставка}}/g, products[rule.target_product]?.Ставка != null
                                 ? `${products[rule.target_product].Ставка}%` : '—')
      .replace(/{{срок}}/g, products[rule.target_product]?.Срок != null
                                 ? `${products[rule.target_product].Срок} мес.` : '—');
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

      // получаем пары [ключ правила, правило] и фильтруем
      const matched = Object.entries(rules)
        .sort(([, a], [, b]) => a.priority - b.priority)
        .filter(([, rule]) => matchesRule(rule, client));

      // если ничего не подошло — кладём default
      if (matched.length === 0 && rules.default) {
        matched.push(['default', rules.default]);
      }

      matched.forEach(([ruleKey, rule], idx) => {
        const prod = products[rule.target_product] || {};
        // русское название продукта
        const productName = prod.Описание || rule.target_product;
        // ставка и срок для превью
        const rate = prod.Ставка != null ? `${prod.Ставка}%` : '—';
        const term = prod.Срок != null ? `${prod.Срок} мес.` : '—';
        const prelim = `Предварительные условия: ставка ${rate}, срок ${term}.`;

        const body = generateScript(phrases, products, client, rule);

        container.insertAdjacentHTML('beforeend',
          `<div class="script-card">
             <strong>Скрипт #${idx + 1}: ${productName}</strong>
             <p>${prelim} ${body}</p>
           </div>`
        );
      });
    } catch (e) {
      console.error(e);
      alert('Ошибка генерации скриптов: ' + e.message);
    }
  });
})();
