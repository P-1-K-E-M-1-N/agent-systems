"""Daily factory tick (deterministic part). The scheduled Claude job runs this first, then
does the judgment work (resume in-flight lanes, write LANE.md notes).

What it does:
  0. Read ops/FROM_NICK.md FIRST (Nick's Task Desk hand-back): tick the matching needs_nick box,
     file pasted replies / keyword volumes, log the entry in the lane, resume lanes with no open items.
  1. Ingest ops/INBOX.md bullets into ops/queue.json (new ideas become queued lanes).
  2. Refresh data for every active lane that has a refresh.py (lanes/<slug>/refresh.py).
  3. Promote queued lanes into free slots (creates the lane folder at G0, status active).
  4. Regenerate every ops roll-up (python -m core.board).
  5. Append a line to ops/TICK_LOG.md with what happened and what failed.

Run: python scripts/tick.py [--dry-run] [--no-refresh]
"""
import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core import LANES, OPS  # noqa: E402
from core import board, from_nick, lane as lanemod  # noqa: E402


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def ingest_inbox(dry):
    inbox = OPS / "INBOX.md"
    if not inbox.exists():
        return []
    text = inbox.read_text(encoding="utf-8")
    pat = re.compile(r"^- \*\*(.+?)\*\*\s*\((revenue|traffic)\):\s*(.+)$", re.M)
    found = pat.findall(text)
    if not found:
        return []
    queue = json.loads((OPS / "queue.json").read_text(encoding="utf-8"))
    nxt = max(q["order"] for q in queue) + 1 if queue else 1
    added = []
    for name, kind, pitch in found:
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40]
        if any(q["slug"] == slug for q in queue):
            continue
        queue.append({"order": nxt, "slug": slug, "name": name, "type": kind, "pitch": pitch.strip()})
        added.append(f"{slug} (#{nxt})")
        nxt += 1
    if not dry and added:
        (OPS / "queue.json").write_text(json.dumps(queue, indent=2), encoding="utf-8")
        cleaned = pat.sub("", text)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        if "(empty)" not in cleaned:
            cleaned = cleaned.rstrip() + "\n\n(empty)\n"
        inbox.write_text(cleaned, encoding="utf-8")
    return added


def refresh_lanes(dry):
    results = []
    for d in lanemod.load_all():
        if d["status"] != "active":
            continue
        script = LANES / d["slug"] / "refresh.py"
        if not script.exists():
            continue
        if dry:
            results.append((d["slug"], "would run refresh.py"))
            continue
        try:
            r = subprocess.run([sys.executable, str(script)], cwd=ROOT, capture_output=True, text=True, timeout=600)
            ok = r.returncode == 0
            results.append((d["slug"], "refresh ok" if ok else f"refresh FAILED rc={r.returncode}: {r.stderr[-300:]}"))
        except subprocess.TimeoutExpired:
            results.append((d["slug"], "refresh FAILED: timeout"))
    return results


def promote(dry):
    lanes = lanemod.load_all()
    have = {d["slug"] for d in lanes}
    active = [d for d in lanes if d["status"] in board.ACTIVE_STATUSES]
    free = board.MAX_ACTIVE - len(active)
    queue = json.loads((OPS / "queue.json").read_text(encoding="utf-8"))
    promoted = []
    for q in sorted(queue, key=lambda q: q["order"]):
        if free <= 0:
            break
        if q["slug"] in have:
            continue
        if not dry:
            lanemod.init(q["slug"], q["name"], q["type"], q["order"], q.get("pitch", ""))
        promoted.append(q["slug"])
        free -= 1
    return promoted


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-refresh", action="store_true")
    a = ap.parse_args()
    log = [f"## Tick {now()}" + (" (dry run)" if a.dry_run else "")]
    try:
        for line in from_nick.process(a.dry_run):
            log.append(f"- {line}")
    except Exception as e:  # noqa: BLE001
        log.append(f"- FROM_NICK FAILED: {e}")
    try:
        added = ingest_inbox(a.dry_run)
        log.append(f"- Inbox: {', '.join(added) if added else 'nothing new'}")
    except Exception as e:  # noqa: BLE001
        log.append(f"- Inbox FAILED: {e}")
    if not a.no_refresh:
        for slug, msg in refresh_lanes(a.dry_run):
            log.append(f"- {slug}: {msg}")
    try:
        promoted = promote(a.dry_run)
        log.append(f"- Promoted: {', '.join(promoted) if promoted else 'none (no free slot or empty queue)'}")
    except Exception as e:  # noqa: BLE001
        log.append(f"- Promote FAILED: {e}")
    if not a.dry_run:
        board.render_all()
        log.append("- Board regenerated")
        with open(OPS / "TICK_LOG.md", "a", encoding="utf-8") as f:
            f.write("\n".join(log) + "\n\n")
    print("\n".join(log))


if __name__ == "__main__":
    main()
