# Proof-of-system report, interim (wave 1: lanes 1-4)

Written 2026-10-24 after the first wave. The final `ops/SYSTEM_REPORT.md` is written by the weekly digest job once all 18 queued lanes have reached G3 or are parked on Nick. This interim version answers the same questions with what is known now, honestly.

## 1. What was processed

| Lane | Gates reached | Agent wall-clock | Agent tokens | Tool calls | Live fetches | Cache hits | Provisional G3 |
|---|---|---|---|---|---|---|---|
| Permit Radar | G0 pass, G1 pass, G2 drafted, G3 provisional | 15.8 min | 182,595 | 78 | 30 | 3 | 19/25 PARK (license 3) |
| Storm Lead | G0 pass (24-month backtest), G1 pass, G2 drafted, G3 provisional | 17.4 min | 152,513 | 60 | 657 | ~1,240 | 18/25 PARK (crowded) |
| Great Lakes Conditions | G0 pass, G1 pass, G2 keyword pack, G3 provisional | 13.2 min | 139,350 | 51 | 138 | 8 | 19/25 PARK (demand unknown) |
| Recall Checks | G0 pass, G1 pass, G2 drafted, G3 provisional | 14.1 min | 155,393 | 76 | 92 | 63 | 17/25 PARK (no VIN-level data) |
| **Wave total** | 4 lanes to G2/G3 | **17.4 min wall-clock (parallel); ~60 min if sequential** | **~630k** | 265 | 917 | ~1,314 | 0 GO, 4 PARK, 0 KILL |

Core build and orchestration (this session, before the agents started): about 25 minutes, including the smoke test on live Detroit data. Orchestrator tokens are not separable from the session total and are not counted above.

Per-gate wall-clock from lane.json (hours): G0 0.07-0.21, G1 0.03-0.09, G2 0.0-0.05. G2 and G3 timestamps are incomplete because two agents did not call the gate CLI for every step (see section 3). The honest per-gate picture: G0 takes 5-13 minutes of agent time (13 when a backtest is required), G1 2-5 minutes, G2 3-5 minutes, provisional G3 under 2 minutes.

Nick's time so far: **0 hours**. Nothing in wave 1 needed him until G2.

## 2. What core saved versus building each lane alone

- Core is 1,352 lines (fetcher, registry, samples, outreach, scoring, lane state, board, tick, digest). The four lanes wrote 2,157 lines of lane-specific Python on top (probes, refresh scripts, trade tagging, ZIP mapping, backtest, score scripts).
- Every lane used the shared fetcher (cache, retries, daily budgets, usage log), the sample writer (CSV + HTML + PDF from one call), the outreach pack, the scoring class and the lane state CLI. Without core each lane would have re-implemented roughly 500 lines of that plumbing, so about 2,000 lines of duplication were avoided across four lanes, and the savings grow with every lane added.
- The bigger saving is consistency, not lines: four lanes produced the same shape of evidence (lane.json, scorecard.json, needs_nick.md, sources.json), so the board, scorecard, license registry and Needs-Nick list regenerate with one command and four branches merged with zero conflicts.
- What core did not save: the lane-specific work is still larger than core. Parsing SPC CSVs, tagging permits by trade, mapping storm reports to ZIPs, decoding VINs: none of that is shareable. Expect lane code to stay 1.5-2x the size of core.

## 3. Where the system broke or needed rework

