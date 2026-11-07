"""Summarise fetch usage per lane and gate from lanes/*/usage.jsonl and ops/usage/core.jsonl.
Run: python -m core.usage
"""
import json
from collections import defaultdict

from . import LANES, OPS


def _iter_records():
    files = []
    if (OPS / "usage" / "core.jsonl").exists():
        files.append(OPS / "usage" / "core.jsonl")
    if LANES.exists():
        files += [p / "usage.jsonl" for p in LANES.iterdir() if (p / "usage.jsonl").exists()]
    for f in files:
        with open(f, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError:
                        continue


def summarize():
    agg = defaultdict(lambda: {"requests": 0, "cache_hits": 0, "errors": 0, "bytes": 0, "ms": 0, "sources": set()})
    for r in _iter_records():
        k = (r["lane"], r["gate"])
        a = agg[k]
        if r.get("cache_hit"):
            a["cache_hits"] += 1
        else:
            a["requests"] += 1
        if r.get("error"):
            a["errors"] += 1
        a["bytes"] += r.get("bytes", 0)
        a["ms"] += r.get("ms", 0)
        a["sources"].add(r["source"])
    return agg


def render_markdown():
    agg = summarize()
    lines = ["| Lane | Gate | Live requests | Cache hits | Errors | MB | Fetch time (s) | Sources |",
             "|---|---|---|---|---|---|---|---|"]
    for (lane, gate), a in sorted(agg.items()):
        lines.append(f"| {lane} | {gate} | {a['requests']} | {a['cache_hits']} | {a['errors']} | "
                     f"{a['bytes']/1e6:.1f} | {a['ms']/1000:.1f} | {', '.join(sorted(a['sources']))} |")
    return "\n".join(lines)


if __name__ == "__main__":
    print(render_markdown())
