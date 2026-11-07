# Automations

Exactly two scheduled jobs run the factory. Both are Claude Code **cloud routines** (they run in Anthropic's cloud on your plan, clone this GitHub repo, do their work, and push commits back to `main`). No extra paid service is involved; they consume Claude usage on your account. Manage both at https://claude.ai/code/routines.

| Job | Schedule (UTC cron) | Local time | Model | Routine link |
|---|---|---|---|---|
| Daily factory tick | `0 11 * * *` | 7:00 am EDT (6:00 am EST after Nov 1; change cron to `0 12 * * *` in winter if the hour matters) | Sonnet 5.5 | https://claude.ai/code/routines/trig_01RQTsfXsHnEHEsxmfxmq17C |
| Weekly portfolio digest | `0 22 * * 0` | Sunday 6:00 pm EDT (5:00 pm EST after Nov 1) | Sonnet 5.5 | https://claude.ai/code/routines/trig_01JiMECL9zpw1VhWxebnUpxm |

## What the daily tick does
1. `git pull`, then `python scripts/tick.py`. First thing it does is read **`ops/FROM_NICK.md`** (written by Nick's Task Desk when you mark a task Done or Skip): for every entry it has not seen before it ticks the matching box in the lane's `needs_nick.md`, files anything you pasted (replies to `outreach/replies.md`, Keyword Planner exports to `data/keyword_volumes.csv`, a raw copy in `lanes/<slug>/from_nick/`), writes a line in the lane log, and records the entry in `ops/from_nick_ledger.jsonl` so it is never handled twice. A lane with no open Nick items left goes back to `active`. Then it ingests `ops/INBOX.md` into `ops/queue.json`, runs each active lane's `refresh.py`, promotes queued lanes into free slots (max 4 active), regenerates the ops roll-ups and appends to `ops/TICK_LOG.md`.
2. Continues every lane you handed back, from your notes (final G3 score, kill, merge, or next gate), and says in LANE.md which FROM_NICK entry it acted on.
3. Advances each other **active** lane by at most one gate, following `CLAUDE.md`. Since 2026-10-25 the G1 gate means building the prototype web app in `lanes/<slug>/app/` (shell from `core.webapp`, live data from the lane's `refresh.py`), so a G1 tick can take the whole run.
4. For lanes **waiting on you**: if replies or keyword volumes have arrived, it finishes G3 and, on GO, writes `lanes/<slug>/BUILD_PLAN.md` and stops.
5. Commits and pushes. Read `ops/TICK_LOG.md` for the plain-language summary.

## Local sync helper (not a factory job: plumbing between your PC and GitHub)
The Task Desk writes `ops/FROM_NICK.md` on your PC; the cloud tick reads the GitHub copy. `scripts\sync_from_nick.cmd` bridges the two: it pulls the latest tick results, commits `ops/FROM_NICK.md` if it changed, and pushes. It runs daily at 6:45 am local time (Windows Task Scheduler task **IdeaFactory sync FROM_NICK**, 15 minutes before the tick) and on demand from the desktop shortcut **Sync Idea Factory**. Log: `ops/usage/sync_log.txt`. To remove it: `schtasks /Delete /TN "IdeaFactory sync FROM_NICK" /F`. If you skip the sync, the cloud tick simply sees yesterday's FROM_NICK.md; nothing breaks, it just lags a day.

## What the weekly digest does
Runs `scripts/digest.py`, writes `ops/digests/<date>.md` with a plain-language brief (what moved, decisions, your top 3 to-dos, stalls, anything waiting on you more than 7 days). When every lane has reached G3 or is parked on you, it writes `ops/SYSTEM_REPORT.md` if it does not exist.

## How to pause
- **Pause one job:** open its routine link above and toggle it off, or tell Claude Code: "pause the Idea Factory daily tick routine" (it uses `RemoteTrigger update {enabled:false}`).
- **Pause everything:** toggle both routines off. Nothing else runs on a schedule.
- **Delete:** only possible from https://claude.ai/code/routines.
- **Run now:** open the routine and click Run, or ask Claude Code to run it.

## Local alternative (if you prefer the jobs on your PC)
Windows Task Scheduler can run `python C:\MrC\idea-factory\scripts\tick.py` daily and `python C:\MrC\idea-factory\scripts\digest.py` weekly. That covers the deterministic parts (refresh, promote, board, digest tables) but not the judgment work (advancing gates, writing briefs). Pause the cloud routines first so the two do not fight over `main`.

## Known limits
- The cloud routine cannot see your local machine. Everything it needs must be committed to the repo.
- API keys for future lanes must be added as environment variables in the routine's cloud environment (https://claude.ai/code/environments), never committed.
- Minimum routine interval is 1 hour; both jobs are far above that.
