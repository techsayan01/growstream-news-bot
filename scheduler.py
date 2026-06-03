"""
GrowStream scheduler — runs as a persistent process (alternative to GHA).

Daily output:
  15 news articles  (3 × daily_news runs of 5 each)
  2  hot takes      (morning + evening)
  1  evergreen      (Mon–Fri)
  Specialist pipelines on rotation

Usage:
    venv/bin/python3.13 scheduler.py
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
    print(f"[{now}] Starting: {pipeline}")
    try:
        with open(logfile, "a") as f:
            subprocess.run(
                [PYTHON, RUNNER, "--pipeline", pipeline],
                cwd=BASE_DIR, stdout=f, stderr=subprocess.STDOUT, check=False,
            )
        print(f"[{now}] Finished: {pipeline}")
    except Exception as e:
        print(f"[{now}] ERROR running {pipeline}: {e}", file=sys.stderr)


# ── Daily News — 3 runs ───────────────────────────────────────────────────────
schedule.every().day.at("08:30").do(_run, "daily_news")
schedule.every().day.at("12:30").do(_run, "daily_news")
schedule.every().day.at("17:00").do(_run, "daily_news")

# ── Hot Takes — 2 per day ─────────────────────────────────────────────────────
schedule.every().day.at("11:00").do(_run, "hot_takes")
schedule.every().day.at("18:30").do(_run, "hot_takes")

# ── Evergreen — Mon to Fri ────────────────────────────────────────────────────
schedule.every().monday.at("07:00").do(_run, "evergreen")
schedule.every().tuesday.at("07:00").do(_run, "evergreen")
schedule.every().wednesday.at("07:00").do(_run, "evergreen")
schedule.every().thursday.at("07:00").do(_run, "evergreen")
schedule.every().friday.at("07:00").do(_run, "evergreen")

# ── Specialist pipelines ──────────────────────────────────────────────────────
schedule.every().monday.at("10:00").do(_run, "follow_the_money")
schedule.every().wednesday.at("10:00").do(_run, "follow_the_money")
schedule.every().friday.at("10:00").do(_run, "follow_the_money")

schedule.every().tuesday.at("10:00").do(_run, "translated")
schedule.every().thursday.at("10:00").do(_run, "translated")

schedule.every().sunday.at("09:00").do(_run, "dumbest_move")


def _maybe_leaderboards():
    if datetime.now().day == 1:
        _run("leaderboards")

schedule.every().day.at("09:30").do(_maybe_leaderboards)


if __name__ == "__main__":
    print("GrowStream scheduler started.")
    print("\nDaily output target:")
    print("  15 news articles  (08:30, 12:30, 17:00)")
    print("   2 hot takes      (11:00, 18:30)")
    print("   1 evergreen      (07:00 Mon-Fri)")
    print("   + specialists on rotation")
    print("\nJobs scheduled:")
    for job in schedule.get_jobs():
        print(f"  {job}")
    print()
    while True:
        schedule.run_pending()
        time.sleep(30)
