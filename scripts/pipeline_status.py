"""
pipeline_status.py
Runs at 09:00 daily — checks whether the 06:00 pipeline actually ran and
sends a Telegram summary so you always know the pipeline state.

Reports:
  - Did BootHop-TikTok run today?
  - Exit code (0 = OK, 1 = crash/timeout)
  - How many videos are in today's output folder
  - Whether a crash was logged in pipeline_crash.log
  - Music status (are daily tracks ready?)
  - Quick action list if something is wrong
"""

import sys, os, json, subprocess
from pathlib import Path
from datetime import datetime, date

sys.path.insert(0, str(Path(__file__).parent.parent))
try:
    if hasattr(sys.stdout, "reconfigure") and sys.stdout.encoding != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from config import TELEGRAM_TOKEN as TOKEN, TELEGRAM_CHAT_ID as CHAT_ID, BASE

try:
    import requests
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "-q"])
    import requests


def send(text: str):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": text[:4096], "parse_mode": "Markdown"},
            timeout=15,
        )
    except Exception as e:
        print(f"Telegram send failed: {e}")


def task_info(task_name: str) -> dict:
    """Query Task Scheduler for last run time, result and status."""
    try:
        r = subprocess.run(
            ["schtasks", "/query", "/tn", task_name, "/fo", "list", "/v"],
            capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
        info = {}
        for line in r.stdout.splitlines():
            if "Last Run Time" in line:
                info["last_run"] = line.split(":", 1)[1].strip()
            elif "Last Result" in line:
                info["last_result"] = line.split(":", 1)[1].strip()
            elif "Status" in line and "status" not in info:
                info["status"] = line.split(":", 1)[1].strip()
        return info
    except Exception:
        return {}


def ran_today(task_info_dict: dict) -> bool:
    lr = task_info_dict.get("last_run", "")
    today_str = datetime.now().strftime("%d/%m/%Y")
    return today_str in lr


def count_videos(folder: Path) -> int:
    if not folder.exists():
        return 0
    return len(list(folder.glob("*.mp4")))


def last_crash_entry() -> str:
    log = BASE / "data" / "pipeline_crash.log"
    if not log.exists():
        return ""
    try:
        lines = log.read_text(encoding="utf-8", errors="replace").strip().splitlines()
        # Only show entries from today
        today = datetime.now().strftime("%Y-%m-%d")
        today_lines = [l for l in lines if today in l]
        if today_lines:
            return "\n".join(today_lines[-6:])
    except Exception:
        pass
    return ""


def music_status() -> str:
    daily = BASE / "music" / "daily"
    tracks = [f for f in ["track_1.mp3", "track_2.mp3", "track_3.mp3"]
              if (daily / f).exists()]
    if len(tracks) == 3:
        return "OK (3/3 tracks ready)"
    elif tracks:
        return f"Partial ({len(tracks)}/3 tracks)"
    return "MISSING - no daily tracks downloaded"


def main():
    today      = datetime.now().strftime("%Y-%m-%d")
    day_name   = datetime.now().strftime("%A")
    out_folder = BASE / "output" / today

    tiktok  = task_info("BootHop-TikTok")
    after   = task_info("BootHop-Afternoon")
    morning = task_info("BootHopMorning")

    tiktok_ran   = ran_today(tiktok)
    tiktok_ok    = tiktok_ran and tiktok.get("last_result", "1") == "0"
    morning_ran  = ran_today(morning)
    videos_today = count_videos(out_folder)
    crash_log    = last_crash_entry()
    music        = music_status()

    # Determine overall status
    if tiktok_ok and videos_today >= 4:
        overall = "GOOD"
        icon    = "OK"
    elif tiktok_ran and not tiktok_ok:
        overall = "ERROR"
        icon    = "FAIL"
    elif not tiktok_ran:
        overall = "MISSED"
        icon    = "WARN"
    else:
        overall = "PARTIAL"
        icon    = "WARN"

    lines = [
        f"[{icon}] *BootHop Pipeline - {day_name} {today}*",
        "",
        f"*06:00 Pipeline (TikTok):*",
        f"  Ran today:  {'YES' if tiktok_ran else 'NO - computer may have been off at 06:00'}",
        f"  Exit code:  {tiktok.get('last_result','?')} ({'OK' if tiktok_ok else 'FAIL' if tiktok_ran else 'N/A'})",
        f"  Videos out: {videos_today} in output/{today}/",
        "",
        f"*05:45 Morning (main.py):*  {'Ran OK' if morning_ran else 'Did NOT run'}",
        f"*Music:*  {music}",
    ]

    if crash_log:
        lines += ["", "*Crash log (today):*", f"```\n{crash_log[:600]}\n```"]

    if overall == "MISSED":
        lines += [
            "",
            "*Action:* Run pipeline manually now:",
            "`python pipeline.py`",
            "Or wait — it will run at 12:30 (Afternoon slot).",
        ]
    elif overall == "ERROR":
        lines += [
            "",
            "*Action:* Check crash log at `data/pipeline_crash.log`",
            "Re-run: `python pipeline.py`",
        ]

    lines += [
        "",
        f"12:30 Afternoon | 18:00 Evening — still to come today.",
    ]

    send("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
