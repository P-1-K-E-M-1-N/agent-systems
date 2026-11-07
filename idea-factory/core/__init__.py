"""Idea Factory shared core. Standard library only; nothing to install.

Modules:
  fetch     - cached HTTP fetcher with retries and per-source daily budgets
  registry  - data-source license registry (core/sources.json + lanes/*/sources.json)
  samples   - CSV / HTML / PDF sample-output writers
  outreach  - outreach email + 3-question survey drafts
  scoring   - G3 scoring and GO/PARK/KILL decision
  lane      - lane state (lane.json + LANE.md)
  board     - regenerates every file in /ops from lane state
  usage     - summarises request/time usage per lane and gate
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANES = ROOT / "lanes"
OPS = ROOT / "ops"
CACHE = ROOT / ".cache"
