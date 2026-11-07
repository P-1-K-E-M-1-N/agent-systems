/* Idea Factory prototype helpers. Plain script, no build step. */
window.Factory = (function () {
  const qs = (sel, el) => (el || document).querySelector(sel);
  const qsa = (sel, el) => Array.from((el || document).querySelectorAll(sel));

  async function loadJSON(path) {
    const r = await fetch(path, { cache: 'no-cache' });
    if (!r.ok) throw new Error(path + ' -> HTTP ' + r.status);
    return r.json();
  }

  /* The review sandbox (claude.ai artifact) blocks images from other hosts. Optional raster layers
     (OpenStreetMap, NOAA radar) must only be added after this resolves true. */
  function canLoadImage(url, timeoutMs) {
    return new Promise((resolve) => {
      const im = new Image();
      const t = setTimeout(() => resolve(false), timeoutMs || 4000);
      im.onload = () => { clearTimeout(t); resolve(true); };
      im.onerror = () => { clearTimeout(t); resolve(false); };
      im.src = url + (url.includes('?') ? '&' : '?') + '_=' + Date.now();
    });
  }

  function registerSW() {
    if (!('serviceWorker' in navigator) || !/^https?:/.test(location.protocol)) return;
    navigator.serviceWorker.register('sw.js').catch(() => {});
  }

  let deferredInstall = null;
  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredInstall = e;
    qsa('[data-install]').forEach((b) => { b.hidden = false; });
  });
  function install() {
    if (!deferredInstall) return false;
    deferredInstall.prompt();
    deferredInstall = null;
    qsa('[data-install]').forEach((b) => { b.hidden = true; });
    return true;
  }

  const fmt = {
    int: (n) => (n == null || isNaN(n)) ? '–' : Number(n).toLocaleString('en-US'),
    money: (n, digits) => (n == null || isNaN(n)) ? '–' : '$' + Number(n).toLocaleString('en-US', { maximumFractionDigits: digits == null ? 0 : digits }),
    date: (iso) => { const d = new Date(iso.length === 10 ? iso + 'T12:00:00' : iso); return isNaN(d) ? iso : d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' }); },
    dateLong: (iso) => { const d = new Date(iso.length === 10 ? iso + 'T12:00:00' : iso); return isNaN(d) ? iso : d.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' }); },
    time: (iso) => { const d = new Date(iso); return isNaN(d) ? iso : d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' }); },
    ago: (iso) => {
      const s = (Date.now() - new Date(iso).getTime()) / 1000;
      if (isNaN(s)) return '';
      if (s < 90) return 'just now';
      if (s < 5400) return Math.round(s / 60) + ' min ago';
      if (s < 172800) return Math.round(s / 3600) + ' h ago';
      return Math.round(s / 86400) + ' days ago';
    },
  };

  function el(tag, attrs, children) {
    const e = document.createElement(tag);
    if (attrs) for (const k in attrs) {
      if (k === 'class') e.className = attrs[k];
      else if (k === 'text') e.textContent = attrs[k];
      else if (k === 'html') e.innerHTML = attrs[k];
      else if (k.startsWith('on')) e.addEventListener(k.slice(2), attrs[k]);
      else if (attrs[k] != null) e.setAttribute(k, attrs[k]);
    }
    (children || []).forEach((c) => e.append(c));
    return e;
  }

  function copy(text, btn) {
    const done = () => { if (btn) { const t = btn.textContent; btn.textContent = 'Copied'; setTimeout(() => { btn.textContent = t; }, 1200); } };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done).catch(() => fallback());
    } else fallback();
    function fallback() {
      const ta = el('textarea', { style: 'position:fixed;opacity:0' }); ta.value = text; document.body.append(ta);
      ta.select(); try { document.execCommand('copy'); done(); } catch (e) {} ta.remove();
    }
  }

  /* Remembered per-viewer conveniences only; never state that matters. */
  const store = {
    get: (k, d) => { try { const v = localStorage.getItem(k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } },
    set: (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} },
  };

  /* Sequential color ramp between two CSS colors for choropleths, t in [0,1]. */
  function ramp(t, from, to) {
    const a = parse(from), b = parse(to);
    const m = a.map((x, i) => Math.round(x + (b[i] - x) * Math.max(0, Math.min(1, t))));
    return 'rgb(' + m.join(',') + ')';
    function parse(c) {
      const ctx = parse.ctx || (parse.ctx = document.createElement('canvas').getContext('2d'));
      ctx.fillStyle = c; const h = ctx.fillStyle; // normalised to #rrggbb
      return [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
    }
  }

  function cssVar(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }

  return { qs, qsa, loadJSON, canLoadImage, registerSW, install, fmt, el, copy, store, ramp, cssVar };
})();
