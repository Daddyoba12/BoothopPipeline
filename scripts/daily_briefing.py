"""
daily_briefing.py
Runs at 07:00 every morning.
Sends a Telegram briefing showing:
  - Whether 06:00 pipeline ran + how many videos
  - Today's bucket, theme, and sample hooks
  - What's still coming (12:30 and 18:00 runs)
  - Yesterday's social posts
  - Blog system status
  - Any warnings that need attention

Broadcasting: add extra Telegram chat IDs to BROADCAST_IDS below to
send the same briefing to friends / team members every morning.
"""

import sys, os, json, subprocess
from pathlib import Path
from datetime import datetime, date, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))
try:
    if hasattr(sys.stdout, "reconfigure") and sys.stdout.encoding != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from config import TELEGRAM_TOKEN as TOKEN, TELEGRAM_CHAT_ID as MY_CHAT_ID, BASE

try:
    import requests
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "-q"])
    import requests

# ── Add extra Telegram chat IDs here to broadcast to friends / team ─────────
# Each ID gets the same morning briefing automatically.
# To find someone's chat ID: they message @userinfobot on Telegram.
BROADCAST_IDS: list[str] = [
    # "123456789",   # example: friend 1
    # "-100987654321",  # example: group chat
]

ALL_CHATS = [MY_CHAT_ID] + BROADCAST_IDS

DAY_BUCKETS = {
    0: "business",
    1: "family",
    2: "airport",
    3: "smart",
    4: "cinematic",
    5: "community",
    6: "community",
}

WEEKLY_THEMES = {
    0: "Problem Awareness",
    1: "Social Proof & Trust",
    2: "Aspiration & Lifestyle",
    3: "Community & Culture",
}

BUCKET_EMOJI = {
    "business":  "💼",
    "family":    "❤️",
    "airport":   "✈️",
    "smart":     "🧠",
    "cinematic": "🎬",
    "community": "🌍",
}

DATA        = BASE / "data"
OUTPUT      = BASE / "output"
BLOG_LOG    = BASE / "blog" / "gmail_blog_log.txt"
CRASH_LOG   = DATA / "pipeline_crash.log"
POST_LOG    = DATA / "post_log.json"
USED_CONTENT = DATA / "used_content.json"


def send(chat_id: str, text: str):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={"chat_id": chat_id, "text": text[:4096], "parse_mode": "Markdown"},
            timeout=15,
        )
    except Exception as e:
        print(f"Telegram send failed ({chat_id}): {e}")


def task_last_result(task_name: str) -> dict:
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
        return info
    except Exception:
        return {}


def count_videos(folder: Path) -> int:
    if not folder.exists():
        return 0
    return len(list(folder.glob("*.mp4")))


def posts_yesterday() -> list[dict]:
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    if not POST_LOG.exists():
        return []
    try:
        all_posts = json.loads(POST_LOG.read_text(encoding="utf-8"))
        return [p for p in all_posts if p.get("date") == yesterday]
    except Exception:
        return []


def posts_today() -> list[dict]:
    today = date.today().isoformat()
    if not POST_LOG.exists():
        return []
    try:
        all_posts = json.loads(POST_LOG.read_text(encoding="utf-8"))
        return [p for p in all_posts if p.get("date") == today]
    except Exception:
        return []


def blog_status() -> str:
    """Check whether a post was published today via post_to_blogger.py."""
    blog_log = BASE / "blog" / "blog_log.txt"
    pending  = BASE / "blog" / "pending"
    today    = date.today().isoformat()

    pending_count = len(list(pending.glob("*.html"))) if pending.exists() else 0

    if blog_log.exists():
        try:
            lines = blog_log.read_text(encoding="utf-8", errors="replace").strip().splitlines()
            today_lines = [l for l in lines if today in l]
            posted_today = [l for l in today_lines if "Posted via API" in l or "Done" in l]
            if posted_today:
                return f"OK — {len(posted_today)} post(s) published today"
            if pending_count:
                return f"WARN — {pending_count} post(s) in pending/, not yet published (publishes at 08:15)"
        except Exception:
            pass

    if pending_count:
        return f"WARN — {pending_count} post(s) waiting in pending/"
    return "OK — no pending posts"


