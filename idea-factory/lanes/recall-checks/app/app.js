/* Recall Checks: lot overview, vehicle cards, check-a-vehicle. Plain script, no build step.
   Data: window.RECALL_SNAPSHOT (data/latest.js, loaded before first paint) or data/latest.json;
   data/campaigns.json for the offline lookup. Live NHTSA calls are optional and fall back to the snapshot. */
(function () {
  const F = window.Factory;
  const { qs, qsa, el, fmt } = F;
  const NHTSA = (id) => 'https://www.nhtsa.gov/recalls?nhtsaId=' + encodeURIComponent(id);
  const ORDER = { critical: 0, serious: 1, moderate: 2, unknown: 3, clean: 4 };
  const LABEL = { critical: 'Critical', serious: 'Serious', moderate: 'Moderate', unknown: 'Lookup failed', clean: 'No campaigns' };

  /* Same rule as refresh.py category(): keep the two in step. */
  const RX = {
    critC: /air ?bag|inflator|brake|steering|fuel/i,
    critQ: /\bfire\b|loss of (steering|brak)|unable to (stop|steer)|do not drive|park (it|outside)/i,
    serC: /seat ?belt|restraint|child seat|wheel|tire|axle|suspension|control arm|hood|latch|structure|frame|power train|transmission|engine|visibility|exterior lighting/i,
    serQ: /stall|roll ?away|loss of (motive )?power|loss of (drive|propulsion)|detach|separate|unintended/i,
  };
  function categorize(r) {
    if (r.parkIt || r.parkOutSide) return 'critical';
    const c = r.Component || '', q = r.Consequence || '';
    if (RX.critC.test(c) || RX.critQ.test(q)) return 'critical';
    if (RX.serC.test(c) || RX.serQ.test(q)) return 'serious';
    return 'moderate';
  }
  const clean = (s) => String(s || '').replace(/[\u0091\u0092\uFFFD]/g, "'").replace(/[\u0093\u0094]/g, '"').replace(/\s+/g, ' ').trim();
  function niceComponent(c) {
    const parts = String(c || '').split(':').map((p) => p.trim().toLowerCase()).filter(Boolean);
    const s = parts.join(' / ');
    return s ? s[0].toUpperCase() + s.slice(1) : '';
  }
  function sentences(t) {
    let s = clean(t);
    if (s && s === s.toUpperCase()) s = s.split('. ').map((x) => x[0] + x.slice(1).toLowerCase()).join('. ');
    return s.split(/(?<=[a-z0-9)"])\.\s+(?=[A-Z"])/).map((x) => x.trim()).filter(Boolean);
  }
  function plainDefect(summary) {
    let ss = sentences(summary);
    if (ss.length > 1 && /\b(is|are) recalling\b/i.test(ss[0])) ss = ss.slice(1);
    let out = ss.slice(0, 2).join(' ');
    if (out && !out.endsWith('.')) out += '.';
    return out.length > 240 ? out.slice(0, 237).replace(/\s\S*$/, '') + '...' : out;
  }
  function plainFix(remedy) {
    const ss = sentences(remedy);
    if (!ss.length) return '';
    let s = ss[0].replace(/^.*?\bwill notify (the )?owners?,?\s*(and|;)?\s*/i, '');
    s = s[0].toUpperCase() + s.slice(1);
    if (!s.endsWith('.')) s += '.';
    return s.length > 160 ? s.slice(0, 157).replace(/\s\S*$/, '') + '...' : s;
  }
  const isoDate = (d) => { const m = /^(\d\d)\/(\d\d)\/(\d{4})$/.exec(d || ''); return m ? m[3] + '-' + m[2] + '-' + m[1] : (d || ''); };
  /* A live NHTSA record -> the same shape refresh.py writes. */
  function fromLive(r) {
    return { id: r.NHTSACampaignNumber || '', component: niceComponent(r.Component), component_raw: r.Component || '',
      defect: plainDefect(r.Summary), fix: plainFix(r.Remedy), summary: clean(r.Summary), consequence: clean(r.Consequence),
      remedy: clean(r.Remedy), manufacturer: r.Manufacturer || '', report_date: isoDate(r.ReportReceivedDate),
      severity: categorize(r), park_it: !!r.parkIt, park_outside: !!r.parkOutSide, ota: !!r.overTheAirUpdate };
  }
  function finish(v) {
    v.campaigns.sort((a, b) => (ORDER[a.severity] - ORDER[b.severity]) || (b.report_date > a.report_date ? 1 : -1));
    v.n = v.campaigns.length;
    v.worst = v.n ? v.campaigns[0].severity : (v.lookup_failed ? 'unknown' : 'clean');
    v.flags = [].concat(v.campaigns.some((c) => c.park_it) ? ['DO NOT DRIVE'] : [], v.campaigns.some((c) => c.park_outside) ? ['PARK OUTSIDE'] : []);
    v.newest = v.campaigns.reduce((m, c) => (c.report_date > m ? c.report_date : m), '');
    return v;
  }
  const key = (y, m, mo) => `${y}|${String(m).toLowerCase().trim()}|${String(mo).toLowerCase().trim()}`;
  const dateShort = (iso) => iso ? new Date(iso + 'T12:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : '';

  /* ---------- state ---------- */
  let data = null, filter = 'all', query = '';
  let lookup = null; // campaigns.json by_key, or derived from the lot

  /* ---------- theme ---------- */
  (function theme() {
    const saved = F.store.get('rc.theme');
    if (saved) document.documentElement.dataset.theme = saved;
    qs('#themebtn').addEventListener('click', () => {
      const cur = document.documentElement.dataset.theme || (matchMedia('(prefers-color-scheme:dark)').matches ? 'dark' : 'light');
      const next = cur === 'dark' ? 'light' : 'dark';
      document.documentElement.dataset.theme = next; F.store.set('rc.theme', next);
    });
  })();

  /* ---------- lot header ---------- */
  function renderHead() {
    const t = data.totals, lot = data.lot || {};
    qs('#lotname').textContent = lot.label || 'Lot';
    qs('#lottag').textContent = lot.note ? 'example stock' : 'your lot';
    qs('#lottag').title = lot.note || '';
    qs('#checked').textContent = `${t.vehicles} vehicles · checked ${dateShort(data.checked_at)} against NHTSA`;
    const adv = data.vehicles.filter((v) => v.flags && v.flags.length).length;
    const k = qs('#kpis'); k.innerHTML = '';
    k.append(
      kpi(t.vehicles, 'vehicles on the lot', '', `${t.vehicles - t.with_campaigns - t.lookup_failed} with no campaign on file`),
      kpi(t.with_campaigns, 'with an open campaign', 'acc', `${t.campaigns} campaigns apply in all`),
      kpi(t.campaigns, 'campaigns to confirm', '', `${t.by_severity.critical} critical · ${t.by_severity.serious} serious`),
      kpi(t.critical_vehicles, 'vehicles flagged critical', 'crit', adv ? `${adv} carry an NHTSA do-not-drive or park-outside advisory` : 'no NHTSA park-it advisories')
    );
    const s = qs('#strip'); s.innerHTML = '';
    const bs = t.by_severity, total = Math.max(1, t.campaigns);
    const bar = el('div', { class: 'bar', role: 'img', 'aria-label': `Campaigns by severity: ${bs.critical} critical, ${bs.serious} serious, ${bs.moderate} moderate` });
    ['critical', 'serious', 'moderate'].forEach((c) => { if (bs[c]) bar.append(el('span', { class: 'c-' + c, style: `flex:${bs[c]} 1 0` })); });
    const lg = el('div', { class: 'lg' }, ['critical', 'serious', 'moderate'].map((c) => el('span', {}, [el('i', { class: 'c-' + c }), el('b', { text: bs[c] }), document.createTextNode(' ' + LABEL[c].toLowerCase())])));
    lg.append(el('span', { class: 'mute', text: `${Math.round(100 * bs.critical / total)}% of campaigns critical` }));
    s.append(bar, lg);
    qs('#refreshed').textContent = `Refreshed ${dateShort(data.checked_at)} (${fmt.ago(data.generated_at)}) · weekly cadence · snapshot ${data.generated_at.slice(0, 16).replace('T', ' ')} UTC`;
    qs('#honest-line').textContent = data.limitation || qs('#honest-line').textContent;
  }
  function kpi(n, label, cls, sub) {
    return el('div', { class: 'kpi ' + (cls || '') }, [el('b', { class: 'num', text: fmt.int(n) }), el('span', { text: label }), el('small', { text: sub })]);
  }

  /* ---------- what to do this week ---------- */
  function renderWeek() {
    const ol = qs('#week-list'); ol.innerHTML = '';
    const since = new Date(Date.now() - 120 * 86400000).toISOString().slice(0, 10);
    const ranked = data.vehicles.slice().sort((a, b) => {
      const fa = a.flags.length ? 0 : 1, fb = b.flags.length ? 0 : 1;
      if (fa !== fb) return fa - fb;
      const ca = a.campaigns.filter((c) => c.severity === 'critical').length, cb = b.campaigns.filter((c) => c.severity === 'critical').length;
      if (ca !== cb) return cb - ca;
      return b.newest > a.newest ? 1 : -1;
    });
    const items = [];
    ranked.forEach((v) => {
      if (items.length >= 5) return;
      if (v.flags.length) items.push([v, `NHTSA ${v.flags.join(' and ').toLowerCase()} advisory (${v.campaigns.find((c) => c.park_it || c.park_outside).component.toLowerCase()}). Run the VIN before it moves or is test-driven.`]);
      else if (v.newest >= since) items.push([v, `New campaign filed ${dateShort(v.newest)} (${v.campaigns.filter((c) => c.report_date === v.newest)[0].component.toLowerCase()}); a prior owner is unlikely to have had it done.`]);
      else if (v.campaigns.filter((c) => c.severity === 'critical').length >= 5) items.push([v, `${v.campaigns.filter((c) => c.severity === 'critical').length} critical campaigns apply; worth the VIN check before it is listed.`]);
    });
    data.vehicles.filter((v) => v.lookup_failed).forEach((v) => items.push([v, 'NHTSA’s API refused this year/make/model this run (their side). Search nhtsa.gov/recalls by hand or wait for next week’s run.']));
    if (!items.length) ol.append(el('li', {}, [el('span', { class: 'stk', text: '–' }), el('span', { text: 'Nothing urgent. Keep running VINs on cars before they go out.' })]));
    items.forEach(([v, why]) => ol.append(el('li', {}, [
      el('span', { class: 'stk', text: v.stock }),
      el('span', {}, [el('b', { text: `${v.year} ${v.make} ${v.model}` }), document.createTextNode(' '), el('span', { class: 'why', text: why })]),
    ])));
    const noVin = data.vehicles.filter((v) => !v.vin || v.vin.includes('*')).length;
    qs('#week-tip').textContent = noVin
      ? `${noVin} of ${data.vehicles.length} vehicles are on file as year/make/model only (or a partial VIN). Adding full VINs lets you paste the whole lot into NHTSA’s free 100-VIN check in one go.`
      : 'Every vehicle has a VIN on file: paste them into NHTSA’s free 100-VIN check to see open vs. repaired.';
  }

  /* ---------- vehicle cards ---------- */
  function matches(v) {
    if (filter === 'with' && !v.n) return false;
    if (filter === 'critical' && v.worst !== 'critical') return false;
    if (filter === 'clean' && (v.n || v.lookup_failed)) return false;
    if (!query) return true;
    const hay = `${v.stock} ${v.vin} ${v.year} ${v.make} ${v.model} ${v.trim}`.toLowerCase();
    return query.split(/\s+/).every((w) => hay.includes(w));
  }
  function renderLot() {
    const lot = qs('#lot'); lot.innerHTML = '';
    const shown = data.vehicles.filter(matches);
    qs('#count').textContent = `${shown.length} of ${data.vehicles.length}`;
    qs('#f-all').textContent = data.vehicles.length;
    qs('#f-with').textContent = data.vehicles.filter((v) => v.n).length;
    qs('#f-critical').textContent = data.vehicles.filter((v) => v.worst === 'critical').length;
    qs('#f-clean').textContent = data.vehicles.filter((v) => !v.n && !v.lookup_failed).length;
    if (!shown.length) { lot.append(el('div', { class: 'empty', text: 'No vehicles match. Clear the search or pick another filter.' })); return; }
    shown.forEach((v) => lot.append(card(v)));
  }
  function card(v, origin) {
    const c = el('article', { class: 'card veh s-' + v.worst, 'data-stock': v.stock || '' });
    if (origin) c.append(el('div', { class: 'origin', text: origin }));
    const head = el('div', { class: 'head' });
    if (v.stock) head.append(el('span', { class: 'stk', text: v.stock }));
    head.append(el('span', { class: 'sev ' + v.worst, text: LABEL[v.worst] }));
    (v.flags || []).forEach((f) => head.append(el('span', { class: 'adv', text: f })));
    head.append(el('span', { class: 'n num', text: v.lookup_failed ? '? campaigns' : (v.n === 1 ? '1 campaign' : `${v.n} campaigns`) }));
    c.append(head);
    const name = el('div', { class: 'name', text: `${v.year} ${v.make} ${v.model}`.trim() });
    if (v.trim) name.append(el('small', { text: v.trim }));
    c.append(name);
    if (v.vin) {
      const vin = el('div', { class: 'vin' }, [el('code', { text: v.vin })]);
      const b = el('button', { class: 'btn small', type: 'button', text: 'Copy' });
      b.addEventListener('click', () => F.copy(v.vin, b));
      vin.append(b);
      c.append(vin);
      if (v.vin_note) c.append(el('div', { class: 'vin note', text: v.vin_note }));
    } else {
      c.append(el('div', { class: 'vin none' }, [el('code', { text: 'Year, make and model only. Add the VIN to check open vs. repaired on nhtsa.gov.' })]));
    }
    const top = v.campaigns[0];
    if (top) {
      const w = el('div', { class: 'worst' });
      w.append(el('div', {}, [el('span', { class: 'lbl', text: 'Most serious' }), el('span', { class: 'comp', text: top.component })]));
      if (top.defect) w.append(el('div', { text: top.defect }));
      if (top.fix) w.append(el('div', { class: 'fix' }, [el('b', { text: 'The fix: ' }), document.createTextNode(top.fix)]));
      c.append(w);
      c.append(campaignChips(v));
      c.append(el('div', { class: 'meta' }, [el('span', { text: `Newest campaign ${dateShort(v.newest)}` }), el('span', { text: `Reported by ${top.manufacturer || 'the manufacturer'}` })]));
    } else if (v.lookup_failed) {
      c.append(el('div', { class: 'worst' }, [el('div', { text: 'NHTSA’s recall API answered an error for this year, make and model on this run. That is their API, not the car; it is retried next week. Search nhtsa.gov/recalls by hand in the meantime.' })]));
    } else {
      c.append(el('div', { class: 'worst' }, [el('div', { text: 'No NHTSA safety campaign on file for this year, make and model.' })]));
    }
    return c;
  }
  function campaignChips(v) {
    const wrap = el('div', { class: 'camps' });
    const show = v.campaigns.slice(0, 4);
    show.forEach((cp) => wrap.append(chip(cp)));
    if (v.campaigns.length > 4 || v.campaigns.length > 1) {
      const more = el('button', { class: 'more', type: 'button', text: v.campaigns.length > 4 ? `+${v.campaigns.length - 4} more · show all` : 'Show all' });
      let list = null;
      more.addEventListener('click', () => {
        if (list) { list.remove(); list = null; more.textContent = v.campaigns.length > 4 ? `+${v.campaigns.length - 4} more · show all` : 'Show all'; return; }
        list = el('ul', { class: 'all' }, v.campaigns.map((cp) => el('li', {}, [
          el('i', { class: 'c-' + cp.severity, title: LABEL[cp.severity] }),
          el('div', {}, [
            el('div', { class: 't' }, [el('a', { href: NHTSA(cp.id), target: '_blank', rel: 'noopener', text: cp.id }), el('span', { text: cp.component }), el('span', { class: 'd', text: dateShort(cp.report_date) })]),
            el('p', {}, [document.createTextNode(cp.defect || cp.summary || ''), document.createTextNode(cp.fix ? ' ' : ''), cp.fix ? el('b', { text: cp.fix }) : document.createTextNode('')]),
          ]),
        ])));
        wrap.after(list); more.textContent = 'Hide';
      });
      wrap.append(more);
    }
    return wrap;
  }
  function chip(cp) { return el('a', { href: NHTSA(cp.id), target: '_blank', rel: 'noopener', title: `${LABEL[cp.severity]}: ${cp.component}`, text: cp.id }); }

  /* ---------- filters and search ---------- */
  qsa('#filters button').forEach((b) => b.addEventListener('click', () => {
    filter = b.dataset.f;
    qsa('#filters button').forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
    renderLot();
  }));
  qs('#q').addEventListener('input', (e) => { query = e.target.value.trim().toLowerCase(); renderLot(); });

  /* ---------- check a vehicle ---------- */
  const LIVE_HINT = 'Live NHTSA lookup is not reachable from here; it works when the app is installed from its own address.';
  function fetchJSON(url, ms) {
    const ctl = new AbortController(); const t = setTimeout(() => ctl.abort(), ms || 7000);
    return fetch(url, { signal: ctl.signal }).then((r) => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); }).finally(() => clearTimeout(t));
  }
  function snapshotFind(y, mk, md) {
    if (!lookup) return null;
    const k = key(y, mk, md);
    if (lookup[k]) return lookup[k];
    const want = String(md).toLowerCase().replace(/[^a-z0-9]/g, '');
    const hit = Object.keys(lookup).find((kk) => { const [yy, mm, mo] = kk.split('|'); return yy === String(y) && mm === String(mk).toLowerCase().trim() && (mo.replace(/[^a-z0-9]/g, '').startsWith(want) || want.startsWith(mo.replace(/[^a-z0-9]/g, ''))); });
    return hit ? lookup[hit] : null;
  }
  async function liveRecalls(y, mk, md) {
    const u = `https://api.nhtsa.gov/recalls/recallsByVehicle?make=${encodeURIComponent(mk)}&model=${encodeURIComponent(md)}&modelYear=${encodeURIComponent(y)}`;
    const d = await fetchJSON(u);
    return (d.results || []).map(fromLive);
  }
  async function liveDecode(vin) {
    const d = await fetchJSON(`https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValues/${encodeURIComponent(vin)}?format=json`);
    const r = (d.Results || [])[0] || {};
    if (!r.ModelYear || !r.Make || !r.Model) throw new Error('vPIC could not decode that VIN');
    let make = r.Make.length <= 3 ? r.Make.toUpperCase() : r.Make[0] + r.Make.slice(1).toLowerCase();
    return { year: r.ModelYear, make, model: r.Model, trim: (r.Trim || r.Series || '').trim() };
  }
  qs('#checkform').addEventListener('submit', async (e) => {
    e.preventDefault();
    const status = qs('#c-status'), out = qs('#c-result'); out.innerHTML = '';
    const vin = qs('#c-vin').value.trim().toUpperCase();
    let y = qs('#c-year').value.trim(), mk = qs('#c-make').value.trim(), md = qs('#c-model').value.trim();
    const btn = qs('#c-go'); btn.disabled = true;
    try {
      let origin = '', trim = '', foundVin = '';
      if (vin) {
        if (!/^[A-HJ-NPR-Z0-9]{11,17}$/.test(vin)) { status.textContent = 'A VIN is 17 letters and digits (no I, O or Q).'; return; }
        const onLot = data.vehicles.find((v) => v.vin && v.vin.replace(/\*/g, '') === vin.slice(0, v.vin.replace(/\*/g, '').length) && v.vin.length >= 11);
        if (onLot && onLot.vin.toUpperCase() === vin) { status.textContent = 'This VIN is on the lot.'; out.append(card(onLot, 'From this week’s snapshot')); return; }
        status.textContent = 'Decoding the VIN with NHTSA vPIC…';
        try { const d = await liveDecode(vin); y = d.year; mk = d.make; md = d.model; trim = d.trim; foundVin = vin; origin = 'live'; }
        catch (err) {
          status.textContent = LIVE_HINT + ' Enter the year, make and model instead to search the snapshot.';
          return;
        }
      }
      if (!y || !mk || !md) { status.textContent = 'Enter a VIN, or a year, make and model.'; return; }
      status.textContent = `Looking up ${y} ${mk} ${md}…`;
      let campaigns = null, from = '';
      const snap = snapshotFind(y, mk, md);
      try { campaigns = await liveRecalls(y, mk, snap ? snap.api_model || md : md); from = 'Live from NHTSA just now'; }
      catch (err) {
        if (snap && !snap.lookup_failed) { campaigns = snap.campaigns.slice(); from = `From this week’s snapshot (${dateShort(data.checked_at)})`; status.textContent = LIVE_HINT; }
        else if (snap && snap.lookup_failed) { status.textContent = `NHTSA’s API refused ${y} ${mk} ${md} in this week’s run too. Search nhtsa.gov/recalls by hand.`; return; }
        else { status.textContent = `${y} ${mk} ${md} is not in this week’s snapshot. ${LIVE_HINT}`; return; }
      }
      if (from.startsWith('Live')) status.textContent = `NHTSA answered: ${campaigns.length} campaign${campaigns.length === 1 ? '' : 's'} apply to ${y} ${mk} ${md}.`;
      const v = finish({ stock: '', year: y, make: mk, model: md, trim, vin: foundVin, vin_note: '', lookup_failed: false, campaigns });
      out.append(card(v, from));
    } finally { btn.disabled = false; }
  });

  /* ---------- boot ---------- */
  function deriveLookup() {
    const m = {};
    data.vehicles.forEach((v) => { const k = v.lookup_key || key(v.year, v.make, v.model); m[k] = m[k] || { year: v.year, make: v.make, model: v.model, api_model: v.model, lookup_failed: v.lookup_failed, campaigns: v.campaigns }; });
    return m;
  }
  function render() { renderHead(); renderWeek(); renderLot(); }
  async function boot() {
    F.registerSW();
    if (window.RECALL_SNAPSHOT) { data = window.RECALL_SNAPSHOT; render(); }
    try {
      const fresh = await F.loadJSON('data/latest.json');
      if (!data || fresh.generated_at !== data.generated_at) { data = fresh; render(); }
    } catch (e) {
      if (!data) { qs('#lot').append(el('div', { class: 'empty', text: 'Could not load data/latest.json. Run refresh.py.' })); return; }
    }
    lookup = deriveLookup();
    try { const c = await F.loadJSON('data/campaigns.json'); if (c && c.by_key) lookup = Object.assign({}, lookup, c.by_key); } catch (e) { /* snapshot-derived lookup is enough */ }
  }
  boot();
})();
