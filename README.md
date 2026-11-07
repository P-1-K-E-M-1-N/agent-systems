# Agent Systems — Nickolas Lektzian

Selected work from my personal AI-agent projects. I design these systems and direct Claude Code agents to build them. My part is the architecture, the guardrails, and judging the output: what agents are allowed to do, where they must stop for a human, and where their work drifts from the spec.

| Project | What it shows | Where |
|---|---|---|
| **Idea Factory** | One agent system running 11 product ideas in parallel through the same validation gates. Any action that costs money, creates an account, or contacts a real person goes to a human approval queue instead of happening. | [`idea-factory/`](idea-factory/) — start with [`CLAUDE.md`](idea-factory/CLAUDE.md) (the agents' rules) and [`ops/NEEDS_NICK.md`](idea-factory/ops/NEEDS_NICK.md) (the approval queue) |
| **Claude API generation layer** | Server-side copywriting for a short-form video tool: forced tool use for structured output, prompt caching, and a logged fallback when no key is set. | [`claude-api-layer/`](claude-api-layer/) |
| **Multi-agent game studio** | A Godot game built by orchestrator-led agent phases, with a written report after each phase and balance numbers computed from live scene data. | [MrC repository](https://github.com/P-1-K-E-M-1-N/MrC) — see `reports/` |
| **BidRadar** | A weekly unattended scan of the SAM.gov API that scores federal contract opportunities against fixed criteria and publishes a ranked digest. | [BidRadar-v2 repository](https://github.com/P-1-K-E-M-1-N/BidRadar-v2) |

## How the Idea Factory keeps agents in bounds

- **Rules live in one file.** Every lane agent reads [`CLAUDE.md`](idea-factory/CLAUDE.md) before acting.
- **Humans approve side effects.** Lane agents write requests to `lanes/<lane>/needs_nick.md`. `python -m core.board` rolls them up into [`ops/NEEDS_NICK.md`](idea-factory/ops/NEEDS_NICK.md), and nothing in a request happens until a person ticks it off.
- **Licenses are checked before data is used.** The fetcher refuses any source that isn't registered in [`core/registry.py`](idea-factory/core/registry.py) with its license and terms, and a lane whose data doesn't allow commercial use is killed at its first gate.
- **Network use has budgets.** [`core/fetch.py`](idea-factory/core/fetch.py) caches responses and enforces retry and request limits per source.

## What was removed for publication

The working repositories also hold scraped business contact lists, outreach drafts, raw datasets, and my private notes. None of that is in this repository, so some lanes reference `data/`, `samples/` or `outreach/` folders that are not here.
