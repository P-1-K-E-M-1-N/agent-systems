@echo off
rem Sync Nick's local Idea Factory checkout with GitHub so the cloud tick can see
rem ops/FROM_NICK.md (written locally by Nick's Task Desk) and so the Task Desk sees
rem the boxes the cloud tick ticked. Safe to run any time; it only commits FROM_NICK.md.
rem
rem   1. pull the latest tick results (rebase keeps any local commits on top)
rem   2. commit ops/FROM_NICK.md if it changed
rem   3. push
rem
rem Scheduled daily at 6:45 am (Task Scheduler task "IdeaFactory sync FROM_NICK"),
rem also runnable from the desktop shortcut "Sync Idea Factory".
setlocal
cd /d C:\MrC\idea-factory
set LOG=ops\usage\sync_log.txt
echo ==== %date% %time% >> %LOG%
git pull --rebase --autostash origin main >> %LOG% 2>&1
if exist ops\FROM_NICK.md (
  git add ops\FROM_NICK.md
  git diff --cached --quiet || git commit -m "from Nick: Task Desk hand-back %date%" >> %LOG% 2>&1
)
git push origin main >> %LOG% 2>&1
echo done >> %LOG%
endlocal
