"""
News bot scheduler — publishes 10 articles per day across two daily_news runs
plus specialist pipelines (hot_takes, follow_the_money, translated, dumbest_move).

Usage:
    venv/bin/python3.13 scheduler.py

Runs as a persistent process. Use a process manager (systemd, supervisor, screen)
or the crontab entries in README to keep it alive.

Schedule:
    08:00  daily_news      → 5 articles (morning news cycle)
    11:00  hot_takes       → 1 article  (daily opinion)
    14:00  daily_news      → 5 articles (afternoon news cycle)
    10:00  follow_the_money→ 1 article  (Mon/Wed/Fri)
    10:00  translated      → 1 article  (Tue/Thu)
    09:00  dumbest_move    → 1 article  (Sunday)
"""

import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import schedule

BASE_DIR = Path(__file__).parent
PYTHON   = str(BASE_DIR / "venv/bin/python3.13")
RUNNER   = str(BASE_DIR / "run.py")
LOG_DIR  = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)


def _run(pipeline: str) -> None:
    now     = datetime.now().strftime("%Y-%m-%d %H:%M")
    logfile = LOG_DIR / f"{pipeline}_{datetime.now().strftime('%Y%m%d')}.log"
    print(f"[{now}] Starting pipeline: {pipeline}")
    try:
        with open(logfile, "a") as f:
            subprocess.run(
                [PYTHON, RUNNER, "--pipeline", pipeline],
                cwd=BASE_DIR,
                stdout=f,
                stderr=subprocess.STDOUT,
                check=False,
            )
        print(f"[{now}] Finished: {pipeline}")
    except Exception as e:
        print(f"[{now}] ERROR running {pipeline}: {e}", file=sys.stderr)


# ── Daily schedules ──────────────────────────────────────────────────────────

schedule.every().day.at("08:00").do(_run, "daily_news")
schedule.every().day.at("11:00").do(_run, "hot_takes")
schedule.every().day.at("14:00").do(_run, "daily_news")

# ── Weekly / multi-day schedules ─────────────────────────────────────────────

schedule.every().monday.at("10:00").do(_run, "follow_the_money")
schedule.every().wednesday.at("10:00").do(_run, "follow_the_money")
schedule.every().friday.at("10:00").do(_run, "follow_the_money")

schedule.every().tuesday.at("10:00").do(_run, "translated")
schedule.every().thursday.at("10:00").do(_run, "translated")

schedule.every().sunday.at("09:00").do(_run, "dumbest_move")

# First of the month — leaderboards
# (schedule library doesn't support "first of month" natively;
#  check the date inside a daily job instead)
def _maybe_leaderboards():
    if datetime.now().day == 1:
        _run("leaderboards")

schedule.every().day.at("09:30").do(_maybe_leaderboards)


if __name__ == "__main__":
    print("GrowStream scheduler started.")
    print("Jobs scheduled:")
    for job in schedule.get_jobs():
        print(f"  {job}")
    print()

    while True:
        schedule.run_pending()
        time.sleep(30)