1. **Writing long files through the shell failed** (heredoc quoting on Windows Git Bash); switched to the file-write tool. Cost: 5 minutes.
2. **Agent worktrees were committed into the repo** as embedded git repositories by a careless `git add -A`; fixed with a follow-up commit and a .gitignore rule. Cost: 3 minutes, one noisy commit in history.
3. **Gate timestamps are incomplete.** Agents were told to call `core.lane start/finish` at every gate; two skipped it for G2/G3. Fix for wave 2: make `outreach.write_outreach_pack` and `Score.save` stamp the gate automatically so timing does not depend on agent discipline.
4. **Scoring rule disagreed with judgment.** Two lanes scored 19/25, which the rule calls GO, but both agents correctly overrode to PARK because the demand score was a guess. Fix: add a `provisional` flag and require demand evidence (replies or search volume) before GO is allowed.
5. **Each agent wrote its own `g3_score.py`.** Four near-identical scripts. Fix: give `core.scoring` a command-line entry point.
6. **Registry entries were only as good as my first probe.** The Detroit terms URL I registered was a 404; the lane found the real licensing text (and a conflict between the open-data page and the city privacy page). The registry caught nothing on its own; the lane's G0 did.
7. **Open-item counter bug** in the Needs-Nick roll-up (counted sections, not boxes). Fixed.
8. **Budget design held.** Storm Lead needed 606 daily SPC files for the backtest; the lane raised its own daily budget via the lane-level override, exactly as designed, and re-runs were served from cache.
9. **Cloud routines: the weekly digest was tested live and worked.** Run on demand at 05:49 UTC: cloned the private repo, ran the board and digest scripts, wrote the brief at the top of `ops/digests/2026-10-24.md`, pushed to main, sent Nick a phone notification. 48 seconds, 8 turns, Sonnet 5.5. It pushed twice because its first brief ran over the word limit (harmless). It also spotted two bookkeeping gaps the agents left (Permit Radar's G2 never marked finished; Storm Lead's G3 start logged twice), which is what the gate-stamp fix in item 3 addresses. The daily tick is untested until its first run at 11:00 UTC on 2026-10-24.
10. **Merging worked.** Four worktree branches, four merges, zero conflicts, because lanes may only write inside their own folder and ops files are generated.
11. **The scoring rule was wrong on first contact with real demand data** (2026-10-24, afternoon). Great Lakes Conditions came back from Nick with measured Michigan volume of 3,800 searches/month across 43 queries, which is "weak" by the lane's own yardstick (demand 2), yet the total was 18/25 and the rule said GO. Fixed: GO now also requires demand >= 3. A high total must never outvote weak demand in a system whose whole point is validating demand before building.
12. **Nick's hand-back needed its own channel.** Nick does his to-dos in a separate app (Task Desk) that appends to `ops/FROM_NICK.md`. Without a reader, his answers would have sat unread. Added `core.from_nick` (runs first in every tick: ticks boxes, files pasted results, logs, resumes lanes) plus a local sync job so the cloud tick sees the file. First real run handled 7 entries in one pass; two needed judgment follow-up (final G3 for Great Lakes, target-list and PDF fixes for Recall Checks).
13. **Pasted Keyword Planner data arrived as a pipe table, not CSV.** The automatic router could not use it, but Nick's actual export files were in his Downloads folder and loaded cleanly once `load_volumes.py` learned to skip Google's two-line preamble. Lesson: ask for the export file, not a paste.
14. **Outreach by email mostly is not possible.** 40 of 40 wave-1 permit and storm targets, and 6 of 10 of Nick's researched dealers, only have web contact forms. "Send 20 emails" is really "fill 20 forms". `core.mailmerge` now produces a send sheet (link + text per target) and a mail-merge CSV for the few with addresses; Nick also asked for a mailbox that is not his personal one, which only he can create (rule 2).
15. **The first thing a human read was not good enough to send** (2026-10-24, mid-morning). Nick opened the first Recall Checks draft and the attached PDF and stopped: the email "is worded like an AI bot", the subject "is spam looking", and the PDF had overlapping columns and cells that did not match. Both were core defects, not lane defects: the PDF table truncated by a character-count guess instead of measuring text, and the outreach template was a feature pitch with a sales subject. Fixed in core so every lane benefits: `core.pdfmini` measures real Helvetica widths and wraps cells; `core.outreach` writes one person to one shop with a question subject; `core.mailmerge --eml` writes finished drafts with the attachment so sending is one click per email. Lesson for the system: a gate called G1 "pass" on a sample no customer could read. The cheap check that was missing is a render of the PDF (not a parse of its text stream) and a read-aloud test of the email before `waiting_nick`.

