"""Weekly portfolio digest: one summary of every lane plus what needs Nick.
Writes ops/digests/YYYY-MM-DD.md and prints it. Run: python scripts/digest.py
"""
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core import LANES, OPS  # noqa: E402
from core import lane as lanemod, scoring, usage  # noqa: E402


def main():
    lanes = lanemod.load_all()
    scores = {s["slug"]: s for s in scoring.load_all()}
    lines = [f"# Portfolio digest, week ending {date.today().isoformat()}", ""]
    by_status = {}
    for d in lanes:
        by_status.setdefault(d["status"], []).append(d)
    lines.append("## Where every lane stands")
    lines.append("")
    for status in ("go", "active", "waiting_nick", "parked", "killed", "queued"):
        for d in by_status.get(status, []):
            s = scores.get(d["slug"])
            sc = f" Score {s['total']}/25 -> {s['decision']}." if s else ""
            lines.append(f"- **{d['name']}** [{status}, {d['gate']}]: {d.get('next_step','')}."
                         f"{' Blocker: ' + d['blocker'] + '.' if d.get('blocker') else ''}{sc}")
    lines += ["", "## Needs Nick", ""]
    nn = OPS / "NEEDS_NICK.md"
    if nn.exists():
        open_items = [l for l in nn.read_text(encoding="utf-8").splitlines() if l.lstrip().startswith("- [ ]")]
        lines += open_items or ["Nothing open."]
    lines += ["", "## Data usage this period", "", usage.render_markdown(), ""]
    out = OPS / "digests"
    out.mkdir(exist_ok=True)
    p = out / f"{date.today().isoformat()}.md"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\nwrote {p.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
