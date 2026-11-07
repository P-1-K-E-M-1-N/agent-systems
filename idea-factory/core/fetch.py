"""Cached, budgeted HTTP fetcher (the "God's Eye View" pattern):
  * API keys stay server-side: read from environment variables named in the registry,
    never written to cache, logs or output.
  * Every response is cached on disk (.cache/<source>/<hash>.json) with a per-source TTL.
  * Per-source daily request budgets and a minimum interval between calls.
  * Retries with exponential backoff on 429 / 5xx / network errors; honours Retry-After.
  * Every request is logged to lanes/<lane>/usage.jsonl so the system report can
    account for calls, cache hits and latency per lane and gate.

Usage:
    from core.fetch import Fetcher
    f = Fetcher("detroit_permits", lane="permit-radar", gate="G1")
    data = f.get_json(url, params={...})
"""
import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

from . import CACHE, LANES, OPS
from . import registry

USER_AGENT = "IdeaFactory/0.1 (open-data validation; github P-1-K-E-M-1-N)"
# A source may set "user_agent" in its registry entry when the host requires a contact address
# (SEC fair-access rule). Set per source, never globally, so the address only goes where it is required.


class BudgetExceeded(Exception):
    pass


class FetchError(Exception):
    pass


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Fetcher:
    def __init__(self, source_id, lane="core", gate="G0", allow_noncommercial=False,
                 cache_dir=None, timeout=45):
        self.source = registry.get(source_id)
        registry.check_commercial(source_id, allow_noncommercial)
        self.source_id = source_id
        self.lane = lane
        self.gate = gate
        self.timeout = timeout
        self.cache_dir = Path(cache_dir) if cache_dir else CACHE / source_id
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.budget_file = CACHE / "budgets.json"
        self.ttl = int(self.source.get("cache_ttl_s", 6 * 3600))
        self.daily_budget = int(self.source.get("daily_budget", 500))
        self.min_interval = float(self.source.get("min_interval_s", 0))
        self._last_call = 0.0
        self.stats = {"requests": 0, "cache_hits": 0, "errors": 0, "bytes": 0, "ms": 0}

    # ---------- key handling ----------
    def _apply_key(self, url, params, headers):
        key_env = self.source.get("key_env")
        if not key_env:
            return url, params, headers
        key = os.environ.get(key_env, "")
        if not key:
            raise FetchError(f"Source '{self.source_id}' needs an API key in env var {key_env} (free tier). "
                             "If Nick must sign up, put the request in the lane's needs_nick.md.")
        if self.source.get("key_header"):
            headers = {**headers, self.source["key_header"]: key}
        else:
            params = {**params, self.source.get("key_param", "api_key"): key}
        return url, params, headers

    def _redact(self, url):
        key_env = self.source.get("key_env")
        key = os.environ.get(key_env, "") if key_env else ""
        return url.replace(key, "<KEY>") if key else url

    # ---------- cache ----------
    def _cache_path(self, url, params, body):
        raw = url + "|" + json.dumps(params, sort_keys=True) + "|" + (body or "")
        return self.cache_dir / (hashlib.sha1(raw.encode()).hexdigest() + ".json")

    def _cache_read(self, p, ttl):
        if not p.exists():
            return None
        age = time.time() - p.stat().st_mtime
        if age > ttl:
            return None
        with open(p, encoding="utf-8") as f:
            return json.load(f)

    # ---------- budget ----------
    def _budget_take(self):
        self.budget_file.parent.mkdir(parents=True, exist_ok=True)
        today = date.today().isoformat()
        data = {}
        if self.budget_file.exists():
            try:
                data = json.loads(self.budget_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                data = {}
        used = data.get(self.source_id, {}).get(today, 0)
        if used >= self.daily_budget:
            raise BudgetExceeded(
                f"Daily budget for '{self.source_id}' ({self.daily_budget}) exhausted. "
                "Use cached data or wait until tomorrow.")
        data[self.source_id] = {today: used + 1}  # keep only today
        self.budget_file.write_text(json.dumps(data, indent=1), encoding="utf-8")
        return used + 1

    def budget_used_today(self):
        if not self.budget_file.exists():
            return 0
        data = json.loads(self.budget_file.read_text(encoding="utf-8"))
        return data.get(self.source_id, {}).get(date.today().isoformat(), 0)

    # ---------- logging ----------
    def _log(self, url, cache_hit, status, ms, nbytes, error=""):
        rec = {"ts": _now(), "lane": self.lane, "gate": self.gate, "source": self.source_id,
               "url": self._redact(url)[:300], "cache_hit": cache_hit, "status": status,
               "ms": ms, "bytes": nbytes, "error": error}
        if self.lane == "core":
            target = OPS / "usage" / "core.jsonl"
        else:
            target = LANES / self.lane / "usage.jsonl"
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")

    # ---------- main ----------
    def get(self, url, params=None, headers=None, ttl=None, body=None, method="GET",
            retries=4, force=False):
        """Return (text, status). Served from cache unless force=True or the TTL expired."""
        params = dict(params or {})
        headers = {"User-Agent": self.source.get("user_agent") or USER_AGENT, "Accept": "*/*", **(headers or {})}
        ttl = self.ttl if ttl is None else ttl
        cpath = self._cache_path(url, params, body)
        if not force:
            hit = self._cache_read(cpath, ttl)
            if hit is not None:
                self.stats["cache_hits"] += 1
                self._log(url, True, hit["status"], 0, len(hit["text"]))
                return hit["text"], hit["status"]

        url_k, params_k, headers_k = self._apply_key(url, params, headers)
        full = url_k + ("?" + urllib.parse.urlencode(params_k, doseq=True) if params_k else "")
        self._budget_take()

        delay = 1.0
        last_err = ""
        for attempt in range(retries + 1):
            wait = self.min_interval - (time.time() - self._last_call)
            if wait > 0:
                time.sleep(wait)
            t0 = time.time()
            try:
                req = urllib.request.Request(full, data=body.encode() if body else None,
                                             headers=headers_k, method=method)
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    text = r.read().decode(r.headers.get_content_charset() or "utf-8", "replace")
                    status = r.status
                self._last_call = time.time()
                ms = int((time.time() - t0) * 1000)
                self.stats["requests"] += 1
                self.stats["bytes"] += len(text)
                self.stats["ms"] += ms
                cpath.write_text(json.dumps({"fetched_at": _now(), "url": self._redact(full),
                                             "status": status, "text": text}), encoding="utf-8")
                self._log(url, False, status, ms, len(text))
                return text, status
            except urllib.error.HTTPError as e:
                self._last_call = time.time()
                last_err = f"HTTP {e.code}"
                if e.code in (429, 500, 502, 503, 504) and attempt < retries:
                    ra = e.headers.get("Retry-After")
                    sleep_for = float(ra) if ra and ra.isdigit() else delay
                    time.sleep(min(sleep_for, 60))
                    delay *= 2
                    continue
                self.stats["errors"] += 1
                self._log(url, False, e.code, int((time.time() - t0) * 1000), 0, last_err)
                raise FetchError(f"{last_err} for {self._redact(full)}") from e
            except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
                last_err = f"{type(e).__name__}: {e}"
                if attempt < retries:
                    time.sleep(delay)
                    delay *= 2
                    continue
                self.stats["errors"] += 1
                self._log(url, False, 0, int((time.time() - t0) * 1000), 0, last_err)
                raise FetchError(f"{last_err} for {self._redact(full)}") from e
        raise FetchError(last_err)

    def get_bytes(self, url, params=None, headers=None, ttl=None, force=False):
        """Return raw bytes (zip, PDF, images). Cached like get(), stored base64 in the JSON cache."""
        import base64
        params = dict(params or {})
        headers = {"User-Agent": self.source.get("user_agent") or USER_AGENT, "Accept": "*/*", **(headers or {})}
        ttl = self.ttl if ttl is None else ttl
        cpath = self._cache_path(url, params, "<bytes>")
        if not force:
            hit = self._cache_read(cpath, ttl)
            if hit is not None and "b64" in hit:
                self.stats["cache_hits"] += 1
                self._log(url, True, hit["status"], 0, hit.get("bytes", 0))
                return base64.b64decode(hit["b64"])
        url_k, params_k, headers_k = self._apply_key(url, params, headers)
        full = url_k + ("?" + urllib.parse.urlencode(params_k, doseq=True) if params_k else "")
        self._budget_take()
        t0 = time.time()
        try:
            req = urllib.request.Request(full, headers=headers_k)
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                data = r.read()
                status = r.status
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            self.stats["errors"] += 1
            self._log(url, False, getattr(e, "code", 0), int((time.time() - t0) * 1000), 0, str(e))
            raise FetchError(f"{e} for {self._redact(full)}") from e
        self._last_call = time.time()
        ms = int((time.time() - t0) * 1000)
        self.stats["requests"] += 1
        self.stats["bytes"] += len(data)
        self.stats["ms"] += ms
        cpath.write_text(json.dumps({"fetched_at": _now(), "url": self._redact(full), "status": status,
                                     "bytes": len(data), "b64": base64.b64encode(data).decode()}), encoding="utf-8")
        self._log(url, False, status, ms, len(data))
        return data

    def get_json(self, url, params=None, **kw):
        text, _ = self.get(url, params, **kw)
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise FetchError(f"Non-JSON response from {url}: {text[:200]}") from e

    def get_text(self, url, params=None, **kw):
        return self.get(url, params, **kw)[0]


def arcgis_query_all(fetcher, layer_url, where="1=1", out_fields="*", order_by=None,
                     max_records=5000, page=1000, extra=None):
    """Page through an ArcGIS FeatureServer layer; returns a list of attribute dicts."""
    out, offset = [], 0
    while offset < max_records:
        params = {"where": where, "outFields": out_fields, "f": "json",
                  "resultOffset": offset, "resultRecordCount": min(page, max_records - offset),
                  "returnGeometry": "false"}
        if order_by:
            params["orderByFields"] = order_by
        if extra:
            params.update(extra)
        data = fetcher.get_json(layer_url.rstrip("/") + "/query", params)
        if "error" in data:
            raise FetchError(f"ArcGIS error: {data['error']}")
        feats = data.get("features", [])
        out.extend(f["attributes"] for f in feats)
        if not data.get("exceededTransferLimit") or not feats:
            break
        offset += len(feats)
    return out
