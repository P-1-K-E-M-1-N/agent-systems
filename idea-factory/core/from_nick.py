"""Hand-back from Nick's Task Desk (C:\\MrC\\task-desk).

The Task Desk appends one entry to ops/FROM_NICK.md every time Nick marks a task DONE or
SKIPPED. That file is append-only and belongs to the app: this module only READS it.

Entry shape (written by task-desk/src/main/handback.js):

    ## 2026-10-24 02:46 · permit-radar · DONE
    **Task:** <needs_nick item text, bold markers removed>
    **Steps ticked:** 1/5                      (optional)
    **Nick's notes:** <free text or (none)>
    **Pasted results:**                        (optional)
    - <label>:
        <value, indented 4 spaces>
    ---

On every daily tick, `process()` runs FIRST and, for each entry not yet in the ledger
(ops/from_nick_ledger.jsonl):
  1. ticks the matching `- [ ]` box in lanes/<lane>/needs_nick.md (or ops/needs_nick_global.md
     for lane "factory") so it drops off ops/NEEDS_NICK.md;
  2. files pasted results where the lane expects them: outreach reply tallies -> outreach/replies.md,
     keyword exports -> data/keyword_volumes.csv, and every entry -> a raw copy in
     lanes/<slug>/from_nick/ (ops/from_nick/ for factory-wide items);
  3. writes a line in the lane log (LANE.md) naming the FROM_NICK entry;
  4. sets lane.json next_step to "resume from FROM_NICK ..." and, when no open boxes remain
     for a waiting_nick lane, flips it back to active so the tick agent continues it.
The judgment part (actually continuing the lane from Nick's notes) is done by the tick agent,
which reads the summary this module prints.

CLI: python -m core.from_nick [--dry-run]
"""
import argparse
import hashlib
import json
import re
from datetime import datetime, timezone

from . import LANES, OPS
from . import lane as lanemod

FROM_NICK = OPS / "FROM_NICK.md"
LEDGER = OPS / "from_nick_ledger.jsonl"
GLOBAL_NEEDS = OPS / "needs_nick_global.md"

HEAD_RE = re.compile(r"^## (\d{4}-\d{2}-\d{2} \d{2}:\d{2}) \u00b7 (.+?) \u00b7 (DONE|SKIPPED)\s*$", re.M)


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _norm(s):
    return re.sub(r"\s+", " ", re.sub(r"[`*_]", "", s or "")).strip().lower()


def _title(task):
    """Short title for a task: text up to the '(YYYY-MM-DD)' stamp or the first sentence break."""
    m = re.match(r"(.+?)(?:\s\(|[.:]\s|$)", task.strip())
    t = m.group(1) if m and len(m.group(1)) >= 12 else task.strip()
    return t[:90]


# ---------- parsing ----------
def parse(text):
    entries = []
    heads = list(HEAD_RE.finditer(text))
    for i, m in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        block = text[m.start():end]
        body = block[m.end() - m.start():]
        task = re.search(r"\*\*Task:\*\*\s*(.+?)(?=\n\n|\n\*\*|\n---|\Z)", body, re.S)
        ticked = re.search(r"\*\*Steps ticked:\*\*\s*(\S+)", body)
        notes = re.search(r"\*\*Nick's notes:\*\*\s*(.*?)(?=\n\*\*Pasted results:\*\*|\n---\s*(?:\n|\Z)|\Z)",
                          body, re.S)
        results = []
        pr = re.search(r"\*\*Pasted results:\*\*\n(.*?)(?=\n---\s*(?:\n|\Z)|\Z)", body, re.S)
        if pr:
            cur = None
            for line in pr.group(1).splitlines():
                lab = re.match(r"^- (.+):\s*$", line)
                if lab and not line.startswith("    "):
                    cur = {"label": lab.group(1).strip(), "lines": []}
                    results.append(cur)
                elif cur is not None:
                    if line.startswith("    "):
                        cur["lines"].append(line[4:])
                    elif line.strip() == "":
                        cur["lines"].append("")
            for r in results:
                r["value"] = "\n".join(r.pop("lines")).strip()
        notes_txt = notes.group(1).strip() if notes else ""
        if notes_txt.lower() == "(none)":
            notes_txt = ""
        entries.append({
            "id": hashlib.sha1(block.strip().encode("utf-8")).hexdigest()[:12],
            "stamp": m.group(1), "lane": m.group(2).strip(), "status": m.group(3),
            "task": re.sub(r"\s+", " ", task.group(1)).strip() if task else "",
            "ticked": ticked.group(1) if ticked else "",
            "notes": notes_txt, "results": results, "raw": block.strip(),
        })
    return entries


