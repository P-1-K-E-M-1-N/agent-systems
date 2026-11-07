"""Lane state. Each lane folder holds:
  lane.json      machine state (gate, status, blocker, next_step, gate timings)
  LANE.md        human-readable: summary + evidence + decision + running log
  sources.json   data sources this lane registered (merged into the license registry)
  needs_nick.md  things only Nick can do (rolled up into ops/NEEDS_NICK.md)
  scorecard.json G3 score (rolled up into ops/SCORECARD.md)
  usage.jsonl    every fetch the lane made (for the system report)
  data/ samples/ outreach/

Statuses: queued | active | waiting_nick | parked | killed | go
Gates:    G0 | G1 | G2 | G3 | PLAN (build plan written, awaiting approval)

CLI (what subagents call):
  python -m core.lane permit-radar start G1 "fetching 7 days of permits"
  python -m core.lane permit-radar finish G1 pass "sample.pdf produced from 143 permits"
  python -m core.lane permit-radar status waiting_nick --blocker "needs Keyword Planner numbers" --next "..."
  python -m core.lane permit-radar log "any note"
"""
import argparse
import json
from datetime import datetime, timezone

from . import LANES

GATES = ["G0", "G1", "G2", "G3", "PLAN"]
STATUSES = ["queued", "active", "waiting_nick", "parked", "killed", "go"]


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def path(slug):
    return LANES / slug / "lane.json"


def load(slug):
    p = path(slug)
    if not p.exists():
        raise FileNotFoundError(f"lane {slug} has no lane.json; run core.lane init first")
    return json.loads(p.read_text(encoding="utf-8"))


def save(slug, data):
    data["updated"] = _now()
    p = path(slug)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def init(slug, name, kind, order, pitch="", sources=()):
    if path(slug).exists():
        return load(slug)
    data = {"slug": slug, "name": name, "type": kind, "order": order, "pitch": pitch,
            "gate": "G0", "status": "active", "blocker": "", "next_step": "G0 data check",
            "gates": {g: {"started": None, "finished": None, "result": None, "note": ""} for g in GATES},
            "merge_candidates": [], "created": _now()}
    (LANES / slug / "data").mkdir(parents=True, exist_ok=True)
    (LANES / slug / "samples").mkdir(parents=True, exist_ok=True)
    md = LANES / slug / "LANE.md"
    if not md.exists():
        md.write_text(f"# {name}\n\n**Type:** {kind}  |  **Queue order:** {order}\n\n{pitch}\n\n"
                      "## Current state\n\n(see lane.json; board regenerates ops/STATUS.md)\n\n"
                      "## G0 Data check\n\n_pending_\n\n## G1 Sample\n\n_pending_\n\n## G2 Demand test\n\n_pending_\n\n"
                      "## G3 Decision\n\n_pending_\n\n## Log\n\n", encoding="utf-8")
    sj = LANES / slug / "sources.json"
    if not sj.exists():
        sj.write_text(json.dumps({"sources": list(sources)}, indent=2), encoding="utf-8")
    return save(slug, data)


def log(slug, msg):
    md = LANES / slug / "LANE.md"
    with open(md, "a", encoding="utf-8") as f:
        f.write(f"- {_now()} {msg}\n")


def start_gate(slug, gate, note=""):
    d = load(slug)
    d["gate"] = gate
    d["status"] = "active"
    d["gates"][gate]["started"] = d["gates"][gate]["started"] or _now()
    if note:
        d["gates"][gate]["note"] = note
    save(slug, d)
    log(slug, f"{gate} started. {note}")
    return d


def finish_gate(slug, gate, result, note=""):
    """result: pass | fail | go | park | kill"""
    d = load(slug)
    g = d["gates"][gate]
    g["finished"] = _now()
    g["result"] = result
    g["note"] = note or g["note"]
    if result in ("fail", "kill"):
        d["status"] = "killed"
        d["next_step"] = "none (killed)"
    elif result == "park":
        d["status"] = "parked"
    elif result == "go":
        d["status"] = "go"
        d["gate"] = "PLAN"
        d["next_step"] = "write one-page build plan, then wait for Nick's approval"
    else:
        nxt = GATES[min(GATES.index(gate) + 1, len(GATES) - 1)]
        d["gate"] = nxt
        d["next_step"] = f"{nxt}"
    save(slug, d)
    log(slug, f"{gate} finished: {result}. {note}")
    return d


def set_status(slug, status, blocker=None, next_step=None):
    d = load(slug)
    d["status"] = status
    if blocker is not None:
        d["blocker"] = blocker
    if next_step is not None:
        d["next_step"] = next_step
    save(slug, d)
    log(slug, f"status -> {status}. blocker: {d['blocker']}. next: {d['next_step']}")
    return d


def gate_hours(d):
    out = {}
    for g, v in d["gates"].items():
        if v["started"] and v["finished"]:
            a = datetime.fromisoformat(v["started"])
            b = datetime.fromisoformat(v["finished"])
            out[g] = round((b - a).total_seconds() / 3600, 2)
    return out


def load_all():
    out = []
    if LANES.exists():
        for lane_dir in sorted(LANES.iterdir()):
            if (lane_dir / "lane.json").exists():
                out.append(load(lane_dir.name))
    return sorted(out, key=lambda d: d.get("order", 99))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("cmd", choices=["init", "start", "finish", "status", "log", "show"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--blocker")
    ap.add_argument("--next")
    ap.add_argument("--name")
    ap.add_argument("--type", dest="kind", choices=["revenue", "traffic"])
    ap.add_argument("--order", type=int, default=99)
    a = ap.parse_args()
    if a.cmd == "init":
        print(json.dumps(init(a.slug, a.name or a.slug, a.kind or "revenue", a.order, " ".join(a.args)), indent=1))
    elif a.cmd == "start":
        start_gate(a.slug, a.args[0], " ".join(a.args[1:]))
    elif a.cmd == "finish":
        finish_gate(a.slug, a.args[0], a.args[1], " ".join(a.args[2:]))
    elif a.cmd == "status":
        set_status(a.slug, a.args[0], a.blocker, a.next)
    elif a.cmd == "log":
        log(a.slug, " ".join(a.args))
    else:
        print(json.dumps(load(a.slug), indent=1))