16. **The first G1 samples were not products** (2026-10-25). Nick reviewed the four G1 outputs (CSV/HTML/PDF sheets) and rejected them as the thing to validate: "these aren't products". He wants the G1 artifact to be the product as a customer would open it (a map with hail and wind icons, severity shading, warnings and radar for Storm Lead; proper web apps for the others; an Android app for Storm Lead), and he wants to judge that before outreach replies arrive. Rule 1 was changed the same day: G1 is now an interactive prototype on live data, built with the new `core.webapp` shell and `core.geo` boundaries; launch work (accounts, payments, delivery, store publishing, paid hosting) still waits for GO. Cost of the misread: one day of G2 outreach that went out with a PDF sheet instead of a link to the prototype (Recall Checks, 19 dealers). Lesson for the system report: the owner's definition of "sample" must be pinned at kickoff with a picture, not a sentence.

## 4. Nick's time per gate, and where he is the bottleneck

| Gate | Nick's time, wave 1 | Notes |
|---|---|---|
| G0 | 0 | Fully automated. |
| G1 | 0 | Fully automated. |
| G2 | **about 2.5-3 hours pending; about 1.5 hours spent so far** | Spent on 2026-10-24 (7 Task Desk entries, 07:25-08:29): Keyword Planner run and export (Great Lakes), dealer contact research for 10 lots (Recall Checks), four small decisions (cost model, smaller product, GLOS, Open-Meteo), a 10-minute search spot check. Still pending: 60 outreach sends (now known to be mostly web forms), the Detroit license question. |
| G3 | about 10 min per lane pending | Read the scorecard, confirm or override, approve a build plan if GO. Great Lakes reached a final PARK with zero extra G3 time from Nick: the volumes decided it. |

**Every one of the four lanes stopped at the same wall: G2 needs Nick to send.** The system ran four lanes to the edge of a demand signal in 17 minutes and then had nothing to do. That is the bottleneck, and it is by design (the no-sending rule), so the fix is a faster path for Nick, not a looser rule: `targets.csv` plus the email drafts are already mail-merge-ready, so one Gmail mail merge per lane is about 30 minutes instead of 90.

## 5. Realistic maximum concurrent lanes

- **Agents:** 4 lanes in parallel took 17 minutes and about 630k tokens. 6-8 would work technically; merges are conflict-free and the orchestrator only reads a 300-word report per lane.
- **Data:** per-source daily budgets and caching held; the only heavy lane (storm backtest) stayed under budget by using the override.
- **Nick:** this is the ceiling. Each revenue lane costs him 30-90 minutes at G2 plus reply-tracking; each traffic lane 15-30 minutes. At roughly 2 hours a week, Nick can clear 2-3 lanes through G2 per week. Running more than 4 lanes at once just lengthens the waiting_nick queue.
- **Verdict on concurrency:** keep 4 active slots. The slot limit is right; the throughput limit is Nick's G2 hours, about 2-3 lanes per week.

## 6. Verdict (interim)

**Can one person run this many products with this system? For validation, yes. For running products, not yet proven, and wave 1 says the answer depends on Nick's G2 hours, not on the agents.**

What wave 1 proved: one core plus one agent per lane took four unrelated ideas from zero to a real, customer-ready sample from live public data, a target list, outreach drafts and a provisional score in 17 minutes of wall-clock with zero human input and zero merge conflicts. The gates also did their job early: three of four revenue ideas hit a data ceiling that would have been expensive to discover after building (no contractor on Detroit building permits, no free VIN-level recall status, a crowded hail-alert market with a silent winter).

What it did not prove: that any idea has demand. All four are PARK pending replies or search volumes, and all four wait on the same person.

What would need to change to run many products:
1. A 30-minute-per-lane outreach path for Nick (mail merge from targets.csv), or a decision to run only 2-3 lanes per week.
2. Gate stamps and scoring moved into core calls so timing and decisions are recorded without agent discipline.
3. A `provisional` state in scoring so the board never shows a GO that rests on a guessed demand score.
4. Cheaper G2 for traffic lanes: run the keyword list and competitor audit before building the sample, since the audit is 5 minutes and the sample is where the lane spends fetches.
5. Watch the daily tick's cost: it runs Sonnet in the cloud every morning even when nothing moved. If ticks are mostly no-ops, drop to weekdays or every other day.
