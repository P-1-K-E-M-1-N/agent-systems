/* Site Check: residents per existing shop by Michigan county and business type, plus a ZIP report.
   Data: data/latest.json (refresh.py; Census ACS 2023 + County Business Patterns 2022). */
(async function () {
  Factory.registerSW();
  const page = Factory.qs('#page');
  let D = window.__LATEST__;
  if (!D) { try { D = await Factory.loadJSON('data/latest.json'); } catch (e) {} }
  if (!D) { page.innerHTML = '<div class="empty">No data yet: run lanes/site-selection/refresh.py.</div>'; return; }
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const n0 = (n) => n == null ? 'n/a' : Math.round(n).toLocaleString('en-US');
  const usd = (n) => n == null ? 'n/a' : '$' + Math.round(n).toLocaleString('en-US');
  const st = { type: D.types[0].code, fips: '', zip: D.zips['48067'] ? '48067' : '' };
  const cs = D.counties;
  page.innerHTML = `
    <div class="kpis">
      <div class="kpi"><b id="k1"></b><small id="k1l"></small></div>
      <div class="kpi"><b id="k2"></b><small>shops statewide (counties with data)</small></div>
      <div class="kpi"><b id="k3"></b><small>county with most room</small></div>
      <div class="kpi"><b id="k4"></b><small>county with least room</small></div>
    </div>
    <details class="honest"><summary>What this can and cannot tell you</summary>${D.limits.map((l) => '<p>' + esc(l) + '</p>').join('')}</details>
    <section class="card"><h2>1. Pick the kind of shop</h2>
      <div class="toolbar"><select id="type" aria-label="Business type">${D.types.map((t) => `<option value="${t.code}">${esc(t.label)}</option>`).join('')}</select>
      <input id="zip" inputmode="numeric" maxlength="5" value="${D.zips['48067'] ? '48067' : ''}" placeholder="Michigan ZIP, e.g. 48067" aria-label="ZIP code"></div>
      <div id="rep" style="margin-top:12px"></div></section>
    <div class="grid2">
      <section class="card"><h2>Residents per shop, by county</h2><div id="map" role="img" aria-label="Michigan counties shaded by residents per existing shop"></div>
        <div class="legend" id="legend"></div></section>
      <section class="card"><h2>Most room (per resident)</h2><div class="bars" id="top"></div>
        <h2 style="margin-top:14px">Most crowded</h2><div class="bars" id="bot"></div>
        <p class="foot">Counties with fewer than 10,000 residents or fewer than 5 shops are left out of the rankings.</p></section>
    </div>
    <p class="foot">${esc(D.source)} Updated ${esc(D.generated.slice(0, 10))}.</p>`;
  const $ = (id) => Factory.qs('#' + id);

  const cells = () => Object.entries(cs).filter(([, c]) => c.biz[st.type]).map(([f, c]) => ({ f, c, b: c.biz[st.type] }));
  const ranked = () => cells().filter((x) => x.c.pop >= 10000 && x.b.est >= 5 && x.b.per).sort((a, b) => b.b.per - a.b.per);

  function bars(el, rows) {
    const mx = Math.max(...ranked().map((x) => x.b.per), 1);
    el.innerHTML = rows.map((x) => `<div class="r" data-f="${x.f}"><span>${esc(x.c.name)}</span><b>${n0(x.b.per)} per shop</b><i style="width:${Math.max(3, x.b.per / mx * 100)}%"></i></div>`).join('');
    el.querySelectorAll('.r').forEach((r) => r.addEventListener('click', () => { st.fips = r.dataset.f; st.zip = ''; $('zip').value = ''; report(); }));
  }

  function report() {
    const t = D.state[st.type], m = t.median_ratio;
    let fips = st.fips, z = null;
    if (st.zip && D.zips[st.zip]) { z = D.zips[st.zip]; fips = z.fips; }
    const el = $('rep');
    if (st.zip && !z) { el.innerHTML = `<div class="verdict tight">ZIP ${esc(st.zip)} is not in our Michigan list. Try a 5-digit Michigan ZIP.</div>`; return; }
    if (!fips) { el.innerHTML = '<div class="empty">Type a ZIP above, or tap a county on the map.</div>'; return; }
    const c = cs[fips], b = c.biz[st.type];
    const label = z ? 'ZIP ' + st.zip + ' (' + c.name + ' County)' : c.name + ' County';
    let h = `<h3 style="margin:0 0 8px">${esc(label)}: ${esc(t.label.toLowerCase())}</h3><div class="rep">`;
    if (z) h += `<div><b>${n0(z.pop)}</b><small>residents in this ZIP</small></div><div><b>${usd(z.income)}</b><small>median household income</small></div>
      <div><b>${z.age == null ? 'n/a' : z.age}</b><small>median age</small></div>`;
    else h += `<div><b>${n0(c.pop)}</b><small>residents</small></div><div><b>${usd(c.income)}</b><small>median household income</small></div>
      <div><b>${c.age == null ? 'n/a' : c.age}</b><small>median age</small></div>`;
    if (b) {
      h += z ? `<div><b>~${n0(z.pop / c.pop * b.est)}</b><small>shops here (estimate from county share)</small></div>` : `<div><b>${n0(b.est)}</b><small>shops in county</small></div>`;
      h += `</div>`;
      const diff = b.per / m - 1;
      const room = diff > 0.1;
      h += `<p class="verdict ${room ? '' : 'tight'}" style="margin-top:10px">${esc(c.name)} County has <b>${n0(b.per)} residents per shop</b>; a typical Michigan county has ${n0(m)}. ` +
        (room ? `That is ${Math.round(diff * 100)}% fewer shops per resident than typical, so on the numbers there may be room for ${b.gap > 0 ? 'about ' + n0(b.gap) + ' more' : 'one more'}.` :
          diff < -0.1 ? `That is ${Math.round(-diff * 100)}% more shops per resident than typical, so the county looks well served already.` : 'That is close to typical.') +
        ` Screening only: it ignores traffic, rent and chains.</p>`;
    } else h += `</div><p class="verdict tight" style="margin-top:10px">The Census Bureau hides this business count for ${esc(c.name)} County (too few shops to publish).</p>`;
    el.innerHTML = h;
  }

  let layer = null, map = null;
  function recolor() {
    const rs = cells().filter((x) => x.b.per).map((x) => x.b.per).sort((a, b) => a - b);
    const lo = rs[Math.floor(rs.length * 0.05)] || 0, hi = rs[Math.floor(rs.length * 0.95)] || 1;
    const dark = matchMedia('(prefers-color-scheme: dark)').matches || document.documentElement.dataset.theme === 'dark';
    const col = dark ? '127,203,165' : '47,107,79';
    const op = (v) => 0.12 + 0.78 * Math.min(1, Math.max(0, (v - lo) / (hi - lo || 1)));
    if (layer) layer.setStyle((f) => { const c = cs[f.properties.GEOID], b = c && c.biz[st.type];
      return { color: dark ? '#4a5a52' : '#8b9a92', weight: 0.8, fillColor: 'rgb(' + col + ')', fillOpacity: b && b.per ? op(b.per) : 0 }; });
    $('legend').innerHTML = `<span>Crowded (${n0(lo)})</span>` + [0.1, 0.4, 0.7, 1].map((p) => `<i style="background:rgba(${col},${0.12 + 0.78 * p})"></i>`).join('') + `<span>Room (${n0(hi)}+ residents per shop). Blank = hidden by Census. Tap a county.</span>`;
  }

  function refresh() {
    const t = D.state[st.type], all = cells(), r = ranked();
    $('k1').textContent = n0(t.median_ratio); $('k1l').textContent = 'residents per shop, typical county';
    $('k2').textContent = n0(all.reduce((s, x) => s + x.b.est, 0));
    $('k3').textContent = r.length ? r[0].c.name : 'n/a'; $('k4').textContent = r.length ? r[r.length - 1].c.name : 'n/a';
    bars($('top'), r.slice(0, 5)); bars($('bot'), r.slice(-5).reverse());
    recolor(); report();
  }
  $('type').addEventListener('change', (e) => { st.type = e.target.value; refresh(); });
  $('zip').addEventListener('input', (e) => { st.zip = e.target.value.replace(/\D/g, '').slice(0, 5); if (st.zip.length === 5) { report(); } else if (!st.zip) { report(); } });

  try {
    const geo = await Factory.loadJSON('data/mi_counties.json');
    map = L.map('map', { zoomControl: true, attributionControl: false, scrollWheelZoom: false });
    layer = L.geoJSON(geo, { style: { weight: 0.8, fillOpacity: 0 },
      onEachFeature: (f, l) => { const c = cs[f.properties.GEOID];
        l.bindTooltip(() => { const b = c && c.biz[st.type]; return esc(f.properties.NAME) + (b && b.per ? ': ' + n0(b.per) + ' residents per shop (' + b.est + ' shops)' : ': hidden by Census'); });
        l.on('click', () => { st.fips = f.properties.GEOID; st.zip = ''; $('zip').value = ''; report(); }); } }).addTo(map);
    map.fitBounds(layer.getBounds());
  } catch (e) { $('map').innerHTML = '<div class="empty">Map unavailable.</div>'; }
  refresh();
})();