def upcoming_hooks(bucket: str, n: int = 3) -> list[str]:
    """Return unused hooks that match today's bucket."""
    hooks_file = DATA / "hooks.txt"
    if not hooks_file.exists():
        return []
    try:
        all_hooks = [l.strip() for l in hooks_file.read_text(encoding="utf-8").splitlines() if l.strip()]
        used_data = json.loads(USED_CONTENT.read_text(encoding="utf-8")) if USED_CONTENT.exists() else {}
        used = set(used_data.get("hooks", []))
    except Exception:
        return []

    from pipeline import BUCKET_KEYWORDS
    keywords = BUCKET_KEYWORDS.get(bucket, [])

    candidates = [h for h in all_hooks if h not in used]
    bucket_hooks = [h for h in candidates if any(kw.lower() in h.lower() for kw in keywords)]
    if not bucket_hooks:
        bucket_hooks = candidates[:n]
    return bucket_hooks[:n]


def main():
    now       = datetime.now()
    today     = now.strftime("%Y-%m-%d")
    day_name  = now.strftime("%A")
    weekday   = now.weekday()
    iso_week  = now.isocalendar()[1]
    theme_idx = (iso_week - 1) % 4
    theme     = WEEKLY_THEMES[theme_idx]
    bucket    = DAY_BUCKETS[weekday]
    emoji     = BUCKET_EMOJI[bucket]
    out_dir   = OUTPUT / today

    # ── 06:00 run check ────────────────────────────────────────────────────────
    tiktok_info   = task_last_result("BootHop-TikTok")
    last_run      = tiktok_info.get("last_run", "")
    today_short   = now.strftime("%d/%m/%Y")
    ran_this_am   = today_short in last_run
    exit_code     = tiktok_info.get("last_result", "?")
    videos_so_far = count_videos(out_dir)

    # ── Yesterday's posts ─────────────────────────────────────────────────────
    yesterday_posts = posts_yesterday()
    today_posts     = posts_today()

    # ── Blog status ───────────────────────────────────────────────────────────
    blog_st = blog_status()

    # ── Sample hooks for today ────────────────────────────────────────────────
    try:
        hooks_preview = upcoming_hooks(bucket, n=2)
    except Exception:
        hooks_preview = []

    # ── Build message ─────────────────────────────────────────────────────────
    lines = [
        f"Good morning! Here's your *BootHop Daily Briefing* {emoji}",
        f"*{day_name} {today}* | Week {theme_idx+1}/4 — _{theme}_",
        "",
        f"*Today's content bucket:*  {bucket.upper()} {emoji}",
    ]

    if hooks_preview:
        lines.append("*Sample hooks lined up:*")
        for h in hooks_preview:
            short = h[:80] + ("..." if len(h) > 80 else "")
            lines.append(f"  • {short}")

    lines += [
        "",
        "*06:00 Pipeline:*",
    ]
    if videos_so_far >= 4:
        lines.append(f"  OK — {videos_so_far} videos ready in output/{today}/")
    elif ran_this_am:
        if exit_code == "0":
            lines.append(f"  WARN — ran but only {videos_so_far} videos (expected 4+)")
        else:
            lines.append(f"  FAIL — exit code {exit_code}, check crash log")
    else:
        lines.append(f"  MISSED — machine may have been off. Videos: {videos_so_far}")
        if videos_so_far == 0:
            lines.append("  Action: pipeline will retry at 12:30 automatically")

    lines += [
        "",
        "*Still coming today:*",
        "  12:30  — Afternoon pipeline run",
        "  18:00  — Evening pipeline run",
        "",
    ]

    # Yesterday's posts summary
    if yesterday_posts:
        platforms = list({p["platform"] for p in yesterday_posts})
        lines.append(f"*Yesterday's posts:*  {len(yesterday_posts)} video(s) on {', '.join(platforms)}")
        for p in yesterday_posts[:3]:
            hook_short = p.get("hook", "")[:60]
            lines.append(f"  [{p['platform']}] {hook_short}")
    else:
        lines.append("*Yesterday:*  No posts recorded")

    # Today's posts so far
    if today_posts:
        lines.append(f"*Posted so far today:*  {len(today_posts)} video(s)")

    lines += ["", f"*Blog:*  {blog_st}"]

    lines += ["", "boothop.com"]

    msg = "\n".join(lines)

    for chat_id in ALL_CHATS:
        send(chat_id, msg)
        print(f"Sent to {chat_id}")

    print(msg)


if __name__ == "__main__":
    main()