def load_ledger():
    seen = {}
    if LEDGER.exists():
        for line in LEDGER.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                seen[rec["id"]] = rec
    return seen


def pending():
    """Entries in FROM_NICK.md that the factory has not handled yet (oldest first)."""
    if not FROM_NICK.exists():
        return []
    seen = load_ledger()
    return [e for e in parse(FROM_NICK.read_text(encoding="utf-8")) if e["id"] not in seen]


# ---------- ticking the box ----------
def _items(lines):
    """Yield (first_line_index, last_line_index, full_text) for each open '- [ ]' item incl. continuation lines."""
    i = 0
    while i < len(lines):
        m = re.match(r"^\s*[-*]\s+\[ \]\s+(.*)$", lines[i])
        if m:
            start, parts = i, [m.group(1)]
            j = i + 1
            while j < len(lines) and re.match(r"^\s{2,}\S", lines[j]):
                parts.append(lines[j].strip())
                j += 1
            yield start, j - 1, " ".join(parts)
            i = j
        else:
            i += 1


def tick_box(needs_file, task, status, stamp, dry=False):
    """Mark the matching open box as [x]. Returns the matched item text or None."""
    if not needs_file.exists() or not task:
        return None
    lines = needs_file.read_text(encoding="utf-8").splitlines()
    want = _norm(task)
    want_title = _norm(_title(task))
    best = None
    for start, end, text in _items(lines):
        got = _norm(text)
        if got == want:
            best = (0, start, text)
            break
        if want_title and got.startswith(want_title) and (best is None or best[0] > 1):
            best = (1, start, text)
        elif got[:80] == want[:80] and best is None:
            best = (2, start, text)
    if best is None:
        return None
    _, start, text = best
    lines[start] = lines[start].replace("[ ]", "[x]", 1) + f" _({status} via FROM_NICK {stamp})_"
    if not dry:
        needs_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return text


def open_boxes(needs_file):
    if not needs_file.exists():
        return 0
    return sum(1 for l in needs_file.read_text(encoding="utf-8").splitlines()
               if re.match(r"^\s*[-*]\s+\[ \]", l))


# ---------- filing results ----------
def _looks_tabular(v):
    rows = [l for l in v.splitlines() if l.strip()]
    return len(rows) >= 2 and all(("," in l or "\t" in l) for l in rows[:3])


