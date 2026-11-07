/* Job-Day Alerts: forecast go/no-go for Michigan trades. Data: data/forecast.json (NWS hourly, 8 cities),
   data/warnings.json (active NWS alerts), mi_state/mi_counties (Census boundaries). No build step. */
(function () {
  'use strict';
  const F = window.Factory, $ = F.qs, KEY = 'job-day:';
  /* Window = local hours checked. Each rule returns a reason string when it trips at "stop" or "maybe". */
  const TRADES = {
    roofing: { label: 'Roofing', from: 7, to: 17,
      rules: 'Working window 7am to 5pm. Hold the crew if rain chance reaches 40%, wind reaches 25 mph, or it is 34 F or colder. Risky at 20% rain, 15 mph wind or 40 F or colder.',
      check: (h) => [h.pop >= 40 ? ['stop', 'rain ' + h.pop + '%'] : h.pop >= 20 ? ['maybe', 'rain ' + h.pop + '%'] : null,
        h.wind >= 25 ? ['stop', 'wind ' + h.wind + ' mph'] : h.wind >= 15 ? ['maybe', 'wind ' + h.wind + ' mph'] : null,
        h.temp <= 34 ? ['stop', h.temp + ' F'] : h.temp <= 40 ? ['maybe', h.temp + ' F'] : null] },
    landscaping: { label: 'Landscaping', from: 7, to: 17,
      rules: 'Working window 7am to 5pm. Hold the crew at 50% rain chance, 30 mph wind, or 28 F or colder (frozen ground). Risky at 25% rain, 20 mph wind or 34 F or colder (frost on planting).',
      check: (h) => [h.pop >= 50 ? ['stop', 'rain ' + h.pop + '%'] : h.pop >= 25 ? ['maybe', 'rain ' + h.pop + '%'] : null,
        h.wind >= 30 ? ['stop', 'wind ' + h.wind + ' mph'] : h.wind >= 20 ? ['maybe', 'wind ' + h.wind + ' mph'] : null,
        h.temp <= 28 ? ['stop', 'freezing ' + h.temp + ' F'] : h.temp <= 34 ? ['maybe', 'frost risk ' + h.temp + ' F'] : null] },
    events: { label: 'Outdoor events', from: 10, to: 22,
      rules: 'Window 10am to 10pm. Move indoors at 50% rain chance, 30 mph wind, 40 F or colder, or 95 F or hotter. Risky at 25% rain, 20 mph wind, 50 F or colder or 88 F or hotter.',
      check: (h) => [h.pop >= 50 ? ['stop', 'rain ' + h.pop + '%'] : h.pop >= 25 ? ['maybe', 'rain ' + h.pop + '%'] : null,
        h.wind >= 30 ? ['stop', 'wind ' + h.wind + ' mph'] : h.wind >= 20 ? ['maybe', 'wind ' + h.wind + ' mph'] : null,
        h.temp <= 40 || h.temp >= 95 ? ['stop', h.temp + ' F'] : h.temp <= 50 || h.temp >= 88 ? ['maybe', h.temp + ' F'] : null] },
  };
  const S = { fc: null, warn: null, geo: {}, trade: F.store.get(KEY + 'trade', 'roofing'), day: 0, dates: [], sel: null };
  const M = { map: null, dots: {} };
  const css = (n) => F.cssVar(n) || '#888';
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const RANK = { go: 0, maybe: 1, stop: 2 };

  /* Verdict for one city on one date: worst level over the working window, with the first reasons that caused it. */
  function verdict(city, date, tr) {
    const hrs = city.hours.filter((h) => h.t.slice(0, 10) === date && +h.t.slice(11, 13) >= tr.from && +h.t.slice(11, 13) < tr.to);
    if (!hrs.length) return { level: null, reasons: [], hours: [] };
    let level = 'go'; const reasons = new Set(); const per = [];
    hrs.forEach((h) => {
      let lv = 'go';
      tr.check(h).forEach((r) => { if (r) { if (RANK[r[0]] > RANK[lv]) lv = r[0]; if (r[0] === 'stop' || (!reasons.size && r[0] === 'maybe')) reasons.add(r[1]); } });
      per.push(lv); if (RANK[lv] > RANK[level]) level = lv;
    });
    const stopHrs = per.filter((l) => l === 'stop').length;
    return { level, reasons: [...reasons].slice(0, 3), hours: per, stopHrs, n: hrs.length,
      hi: Math.max(...hrs.map((h) => h.temp)), lo: Math.min(...hrs.map((h) => h.temp)), pop: Math.max(...hrs.map((h) => h.pop)), wind: Math.max(...hrs.map((h) => h.wind)) };
  }
  function dayLevel(date, tr) {
    const vs = S.fc.cities.map((c) => verdict(c, date, tr)).filter((v) => v.level);
    if (!vs.length) return null;
    const bad = vs.filter((v) => v.level === 'stop').length, mb = vs.filter((v) => v.level === 'maybe').length;
    return bad * 2 >= vs.length ? 'stop' : (bad + mb) * 2 >= vs.length ? 'maybe' : 'go';
  }
  const LABEL = { go: 'Good to work', maybe: 'Risky', stop: 'Hold the crew' };

  function renderTabs() {
    const box = $('#tabs'); box.textContent = '';
    Object.keys(TRADES).forEach((k) => box.append(F.el('button', { class: 'btn small', type: 'button', 'aria-pressed': String(k === S.trade), text: TRADES[k].label,
      onclick: () => { S.trade = k; F.store.set(KEY + 'trade', k); render(); } })));
  }
  function renderDays() {
    const box = $('#days'); box.textContent = '';
    const tr = TRADES[S.trade];
    S.dates.forEach((d, i) => {
      const lv = dayLevel(d, tr);
      const dt = new Date(d + 'T12:00:00');
      box.append(F.el('button', { type: 'button', 'aria-pressed': String(i === S.day), 'aria-label': F.fmt.date(d) + ': ' + (lv ? LABEL[lv] : 'no data'),
        onclick: () => { S.day = i; render(); } },
        [F.el('span', { text: dt.toLocaleDateString('en-US', { weekday: 'short' }) }), F.el('span', { class: 'num', text: String(dt.getDate()) }), F.el('i', { class: lv || '', style: lv ? '' : 'background:var(--line)' })]));
    });
  }
  function renderPanel() {
    const tr = TRADES[S.trade], date = S.dates[S.day];
    $('#when').textContent = F.fmt.dateLong(date);
    $('#whensub').textContent = tr.label + ', ' + tr.from % 12 + (tr.from < 12 ? 'am' : 'pm') + ' to ' + ((tr.to % 12) || 12) + (tr.to < 12 ? 'am' : 'pm') + ' local time';
    $('#rules').textContent = tr.rules;
    const rows = S.fc.cities.map((c) => ({ c, v: verdict(c, date, tr) })).filter((r) => r.v.level)
      .sort((a, b) => RANK[a.v.level] - RANK[b.v.level] || a.c.name.localeCompare(b.c.name));
    const cnt = { go: 0, maybe: 0, stop: 0 }; rows.forEach((r) => cnt[r.v.level]++);
    const sum = !rows.length ? 'No forecast hours for this day yet.' :
      cnt.stop === rows.length ? 'Hold crews statewide: every city trips the ' + tr.label.toLowerCase() + ' limits.' :
      cnt.go === rows.length ? 'Clear to schedule in all ' + rows.length + ' cities.' :
      cnt.go + ' of ' + rows.length + ' cities look good to work' + (cnt.stop ? ', ' + cnt.stop + ' should hold' : '') + (cnt.maybe ? ', ' + cnt.maybe + ' are risky' : '') + '. Best: ' + rows.filter((r) => r.v.level === 'go').slice(0, 3).map((r) => r.c.name).join(', ') + (cnt.go ? '' : 'none') + '.';
    $('#summary').textContent = sum;
    const ul = $('#cities'); ul.textContent = '';
    rows.forEach(({ c, v }) => {
      const li = F.el('li', { tabindex: 0, role: 'button', 'aria-label': c.name + ': ' + LABEL[v.level], class: S.sel === c.name ? 'active' : '', onclick: () => select(c.name) }, [
        F.el('span', { class: 'dot ' + v.level }),
        F.el('div', {}, [F.el('b', { text: c.name }), F.el('span', { class: 'r', text: v.level === 'go' ? 'Max rain ' + v.pop + '%, wind ' + v.wind + ' mph, ' + v.lo + '-' + v.hi + ' F' : v.reasons.join(', ') + (v.stopHrs ? ' (' + v.stopHrs + ' of ' + v.n + ' hours over limit)' : '') })]),
        F.el('span', { class: 'pill ' + (v.level === 'go' ? 'good' : v.level === 'maybe' ? 'warn' : 'bad'), text: LABEL[v.level] })]);
      li.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); select(c.name); } });
      ul.append(li);
    });
  }
  function popup(c) {
    const tr = TRADES[S.trade], v = verdict(c, S.dates[S.day], tr);
    const bar = v.hours.map((l) => '<i class="' + l + '"></i>').join('');
    return '<b>' + esc(c.name) + '</b> <small>(' + esc(c.county) + ' Co.)</small><br>' + (v.level ? LABEL[v.level] + (v.reasons.length ? ': ' + esc(v.reasons.join(', ')) : '') +
      '<div class="hrs" style="grid-template-columns:repeat(' + v.hours.length + ',1fr)">' + bar + '</div><small>One block per hour in the window</small>' : 'No data');
  }
  function select(name) { S.sel = name; renderPanel(); const m = M.dots[name]; if (m) { m.openPopup(); } }
  function renderMap() {
    const tr = TRADES[S.trade], date = S.dates[S.day];
    S.fc.cities.forEach((c) => {
      const v = verdict(c, date, tr), m = M.dots[c.name];
      m.setStyle({ fillColor: v.level ? css('--' + v.level) : css('--mute'), color: css('--card'), fillOpacity: .95, weight: 2.5 });
      m.setPopupContent(popup(c));
    });
  }
  function initMap() {
    if (!window.L) { $('#map').innerHTML = '<div class="empty">Map library did not load. The city list still works.</div>'; return; }
    const map = M.map = L.map('map', { zoomControl: true, attributionControl: true }).setView([44.2, -84.8], window.innerWidth < 700 ? 5.6 : 6.2);
    map.attributionControl.setPrefix(false); map.attributionControl.addAttribution('Boundaries: US Census TIGERweb. Weather: National Weather Service');
    L.geoJSON(S.geo.state, { style: () => ({ color: css('--map-line'), weight: 1.2, fillColor: css('--map-land'), fillOpacity: 1, interactive: false }) }).addTo(map);
    L.geoJSON(S.geo.counties, { style: () => ({ color: css('--map-line'), weight: .5, fillOpacity: 0, interactive: false }) }).addTo(map);
    S.fc.cities.forEach((c) => {
      const m = L.circleMarker([c.lat, c.lon], { radius: 13 }).addTo(map).bindTooltip(c.name).bindPopup('');
      m.on('click', () => { S.sel = c.name; renderPanel(); });
      M.dots[c.name] = m;
    });
  }
  function renderWarn() {
    const W = S.warn, ul = $('#w-list'); ul.textContent = '';
    $('#w-stamp').textContent = W && W.as_of ? 'as of ' + F.fmt.time(W.as_of) : '';
    if (!W || W.error || !W.warnings.length) { ul.append(F.el('li', { class: 'mute', text: W && W.error ? 'Alerts unavailable at refresh.' : 'No weather alerts that affect outdoor work are active in Michigan.' })); return; }
    W.warnings.slice(0, 12).forEach((w) => ul.append(F.el('li', {}, [F.el('div', {}, [F.el('b', { text: w.event }), F.el('div', { class: 'rules', text: (w.areaDesc || '').slice(0, 140) + (w.expires ? ' - until ' + F.fmt.time(w.expires) : '') })])])));
  }
  function render() { renderTabs(); renderDays(); renderPanel(); if (M.map) renderMap(); }
  function applyTheme(t) {
    if (t === 'light' || t === 'dark') document.documentElement.setAttribute('data-theme', t); else document.documentElement.removeAttribute('data-theme');
    const b = $('#themebtn'); b.title = 'Theme: ' + t; b.setAttribute('aria-label', 'Switch theme, now ' + t);
  }
  async function init() {
    F.registerSW();
    applyTheme(F.store.get(KEY + 'theme', 'auto'));
    $('#themebtn').onclick = () => { const c = F.store.get(KEY + 'theme', 'auto'), n = c === 'auto' ? 'light' : c === 'light' ? 'dark' : 'auto'; F.store.set(KEY + 'theme', n); applyTheme(n); render(); };
    try {
      const [fc, st, co] = await Promise.all([F.loadJSON('data/forecast.json'), F.loadJSON('data/mi_state.json'), F.loadJSON('data/mi_counties.json')]);
      S.fc = fc; S.geo = { state: st, counties: co };
    } catch (e) { $('#panel').innerHTML = '<div class="empty">No forecast yet. The daily refresh writes data/forecast.json.</div>'; return; }
    try { S.warn = await F.loadJSON('data/warnings.json'); } catch (e) { S.warn = null; }
    const first = S.fc.cities[0].hours;
    S.dates = [...new Set(first.map((h) => h.t.slice(0, 10)))].filter((d) => first.filter((h) => h.t.slice(0, 10) === d).length >= 12).slice(0, 7);
    const today = first[0].t.slice(0, 10); if (!S.dates.includes(today)) S.dates.unshift(today);
    S.dates = S.dates.slice(0, 7);
    $('#stamp').textContent = 'Forecast ' + F.fmt.ago(S.fc.as_of);
    $('#asof').textContent = 'Data refreshed ' + new Date(S.fc.as_of).toLocaleString('en-US') + '.';
    initMap(); renderWarn(); render();
    if (M.map) setTimeout(() => M.map.invalidateSize(), 200);
  }
  init();
})();
