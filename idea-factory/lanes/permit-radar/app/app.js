/* Permit Radar: last week's Detroit permits for your trade.
   Data files written by lanes/permit-radar/refresh.py:
     data/latest.json         permits issued in the last 7 days (point coordinates from the city's layers)
     data/weeks.json          8 weekly buckets of counts per trade tag and per tag combination
     data/detroit_zctas.json  482xx ZIP polygons (Census ZCTAs) with centroids
     data/wayne_county.json   Wayne County outline
   Basemap is the GeoJSON above, styled from the --map-* tokens, so the page renders with no outside host.
   OpenStreetMap street tiles are optional and only offered after Factory.canLoadImage() succeeds. */
(function () {
  const F = window.Factory;
  const $ = F.qs;

  const CHIPS = ['roofing', 'electrical', 'hvac', 'plumbing', 'demolition', 'demolition_dumpster'];
  const ORDER = CHIPS.concat(['general']);
  const LABEL = { roofing: 'Roofing', electrical: 'Electrical', hvac: 'HVAC', plumbing: 'Plumbing',
    demolition: 'Demolition', demolition_dumpster: 'Dumpster', general: 'General building', all: 'All trades' };
  const HINT = { roofing: 'Roof replacements, roof-mounted solar', electrical: 'Electrical permits, service upgrades',
    hvac: 'Furnace, A/C, boiler, duct', plumbing: 'Plumbing, water heaters, sewers (utility work removed)',
    demolition: 'Wrecking and demolition permits', demolition_dumpster: 'Demolition plus gut jobs, rehabs, additions and new builds',
    general: 'Building permits with no trade keyword', all: 'Every permit issued last week' };
  const OSM_TILE = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
  const OSM_SAMPLE = 'https://tile.openstreetmap.org/12/1101/1522.png';
  const PAGE = 60;

  const state = {
    sel: normalise(F.store.get('pr.trades', ['all'])),
    q: '',
    showAll: false,
    streets: F.store.get('pr.streets', false),
    active: null,
  };
  let data = null, weeks = null, zctas = null, county = null;
  let map, zctaLayer, countyLayer, pinLayer, tileLayer, legend;
  const markers = new Map();   // permit id -> circleMarker

  function normalise(sel) {
    if (!Array.isArray(sel) || !sel.length) return ['all'];
    const ok = sel.filter((s) => s === 'all' || CHIPS.includes(s));
    return !ok.length || ok.includes('all') ? ['all'] : ok;
  }
  const isAll = () => state.sel.includes('all');
  const matches = (p) => isAll() || p.trades.some((t) => state.sel.includes(t));
  const col = (t) => F.cssVar('--t-' + t) || '#888';
  function primary(p) {
    const pool = isAll() ? ORDER : state.sel;
    for (const t of pool) if (p.trades.includes(t)) return t;
    return p.trades[0] || 'general';
  }
  function selLabel(n) {
    if (isAll()) return n === 1 ? 'permit' : 'permits';
    const names = state.sel.map((s) => LABEL[s]);
    const joined = names.length > 1 ? names.slice(0, -1).join(', ') + ' and ' + names[names.length - 1] : names[0];
    return joined + (n === 1 ? ' permit' : ' permits');
  }
  function weekCount(w) {
    if (isAll()) return w.total;
    let n = 0;
    for (const combo in w.combos) {
      const tags = combo.split('|');
      if (tags.some((t) => state.sel.includes(t))) n += w.combos[combo];
    }
    return n;
  }
  function searchHit(p) {
    const q = state.q.trim().toLowerCase();
    if (!q) return true;
    return [p.address, p.contractor, p.zip, p.neighborhood, p.permit_type, p.work_summary].join(' ').toLowerCase().includes(q);
  }
  const shortAddr = (a) => (a || '').replace(/\s+/g, ' ').trim();

  /* ---------- boot ---------- */
  async function boot() {
    F.registerSW();
    try {
      [data, weeks, zctas, county] = await Promise.all([
        F.loadJSON('data/latest.json'), F.loadJSON('data/weeks.json'),
        F.loadJSON('data/detroit_zctas.json'), F.loadJSON('data/wayne_county.json')]);
    } catch (e) {
      $('#panel').innerHTML = '<div class="empty">No data yet. Run <code>python lanes/permit-radar/refresh.py</code> so it writes app/data/latest.json.</div>';
      return;
    }
    data.permits.forEach((p, i) => { p._i = i; });
    buildChips();
    buildMap();
    wire();
    render();
    offerStreets();
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    if (mq.addEventListener) mq.addEventListener('change', () => { restyleMap(); render(); });
  }

  /* ---------- trade chips ---------- */
  function buildChips() {
    const nav = $('#trades');
    nav.replaceChildren();
    const counts = {};
    data.permits.forEach((p) => p.trades.forEach((t) => { counts[t] = (counts[t] || 0) + 1; }));
    const mk = (key, color) => {
      const b = F.el('button', { class: 'chip', type: 'button', 'data-key': key, title: HINT[key],
        'aria-pressed': 'false', style: color ? '--c:' + color : '' }, [
        F.el('span', { class: 'dot' }),
        F.el('span', { text: LABEL[key] }),
        F.el('span', { class: 'n num', text: F.fmt.int(key === 'all' ? data.permits.length : counts[key] || 0) })]);
      b.addEventListener('click', () => toggle(key));
      return b;
    };
    nav.append(mk('all', null));
    CHIPS.forEach((k) => nav.append(mk(k, col(k))));
  }
  function toggle(key) {
    if (key === 'all') state.sel = ['all'];
    else {
      const cur = isAll() ? [] : state.sel.slice();
      const i = cur.indexOf(key);
      if (i >= 0) cur.splice(i, 1); else cur.push(key);
      state.sel = normalise(cur);
    }
    F.store.set('pr.trades', state.sel);
    state.showAll = false;
    render();
  }

  /* ---------- map ---------- */
  function buildMap() {
    map = L.map('map', { zoomControl: true, preferCanvas: true, attributionControl: true, zoomSnap: 0.5 });
    map.attributionControl.setPrefix('');
    map.attributionControl.addAttribution('Permits: City of Detroit Open Data · Boundaries: US Census');
    countyLayer = L.geoJSON(county, { style: countyStyle, interactive: false }).addTo(map);
    zctaLayer = L.geoJSON(zctas, {
      style: () => zctaStyle(0, 1),
      onEachFeature: (ft, layer) => {
        layer.on('click', () => { $('#q').value = ft.properties.ZCTA5; state.q = ft.properties.ZCTA5; state.showAll = false; render(); });
      },
    }).addTo(map);
    pinLayer = L.layerGroup().addTo(map);
    legend = L.control({ position: 'bottomleft' });
    legend.onAdd = () => { const d = L.DomUtil.create('div', 'legend-ctl'); L.DomEvent.disableClickPropagation(d); return d; };
    legend.addTo(map);
    map.fitBounds(zctaLayer.getBounds(), { padding: [6, 6] });
    map.setMaxBounds(zctaLayer.getBounds().pad(0.6));
  }
  function countyStyle() {
    return { color: F.cssVar('--map-line'), weight: 1.2, dashArray: '4 4', fillColor: F.cssVar('--map-land'), fillOpacity: 0.6 };
  }
  function zctaStyle(t, maxN) {
    const base = F.cssVar('--map-land');
    const hue = isAll() ? F.cssVar('--acc') : col(state.sel[0]);
    const fill = maxN ? F.ramp(Math.pow(t, 0.7) * 0.85, base, hue) : base;
    return { color: F.cssVar('--map-line'), weight: 1, fillColor: fill, fillOpacity: tileLayer ? 0.45 : 0.9 };
  }
  function restyleMap() {
    countyLayer.setStyle(countyStyle());
  }
  function paintZctas(weekSet) {
    const byZip = {};
    const hoods = {};
    weekSet.forEach((p) => {
      if (!p.zip) return;
      byZip[p.zip] = (byZip[p.zip] || 0) + 1;
      if (p.neighborhood) { hoods[p.zip] = hoods[p.zip] || {}; hoods[p.zip][p.neighborhood] = (hoods[p.zip][p.neighborhood] || 0) + 1; }
    });
    const maxN = Math.max(0, ...Object.values(byZip));
    zctaLayer.eachLayer((layer) => {
      const z = layer.feature.properties.ZCTA5;
      const n = byZip[z] || 0;
      layer.setStyle(zctaStyle(maxN ? n / maxN : 0, maxN));
      const top = Object.entries(hoods[z] || {}).sort((a, b) => b[1] - a[1]).slice(0, 3).map((e) => e[0]).join(', ');
      layer.unbindTooltip();
      layer.bindTooltip('<b>' + z + '</b> · ' + n + (n === 1 ? ' permit' : ' permits') + (top ? '<br><span class="mute">' + esc(top) + '</span>' : ''),
        { sticky: true, className: 'zip', direction: 'top', opacity: 0.97 });
    });
    return { byZip, maxN };
  }
  function paintPins(listSet) {
    pinLayer.clearLayers();
    markers.clear();
    const sorted = listSet.slice().sort((a, b) => (a.est_cost || 0) - (b.est_cost || 0)); // big jobs drawn last, on top
    sorted.forEach((p) => {
      if (p.lat == null || p.lon == null) return;
      const t = primary(p);
      const big = (p.est_cost || 0) >= 100000;
      const m = L.circleMarker([p.lat, p.lon], {
        radius: big ? 8 : 5.5, color: '#fff', weight: 1.2, fillColor: col(t), fillOpacity: 0.92,
      });
      m.bindPopup(() => popupHTML(p), { maxWidth: 300, autoPanPadding: [20, 20] });
      m.on('click', () => setActive(p, false));
      m.addTo(pinLayer);
      markers.set(p.id, m);
    });
  }
  function popupHTML(p) {
    const tags = p.trades.map((t) => '<span class="tag" style="--c:' + col(t) + '">' + LABEL[t] + '</span>').join('');
    const row = (k, v) => v ? '<dt>' + k + '</dt><dd>' + esc(v) + '</dd>' : '';
    return '<div class="pop"><h4>' + esc(shortAddr(p.address)) + '</h4>' +
      '<div class="mute" style="font-size:12px">' + esc([p.zip, p.neighborhood].filter(Boolean).join(' · ')) + '</div>' +
      '<div class="tags">' + tags + '</div><dl>' +
      row('Permit', p.permit_type) + row('Issued', F.fmt.date(p.issued)) +
      row('Est. cost', p.est_cost ? F.fmt.money(p.est_cost) : '') +
      row('Contractor', p.contractor || (p.source === 'Building' ? 'not listed for building permits' : '')) +
      row('Source', (data.sources[p.source] || p.source) + (p.id ? ' · ' + p.id : '')) +
      row('Location', p.geo === 'zip' ? 'ZIP centroid (no point published)' : '') +
      '</dl>' + (p.work_summary ? '<p class="work">' + esc(p.work_summary) + '</p>' : '') +
      (p.record_url ? '<div class="links"><a href="' + p.record_url + '" target="_blank" rel="noopener">City record ↗</a></div>' : '') +
      '</div>';
  }
  function paintLegend(maxN) {
    const d = legend.getContainer();
    const prev = d.querySelector('details');
    const open = prev ? prev.open : window.innerWidth > 860;
    const trades = isAll() ? ORDER : state.sel;
    const base = F.cssVar('--map-land');
    const hue = isAll() ? F.cssVar('--acc') : col(state.sel[0]);
    d.innerHTML = '<details' + (open ? ' open' : '') + '><summary>Legend</summary>' +
      trades.map((t) => '<div class="item"><span class="dot" style="background:' + col(t) + '"></span>' + LABEL[t] + '</div>').join('') +
      '<div class="ramp" style="background:linear-gradient(90deg,' + base + ',' + F.ramp(0.85, base, hue) + ')"></div>' +
      '<div class="ends"><span>0</span><span>ZIP permits</span><span>' + maxN + '</span></div></details>';
  }
  function setActive(p, fly) {
    state.active = p ? p.id : null;
    F.qsa('#list li').forEach((li) => li.classList.toggle('active', li.dataset.id === state.active));
    if (!p) return;
    const m = markers.get(p.id);
    if (m && fly) {
      map.flyTo(m.getLatLng(), Math.max(map.getZoom(), 14), { duration: 0.6 });
      m.openPopup();
      if (window.innerWidth <= 860) $('#map').scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }

  /* Optional street tiles: only offered when the host is reachable (the review sandbox blocks it). */
  async function offerStreets() {
    const tools = $('#maptools');
    const ok = await F.canLoadImage(OSM_SAMPLE, 3500);
    if (!ok) {
      tools.append(F.el('div', { class: 'note', text: 'Street tiles are off here (outside host blocked). The map is drawn from the app’s own ZIP boundaries.' }));
      return;
    }
    const btn = F.el('button', { class: 'btn small', type: 'button', 'aria-pressed': String(!!state.streets), text: 'Streets' });
    btn.addEventListener('click', () => { state.streets = !state.streets; F.store.set('pr.streets', state.streets); applyStreets(btn); });
    tools.append(btn);
    applyStreets(btn);
  }
  function applyStreets(btn) {
    btn.setAttribute('aria-pressed', String(!!state.streets));
    if (state.streets && !tileLayer) {
      tileLayer = L.tileLayer(OSM_TILE, { maxZoom: 19, opacity: 0.9, attribution: '© OpenStreetMap contributors' }).addTo(map);
      tileLayer.bringToBack();
      countyLayer.setStyle({ fillOpacity: 0 });
    } else if (!state.streets && tileLayer) {
      map.removeLayer(tileLayer); tileLayer = null;
      countyLayer.setStyle(countyStyle());
    }
    render();
  }

  /* ---------- panel ---------- */
  function render() {
    const weekSet = data.permits.filter(matches);
    const listSet = weekSet.filter(searchHit);
    F.qsa('#trades .chip').forEach((b) => b.setAttribute('aria-pressed', String(state.sel.includes(b.dataset.key))));

    const wk = data.week;
    $('#weekpill').textContent = wk.label;
    $('#weekTitle').textContent = 'Permits issued ' + wk.label;
    $('#refreshed').textContent = 'Refreshed ' + F.fmt.ago(data.generated_at) + ' (' + F.fmt.date(data.generated_at) + ')';
    $('#geonote').textContent = data.geometry_note ? '· ' + data.geometry_note : '';
    $('#footData').textContent = 'Data: City of Detroit Open Data Portal (BSEED building, trades and demolition permits), refreshed ' +
      new Date(data.generated_at).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }) + '.';

    // numbers
    const zips = {};
    let value = 0, biggest = null, withCost = 0;
    const contractors = {};
    weekSet.forEach((p) => {
      if (p.zip) zips[p.zip] = (zips[p.zip] || 0) + 1;
      if (p.est_cost) { value += p.est_cost; withCost++; if (!biggest || p.est_cost > biggest.est_cost) biggest = p; }
      if (p.contractor) contractors[p.contractor] = (contractors[p.contractor] || 0) + 1;
    });
    const topZips = Object.entries(zips).sort((a, b) => b[1] - a[1]);
    const topC = Object.entries(contractors).sort((a, b) => b[1] - a[1]);
    const named = weekSet.filter((p) => p.contractor).length;

    // KPIs
    const kp = $('#kpis');
    kp.replaceChildren(
      kpi(F.fmt.int(weekSet.length), 'permits', isAll() ? 'all trades' : state.sel.map((s) => LABEL[s]).join(' + ')),
      kpi(value ? F.fmt.money(value) : '–', 'estimated value', value ? withCost + ' building permits list a cost' : 'no building-permit costs in this set'),
      kpi(F.fmt.int(topZips.length), 'ZIPs touched', topZips.length ? 'busiest ' + topZips.slice(0, 2).map((z) => z[0]).join(', ') : ''),
      kpi(biggest ? F.fmt.money(biggest.est_cost) : (topC.length ? F.fmt.int(topC[0][1]) : '–'),
        biggest ? 'biggest job' : 'most permits by one shop',
        biggest ? shortAddr(biggest.address) : (topC.length ? topC[0][0] : '')));

    // summary (two sentences from the numbers)
    const n = weekSet.length;
    let s1 = '<b>' + F.fmt.int(n) + ' ' + selLabel(n) + '</b> issued ' + wk.label;
    if (topZips.length >= 2) s1 += ', most in ' + topZips[0][0] + ' (' + topZips[0][1] + ') and ' + topZips[1][0] + ' (' + topZips[1][1] + ').';
    else if (topZips.length === 1) s1 += ', all in ' + topZips[0][0] + '.';
    else s1 += '.';
    let s2 = '';
    if (biggest) s2 = 'Biggest job: ' + esc((biggest.permit_type || 'building').toLowerCase()) + ' permit at ' + esc(shortAddr(biggest.address)) + ', est. ' + F.fmt.money(biggest.est_cost) + '.';
    else if (topC.length) s2 = esc(topC[0][0]) + ' pulled the most (' + topC[0][1] + '); ' + named + ' of ' + n + ' name a contractor.';
    if (!n) { s1 = 'No permits for this selection last week.'; s2 = 'Try another trade or clear the search.'; }
    $('#summary').innerHTML = s1 + ' ' + s2;

    // breakdown bar across the whole week (selected trades lit, others dimmed)
    const counts = {};
    data.permits.forEach((p) => p.trades.forEach((t) => { counts[t] = (counts[t] || 0) + 1; }));
    const totalTags = ORDER.reduce((a, t) => a + (counts[t] || 0), 0);
    $('#barTitle').textContent = 'By trade, all ' + F.fmt.int(data.permits.length) + ' permits';
    const bar = $('#bar');
    bar.replaceChildren(...ORDER.filter((t) => counts[t]).map((t) => F.el('span', {
      class: (isAll() || state.sel.includes(t)) ? '' : 'dim', style: '--c:' + col(t) + ';flex:' + counts[t], title: LABEL[t] + ': ' + counts[t] })));
    const bars = $('#bars');
    bars.replaceChildren();
    const maxC = Math.max(...ORDER.map((t) => counts[t] || 0), 1);
    ORDER.forEach((t) => {
      const dim = !(isAll() || state.sel.includes(t));
      const lab = F.el('div', { class: 'lab' + (dim ? ' dim' : ''), style: '--c:' + col(t), title: HINT[t] }, [F.el('span', { class: 'dot' }), F.el('span', { text: LABEL[t] })]);
      if (CHIPS.includes(t)) lab.addEventListener('click', () => toggle(t));
      bars.append(lab,
        F.el('div', { class: 'track' + (dim ? ' dim' : ''), style: '--c:' + col(t) }, [F.el('i', { style: 'width:' + Math.round(100 * (counts[t] || 0) / maxC) + '%' })]),
        F.el('span', { class: 'num' + (dim ? ' dim' : ''), text: F.fmt.int(counts[t] || 0) + ' · ' + Math.round(100 * (counts[t] || 0) / Math.max(totalTags, 1)) + '%' }));
    });

    // trend
    const tr = $('#trend');
    const series = weeks.weeks.map((w) => ({ w, n: weekCount(w) }));
    const maxW = Math.max(...series.map((s) => s.n), 1);
    const prior = series.slice(0, -1);
    const avg = prior.length ? prior.reduce((a, s) => a + s.n, 0) / prior.length : 0;
    tr.replaceChildren(...series.map((s, i) => {
      const end = new Date(s.w.end + 'T12:00:00');
      return F.el('div', { class: 'col' + (i === series.length - 1 ? ' now' : ''), title: s.w.label + ': ' + s.n }, [
        F.el('span', { class: 'v num', text: s.n }),
        F.el('span', { class: 'b', style: 'height:' + Math.max(2, Math.round(60 * s.n / maxW)) + 'px' }),
        F.el('span', { class: 'l', text: (end.getMonth() + 1) + '/' + end.getDate() })]);
    }));
    const now = series[series.length - 1].n;
    const diff = avg ? Math.round(100 * (now - avg) / avg) : 0;
    $('#trendcap').textContent = !avg ? 'Weekly counts, 7-day windows ending ' + F.fmt.date(wk.end) + '.' :
      now > avg * 1.1 ? 'Busy week: ' + now + ' vs a ' + Math.round(avg) + ' average over the previous 7 weeks (+' + diff + '%).' :
      now < avg * 0.9 ? 'Quiet week: ' + now + ' vs a ' + Math.round(avg) + ' average over the previous 7 weeks (' + diff + '%).' :
      'Normal week: ' + now + ' vs a ' + Math.round(avg) + ' average over the previous 7 weeks.';

    // list
    const sorted = listSet.slice().sort((a, b) => (b.est_cost || 0) - (a.est_cost || 0) || (a.issued < b.issued ? 1 : a.issued > b.issued ? -1 : 0));
    $('#listTitle').textContent = state.q ? sorted.length + ' of ' + weekSet.length + ' permits' : weekSet.length + ' permits, biggest first';
    const list = $('#list');
    const show = state.showAll ? sorted : sorted.slice(0, PAGE);
    list.replaceChildren(...show.map(rowEl));
    const more = $('#moreBtn');
    more.hidden = sorted.length <= show.length;
    more.textContent = 'Show all ' + sorted.length;
    if (!sorted.length) list.append(F.el('li', { class: 'empty', style: 'display:block', text: 'Nothing matches. Clear the search or pick another trade.' }));
    $('#copyBtn').disabled = !sorted.length;
    $('#copyBtn').onclick = () => F.copy(sorted.map((p) => shortAddr(p.address) + ', Detroit, MI ' + (p.zip || '')).join('\n'), $('#copyBtn'));

    // map
    const { maxN } = paintZctas(weekSet);
    paintPins(listSet);
    paintLegend(maxN);
    setActive(data.permits.find((p) => p.id === state.active) || null, false);
  }
  function kpi(big, label, sub) {
    return F.el('div', { class: 'kpi' }, [F.el('b', { class: 'num', text: big }), F.el('span', { text: label }), F.el('span', { class: 'sub', text: sub || '', title: sub || '' })]);
  }
  function rowEl(p) {
    const t = primary(p);
    const right = p.est_cost ? [F.el('b', { class: 'num', text: F.fmt.money(p.est_cost) }), F.el('span', { text: F.fmt.date(p.issued) })]
      : [F.el('span', { class: 'who', text: p.contractor || p.permit_type, title: p.contractor || '' }), F.el('span', { text: F.fmt.date(p.issued) })];
    const li = F.el('li', { 'data-id': p.id, style: '--c:' + col(t), class: p.id === state.active ? 'active' : '' }, [
      F.el('span', { class: 'rail' }),
      F.el('div', {}, [
        F.el('div', { class: 'addr', text: shortAddr(p.address) || '(no address)' }),
        F.el('div', { class: 'where', text: [p.zip, p.neighborhood].filter(Boolean).join(' · ') }),
        F.el('div', { class: 'what', text: [p.permit_type, p.work_summary].filter(Boolean).join(': ') })]),
      F.el('div', { class: 'right' }, right)]);
    li.addEventListener('click', () => setActive(p, true));
    return li;
  }
  function wire() {
    let t;
    $('#q').addEventListener('input', (e) => { clearTimeout(t); t = setTimeout(() => { state.q = e.target.value; state.showAll = false; render(); }, 120); });
    $('#moreBtn').addEventListener('click', () => { state.showAll = true; render(); });
    window.addEventListener('resize', () => { clearTimeout(t); t = setTimeout(() => map.invalidateSize(), 150); });
  }
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
  }

  boot();
})();
