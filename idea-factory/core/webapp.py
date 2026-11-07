"""Scaffold, check and bundle a lane's G1 prototype: a static web app in lanes/<slug>/app/.

Rule 1 (2026-10-25): the G1 sample is the product as a customer would open it. This module gives
every lane the same shell so the lane agent only writes index.html, app.js and the data files.

    python -m core.webapp scaffold storm-lead --title "Storm Lead" --short "Storm Lead" --color "#1f4e79" \
        --desc "Morning-after hail and wind map for Michigan roofers"
    python -m core.webapp check storm-lead        # files, title, size, external hosts, forbidden APIs
    python -m core.webapp bundle storm-lead       # JSON map of published-path -> file, for publishing

What scaffold writes (never overwrites an existing index.html or app.js):
    app/index.html            starter page (replace it)
    app/app.js                starter script (replace it)
    app/assets/factory.css    shared tokens, both themes, layout and components (copied from core/web)
    app/assets/factory.js     shared helpers: loadJSON, canLoadImage, install prompt, fmt (copied)
    app/manifest.webmanifest  installable PWA manifest
    app/sw.js                 service worker: cache the shell, network-first for data/
    app/icons/icon-192.png, icon-512.png, icon.svg
    app/data/                 the lane's refresh script writes JSON here

Constraints the check enforces (they come from where the prototype is reviewed and hosted):
  - browser libraries only from the CDN allowlist, pinned to an exact version;
  - every other external host is reported: it must be an optional layer the page turns on only after
    Factory.canLoadImage() succeeds, because the artifact sandbox blocks images and fetches from other hosts;
  - no alert/confirm/prompt, no window.print, no mailto forms, no accounts, payments or tracking scripts;
  - whole app under 16 MB.
"""
import json
import re
import shutil
import struct
import sys
import zlib
from pathlib import Path

from . import LANES, ROOT

WEB = ROOT / "core" / "web"
CDN_ALLOW = ("cdnjs.cloudflare.com", "cdn.jsdelivr.net", "unpkg.com", "fonts.googleapis.com", "fonts.gstatic.com")
FORBIDDEN = [(r"(?<![.\w])alert\s*\(", "alert() never shows in the review sandbox"),
             (r"(?<![.\w])confirm\s*\(", "confirm() returns false in the review sandbox"),
             (r"(?<![.\w])prompt\s*\(", "prompt() returns null in the review sandbox"),
             (r"window\.print", "print dialog is blocked"),
             (r"action\s*=\s*[\"']mailto:", "mailto forms do not work"),
             (r"stripe|paypal|lemonsqueezy|gumroad", "payments are launch work (after GO)"),
             (r"googletagmanager|google-analytics|gtag\(|plausible\.io|hotjar", "no tracking scripts before GO (and no people data)")]


def app_dir(slug):
    return LANES / slug / "app"


# ---------- icons (stdlib PNG) ----------
def _hex(c):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def _png(size, bg, fg):
    """Flat icon: rounded square in bg with a centered disc in fg. Enough for an installable manifest."""
    r = size * 0.18
    cx = cy = size / 2
    disc = size * 0.28
    rows = []
    for y in range(size):
        row = bytearray([0])
        for x in range(size):
            # rounded-square mask
            dx = max(r - x - 0.5, x + 0.5 - (size - r), 0)
            dy = max(r - y - 0.5, y + 0.5 - (size - r), 0)
            inside = dx * dx + dy * dy <= r * r
            if not inside:
                row += bytes((0, 0, 0, 0))
                continue
            d = ((x + 0.5 - cx) ** 2 + (y + 0.5 - cy) ** 2) ** 0.5
            col = fg if d <= disc else bg
            row += bytes(col) + b"\xff"
        rows.append(bytes(row))
    raw = b"".join(rows)

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff)
    ihdr = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")


def _svg_icon(bg, fg, letter):
    return (f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><rect width='100' height='100' rx='18' fill='{bg}'/>"
            f"<circle cx='50' cy='50' r='28' fill='{fg}'/><text x='50' y='61' font-family='system-ui,sans-serif' font-size='34' "
            f"font-weight='700' text-anchor='middle' fill='{bg}'>{letter}</text></svg>")


# ---------- scaffold ----------
def scaffold(slug, title, short=None, color="#1f4e79", desc="", accent=None, force=False):
    d = app_dir(slug)
    for sub in ("assets", "icons", "data"):
        (d / sub).mkdir(parents=True, exist_ok=True)
    short = short or title
    accent = accent or "#f2b134"
    shutil.copy(WEB / "factory.css", d / "assets" / "factory.css")
    shutil.copy(WEB / "factory.js", d / "assets" / "factory.js")
    (d / "icons" / "icon-192.png").write_bytes(_png(192, _hex(color), _hex(accent)))
    (d / "icons" / "icon-512.png").write_bytes(_png(512, _hex(color), _hex(accent)))
    (d / "icons" / "icon.svg").write_text(_svg_icon(color, accent, short[0].upper()), encoding="utf-8")
    manifest = {"name": title, "short_name": short[:12], "description": desc, "start_url": "./index.html",
                "scope": "./", "display": "standalone", "orientation": "any", "background_color": color,
                "theme_color": color,
                "icons": [{"src": "icons/icon-192.png", "sizes": "192x192", "type": "image/png"},
                          {"src": "icons/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"}]}
    (d / "manifest.webmanifest").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    sw = (WEB / "sw.js").read_text(encoding="utf-8").replace("{{CACHE}}", f"{slug}-v1").replace(
        "{{SHELL}}", json.dumps(["./", "./index.html", "./app.js", "./assets/factory.css", "./assets/factory.js",
                                 "./manifest.webmanifest", "./icons/icon-192.png"]))
    (d / "sw.js").write_text(sw, encoding="utf-8")
    if force or not (d / "index.html").exists():
        (d / "index.html").write_text((WEB / "starter.html").read_text(encoding="utf-8")
                                      .replace("{{TITLE}}", title).replace("{{DESC}}", desc).replace("{{COLOR}}", color),
                                      encoding="utf-8")
    if force or not (d / "app.js").exists():
        (d / "app.js").write_text((WEB / "starter.js").read_text(encoding="utf-8").replace("{{TITLE}}", title),
                                  encoding="utf-8")
    return d