def file_results(entry, lane_dir, dry=False):
    """Save the raw entry and route pasted results to where the lane expects them."""
    filed = []
    raw_dir = lane_dir / "from_nick"
    raw_name = f"{entry['stamp'].replace(' ', '_').replace(':', '')}_{entry['id']}.md"
    filed.append(f"from_nick/{raw_name}")
    if not dry:
        raw_dir.mkdir(parents=True, exist_ok=True)
        (raw_dir / raw_name).write_text(entry["raw"] + "\n", encoding="utf-8")
    hay = (entry["task"] + " " + " ".join(r["label"] for r in entry["results"])).lower()
    for r in entry["results"]:
        lab, val = r["label"], r["value"]
        if not val:
            continue
        keywordish = re.search(r"keyword|volume", lab.lower()) or "keyword" in hay
        if keywordish and _looks_tabular(val):
            target = lane_dir / "data" / "keyword_volumes.csv"
            has_rows = target.exists() and len([l for l in target.read_text(encoding="utf-8-sig", errors="replace")
                                                .splitlines() if l.strip()]) > 1
            if has_rows:  # keep an earlier real export; a header-only template is overwritten
                target = lane_dir / "data" / f"keyword_volumes_{entry['id']}.csv"
            filed.append(f"data/{target.name}")
            if not dry:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(val + "\n", encoding="utf-8")
        elif (lane_dir / "outreach").is_dir() and re.search(r"outreach|survey", hay) \
                and re.search(r"repl|tally|answer", lab.lower() + " " + hay):
            target = lane_dir / "outreach" / "replies.md"
            filed.append("outreach/replies.md")
            if not dry:
                target.parent.mkdir(parents=True, exist_ok=True)
                with open(target, "a", encoding="utf-8") as f:
                    f.write(f"\n## From Nick, {entry['stamp']} ({entry['status']}): {lab}\n\n{val}\n")
    return filed


# ---------- main ----------
def handle(entry, dry=False):
    lane = entry["lane"]
    is_factory = lane.lower() in ("factory", "factory-wide", "ops")
    title = _title(entry["task"])
    if is_factory:
        needs, lane_dir, has_lane = GLOBAL_NEEDS, OPS, False
    else:
        lane_dir = LANES / lane
        needs = lane_dir / "needs_nick.md"
        has_lane = (lane_dir / "lane.json").exists()
    matched = tick_box(needs, entry["task"], entry["status"], entry["stamp"], dry)
    filed = file_results(entry, lane_dir, dry) if (is_factory or lane_dir.exists()) else []
    remaining = open_boxes(needs)
    resumed = False
    if has_lane and not dry:
        d = lanemod.load(lane)
        d["next_step"] = f"resume from FROM_NICK {entry['stamp']} ({entry['status']}): {title}"
        if d["status"] == "waiting_nick" and remaining == 0:
            d["status"], d["blocker"], resumed = "active", "", True
        lanemod.save(lane, d)
        lanemod.log(lane, f"FROM_NICK {entry['stamp']} ({entry['status']}, entry {entry['id']}): \"{title}\". "
                          f"Box ticked: {'yes' if matched else 'NO MATCH, tick by hand'}. "
                          f"Filed: {', '.join(filed) or 'nothing'}. "
                          f"Notes: {entry['notes'] or '(none)'}"
                          + (" Lane set back to active: no open Nick items left." if resumed else "")
                          + " Tick agent: continue this lane from these notes.")
    rec = {"id": entry["id"], "stamp": entry["stamp"], "lane": lane, "status": entry["status"], "title": title,
           "box_ticked": bool(matched), "filed": filed, "remaining_open": remaining, "resumed": resumed,
           "handled": _now()}
    if not dry:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with open(LEDGER, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
    return rec


def process(dry=False):
    """Handle every unhandled entry. Returns plain-language summary lines for the tick log."""
    out = []
    if not FROM_NICK.exists():
        return ["FROM_NICK.md: file not present yet (Task Desk creates it on first Done/Skip)"]
    todo = pending()
    if not todo:
        return ["FROM_NICK.md: nothing new"]
    for e in todo:
        rec = handle(e, dry)
        line = (f"FROM_NICK {rec['stamp']} / {rec['lane']} / {rec['status']}: \"{rec['title']}\" -> "
                f"box {'ticked' if rec['box_ticked'] else 'NOT FOUND (tick by hand)'}; "
                f"filed {', '.join(rec['filed']) or 'nothing'}; {rec['remaining_open']} Nick item(s) still open"
                + ("; lane back to active" if rec["resumed"] else ""))
        if e["notes"]:
            line += f". Nick's notes: {e['notes'][:300]}"
        out.append(line)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Handle new entries in ops/FROM_NICK.md")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    for line in process(a.dry_run):
        print(line)
