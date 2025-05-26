(async () => {
  const BASE = 'https://raw.githubusercontent.com/Wooinpoorin/sovcombank-scripts/main/data/';

  async function loadJSON(name) {
    const res = await fetch(BASE + name);
    if (!res.ok) throw new Error(`${name} загрузка: ${res.status}`);
    return res.json();
  }

  function extractClient() {
    const fioEl = document.querySelector('#fio');
    const fullName = fioEl ? fioEl.textContent.trim() : '';
    const parts = fullName.split(/\s+/);
    return {
      fullName,
      firstName: parts[1] || '',
      patronymic: parts[2] || '',
      category: document.querySelector('.client-category')?.textContent.trim() || '',
      credit_remaining_months: Number(document.querySelector('.credit-remaining')?.textContent.trim()) || 0,
      operations: Array.from(document.querySelectorAll('#ops-table tr')).map(tr => ({
        mcc: Number(tr.cells[4]?.textContent.trim()) || null
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

  function pickRandom(arr) {
    return arr[Math.floor(Math.random() * arr.length)] || '';
  }
  function capitalize(str) {
    return str.charAt(0).toUpperCase() + str.slice(1);
  }

  function formatConditions(product) {
    if (!product) return '';
    const parts = [];
    // always include rate with % (or placeholder)
    const rateText = product.Ставка != null ? `${product.Ставка}%` : '—%';
    parts.push(`ставка ${rateText}`);
    if (product.Срок != null && product.Срок > 0)            parts.push(`срок ${product.Срок} мес.`);
    if (product.cashback != null)        parts.push(`кэшбэк ${product.cashback}%`);
    if (product.saving != null)          parts.push(`экономия ${product.saving} ₽`);
    if (product.discount != null)        parts.push(`скидка ${product.discount}%`);
    if (product.installment_months != null) parts.push(`рассрочка ${product.installment_months} мес.`);
    return `Предварительные условия: ${parts.join(', ')}.`;
  }

  function buildScript(phrases, product, client, rule) {
    const rateText = product?.Ставка != null ? `${product.Ставка}%` : '—%';
    const termText = product?.Срок   != null ? `${product.Срок} мес.`  : '— мес.';
    const values = {
      '{{ФИО}}': client.fullName,
      '{{Имя}}': client.firstName,
      '{{Отчество}}': client.patronymic,
      '{{credit_remaining_months}}': client.credit_remaining_months,
      '{{ставка}}': rateText,
      '{{срок}}': termText
    };
    const fill = txt => Object.entries(values)
      .reduce((t,[ph,v]) => t.replace(new RegExp(ph,'g'), v), txt);

    const parts = [];

    if (rule.phrase_blocks.includes('greeting')) {
      parts.push(fill(pickRandom(phrases.greeting)));
    }

    ['hook','interest_auto','interest_home','interest_travel','interest_groceries'].forEach(block => {
      if (rule.phrase_blocks.includes(block)) {
        parts.push(fill(pickRandom(phrases[block])));
      }
    });

    if (rule.phrase_blocks.includes('offer_intro') && rule.phrase_blocks.includes('usp')) {
      const intro = fill(pickRandom(phrases.offer_intro));
      const usp   = fill(pickRandom(phrases.usp));
      parts.push(capitalize(`${intro} ${usp}`));
    } else if (rule.phrase_blocks.includes('offer_intro')) {
      parts.push(capitalize(fill(pickRandom(phrases.offer_intro))));
    }

    if (rule.phrase_blocks.includes('auto_pledge')) {
      parts.push(fill(pickRandom(phrases.auto_pledge)));
    }
    if (rule.phrase_blocks.includes('real_estate')) {
      parts.push(fill(pickRandom(phrases.real_estate)));
    }
    if (rule.phrase_blocks.includes('context_question')) {
      parts.push(fill(pickRandom(phrases.context_question)));
    }
    if (rule.phrase_blocks.includes('sum_term_question')) {
      parts.push(fill(pickRandom(phrases.sum_term_question)));
    }
    if (rule.phrase_blocks.includes('objection')) {
      parts.push(fill(pickRandom(phrases.objection)));
    }
    if (rule.phrase_blocks.includes('closing')) {
      parts.push(fill(pickRandom(phrases.closing)));
    }

    let text = parts.map(s => s.trim()).join(' ');
    // ensure every script mentions rate
    if (!text.includes('%')) {
      text = `Ставка ${rateText}. ` + text;
    }
    return text;
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

      const container = document.getElementById('scriptsContainer');
      container.innerHTML = '';

      const matched = Object.entries(rules)
        .sort(([,a],[,b]) => a.priority - b.priority)
        .filter(([,r]) => matchesRule(r, client));
      if (matched.length === 0 && rules.default) matched.push(['default', rules.default]);

      matched.forEach(([ruleKey, rule], idx) => {
        const ALIASES = {
          prime_plus:             ['prime_plus', 'Кредит Прайм Плюс'],
          car_pledge_loan:        ['car_pledge_loan', 'Автокредит под залог авто'],
          real_estate_pledge_loan:['real_estate_pledge_loan', 'Кредит под залог недвижимости']
        };
        const [prodKey, humanName] = ALIASES[rule.target_product] || [rule.target_product, rule.target_product];
        const product = products[prodKey];

        const prelim = formatConditions(product);
        const scriptText = buildScript(phrases, product, client, rule);

        const card = document.createElement('div');
        card.className = 'script-card';
        card.innerHTML = `
          <strong>Скрипт #${idx + 1}: ${humanName}</strong>
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
