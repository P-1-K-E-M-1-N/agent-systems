/* Storm Lead: morning-after hail and wind map for Michigan roofers.
   Plain script, no build step. Data comes from app/data/*.json written by refresh.py:
     latest.json   the day the app opens on (yesterday, or the most recent storm day)
     days.json     the last 30 convective days with every qualifying report (replay bar)
     warnings.json active NWS alerts for Michigan, polygons when NWS gives them
     mi_state.json, mi_counties.json  Census TIGERweb boundaries (the basemap; no tile server needed)
   Street tiles (OpenStreetMap) and radar (NOAA nowcoast MRMS) are optional layers that only switch on
   after Factory.canLoadImage() proves the host can load them; the review sandbox cannot. */
(function () {
  'use strict';
  const F = window.Factory;
  const $ = F.qs;
  const KEY = 'storm-lead:';
  const MI_PER_M = 1 / 1609.344;

  const OSM_URL = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
  const OSM_SAMPLE = 'https://tile.openstreetmap.org/6/17/23.png';
  const RADAR_WMS = 'https://nowcoast.noaa.gov/geoserver/weather_radar/wms';
  const RADAR_LAYER = 'base_reflectivity_mosaic';
  const RADAR_SAMPLE = RADAR_WMS + '?service=WMS&version=1.3.0&request=GetMap&layers=' + RADAR_LAYER +
    '&styles=&crs=EPSG:3857&bbox=-10018754,5009377,-7514065,7514065&width=64&height=64&format=image/png&transparent=true';

  const S = {
    latest: null, days: [], warnings: null, geo: {},
    sel: 0,                                  // index into S.days
    home: F.store.get(KEY + 'home', null),   // {lat, lon}
    radius: F.store.get(KEY + 'radius', 25), // miles
    arming: false,
    layers: Object.assign({ counties: true, warnings: true, area: true, osm: false, radar: false }, F.store.get(KEY + 'layers', {})),
    optional: { osm: null, radar: null },    // null = not probed yet, true/false after canLoadImage
  };
  const M = { map: null, state: null, counties: null, pins: null, warn: null, area: null, home: null, circle: null, osm: null, radar: null, byIdx: [] };

  /* ---------- helpers ---------- */
  const normCounty = (s) => String(s || '').replace(/\s+County$/i, '').trim().toLowerCase();
  const plural = (n, one, many) => n === 1 ? one : (many || one + 's');
  const cssVar = (n) => F.cssVar(n) || '#888';
  const dayRec = () => S.days[S.sel] || { day: '', count: 0, hail: 0, wind: 0, counties: {}, zips: {}, reports: [] };
  function miles(lat1, lon1, lat2, lon2) {
    const p = Math.PI / 180;
    const a = Math.sin((lat2 - lat1) * p / 2) ** 2 + Math.cos(lat1 * p) * Math.cos(lat2 * p) * Math.sin((lon2 - lon1) * p / 2) ** 2;
    return 7917.5 * Math.asin(Math.sqrt(a));
  }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])); }

  /* Inline SVG icons: hail is an icy asterisk in a disc, wind is three gust lines; a wind-damage report with no
     measured gust is the same wind mark drawn hollow. Size follows magnitude. */
  function iconSvg(r) {
    if (r.kind === 'hail') {
      return '<svg viewBox="0 0 32 32" aria-hidden="true"><circle class="fill edge" cx="16" cy="16" r="14"/>' +
        '<g stroke="#fff" stroke-width="2.4" stroke-linecap="round" fill="none"><path d="M16 8v16M9.1 12l13.8 8M9.1 20l13.8-8"/></g></svg>';
    }
    return '<svg viewBox="0 0 32 32" aria-hidden="true"><circle class="fill edge" cx="16" cy="16" r="14"/>' +
      '<g class="stroke" stroke="#fff" stroke-width="2.4" stroke-linecap="round" fill="none">' +
      '<path d="M8 12h11a3 3 0 1 0-3-3M6 17h16a3 3 0 1 1-3 3M9 22h7a2.5 2.5 0 1 1-2.5 2.5"/></g></svg>';
  }
  function pinClass(r) { return 'pin ' + r.kind + (r.kind === 'wind' && r.mag == null ? ' dmg' : ''); }
  function pinSize(r) {
    if (r.kind === 'hail') return Math.round(22 + Math.min(Math.max((r.mag || 1) - 1, 0), 2) * 9);   // 1.00in 22px .. 3in+ 40px
    if (r.mag == null) return 18;                                                                      // damage report, no gust
    return Math.round(20 + Math.min(Math.max((r.mag - 58) / 40, 0), 1) * 18);                        // 58mph 20px .. 98mph+ 38px
  }
  function magLabel(r) {
    if (r.kind === 'hail') return r.mag_text + ' hail';
    return r.mag == null ? 'Wind damage' : r.mag_text + ' wind';
  }
  function fmtDay(iso) { return iso ? F.fmt.dateLong(iso) : ''; }
  function fmtShort(iso) { return iso ? F.fmt.date(iso) : ''; }

  /* ---------- theme ---------- */
  function applyTheme(t) {
    if (t === 'light' || t === 'dark') document.documentElement.setAttribute('data-theme', t);
    else document.documentElement.removeAttribute('data-theme');
    const btn = $('#themebtn');
    btn.title = 'Theme: ' + (t || 'auto') + ' (click to switch)';
    btn.setAttribute('aria-label', btn.title);
    const meta = $('meta[name=theme-color]');
    if (meta) meta.content = cssVar('--card') || '#1b3a5c';
  }
  function cycleTheme() {
    const cur = F.store.get(KEY + 'theme', 'auto');
    const next = cur === 'auto' ? 'light' : cur === 'light' ? 'dark' : 'auto';
    F.store.set(KEY + 'theme', next);
    applyTheme(next);
    restyle();
  }
  function restyle() {
    if (!M.map) return;
    if (M.state) M.state.setStyle(stateStyle());
    if (M.counties) M.counties.setStyle(countyStyle);
    if (M.warn) M.warn.eachLayer((l) => l.setStyle && l.setStyle(warnStyle(l.feature)));
    if (M.circle) M.circle.setStyle({ color: cssVar('--acc'), fillColor: cssVar('--acc') });
    renderLegend();
  }

  /* ---------- map ---------- */
  function stateStyle() {
    return { color: cssVar('--map-line'), weight: 1.2, fillColor: cssVar('--map-land'), fillOpacity: S.layers.osm ? 0 : 1, interactive: false };
  }
  function countyCounts() {
    const rec = dayRec(); const out = {}; let max = 0;
    for (const k in rec.counties) { const n = rec.counties[k]; out[normCounty(k)] = n; if (n > max) max = n; }
    return { counts: out, max };
  }
  let CC = { counts: {}, max: 0 };
  function countyStyle(feature) {
    const n = CC.counts[normCounty(feature.properties.NAME)] || 0;
    const t = CC.max ? Math.sqrt(n / CC.max) : 0;
    const on = S.layers.counties;
    return {
      color: n ? cssVar('--acc') : cssVar('--map-line'), weight: n ? 1.1 : 0.7, opacity: n ? 0.9 : 0.8,
      fillColor: n && on ? F.ramp(0.18 + 0.82 * t, cssVar('--map-land'), cssVar('--acc')) : cssVar('--map-land'),
      fillOpacity: S.layers.osm ? (n && on ? 0.5 : 0) : (n && on ? 0.95 : 0.001),
    };
  }
  function worstIn(countyName) {
    const rec = dayRec(); const key = normCounty(countyName);
    const rs = rec.reports.filter((r) => normCounty(r.county) === key);
    if (!rs.length) return '';
    const w = rs[0]; // reports are already sorted worst first
    return magLabel(w) + (w.location ? ' at ' + w.location : '') + ', ' + w.time_local;
  }
  function countyTip(feature) {
    const name = feature.properties.NAME;
    const n = CC.counts[normCounty(name)] || 0;
    const worst = n ? worstIn(name) : '';
    return '<b>' + esc(name) + '</b>' + (n ? n + ' ' + plural(n, 'report') + '<br><small>Worst: ' + esc(worst) + '</small>' : '<small>no qualifying reports this day</small>');
  }
  function warnColor(ev) {
    const e = String(ev || '').toLowerCase();
    if (e.includes('tornado')) return cssVar('--torn');
    if (e.includes('thunderstorm')) return cssVar('--svr');
    if (e.includes('flood')) return cssVar('--flood');
    if (e.includes('hail')) return cssVar('--hail');
    if (e.includes('wind')) return cssVar('--windadv');
    return cssVar('--mute');
  }
  function warnStyle(feature) {
    const p = feature.properties || {};
    const c = warnColor(p.event);
    const watch = /watch|advisory|statement/i.test(p.event || '');
    return { color: c, weight: 2, dashArray: watch ? '6 4' : null, fillColor: c, fillOpacity: watch ? 0.12 : 0.28 };
  }

  function initMap() {
    if (typeof L === 'undefined') {
      $('#map').innerHTML = '<div class="nomap">The map library did not load (no connection to cdnjs). The report list and numbers below still work.</div>';
      $('#layers').hidden = true; $('#maplegend').hidden = true;
      return false;
    }
    const map = L.map('map', { zoomControl: true, zoomSnap: 0.25, attributionControl: true, minZoom: 5, maxZoom: 15, tap: true });
    map.attributionControl.setPrefix('');
    map.attributionControl.addAttribution('Boundaries: US Census Bureau TIGERweb. Reports: NOAA Storm Prediction Center.');
    map.createPane('radar').style.zIndex = 405;
    map.createPane('warn').style.zIndex = 410;
    map.createPane('area').style.zIndex = 415;
    M.map = map;
    M.state = L.geoJSON(S.geo.state, { style: stateStyle(), interactive: false }).addTo(map);
    M.counties = L.geoJSON(S.geo.counties, {
      style: countyStyle, bubblingMouseEvents: true,
      onEachFeature: (f, layer) => {
        layer.bindTooltip(() => countyTip(f), { sticky: true, className: 'county', direction: 'top', opacity: 0.98 });
      },
    }).addTo(map);
    M.warn = L.geoJSON(null, { pane: 'warn', style: warnStyle, onEachFeature: (f, layer) => layer.bindPopup(() => warnPopup(f.properties)) }).addTo(map);
    M.area = L.layerGroup([], { pane: 'area' }).addTo(map);
    M.pins = L.layerGroup().addTo(map);
    const b = M.state.getBounds();
    map.fitBounds(b, { padding: [8, 8] });
    map.setMaxBounds(b.pad(0.6));
    map.on('click', onMapClick);
    return true;
  }

  function onMapClick(e) {
    if (S.arming || !S.home) {
      setHome(e.latlng.lat, e.latlng.lng);
      S.arming = false;
      updateHint();
    }
  }

  /* ---------- pins ---------- */
  function popupHtml(r) {
    const zips = (r.zips || []).map((z) => '<code>' + esc(z) + '</code>').join('');
    return '<div class="popup"><h4><span class="ico ' + pinClass(r) + '">' + iconSvg(r) + '</span>' + esc(magLabel(r)) + '</h4>' +
      '<span class="mute">' + esc(r.time_local) + ' ET' + (r.source === 'archive' ? ' (archive)' : '') + '</span>' +
      '<div><b>' + esc(r.location || 'Michigan') + '</b>, ' + esc(r.county) + ' County</div>' +
      (zips ? '<div class="zips">' + zips + '</div>' : '') +
      (r.comments ? '<div class="cm">' + esc(r.comments) + '</div>' : '') + '</div>';
  }
  function drawPins() {
    if (!M.map) return;
    M.pins.clearLayers(); M.byIdx = [];
    const rec = dayRec();
    rec.reports.forEach((r, i) => {
      if (r.lat == null || r.lon == null) return;
      const s = pinSize(r);
      const icon = L.divIcon({ className: pinClass(r), html: iconSvg(r), iconSize: [s, s], iconAnchor: [s / 2, s / 2], popupAnchor: [0, -s / 2] });
      const m = L.marker([r.lat, r.lon], { icon, zIndexOffset: Math.round(r.severity || 0), title: magLabel(r) + ', ' + (r.location || r.county), riseOnHover: true });
      m.bindPopup(() => popupHtml(r), { maxWidth: 280 });
      m.on('click', () => markActive(i));
      m.addTo(M.pins);
      M.byIdx[i] = m;
    });
  }
  function markActive(i) {
    F.qsa('#r-list li').forEach((li) => li.classList.toggle('active', Number(li.dataset.i) === i));
  }
  function focusReport(i) {
    const r = dayRec().reports[i]; const m = M.byIdx[i];
    markActive(i);
    if (!M.map || !m) return;
    M.map.flyTo([r.lat, r.lon], Math.max(M.map.getZoom(), 9.5), { duration: 0.6 });
    setTimeout(() => m.openPopup(), 650);
  }

  /* ---------- warnings ---------- */
  function warnPopup(p) {
    return '<div class="popup"><h4>' + esc(p.event) + '</h4><div>' + esc(p.headline || '') + '</div>' +
      '<span class="mute">' + esc(p.areaDesc || '') + '</span>' +
      (p.expires ? '<span class="mute">Until ' + esc(F.fmt.time(p.expires)) + ' ' + esc(F.fmt.date(p.expires)) + '</span>' : '') + '</div>';
  }
  function renderWarnings() {
    const W = S.warnings || { warnings: [], as_of: null, error: 'no warnings file' };
    const list = $('#w-list'); list.innerHTML = '';
    $('#w-stamp').textContent = W.as_of ? 'as of ' + F.fmt.time(W.as_of) + ' ' + F.fmt.date(W.as_of) : '';
    if (M.warn) M.warn.clearLayers();
    const ws = W.warnings || [];
    if (!ws.length) {
      list.append(F.el('li', { class: 'mute', style: 'grid-template-columns:1fr', text: W.error ? 'NWS feed unavailable at refresh: ' + W.error : 'No active severe thunderstorm, tornado, wind, hail or flood alerts for Michigan' + (W.total_active ? ' (' + W.total_active + ' other NWS alerts active).' : '.') }));
    }
    ws.forEach((w) => {
      const li = F.el('li', {}, [
        F.el('span', { class: 'sw', style: 'background:' + warnColor(w.event) }),
        F.el('div', {}, [
          F.el('div', { class: 'ev', text: w.event + (w.geometry ? '' : ' (zone-based, not drawn)') }),
          F.el('div', { class: 'ar', text: (w.areaDesc || '') + (w.expires ? ' - until ' + F.fmt.time(w.expires) : '') }),
        ]),
      ]);
      if (w.geometry && M.warn) {
        const f = { type: 'Feature', geometry: w.geometry, properties: w };
        M.warn.addData(f);
        li.style.cursor = 'pointer';
        li.addEventListener('click', () => { const ls = M.warn.getLayers().filter((l) => l.feature && l.feature.properties.id === w.id); if (ls[0]) { M.map.fitBounds(ls[0].getBounds(), { padding: [20, 20] }); ls[0].openPopup(); } });
      }
      list.append(li);
    });
    if (M.warn && M.map) { if (S.layers.warnings) M.warn.addTo(M.map); else M.map.removeLayer(M.warn); }
  }

  /* ---------- panel: header, KPIs, summary, list ---------- */
  function renderHeader() {
    const rec = dayRec(); const L0 = S.latest || {};
    const isLatest = rec.day === L0.day;
    let tag = 'Replay', note = L0.window_note || 'SPC convective day: 8am ET to 8am ET the next morning';
    if (isLatest) {
      if (L0.is_fallback) { tag = 'Most recent storm day'; note = 'No qualifying reports on ' + fmtDay(L0.requested_day) + '; showing the last day that had any.'; }
      else if (/^Yesterday/.test(L0.label || '')) tag = 'Yesterday';
      else tag = 'Selected day';
    }
    if (rec.source === 'archive') note += ' Day filled from the lane archive (live SPC fetch was blocked).';
    $('#daytag').textContent = tag;
    $('#daytag').className = 'pill ' + (isLatest ? 'acc' : '');
    $('#dayname').textContent = fmtDay(rec.day);
    $('#daynote').textContent = note;
    $('#datechip').textContent = fmtShort(rec.day);
    document.title = 'Storm Lead: ' + fmtShort(rec.day);
  }
  function renderKpis() {
    const rec = dayRec();
    const cN = Object.keys(rec.counties).length;
    const top = Object.entries(rec.counties)[0];
    $('#k-count').textContent = F.fmt.int(rec.count);
    $('#k-count-s').textContent = rec.count ? rec.hail + ' hail, ' + rec.wind + ' wind' : 'quiet day';
    $('#k-counties').textContent = F.fmt.int(cN);
    $('#k-counties-s').textContent = top ? top[0] + ' leads with ' + top[1] : ' ';
    const hail = rec.reports.filter((r) => r.kind === 'hail' && r.mag).sort((a, b) => b.mag - a.mag)[0];
    $('#k-hail').textContent = hail ? hail.mag.toFixed(2) + ' in' : 'none';
    $('#k-hail-s').textContent = hail ? (hail.location || hail.county) : 'no 1 inch hail';
    const wind = rec.reports.filter((r) => r.kind === 'wind' && r.mag).sort((a, b) => b.mag - a.mag)[0];
    const dmg = rec.reports.filter((r) => r.kind === 'wind' && r.mag == null).length;
    $('#k-wind').textContent = wind ? Math.round(wind.mag) + ' mph' : (dmg ? 'damage' : 'none');
    $('#k-wind-s').textContent = wind ? (wind.location || wind.county) + (dmg ? ' + ' + dmg + ' damage ' + plural(dmg, 'report') : '') : (dmg ? dmg + ' damage ' + plural(dmg, 'report') + ', no gust measured' : 'no 58 mph gusts');
  }
  function summaryText() {
    const rec = dayRec();
    const when = fmtShort(rec.day);
    if (!rec.count) return 'No qualifying hail or wind reports came in for Michigan on ' + when + '. Nothing to canvass from this day; the bars below replay the last storm day.';
    const cs = Object.entries(rec.counties);
    const s1 = rec.count + ' NWS storm ' + plural(rec.count, 'report') + ' qualified across ' + cs.length + ' ' + plural(cs.length, 'county', 'counties') +
      ', led by ' + cs[0][0] + ' (' + cs[0][1] + ')' + (cs[1] ? ' and ' + cs[1][0] + ' (' + cs[1][1] + ')' : '') + '.';
    const hail = rec.reports.filter((r) => r.kind === 'hail' && r.mag).sort((a, b) => b.mag - a.mag)[0];
    const wind = rec.reports.filter((r) => r.kind === 'wind' && r.mag).sort((a, b) => b.mag - a.mag)[0];
    const dmg = rec.reports.filter((r) => r.kind === 'wind' && r.mag == null).length;
    const parts = [];
    if (hail) parts.push('hail reached ' + hail.mag.toFixed(2) + ' in near ' + (hail.location || hail.county));
    if (wind) parts.push('wind gusted to ' + Math.round(wind.mag) + ' mph at ' + (wind.location || wind.county));
    if (dmg) parts.push(dmg + ' wind-damage ' + plural(dmg, 'report') + ' (trees and wires down) came in with no measured gust');
    const zips = Object.keys(rec.zips).slice(0, 3);
    let s2 = parts.join(', ');
    s2 = s2.charAt(0).toUpperCase() + s2.slice(1);
    if (zips.length) s2 += '; start with ' + plural(zips.length, 'ZIP') + ' ' + zips.join(', ') + '.'; else s2 += '.';
    return s1 + ' ' + s2;
  }
  function renderList() {
    const rec = dayRec(); const ul = $('#r-list'); ul.innerHTML = '';
    $('#r-count').textContent = rec.count ? rec.count + ' on ' + fmtShort(rec.day) : '';
    if (!rec.count) { ul.append(F.el('li', { class: 'mute', style: 'grid-template-columns:1fr;cursor:default', text: 'No qualifying reports this day.' })); return; }
    const CAP = 60;
    const add = (r, i) => {
      const li = F.el('li', { 'data-i': i, tabindex: 0, role: 'button', 'aria-label': magLabel(r) + ' at ' + (r.location || r.county) }, [
        F.el('span', { class: 'ico ' + pinClass(r), html: iconSvg(r) }),
        F.el('div', { class: 't' }, [
          F.el('b', { text: magLabel(r) + (r.location ? ' - ' + r.location : '') }),
          F.el('span', { text: r.county + ' County' + (r.zips && r.zips.length ? ' - ZIP ' + r.zips.slice(0, 3).join(', ') : '') }),
        ]),
        F.el('span', { class: 'tm', text: r.time_local }),
      ]);
      li.addEventListener('click', () => focusReport(i));
      li.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); focusReport(i); } });
      ul.append(li);
    };
    rec.reports.slice(0, CAP).forEach(add);
    if (rec.reports.length > CAP) {
      const more = F.el('li', { class: 'more', style: 'grid-template-columns:1fr' }, [F.el('button', { class: 'btn small', type: 'button', text: 'Show all ' + rec.reports.length })]);
      more.firstChild.addEventListener('click', () => { more.remove(); rec.reports.slice(CAP).forEach((r, j) => add(r, j + CAP)); });
      ul.append(more);
    }
  }

  /* ---------- replay bar ---------- */
  function renderScrub() {
    const bars = $('#bars'); bars.innerHTML = '';
    bars.style.gridTemplateColumns = 'repeat(' + S.days.length + ',minmax(0,1fr))';
    const max = Math.max(1, ...S.days.map((d) => d.count));
    const total = S.days.reduce((a, d) => a + d.count, 0);
    const stormDays = S.days.filter((d) => d.count).length;
    $('#scrub-total').textContent = total + ' ' + plural(total, 'report') + ' on ' + stormDays + ' storm ' + plural(stormDays, 'day');
    S.days.forEach((d, i) => {
      const h = d.count ? Math.max(8, Math.round(100 * Math.sqrt(d.count / max))) : 5;
      const b = F.el('button', { type: 'button', class: (d.count ? 'has' : '') + (i === S.sel ? ' sel' : ''), title: fmtShort(d.day) + ': ' + d.count + ' ' + plural(d.count, 'report'), 'aria-label': fmtShort(d.day) + ', ' + d.count + ' ' + plural(d.count, 'report'), 'aria-pressed': i === S.sel ? 'true' : 'false' },
        [F.el('i', { style: 'height:' + h + '%' })]);
      b.addEventListener('click', () => selectDay(i));
      bars.append(b);
    });
    $('#ax0').textContent = fmtShort(S.days[0].day);
    $('#ax1').textContent = fmtShort(S.days[S.days.length - 1].day);
    const rng = $('#dayrange'); rng.max = S.days.length - 1; rng.value = S.sel;
    const rec = dayRec();
    $('#scrub-cap').innerHTML = '<b>' + esc(fmtShort(rec.day)) + '</b> ' + rec.count + ' ' + plural(rec.count, 'report') + (rec.count ? ', ' + Object.keys(rec.counties).length + ' ' + plural(Object.keys(rec.counties).length, 'county', 'counties') : '');
    const latestIdx = S.days.findIndex((d) => d.day === (S.latest || {}).day);
    $('#backtoday').hidden = latestIdx < 0 || latestIdx === S.sel;
  }
  function selectDay(i) {
    if (i < 0 || i >= S.days.length) return;
    S.sel = i;
    if (M.map) M.map.closePopup();
    renderDay();
  }

  /* ---------- service area ---------- */
  function setHome(lat, lon) {
    S.home = { lat: +lat.toFixed(4), lon: +lon.toFixed(4) };
    F.store.set(KEY + 'home', S.home);
    drawArea(); renderArea(); updateHint();
  }
  function clearHome() {
    S.home = null; F.store.set(KEY + 'home', null);
    drawArea(); renderArea(); updateHint();
  }
  function drawArea() {
    if (!M.map) return;
    M.area.clearLayers(); M.home = null; M.circle = null;
    if (!S.home || !S.layers.area) return;
    const acc = cssVar('--acc');
    M.circle = L.circle([S.home.lat, S.home.lon], { radius: S.radius / MI_PER_M, pane: 'area', color: acc, weight: 2, dashArray: '4 4', fillColor: acc, fillOpacity: 0.08, interactive: false }).addTo(M.area);
    M.home = L.marker([S.home.lat, S.home.lon], { draggable: true, pane: 'area', icon: L.divIcon({ className: 'home', iconSize: [18, 18], iconAnchor: [9, 9] }), title: 'Your home base (drag to move)', zIndexOffset: 2000 }).addTo(M.area);
    M.home.on('drag', (e) => { const ll = e.target.getLatLng(); if (M.circle) M.circle.setLatLng(ll); });
    M.home.on('dragend', (e) => { const ll = e.target.getLatLng(); setHome(ll.lat, ll.lng); });
  }
  function renderArea() {
    const rec = dayRec();
    $('#radius-out').textContent = S.radius + ' mi';
    $('#radius').value = S.radius;
    const zips = $('#a-zips'); zips.innerHTML = '';
    if (!S.home) {
      $('#a-count').textContent = '–'; $('#a-label').textContent = 'reports inside';
      $('#a-hint').textContent = 'Tap the map where your trucks start the day. The circle and count are remembered on this device.';
      $('#a-copy').hidden = true; $('#a-clear').hidden = true; $('#a-set').textContent = 'Set on map';
      return;
    }
    const inside = rec.reports.filter((r) => r.lat != null && miles(S.home.lat, S.home.lon, r.lat, r.lon) <= S.radius);
    $('#a-count').textContent = F.fmt.int(inside.length);
    $('#a-label').textContent = plural(inside.length, 'report') + ' within ' + S.radius + ' mi on ' + fmtShort(rec.day);
    const zc = {};
    inside.forEach((r) => (r.zips || []).forEach((z) => { zc[z] = (zc[z] || 0) + 1; }));
    const list = Object.entries(zc).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
    $('#a-hint').textContent = list.length ? list.length + ' ' + plural(list.length, 'ZIP') + ' to canvass, most reports first. Drag the dot or press Set on map to move.' : 'Nothing inside the circle this day. Widen the radius or replay another day.';
    list.forEach(([z, n]) => zips.append(F.el('code', { class: n > 1 ? 'hit' : '', text: z + (n > 1 ? ' x' + n : '') })));
    $('#a-copy').hidden = !list.length; $('#a-clear').hidden = false; $('#a-set').textContent = 'Move';
    $('#a-copy').onclick = (e) => F.copy(list.map((x) => x[0]).join(', '), e.currentTarget);
  }
  function updateHint() {
    const h = $('#hint');
    if (!M.map) { h.hidden = true; return; }
    if (S.arming) { h.textContent = 'Tap the map to place your home base'; h.className = 'overlay hint arm'; h.hidden = false; }
    else if (!S.home) { h.textContent = 'Tap the map to set your service area'; h.className = 'overlay hint'; h.hidden = false; }
    else h.hidden = true;
  }

  /* ---------- legend and layer toggles ---------- */
  function renderLegend() {
    const lg = $('#maplegend'); if (!lg) return;
    const land = cssVar('--map-land'), acc = cssVar('--acc');
    const steps = [0.18, 0.45, 0.72, 1].map((t) => '<i style="background:' + F.ramp(t, land, acc) + '"></i>').join('');
    lg.innerHTML =
      '<div class="row"><span class="ico pin hail">' + iconSvg({ kind: 'hail' }) + '</span><span>Hail 1 in+ <small>(bigger = larger)</small></span></div>' +
      '<div class="row"><span class="ico pin wind">' + iconSvg({ kind: 'wind', mag: 60 }) + '</span><span>Wind 58 mph+ <small>(bigger = faster)</small></span></div>' +
      '<div class="row"><span class="ico pin wind dmg">' + iconSvg({ kind: 'wind' }) + '</span><span>Wind damage<small>, no gust measured</small></span></div>' +
      (S.layers.counties ? '<div class="ramp">' + steps + '<span style="font-size:11px;color:var(--mute);margin-left:4px">reports / county</span></div>' : '');
  }
  function applyLayers() {
    if (!M.map) return;
    M.counties.setStyle(countyStyle);
    if (M.state) M.state.setStyle(stateStyle());
    if (S.layers.warnings) M.warn.addTo(M.map); else M.map.removeLayer(M.warn);
    drawArea();
    if (S.layers.osm && S.optional.osm) {
      if (!M.osm) M.osm = L.tileLayer(OSM_URL, { maxZoom: 19, attribution: '&copy; OpenStreetMap contributors', opacity: 0.9 });
      M.osm.addTo(M.map);
    } else if (M.osm) M.map.removeLayer(M.osm);
    if (S.layers.radar && S.optional.radar) {
      if (!M.radar) M.radar = L.tileLayer.wms(RADAR_WMS, { layers: RADAR_LAYER, format: 'image/png', transparent: true, version: '1.3.0', opacity: 0.7, pane: 'radar', attribution: 'Radar: NOAA nowcoast MRMS' });
      M.radar.addTo(M.map);
    } else if (M.radar) M.map.removeLayer(M.radar);
    F.qsa('#layers [data-layer]').forEach((b) => { b.setAttribute('aria-pressed', S.layers[b.dataset.layer] ? 'true' : 'false'); });
    F.store.set(KEY + 'layers', S.layers);
    renderLegend();
  }
  async function probeOptional() {
    const [osm, radar] = await Promise.all([F.canLoadImage(OSM_SAMPLE, 5000), F.canLoadImage(RADAR_SAMPLE, 6000)]);
    S.optional.osm = osm; S.optional.radar = radar;
    const bo = $('[data-layer=osm]'), br = $('[data-layer=radar]');
    bo.disabled = !osm; br.disabled = !radar;
    bo.title = osm ? 'OpenStreetMap street tiles (light use only)' : 'Street tiles cannot load from this address';
    br.title = radar ? 'NOAA nowcoast MRMS base reflectivity, refreshed every few minutes' : 'Radar tiles cannot load from this address';
    $('#layernote').hidden = osm && radar;
    if (!osm) S.layers.osm = false;
    if (!radar) S.layers.radar = false;
    applyLayers();
  }

  /* ---------- footer ---------- */
  function renderFoot() {
    const L0 = S.latest || {};
    $('#f-rule').textContent = 'Alert rule: ' + (L0.rule || '') + '. Reports are preliminary local storm reports relayed by NWS offices; late reports are added for several days.';
    $('#f-zip').textContent = L0.zip_note || '';
    $('#f-src').textContent = 'Sources: ' + (L0.sources || []).join('; ') + '. Street map (c) OpenStreetMap contributors and radar from NOAA nowcoast are optional layers.';
    $('#f-time').textContent = L0.generated_at ? 'Data refreshed ' + F.fmt.time(L0.generated_at) + ' ' + F.fmt.date(L0.generated_at) + ' (' + F.fmt.ago(L0.generated_at) + '), by the lane\'s daily refresh.py.' : '';
  }

  /* ---------- render one day ---------- */
  function renderDay() {
    CC = countyCounts();
    renderHeader(); renderKpis();
    $('#summary').textContent = summaryText();
    renderScrub(); renderList(); renderArea(); drawPins();
    if (M.counties) M.counties.setStyle(countyStyle);
  }

  /* ---------- boot ---------- */
  function wire() {
    $('#themebtn').addEventListener('click', cycleTheme);
    $('#dayrange').addEventListener('input', (e) => selectDay(Number(e.target.value)));
    $('#backtoday').addEventListener('click', () => { const i = S.days.findIndex((d) => d.day === (S.latest || {}).day); if (i >= 0) selectDay(i); });
    $('#radius').addEventListener('input', (e) => { S.radius = Number(e.target.value); F.store.set(KEY + 'radius', S.radius); if (M.circle) M.circle.setRadius(S.radius / MI_PER_M); renderArea(); });
    $('#a-set').addEventListener('click', () => { S.arming = !S.arming; updateHint(); if (S.arming && M.map && window.innerWidth < 861) window.scrollTo({ top: 0, behavior: 'smooth' }); });
    $('#a-clear').addEventListener('click', clearHome);
    F.qsa('#layers [data-layer]').forEach((b) => b.addEventListener('click', () => { const k = b.dataset.layer; S.layers[k] = !S.layers[k]; applyLayers(); }));
    window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', restyle);
  }

  async function main() {
    applyTheme(new URLSearchParams(location.search).get('theme') || F.store.get(KEY + 'theme', 'auto'));
    F.registerSW();
    wire();
    let latest, days, warnings, geoState, geoCounties;
    try {
      [latest, days, geoState, geoCounties] = await Promise.all([
        F.loadJSON('data/latest.json'), F.loadJSON('data/days.json'), F.loadJSON('data/mi_state.json'), F.loadJSON('data/mi_counties.json')]);
    } catch (e) {
      $('#summary').textContent = 'No data yet: run lanes/storm-lead/refresh.py so it writes app/data/latest.json and friends. (' + e.message + ')';
      $('#dayname').textContent = 'Storm Lead';
      return;
    }
    try { warnings = await F.loadJSON('data/warnings.json'); } catch (e) { warnings = { warnings: [], error: 'warnings.json missing' }; }
    S.latest = latest; S.warnings = warnings; S.geo = { state: geoState, counties: geoCounties };
    S.days = (days.days || []).slice().sort((a, b) => a.day.localeCompare(b.day));
    if (!S.days.find((d) => d.day === latest.day)) {
      S.days.push({ day: latest.day, count: latest.count, hail: latest.hail, wind: latest.wind, max_hail: latest.max_hail, max_wind: latest.max_wind, counties: latest.counties, zips: latest.zips, reports: latest.reports, source: latest.source });
      S.days.sort((a, b) => a.day.localeCompare(b.day));
    }
    S.sel = Math.max(0, S.days.findIndex((d) => d.day === latest.day));
    CC = countyCounts();
    const hasMap = initMap();
    renderDay(); renderWarnings(); renderFoot(); renderLegend();
    if (hasMap) {
      drawArea(); updateHint(); applyLayers();
      probeOptional();
      // live refresh of warnings when the app runs from its own address (the sandbox blocks it; the snapshot stays)
      refreshWarningsLive();
    }
  }

  async function refreshWarningsLive() {
    try {
      const ctrl = new AbortController(); const t = setTimeout(() => ctrl.abort(), 6000);
      const r = await fetch('https://api.weather.gov/alerts/active?area=MI', { headers: { Accept: 'application/geo+json' }, signal: ctrl.signal });
      clearTimeout(t);
      if (!r.ok) return;
      const d = await r.json();
      const keep = ['tornado', 'thunderstorm', 'wind', 'hail', 'flood'];
      const ws = (d.features || []).filter((f) => keep.some((k) => String(f.properties.event || '').toLowerCase().includes(k)))
        .map((f) => ({ id: f.properties.id || f.id, event: f.properties.event, headline: f.properties.headline, areaDesc: f.properties.areaDesc, expires: f.properties.expires, onset: f.properties.onset, geometry: f.geometry, zones: f.properties.affectedZones || [] }));
      S.warnings = { as_of: new Date().toISOString(), total_active: (d.features || []).length, warnings: ws, error: '', live: true };
      renderWarnings();
      $('#w-stamp').textContent += ' (live)';
    } catch (e) { /* offline or sandboxed: keep the refresh.py snapshot */ }
  }

  main();
})();
