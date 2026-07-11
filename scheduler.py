"""
GrowStream scheduler — runs as a persistent process (alternative to GHA).

Schedule designed to hit global finance audiences at a deliberately reduced
volume — high-volume AI publishing on YMYL finance topics gets throttled by
Google's Helpful Content system, so fewer, tighter articles index better:
  India morning   →  09:00 IST
  US East morning →  18:30 IST  (08:00 EST)
  US midday       →  20:30 IST  (10:00 EST / 07:00 PST)

Daily output:
  ~6 news articles  (2 × daily_news × 3 categories)
   1 hot take       (US midday)
   1 evergreen      (Mon–Fri, early IST — indexable pillar content)
   Specialist pipelines: Follow-the-Money (Wed), Translated (Thu)

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


def _run(pipeline: str, region: str | None = None) -> None:
    now     = datetime.now().strftime("%Y-%m-%d %H:%M")
    logfile = LOG_DIR / f"{pipeline}_{datetime.now().strftime('%Y%m%d')}.log"
    label   = f"{pipeline}[{region}]" if region else pipeline
    print(f"[{now}] Starting: {label}")
    try:
        cmd = [PYTHON, RUNNER, "--pipeline", pipeline]
        if region:
            cmd += ["--region", region]
        with open(logfile, "a") as f:
            subprocess.run(cmd, cwd=BASE_DIR, stdout=f, stderr=subprocess.STDOUT, check=False)
        print(f"[{now}] Finished: {label}")
    except Exception as e:
        print(f"[{now}] ERROR running {label}: {e}", file=sys.stderr)


# ── Evergreen — Mon–Fri, early IST (indexes before peak traffic) ──────────────
schedule.every().monday.at("07:00").do(_run, "evergreen")
schedule.every().tuesday.at("07:00").do(_run, "evergreen")
schedule.every().wednesday.at("07:00").do(_run, "evergreen")
schedule.every().thursday.at("07:00").do(_run, "evergreen")
schedule.every().friday.at("07:00").do(_run, "evergreen")

# ── Daily News — region-targeted ─────────────────────────────────────────────
# Trimmed from 3 slots to 2 (dropped the London slot) to cut daily article
# volume — see REGIONAL_CATEGORIES note in feeds.py. India + US East give
# broad global coverage across two time zones.
schedule.every().day.at("09:00").do(_run, "daily_news", "india")    # India morning
schedule.every().day.at("18:30").do(_run, "daily_news", "us-east")  # US East morning (08:00 EST)

# ── Hot Takes — US midday only (was India midday + US midday) ─────────────────
schedule.every().day.at("20:30").do(_run, "hot_takes")    # US midday (10:00 EST / 07:00 PST)

# ── Follow the Money — Wednesday only (was Mon / Wed / Fri) ───────────────────
schedule.every().wednesday.at("14:30").do(_run, "follow_the_money") # 09:00 GMT

# ── Translated — Thursday only (was Tue / Thu) ───────────────────────────────
schedule.every().thursday.at("15:00").do(_run, "translated")         # 09:30 GMT

# ── Dumbest Move — Sunday US midday ──────────────────────────────────────────
schedule.every().sunday.at("22:30").do(_run, "dumbest_move")         # 12:00 EST / 09:00 PST


def _maybe_leaderboards():
    if datetime.now().day == 1:
        _run("leaderboards")

schedule.every().day.at("09:30").do(_maybe_leaderboards)             # India morning, 1st of month


if __name__ == "__main__":
    print("GrowStream scheduler started.")
    print()
    print("  Time (IST)   Pipeline              GMT        EST        PST")
    print("  " + "─" * 65)
    slots = [
        ("07:00", "evergreen (Mon-Fri)", "01:30", "20:30(-1)", "17:30(-1)"),
        ("09:00", "daily_news",          "03:30", "22:30(-1)", "19:30(-1)"),
        ("14:30", "follow_the_money(W)", "09:00", "04:00",     "01:00"),
        ("15:00", "translated (Thu)",    "09:30", "04:30",     "01:30"),
        ("18:30", "daily_news",          "13:00", "08:00 ✓",   "05:00"),
        ("20:30", "hot_takes",           "15:00", "10:00 ✓",   "07:00 ✓"),
        ("22:30", "dumbest_move (Sun)",  "17:00", "12:00 ✓",   "09:00 ✓"),
    ]
    for ist, pipe, gmt, est, pst in slots:
        print(f"  {ist:12} {pipe:22} {gmt:10} {est:10} {pst}")
    print()
    while True:
        schedule.run_pending()
        time.sleep(30)
