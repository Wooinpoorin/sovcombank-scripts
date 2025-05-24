(async () => {
  const BASE = 'https://raw.githubusercontent.com/Wooinpoorin/sovcombank-scripts/main/data/';

  async function loadJSON(file) {
    const res = await fetch(BASE + file);
    if (!res.ok) throw new Error(`${file} загрузка: ${res.status}`);
    return res.json();
  }

  function extractClient() {
    const fullName = document.querySelector('.full-name')?.innerText.trim() || '';
    const parts = fullName.split(/\s+/);
    return {
      fullName,
      firstName: parts[1] || '',
      patronymic: parts[2] || '',
      operations: Array.from(document.querySelectorAll('.client-operations li')).map(li => ({
        mcc: li.dataset.mcc ? Number(li.dataset.mcc) : null
      }))
    };
  }

  document.getElementById('generate').addEventListener('click', async () => {
    try {
      const [{ result: client }] = await chrome.scripting.executeScript({
        target: { tabId: (await chrome.tabs.query({ active: true, currentWindow: true }))[0].id },
        func: extractClient
      });

      const [phrases, products] = await Promise.all([
        loadJSON('phrases.json'),
        loadJSON('products.json')
      ]);

      // Product data
      const genProd = products["Кредит на карту Прайм Плюс"] || {};
      const autoProd = products["Кредит под залог автомобиля"] || {};
      const realProd = products["Кредит под залог недвижимости"] || {};

      const rateGen  = genProd.Ставка  || '';
      const termGen  = genProd.Срок    || '';
      const rateAuto = autoProd.Ставка || '';
      const termAuto = autoProd.Срок   || '';
      const rateReal = realProd.Ставка || '';
      const termReal = realProd.Срок   || '';

      // Detect fuel purchases
      const haveFuel = client.operations.some(op => [5541, 5542].includes(op.mcc));

      const container = document.getElementById('scriptsContainer');
      container.innerHTML = '';

      // 1. Generic cash offer
      {
        const tpl = phrases.generic_offer;
        const txt = tpl[Math.floor(Math.random() * tpl.length)]
          .replace(/{{ФИО}}/g, client.fullName)
          .replace(/{{Имя}}/g, client.firstName)
          .replace(/{{Отчество}}/g, client.patronymic)
          .replace(/{{ставка}}/g, rateGen)
          .replace(/{{срок}}/g, termGen);
        container.insertAdjacentHTML('beforeend',
          `<div class="script-card"><p>${txt}</p></div>`
        );
      }

      // 2–3. Auto-pledge (or fallback to generic)
      for (let i = 0; i < 2; i++) {
        const key = haveFuel ? 'auto_pledge' : 'generic_offer';
        const tpl = phrases[key];
        const txt = tpl[Math.floor(Math.random() * tpl.length)]
          .replace(/{{ФИО}}/g, client.fullName)
          .replace(/{{Имя}}/g, client.firstName)
          .replace(/{{Отчество}}/g, client.patronymic)
          .replace(/{{ставка}}/g, haveFuel ? rateAuto : rateGen)
          .replace(/{{срок}}/g, haveFuel ? termAuto : termGen);
        container.insertAdjacentHTML('beforeend',
          `<div class="script-card"><p>${txt}</p></div>`
        );
      }

      // 4. Objection handling
      {
        const tpl = phrases.objection;
        const txt = tpl[Math.floor(Math.random() * tpl.length)]
          .replace(/{{ФИО}}/g, client.fullName)
          .replace(/{{Имя}}/g, client.firstName)
          .replace(/{{Отчество}}/g, client.patronymic);
        container.insertAdjacentHTML('beforeend',
          `<div class="script-card"><p>${txt}</p></div>`
        );
      }

      // 5. Real estate pledge
      {
        const tpl = phrases.real_estate;
        const txt = tpl[Math.floor(Math.random() * tpl.length)]
          .replace(/{{ФИО}}/g, client.fullName)
          .replace(/{{Имя}}/g, client.firstName)
          .replace(/{{Отчество}}/g, client.patronymic)
          .replace(/{{ставка}}/g, rateReal)
          .replace(/{{срок}}/g, termReal);
        container.insertAdjacentHTML('beforeend',
          `<div class="script-card"><p>${txt}</p></div>`
        );
      }

    } catch (err) {
      console.error(err);
      alert('Ошибка генерации: ' + err.message);
    }
  });
})();
