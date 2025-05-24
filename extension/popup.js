(async () => {
  const BASE = 'https://raw.githubusercontent.com/Wooinpoorin/sovcombank-scripts/main/data/';

  async function loadJSON(filename) {
    const res = await fetch(BASE + filename);
    if (!res.ok) throw new Error(`${filename} загрузка: ${res.status}`);
    return res.json();
  }

  function extractClient() {
    // ФИО
    const fullName = document.querySelector('#fio')?.innerText.trim() || 'Клиент';
    const parts = fullName.split(/\s+/);
    const firstName = parts[1] || '';
    const patronymic = parts[2] || '';

    // Категория (на этой странице нет, оставляем пустой)
    const category = '';

    // Остаток месяцев по ближайшему кредиту
    const now = new Date();
    let minMonths = Infinity;
    document.querySelectorAll('#credits-table tbody tr').forEach(tr => {
      const closeText = tr.cells[5]?.innerText.trim(); // кол-во ячейка «Дата окончания»
      if (closeText) {
        const [d, m, y] = closeText.split('.');
        const closeDate = new Date(`${y}-${m}-${d}`);
        const months = (closeDate.getFullYear() - now.getFullYear()) * 12
                     + (closeDate.getMonth() - now.getMonth());
        if (months >= 0 && months < minMonths) {
          minMonths = months;
        }
      }
    });
    const credit_remaining_months = isFinite(minMonths) ? minMonths : 0;

    // Операции: описание и MCC из таблицы «Последние покупки»
    const operations = Array.from(document.querySelectorAll('#ops-table tr')).map(tr => {
      const cells = tr.cells;
      const text = cells[2]?.innerText.trim() || '';
      const mcc = parseInt(cells[4]?.innerText.trim()) || null;
      return { text, mcc };
    });

    return { fullName, firstName, patronymic, category, credit_remaining_months, operations };
  }

  function selectRule(rules, client) {
    return Object.values(rules)
      .sort((a, b) => a.priority - b.priority)
      .find(rule => {
        const t = rule.trigger;
        // MCC-триггер
        if (Array.isArray(t.mcc_codes) && t.mcc_codes.length) {
          const count = client.operations.filter(op => t.mcc_codes.includes(op.mcc)).length;
          if (count >= (t.min_count || 0)) return true;
        }
        // Категория клиента
        if (t.client_category && client.category === t.client_category) return true;
        // Остаток месяцев
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
      const [{ result: client }] = await chrome.scripting.executeScript({
        target: { tabId: (await chrome.tabs.query({ active: true, currentWindow: true }))[0].id },
        func: extractClient
      });

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
