(async () => {
  const BASE = 'https://raw.githubusercontent.com/Wooinpoorin/sovcombank-scripts/main/data/';

  async function loadJSON(filename) {
    const res = await fetch(BASE + filename);
    if (!res.ok) throw new Error(`${filename} загрузка: ${res.status}`);
    return res.json();
  }

  // Человеко-понятные названия для ключей из products.json
  const NAME_MAP = {
    online_cash_loan: 'Кредит наличными онлайн',
    car_pledge_loan:  'Кредит под залог авто',
    pod_zalog:        'Кредит под залог недвижимости'
  };

  document.getElementById('generate').addEventListener('click', async () => {
    try {
      const container = document.getElementById('scriptsContainer');
      container.innerHTML = '';

      // Вместо выборки по клиенту — просто выводим все продукты из JSON
      const products = await loadJSON('products.json');
      for (const [key, prod] of Object.entries(products)) {
        const name = NAME_MAP[key] || key;
        const rate = prod.Ставка != null ? `от ${prod.Ставка}%` : '';
        const term = prod.Срок != null ? `${prod.Срок} мес.` : '';
        container.insertAdjacentHTML('beforeend',
          `<div class="script">
             <strong>${name}:</strong>
             <p>Ставка ${rate}, срок ${term}</p>
           </div>`
        );
      }

      if (!Object.keys(products).length) {
        container.innerHTML = '<p>Нет доступных тарифов</p>';
      }
    } catch (e) {
      console.error(e);
      alert('Ошибка при загрузке тарифов: ' + e.message);
    }
  });
})();
