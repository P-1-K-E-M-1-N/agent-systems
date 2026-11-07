"""G3 scoring. Five dimensions, each 1-5 (5 = best for the business):
  demand        - evidence people want it (replies, search volume, pain signals)
  repeat_use    - will they come back weekly/monthly (subscription-shaped?)
  competition   - 5 = weak competition, 1 = crowded with strong incumbents
  license       - 5 = clearly commercial-OK public-domain data, 1 = forbidden/unknown
  build_effort  - 5 = days with core, 1 = months

Decision rule (plain language):
  KILL  if license <= 2, or total <= 11, or demand == 1
  GO    if total >= 18 and license >= 4 and demand >= 3 and no dimension below 2
  PARK  otherwise (promising but blocked on evidence, Nick, or a merge)
The demand >= 3 condition was added 2026-10-24 after the first real demand numbers arrived: a lane
with weak measured demand (score 2) could still total 18 and the rule called it GO, which
contradicts "validate before building". GO now needs real demand evidence, not just a high total.
Overlapping lanes should be named in `merge_with` so the scorecard shows it.

    from core.scoring import Score
    s = Score("permit-radar", demand=3, repeat_use=5, competition=3, license=5, build_effort=4,
              reasons={"demand": "...", ...}, merge_with=[])
    s.save()   # writes lanes/<slug>/scorecard.json; board renders ops/SCORECARD.md
"""
import json
from dataclasses import dataclass, field, asdict
from datetime import date

from . import LANES

DIMS = ("demand", "repeat_use", "competition", "license", "build_effort")


@dataclass
class Score:
    slug: str
    demand: int
    repeat_use: int
    competition: int
    license: int
    build_effort: int
    reasons: dict = field(default_factory=dict)
    merge_with: list = field(default_factory=list)
    decision: str = ""
    decision_reason: str = ""
    scored_on: str = field(default_factory=lambda: date.today().isoformat())
    provisional: bool = False  # True = demand score is a guess (no replies / volumes yet); GO is not allowed

    def __post_init__(self):
        for d in DIMS:
            v = getattr(self, d)
            if not 1 <= int(v) <= 5:
                raise ValueError(f"{d} must be 1-5, got {v}")
        if not self.decision:
            self.decision, self.decision_reason = self.decide()
        if self.provisional and self.decision == "GO":
            self.decision = "PARK"
            self.decision_reason = ("PROVISIONAL: rule says GO (" + self.decision_reason +
                                    ") but demand is a guess until replies or search volumes arrive.")
        elif self.provisional:
            self.decision_reason = "PROVISIONAL: " + self.decision_reason

    @property
    def total(self):
        return sum(int(getattr(self, d)) for d in DIMS)

    def decide(self):
        t = self.total
        low = [d for d in DIMS if int(getattr(self, d)) < 2]
        if self.license <= 2:
            return "KILL", f"License score {self.license}: data cannot safely be used commercially."
        if self.demand == 1:
            return "KILL", "No demand evidence at all."
        if t <= 11:
            return "KILL", f"Total {t}/25 is too weak to justify a build."
        if t >= 18 and self.license >= 4 and self.demand >= 3 and not low:
            return "GO", f"Total {t}/25 with safe license, measured demand and no weak dimension."
        why = f"Total {t}/25."
        if t >= 18 and self.demand < 3:
            why += " Demand evidence is weak (score 2), so no GO despite the total."
        if low:
            why += f" Weak on {', '.join(low)}."
        if self.merge_with:
            why += f" Consider merging with {', '.join(self.merge_with)}."
        return "PARK", why

    def save(self):
        p = LANES / self.slug / "scorecard.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        d = asdict(self)
        d["total"] = self.total
        p.write_text(json.dumps(d, indent=2), encoding="utf-8")
        _stamp_gate(self.slug, "G3", finished=not self.provisional,
                    note=f"{self.decision} {self.total}/25" + (" (provisional)" if self.provisional else ""))
        return p


def _stamp_gate(slug, gate, finished=False, note=""):
    """Record gate timing without changing lane status (so timing never depends on agent discipline)."""
    try:
        from . import lane as lanemod
        d = lanemod.load(slug)
        g = d["gates"][gate]
        g["started"] = g["started"] or lanemod._now()
        if finished and not g["finished"]:
            g["finished"] = lanemod._now()
        if note:
            g["note"] = note
        lanemod.save(slug, d)
    except FileNotFoundError:
        pass


def load_all():
    out = []
    if LANES.exists():
        for lane in sorted(LANES.iterdir()):
            p = lane / "scorecard.json"
            if p.exists():
                out.append(json.loads(p.read_text(encoding="utf-8")))
    return out


def render_markdown():
    rows = load_all()
    lines = ["# Scorecard (G3 decisions)", "",
             f"_Generated by `python -m core.board` on {date.today().isoformat()} from lanes/*/scorecard.json._",
             "", "Scores 1-5, 5 = best for us (for competition, 5 = weak competition).", "",
             "| Lane | Demand | Repeat | Competition | License | Effort | Total | Decision | Scored |",
             "|---|---|---|---|---|---|---|---|---|"]
    for r in sorted(rows, key=lambda r: -r["total"]):
        dec = r["decision"] + (" (provisional)" if r.get("provisional") else "")
        lines.append(f"| {r['slug']} | {r['demand']} | {r['repeat_use']} | {r['competition']} | {r['license']} | "
                     f"{r['build_effort']} | **{r['total']}** | **{dec}** | {r['scored_on']} |")
    lines.append("")
    for r in rows:
        lines.append(f"## {r['slug']}: {r['decision']}")
        lines.append("")
        lines.append(r["decision_reason"])
        if r.get("merge_with"):
            lines.append(f"Overlaps with: {', '.join(r['merge_with'])}")
        lines.append("")
        for d in DIMS:
            if r.get("reasons", {}).get(d):
                lines.append(f"- **{d}** = {r[d]}: {r['reasons'][d]}")
        lines.append("")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Score a lane at G3 and save lanes/<slug>/scorecard.json")
    ap.add_argument("slug")
    for d in DIMS:
        ap.add_argument(f"--{d.replace('_', '-')}", type=int, required=True, metavar="1-5")
        ap.add_argument(f"--why-{d.replace('_', '-')}", default="", metavar="TEXT")
    ap.add_argument("--merge-with", nargs="*", default=[])
    ap.add_argument("--provisional", action="store_true", help="demand is a guess; GO not allowed")
    a = ap.parse_args()
    s = Score(a.slug, demand=a.demand, repeat_use=a.repeat_use, competition=a.competition,
              license=a.license, build_effort=a.build_effort, provisional=a.provisional,
              merge_with=a.merge_with,
              reasons={d: getattr(a, f"why_{d}") for d in DIMS if getattr(a, f"why_{d}")})
    p = s.save()
    print(f"{s.slug}: {s.total}/25 -> {s.decision}. {s.decision_reason}\nwrote {p}")
