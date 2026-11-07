"""Regenerate every roll-up file in /ops from lane state. Lanes never edit /ops directly;
they write inside lanes/<slug>/ and this script aggregates. Run after any lane change:

    python -m core.board

Writes: ops/STATUS.md, ops/NEEDS_NICK.md, ops/SCORECARD.md, ops/DATA_SOURCES.md
Reads:  lanes/*/lane.json, lanes/*/needs_nick.md, lanes/*/scorecard.json, ops/queue.json
"""
import json
from datetime import datetime, timezone

from . import LANES, OPS
from . import lane as lanemod
from . import registry, scoring

MAX_ACTIVE = 4
ACTIVE_STATUSES = ("active",)


def _queue():
    q = OPS / "queue.json"
    return json.loads(q.read_text(encoding="utf-8")) if q.exists() else []


def render_status():
    lanes = lanemod.load_all()
    have = {d["slug"] for d in lanes}
    queued = [q for q in _queue() if q["slug"] not in have]
    active = [d for d in lanes if d["status"] in ACTIVE_STATUSES]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = ["# Portfolio board", "",
             f"_Regenerated {now} by `python -m core.board`. Slots: {len(active)}/{MAX_ACTIVE} active. "
             f"Lanes with folders: {len(lanes)}. Queued without a folder: {len(queued)}._", "",
             "Gates: G0 data check, G1 sample, G2 demand test, G3 decision, PLAN build plan awaiting approval.", "",
             "| # | Lane | Type | Gate | Status | Blocker | Next step | Last update |",
             "|---|---|---|---|---|---|---|---|"]
    for d in lanes:
        upd = d.get("updated", "")[:16].replace("T", " ")
        lines.append(f"| {d['order']} | [{d['name']}](../lanes/{d['slug']}/LANE.md) | {d['type']} | {d['gate']} | "
                     f"**{d['status']}** | {d.get('blocker','') or ''} | {d.get('next_step','')} | {upd} |")
    for q in queued:
        lines.append(f"| {q['order']} | {q['name']} | {q['type']} | - | queued | | waiting for a free slot | |")
    lines += ["", "## Gate timing (hours of wall-clock per gate, from lane.json)", "",
              "| Lane | " + " | ".join(lanemod.GATES) + " |", "|---|" + "---|" * len(lanemod.GATES)]
    for d in lanes:
        h = lanemod.gate_hours(d)
        lines.append(f"| {d['slug']} | " + " | ".join(str(h.get(g, "")) for g in lanemod.GATES) + " |")
    lines += ["", "## Slot rules", "",
              f"- At most {MAX_ACTIVE} lanes `active` at once. `waiting_nick`, `parked`, `killed`, `go` do not hold a slot.",
              "- The daily tick promotes the lowest-numbered queued lane into a free slot.",
              "- Merge candidates are flagged at G3 (see SCORECARD.md).", ""]
    return "\n".join(lines)


def render_needs_nick():
    lines = ["# Needs Nick", "",
             "_Rolled up from lanes/*/needs_nick.md plus ops/needs_nick_global.md by `python -m core.board`. "
             "Tick a box in the lane file when done; this file is regenerated._", ""]
    g = OPS / "needs_nick_global.md"
    if g.exists():
        lines += ["## Factory-wide", "", g.read_text(encoding="utf-8").strip(), ""]
    if LANES.exists():
        for lane_dir in sorted(LANES.iterdir()):
            f = lane_dir / "needs_nick.md"
            if f.exists():
                body = f.read_text(encoding="utf-8").strip()
                body = "\n".join(l for l in body.splitlines() if not l.startswith("# "))
                if body.strip():
                    lines += [f"## {lane_dir.name}", "", body.strip(), ""]
    open_items = sum(1 for l in "\n".join(lines).splitlines() if l.lstrip().startswith("- [ ]"))
    lines.insert(2, f"**Open items: {open_items}**")
    lines.insert(3, "")
    return "\n".join(lines) + "\n"


def render_all():
    OPS.mkdir(exist_ok=True)
    (OPS / "STATUS.md").write_text(render_status(), encoding="utf-8")
    (OPS / "NEEDS_NICK.md").write_text(render_needs_nick(), encoding="utf-8")
    (OPS / "SCORECARD.md").write_text(scoring.render_markdown(), encoding="utf-8")
    (OPS / "DATA_SOURCES.md").write_text(registry.render_markdown(), encoding="utf-8")
    return ["ops/STATUS.md", "ops/NEEDS_NICK.md", "ops/SCORECARD.md", "ops/DATA_SOURCES.md"]


if __name__ == "__main__":
    for f in render_all():
        print("wrote", f)
