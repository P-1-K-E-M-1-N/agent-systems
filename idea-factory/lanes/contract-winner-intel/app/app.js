/* Contract Winners: Michigan federal contract awards, newest first. Data: data/latest.json (refresh.py). */
(async function () {
  Factory.registerSW();
  const page = Factory.qs('#page');
  let D = window.__LATEST__;
  if (!D) { try { D = await Factory.loadJSON('data/latest.json'); } catch (e) {} }
  if (!D) { page.innerHTML = '<div class="empty">No data yet: run lanes/contract-winner-intel/refresh.py.</div>'; return; }
  const money = (n) => n >= 1e6 ? '$' + (n / 1e6).toFixed(1) + 'M' : n >= 1e3 ? '$' + Math.round(n / 1e3) + 'K' : '$' + Math.round(n);
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const st = { agency: '', county: '', kind: 'all', q: '' };
  const agencies = [...new Set(D.awards.map((a) => a.agency))].sort();
  const cnames = Object.entries(D.counties).sort((a, b) => a[1].name.localeCompare(b[1].name));
  page.innerHTML = `
    <div class="kpis">
      <div class="kpi"><b>${D.n}</b><small>awards, last 90 days</small></div>
      <div class="kpi"><b>${D.new}</b><small>brand-new awards</small></div>
      <div class="kpi"><b>${money(D.total)}</b><small>total on these awards</small></div>
      <div class="kpi"><b>${agencies.length}</b><small>agencies buying in Michigan</small></div>
    </div>
    <details class="honest"><summary>What this can and cannot tell you</summary>
      ${D.limits.map((l) => '<p>' + esc(l) + '</p>').join('')}</details>
    <div class="grid2">
      <section class="card"><h2>Where the money lands</h2><div id="map" role="img" aria-label="Michigan counties shaded by contract dollars"></div>
        <div class="legend" id="legend"></div></section>
      <section class="card"><h2>Top winners</h2><div class="bars" id="rbars"></div>
        <h2 style="margin-top:14px">Top agencies</h2><div class="bars" id="abars"></div></section>
    </div>
    <section class="card"><h2>Awards</h2>
      <div class="toolbar">
        <input id="q" type="search" placeholder="Search winner or what for" aria-label="Search">
        <select id="agency" aria-label="Agency"><option value="">All agencies</option>${agencies.map((a) => `<option>${esc(a)}</option>`).join('')}</select>
        <select id="county" aria-label="County"><option value="">All counties</option>${cnames.map(([f, c]) => `<option value="${f}">${esc(c.name)}</option>`).join('')}</select>
        <select id="kind" aria-label="Type"><option value="all">New and modified</option><option value="new">New only</option><option value="mod">Modified only</option></select>
      </div>
      <p class="foot" id="count"></p><div id="list" class="list" style="display:flex;flex-direction:column;gap:8px"></div>
    </section>
    <p class="foot">${esc(D.source)} Updated ${esc(D.generated.slice(0, 10))}. Window ${esc(D.window.start)} to ${esc(D.window.end)}.</p>`;

  const bars = (el, rows) => {
    const mx = Math.max(...rows.map((r) => r.amount), 1);
    el.innerHTML = rows.slice(0, 6).map((r) => `<div class="r"><span>${esc(r.name)}</span><b>${money(r.amount)}</b><i style="width:${Math.max(3, r.amount / mx * 100)}%"></i></div>`).join('');
  };
  bars(Factory.qs('#rbars'), D.recipients); bars(Factory.qs('#abars'), D.agencies);

  const list = Factory.qs('#list'), count = Factory.qs('#count');
  function render() {
    const q = st.q.toLowerCase();
    const rows = D.awards.filter((a) => (!st.agency || a.agency === st.agency) && (!st.county || a.fips === st.county) &&
      (st.kind === 'all' || a.kind === st.kind) && (!q || (a.recipient + ' ' + a.desc).toLowerCase().includes(q)))
      .sort((x, y) => y.amount - x.amount);
    count.textContent = rows.length + ' awards, biggest first' + (rows.length > 40 ? ' (showing 40)' : '');
    list.innerHTML = rows.slice(0, 40).map((a) => `<div class="aw ${a.kind}">
      <div class="top"><span class="who">${esc(a.recipient)}</span><span class="amt">${money(a.amount)}</span></div>
      <div class="meta">${esc(a.agency)}${a.sub ? ' · ' + esc(a.sub) : ''} · ${esc(a.county)} · ${a.kind === 'new' ? '<span class="tag">New</span>' : 'Modified'} · ${esc(a.start)}</div>
      <div class="d">${esc(a.desc.charAt(0) + a.desc.slice(1).toLowerCase())}</div></div>`).join('') || '<div class="empty">No awards match.</div>';
  }
  [['q', 'q', 'input'], ['agency', 'agency', 'change'], ['county', 'county', 'change'], ['kind', 'kind', 'change']].forEach(([id, k, ev]) =>
    Factory.qs('#' + id).addEventListener(ev, (e) => { st[k] = e.target.value; render(); }));
  render();

  // Map: county shading from inlined GeoJSON (no tile server needed).
  try {
    const geo = await Factory.loadJSON('data/mi_counties.json');
    const mx = Math.max(...Object.values(D.counties).map((c) => c.amount), 1);
    const shade = (v) => v ? `rgba(31,78,121,${0.15 + 0.75 * Math.sqrt(v / mx)})` : 'transparent';
    const dark = matchMedia('(prefers-color-scheme: dark)').matches || document.documentElement.dataset.theme === 'dark';
    const map = L.map('map', { zoomControl: true, attributionControl: false, scrollWheelZoom: false });
    const layer = L.geoJSON(geo, {
      style: (f) => { const c = D.counties[f.properties.GEOID]; return { color: dark ? '#4a5766' : '#8b97a6', weight: 0.8, fillColor: dark ? '#7fb2e5' : '#1f4e79', fillOpacity: c ? 0.15 + 0.75 * Math.sqrt(c.amount / mx) : 0 }; },
      onEachFeature: (f, l) => { const c = D.counties[f.properties.GEOID];
        l.bindTooltip(esc(f.properties.NAME) + (c ? ': ' + money(c.amount) + ', ' + c.n + ' awards' : ': none in window'));
        l.on('click', () => { st.county = c ? f.properties.GEOID : ''; Factory.qs('#county').value = st.county; render(); }); }
    }).addTo(map);
    map.fitBounds(layer.getBounds());
    Factory.qs('#legend').innerHTML = '<span>Less</span><i style="background:' + shade(mx * 0.05) + '"></i><i style="background:' + shade(mx * 0.4) + '"></i><i style="background:' + shade(mx) + '"></i><span>More. Tap a county to filter.</span>';
  } catch (e) { Factory.qs('#map').innerHTML = '<div class="empty">Map unavailable.</div>'; }
})();
