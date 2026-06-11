"""Calculate engagement rates and weekly comparison stats."""
import json
from datetime import datetime, timedelta
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import DAILY_LOG

def calculate_engagement(instagram_data, followers=5000):
    results = []
    for post in instagram_data:
        likes    = post.get("like_count", 0) or 0
        comments = post.get("comments_count", 0) or 0
        rate     = round(((likes + comments) / max(followers, 1)) * 100, 2)
        results.append({
            "snippet": (post.get("caption") or "")[:60],
            "likes": likes,
            "comments": comments,
            "engagement_rate": f"{rate}%",
            "timestamp": post.get("timestamp", ""),
        })
    return results

def load_daily_log():
    if DAILY_LOG.exists():
        try:
            return json.loads(DAILY_LOG.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []

def save_daily_entry(entry: dict):
    log = load_daily_log()
    entry["logged_at"] = datetime.now().isoformat()
    log.append(entry)
    # Keep last 60 days
    log = log[-60:]
    DAILY_LOG.write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")

def weekly_summary():
    """Return a short weekly summary dict for the briefing."""
    log = load_daily_log()
    week_ago = datetime.now() - timedelta(days=7)
    recent = [e for e in log if e.get("logged_at", "") > week_ago.isoformat()]
    if not recent:
        return {"entries": 0, "note": "No data in last 7 days"}
    return {
        "entries": len(recent),
        "platforms": list({e.get("platform","?") for e in recent}),
        "note": f"{len(recent)} posts tracked this week",
    }
