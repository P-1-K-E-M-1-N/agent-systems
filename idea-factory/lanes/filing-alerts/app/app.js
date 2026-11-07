/* Filing Alerts: Michigan 8-K feed. Data: window.FILINGS_SNAPSHOT (data/latest.js) or data/latest.json. */
(function () {
  const F = window.Factory, { qs, el, fmt } = F;
  const CATS = [['all', 'All'], ['watch', '★ Watchlist'], ['deal', 'Deals'], ['money', 'Money'], ['leadership', 'Leadership'], ['earnings', 'Earnings'], ['bad', 'Trouble']];
  let data = null, cat = 'all', query = '';
  let watch = new Set(F.store.get('fa.watch', []));

  (function theme() {
    const s = F.store.get('fa.theme'); if (s) document.documentElement.dataset.theme = s;
    qs('#themebtn').addEventListener('click', () => {
      const cur = document.documentElement.dataset.theme || (matchMedia('(prefers-color-scheme:dark)').matches ? 'dark' : 'light');
      const n = cur === 'dark' ? 'light' : 'dark'; document.documentElement.dataset.theme = n; F.store.set('fa.theme', n);
    });
  })();

  /* One flat list of filings, each with a primary kind. "distress" items are shown as Trouble. */
  function flatten(d) {
    const out = [];
    d.companies.forEach((c) => c.filings.forEach((x) => {
      const cats = x.cats.map((k) => (k === 'distress' || k === 'risk') ? 'bad' : k);
      const order = ['bad', 'deal', 'leadership', 'money', 'earnings', 'governance', 'other'];
      const kind = order.find((k) => cats.includes(k)) || 'other';
      out.push({ c, x, cats, kind });
    }));
    return out.sort((a, b) => (b.x.accepted || b.x.date).localeCompare(a.x.accepted || a.x.date));
  }
  const tagKind = (item, d) => { const k = (d.items[item] || {}).cat; return (k === 'distress' || k === 'risk') ? 'bad' : k; };

  function render() {
    const rows = flatten(data);
    const q = query.toLowerCase();
    const shown = rows.filter((r) => {
      if (cat === 'watch' && !watch.has(r.c.cik)) return false;
      if (cat !== 'all' && cat !== 'watch' && !r.cats.includes(cat)) return false;
      if (!q) return true;
      return [r.c.name, r.c.city, r.c.industry, (r.c.tickers || []).join(' ')].join(' ').toLowerCase().includes(q);
    });
    qs('#count').textContent = shown.length + ' of ' + rows.length + ' filings';
    const feed = qs('#feed'); feed.replaceChildren();
    if (!shown.length) {
      feed.append(el('div', { class: 'card empty', text: cat === 'watch' ? 'Star a company to follow it here. Your list stays on this device.' : 'No filings match.' }));
      return;
    }
    let last = '';
    shown.slice(0, 200).forEach((r) => {
      if (r.x.date !== last) { last = r.x.date; feed.append(el('h3', { class: 'day', text: fmt.dateLong(last) })); }
      const c = r.c, x = r.x;
      const tags = x.items.filter((i) => i !== '9.01' && data.items[i]).map((i) => el('span', { class: 'tag ' + tagKind(i, data), text: data.items[i].label }));
      if (!tags.length) tags.push(el('span', { class: 'tag', text: 'Exhibits / other' }));
      const star = el('button', { class: 'star', type: 'button', 'aria-pressed': String(watch.has(c.cik)), text: watch.has(c.cik) ? '★ Following' : '☆ Follow',
        onclick: (e) => { watch.has(c.cik) ? watch.delete(c.cik) : watch.add(c.cik); F.store.set('fa.watch', [...watch]); render(); } });
      const tk = (c.tickers || [])[0];
      feed.append(el('article', { class: 'card fil k-' + r.kind }, [
        el('div', { class: 'top' }, [el('span', { class: 'co', text: c.name }), tk ? el('span', { class: 'tick', text: tk }) : '',
          el('span', { class: 'time', text: x.accepted ? fmt.time(x.accepted) : '' })]),
        el('div', { class: 'meta', text: [c.city, c.industry].filter(Boolean).join(' · ') }),
        el('div', { class: 'what' }, tags),
        el('div', { class: 'acts' }, [el('a', { href: x.url, target: '_blank', rel: 'noopener', text: 'Read the filing' }),
          el('span', { class: 'items', text: 'Items ' + x.items.join(', ') }), star]),
      ]));
    });
  }

  function chips() {
    const rows = flatten(data), box = qs('#chips'); box.replaceChildren();
    CATS.forEach(([k, label]) => {
      const n = k === 'all' ? rows.length : k === 'watch' ? rows.filter((r) => watch.has(r.c.cik)).length : rows.filter((r) => r.cats.includes(k)).length;
      box.append(el('button', { class: 'chip', type: 'button', 'aria-pressed': String(cat === k), onclick: () => { cat = k; chips(); render(); } },
        [label, el('small', { text: String(n) })]));
    });
  }

  function init(d) {
    data = d;
    const rows = flatten(d), bad = rows.filter((r) => r.cats.includes('bad')).length;
    const last = rows[0] ? rows[0].x.accepted : d.generated;
    qs('#sub').textContent = 'Last 8-K ' + (rows[0] ? fmt.ago(last) : '—') + ' · checked ' + fmt.ago(d.generated);
    const k = (b, s, cls) => el('div', { class: 'kpi ' + (cls || '') }, [el('b', { text: fmt.int(b) }), el('small', { text: s })]);
    qs('#kpis').replaceChildren(k(d.n_filings, 'filings in ' + d.window_days + ' days'), k(d.n_companies, 'Michigan companies filed'),
      k(rows.filter((r) => r.cats.includes('deal')).length, 'deals and agreements'), k(bad, 'trouble filings', 'bad'));
    qs('#coverage').textContent = 'Coverage: ' + d.checked + ' Michigan registrants checked so far (' + d.industries_scanned + ' of ' + d.industries_total +
      ' industry groups scanned' + (d.list_complete ? '' : '; the rest are added on each daily refresh') + '). Funds and shell companies are left out.';
    qs('#foot').innerHTML = 'Source: <a href="https://www.sec.gov/edgar" target="_blank" rel="noopener">U.S. Securities and Exchange Commission EDGAR</a>, public record. Company filings only. Refreshed ' + fmt.dateLong(d.generated.slice(0, 10)) + '.';
    chips(); render();
  }

  qs('#q').addEventListener('input', (e) => { query = e.target.value.trim(); render(); });
  F.registerSW();
  if (window.FILINGS_SNAPSHOT) init(window.FILINGS_SNAPSHOT);
  else F.loadJSON('data/latest.json').then(init).catch((e) => { qs('#feed').append(el('div', { class: 'card empty', text: 'Could not load data: ' + e.message })); });
})();