# ---------- check ----------
def check(slug):
    d = app_dir(slug)
    problems, notes = [], []
    if not d.exists():
        return [f"{d} does not exist; run scaffold first"], []
    idx = d / "index.html"
    if not idx.exists():
        problems.append("index.html missing")
    else:
        html = idx.read_text(encoding="utf-8", errors="replace")
        if not re.search(r"<title>[^<]{3,}</title>", html):
            problems.append("index.html has no <title>")
        if "viewport" not in html:
            problems.append("index.html has no viewport meta (phone layout)")
        if "manifest.webmanifest" not in html:
            problems.append("index.html does not link manifest.webmanifest")
        if "factory.css" not in html:
            notes.append("index.html does not use assets/factory.css (shared tokens/themes)")
    texts = {p: p.read_text(encoding="utf-8", errors="replace") for p in d.rglob("*") if p.suffix in (".html", ".js", ".css")}
    hosts = {}
    for p, t in texts.items():
        for m in re.finditer(r"https?://([a-z0-9.-]+)[^\s\"'`)<>]*", t, re.I):
            hosts.setdefault(m.group(1).lower(), set()).add(p.name)
        for pat, why in FORBIDDEN:
            if re.search(pat, t, re.I):
                problems.append(f"{p.relative_to(d)}: {why}")
        for m in re.finditer(r"<script[^>]+src=[\"'](https?://[^\"']+)", t, re.I):
            url = m.group(1)
            if not url.lower().startswith(tuple(f"https://{h}" for h in CDN_ALLOW)):
                problems.append(f"{p.name}: script from non-allowlisted host {url}")
            elif not re.search(r"/\d+\.\d+(\.\d+)?/|@\d+\.\d+\.\d+", url):
                problems.append(f"{p.name}: library not pinned to an exact version: {url}")
    ext = {h: sorted(fs) for h, fs in hosts.items() if h not in CDN_ALLOW}
    if ext:
        notes.append("external hosts (must be optional layers, loaded only after Factory.canLoadImage succeeds): "
                     + "; ".join(f"{h} in {', '.join(fs)}" for h, fs in sorted(ext.items())))
    size = sum(p.stat().st_size for p in d.rglob("*") if p.is_file())
    if size > 16 * 1024 * 1024:
        problems.append(f"app is {size / 1e6:.1f} MB; limit 16 MB")
    notes.append(f"{sum(1 for p in d.rglob('*') if p.is_file())} files, {size / 1024:.0f} KB")
    data = sorted((d / "data").glob("*.json")) if (d / "data").exists() else []
    if not data:
        problems.append("app/data has no JSON: the refresh script must write the live data the page renders")
    else:
        notes.append("data: " + ", ".join(f"{p.name} ({p.stat().st_size // 1024} KB)" for p in data))
    return problems, notes


# ---------- bundle ----------
def bundle(slug, prefix=None):
    """{published_path: absolute_source_path} for every file under app/, prefixed by the slug."""
    d = app_dir(slug)
    prefix = slug if prefix is None else prefix
    out = {}
    for p in sorted(d.rglob("*")):
        if p.is_file():
            rel = p.relative_to(d).as_posix()
            out[f"{prefix}/{rel}" if prefix else rel] = str(p)
    return out


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="G1 prototype shell for a lane")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scaffold"); s.add_argument("slug"); s.add_argument("--title", required=True)
    s.add_argument("--short"); s.add_argument("--color", default="#1f4e79"); s.add_argument("--accent")
    s.add_argument("--desc", default=""); s.add_argument("--force", action="store_true")
    c = sub.add_parser("check"); c.add_argument("slug")
    b = sub.add_parser("bundle"); b.add_argument("slug")
    a = ap.parse_args()
    if a.cmd == "scaffold":
        print("scaffolded", scaffold(a.slug, a.title, a.short, a.color, a.desc, a.accent, a.force))
    elif a.cmd == "check":
        probs, notes = check(a.slug)
        for n in notes:
            print("note:", n)
        for p in probs:
            print("PROBLEM:", p)
        print("OK" if not probs else f"{len(probs)} problem(s)")
        sys.exit(1 if probs else 0)
    else:
        print(json.dumps(bundle(a.slug), indent=1))
