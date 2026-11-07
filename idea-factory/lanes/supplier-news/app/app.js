/* Supplier News Monitor. Data: window.SUPPLIER_SNAPSHOT (data/latest.js) or data/latest.json. Watchlist and hidden rows live in localStorage only. */
(function () {
  const F = window.Factory; const { qs, el, fmt } = F;
  const COLOR = { 'Closure / layoffs': '--t-clo', Bankruptcy: '--t-ban', Disruption: '--t-dis', Labor: '--t-lab', Deal: '--t-dea', Growth: '--t-gro', Mention: '--t-men' };
  let data = null, type = 'All', query = '', miOnly = false, mineOnly = false;
  let watch = new Set(F.store.get('sn.watch', [])), hidden = new Set(F.store.get('sn.hidden', []));
  const saveW = () => F.store.set('sn.watch', [...watch]);
  const saveH = () => F.store.set('sn.hidden', [...hidden]);

  (function theme() {
    const s = F.store.get('sn.theme'); if (s) document.documentElement.dataset.theme = s;
    qs('#themebtn').addEventListener('click', () => {
      const cur = document.documentElement.dataset.theme || (matchMedia('(prefers-color-scheme:dark)').matches ? 'dark' : 'light');
      const n = cur === 'dark' ? 'light' : 'dark'; document.documentElement.dataset.theme = n; F.store.set('sn.theme', n);
    });
  })();

  function visible() {
    const q = query.toLowerCase();
    return data.items.filter((i) => !hidden.has(i.url) && (type === 'All' || i.type === type) && (!miOnly || i.michigan) &&
      (!mineOnly || watch.has(i.company)) && (!q || (i.title + ' ' + i.company + ' ' + i.domain).toLowerCase().includes(q)));
  }
  function render() {
    const vis = visible();
    qs('#count').textContent = vis.length + ' of ' + data.items.length + ' headlines';
    const feed = qs('#feed'); feed.replaceChildren();
    if (!vis.length) feed.append(el('div', { class: 'empty', text: 'Nothing matches. Clear a filter or the search.' }));
    vis.slice(0, 80).forEach((i) => {
      const c = `var(${COLOR[i.type] || '--t-men'})`;
      const star = el('button', { class: 'btn small', 'aria-label': 'Hide', text: '✕', onclick: () => { hidden.add(i.url); saveH(); render(); } });
      star.classList.add('x');
      feed.append(el('article', { class: 'card item', style: 'border-left-color:' + c }, [
        el('a', { class: 't', href: i.url, target: '_blank', rel: 'noopener noreferrer', text: i.title }),
        el('div', { class: 'meta' }, [
          el('span', { class: 'tag', style: 'background:' + c, text: i.type }),
          i.company ? el('span', { class: 'comp', text: i.company }) : '',
          i.michigan ? el('span', { class: 'pill', text: 'Michigan' }) : '',
          el('span', { text: i.domain + ' · ' + (i.seen ? fmt.date(i.seen) : '') }), star])]));
    });
  }
  function chips() {
    const box = qs('#types'); box.replaceChildren();
    [['All', data.items.length]].concat(Object.entries(data.types).sort((a, b) => b[1] - a[1])).forEach(([k, n]) => {
      box.append(el('button', { 'aria-pressed': String(k === type), html: k + '<b>' + n + '</b>', onclick: () => { type = k; chips(); render(); } }));
    });
  }
  function wl() {
    const box = qs('#wl'); box.replaceChildren();
    const hit = {}; data.items.forEach((i) => { if (i.company) hit[i.company] = (hit[i.company] || 0) + 1; });
    data.watchlist.slice().sort((a, b) => (hit[b] || 0) - (hit[a] || 0)).forEach((n) => {
      const l = el('label', { class: watch.has(n) ? 'on' : '' }, [el('input', { type: 'checkbox' }), n + (hit[n] ? ' (' + hit[n] + ')' : '')]);
      l.firstChild.checked = watch.has(n);
      l.firstChild.addEventListener('change', () => { l.firstChild.checked ? watch.add(n) : watch.delete(n); saveW(); wl(); render(); });
      box.append(l);
    });
    qs('#wlcount').textContent = watch.size + ' followed';
  }
  function boot(d) {
    data = d;
    qs('#sub').textContent = 'Michigan auto-supplier headlines, ' + d.window + '. Updated ' + fmt.ago(d.generated) + '.';
    const t = d.types;
    qs('#kpis').replaceChildren(...[['Headlines', d.items.length], ['Closures / layoffs', t['Closure / layoffs'] || 0], ['Bankruptcy', t.Bankruptcy || 0],
      ['Watchlist hits', d.items.filter((i) => i.company).length]].map(([l, n]) => el('div', { class: 'kpi' }, [el('b', { text: fmt.int(n) }), el('span', { text: l })])));
    qs('#src').textContent = d.source + '. ' + d.n_raw + ' articles scanned, ' + d.items.length + ' kept.';
    chips(); wl(); render();
  }
  qs('#q').addEventListener('input', (e) => { query = e.target.value; render(); });
  [['#mi', () => (miOnly = !miOnly)], ['#mine', () => (mineOnly = !mineOnly)]].forEach(([s, fn]) => {
    qs(s).addEventListener('click', (e) => { const v = fn(); e.currentTarget.setAttribute('aria-pressed', String(v)); render(); });
  });
  if (window.SUPPLIER_SNAPSHOT) boot(window.SUPPLIER_SNAPSHOT);
  else F.loadJSON('data/latest.json').then(boot).catch(() => { qs('#feed').append(el('div', { class: 'empty', text: 'Data not available yet.' })); });
})();
