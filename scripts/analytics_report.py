# analytics_report.py
# Fetches fresh metrics for recent posts, updates post_tracker.json,
# and sends a formatted analytics report to Telegram.

import sys
import io
import json
import os
import requests
from datetime import datetime, timedelta, timezone

# Force UTF-8 output on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

# ── Paths ────────────────────────────────────────────────────────────────────
SCRIPT_DIR        = os.path.dirname(os.path.abspath(__file__))
PIPELINE_DIR      = os.path.dirname(SCRIPT_DIR)
TRACKER_PATH      = os.path.join(PIPELINE_DIR, "data", "post_tracker.json")
CREDENTIALS_PATH  = os.path.join(SCRIPT_DIR, "social_credentials.json")


# ── Helpers ──────────────────────────────────────────────────────────────────
def load_json(path, fallback):
    if not os.path.exists(path):
        return fallback
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read().strip()
        return json.loads(content) if content else fallback
    except (json.JSONDecodeError, OSError):
        return fallback


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def composite_score(m):
    return (
        m.get("views", 0)
        + m.get("likes", 0) * 3
        + m.get("comments", 0) * 5
        + m.get("shares", 0) * 8
    )


def platform_creds_ok(creds, platform, required_keys):
    """Return True only if all required keys are non-empty strings."""
    block = creds.get(platform, {})
    return all(block.get(k, "").strip() for k in required_keys)


# ── Metric Fetchers ───────────────────────────────────────────────────────────
def fetch_instagram_metrics(post, creds):
    """Fetch insights from Instagram Graph API."""
    token = creds["instagram"]["access_token"]
    media_id = post.get("post_id", "")
    if not media_id:
        return None
    url = (
        f"https://graph.facebook.com/v19.0/{media_id}/insights"
        f"?metric=plays,reach,likes,comments,shares,saved&access_token={token}"
    )
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json().get("data", [])
        mapping = {item["name"]: item.get("values", [{}])[-1].get("value", 0) for item in data}
        return {
            "views":    mapping.get("plays", mapping.get("reach", 0)),
            "likes":    mapping.get("likes", 0),
            "comments": mapping.get("comments", 0),
            "shares":   mapping.get("shares", 0),
        }
    except Exception as e:
        print(f"  [Instagram] Error for {media_id}: {e}")
        return None


def fetch_tiktok_metrics(post, creds):
    """Fetch metrics from TikTok Research API."""
    token   = creds["tiktok"]["access_token"]
    post_id = post.get("post_id", "")
    if not post_id:
        return None
    url = "https://open.tiktokapis.com/v2/video/query/"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "filters": {"video_ids": [post_id]},
        "fields": ["view_count", "like_count", "comment_count", "share_count"],
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=15)
        resp.raise_for_status()
        videos = resp.json().get("data", {}).get("videos", [])
        if not videos:
            return None
        v = videos[0]
        return {
            "views":    v.get("view_count", 0),
            "likes":    v.get("like_count", 0),
            "comments": v.get("comment_count", 0),
            "shares":   v.get("share_count", 0),
        }
    except Exception as e:
        print(f"  [TikTok] Error for {post_id}: {e}")
        return None


def fetch_youtube_metrics(post, creds):
    """Fetch statistics from YouTube Data API v3."""
    api_key  = creds["youtube"]["api_key"]
    video_id = post.get("youtube_id", "")
    if not video_id:
        return None
    url = (
        f"https://www.googleapis.com/youtube/v3/videos"
        f"?part=statistics&id={video_id}&key={api_key}"
    )
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        items = resp.json().get("items", [])
        if not items:
            return None
        stats = items[0].get("statistics", {})
        return {
            "views":    int(stats.get("viewCount", 0)),
            "likes":    int(stats.get("likeCount", 0)),
            "comments": int(stats.get("commentCount", 0)),
            "shares":   0,  # YouTube API does not expose share count
        }
    except Exception as e:
        print(f"  [YouTube] Error for {video_id}: {e}")
        return None


# ── Metric Update Loop ────────────────────────────────────────────────────────
def update_metrics(posts, creds):
    cutoff = datetime.now(timezone.utc) - timedelta(days=14)
    ig_ok  = platform_creds_ok(creds, "instagram", ["access_token"])
    tt_ok  = platform_creds_ok(creds, "tiktok",    ["access_token"])
    yt_ok  = platform_creds_ok(creds, "youtube",   ["api_key"])

    if not ig_ok:
        print("[INFO] Instagram credentials missing — skipping.")
    if not tt_ok:
        print("[INFO] TikTok credentials missing — skipping.")
    if not yt_ok:
        print("[INFO] YouTube credentials missing — skipping.")

    for post in posts:
        raw_ts = post.get("posted_at", "")
        try:
            posted = datetime.fromisoformat(raw_ts)
            if posted.tzinfo is None:
                posted = posted.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            continue

        if posted < cutoff:
            continue

        platform = post.get("platform", "").lower()
        fetched  = None

        if platform == "instagram" and ig_ok:
            fetched = fetch_instagram_metrics(post, creds)
        elif platform == "tiktok" and tt_ok:
            fetched = fetch_tiktok_metrics(post, creds)
        elif platform == "youtube" and yt_ok:
            fetched = fetch_youtube_metrics(post, creds)

        if fetched:
            post.setdefault("metrics", {})
            post["metrics"].update(fetched)
            post["metrics"]["last_fetched"] = datetime.now(timezone.utc).isoformat()
            print(f"  Updated {platform} post {post.get('post_id')}: score={composite_score(post['metrics'])}")

    return posts


# ── Report Builder ────────────────────────────────────────────────────────────
def build_report(posts):
    cutoff   = datetime.now(timezone.utc) - timedelta(days=14)
    recent   = []
    for p in posts:
        raw_ts = p.get("posted_at", "")
        try:
            ts = datetime.fromisoformat(raw_ts)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts >= cutoff:
                recent.append(p)
        except (ValueError, TypeError):
            pass

    if not recent:
        return "No posts in the last 14 days to report on."

    lines = ["📊 *BootHop Analytics Report* — last 14 days\n"]

    # ── Top 3 per platform ────────────────────────────────────────────────────
    platforms = {}
    for p in recent:
        pl = p.get("platform", "unknown").lower()
        platforms.setdefault(pl, []).append(p)

    lines.append("*🏆 Top 3 Performers by Platform*")
    for pl, pl_posts in sorted(platforms.items()):
        ranked = sorted(pl_posts, key=lambda x: composite_score(x.get("metrics", {})), reverse=True)
        lines.append(f"\n_{pl.title()}_")
        for i, p in enumerate(ranked[:3], 1):
            m     = p.get("metrics", {})
            score = composite_score(m)
            hook  = p.get("hook", "")[:40]
            lines.append(
                f"  {i}. [{score:,}] {hook}… "
                f"👁{m.get('views',0):,} ❤{m.get('likes',0):,} "
                f"💬{m.get('comments',0):,} 🔁{m.get('shares',0):,}"
            )

    # ── Bucket averages ───────────────────────────────────────────────────────
    lines.append("\n*📦 Bucket Averages*")
    bucket_data = {}
    for p in recent:
        b = p.get("bucket", "unknown")
        bucket_data.setdefault(b, []).append(composite_score(p.get("metrics", {})))
    bucket_avgs = {b: sum(v) / len(v) for b, v in bucket_data.items()}
    for b, avg in sorted(bucket_avgs.items(), key=lambda x: x[1], reverse=True):
        count = len(bucket_data[b])
        lines.append(f"  {b:<14} avg={avg:,.0f}  (n={count})")

    # ── Music comparison ──────────────────────────────────────────────────────
    lines.append("\n*🎵 Music: Library vs Trending*")
    music_data = {}
    for p in recent:
        m_type = p.get("music", "unknown")
        music_data.setdefault(m_type, []).append(composite_score(p.get("metrics", {})))
    for m_type, scores in sorted(music_data.items()):
        avg = sum(scores) / len(scores)
        lines.append(f"  {m_type:<10} avg={avg:,.0f}  (n={len(scores)})")

    # ── V1 vs V2 ─────────────────────────────────────────────────────────────
    lines.append("\n*🎬 Version: V1 vs V2*")
    version_data = {}
    for p in recent:
        v = p.get("version", "unknown")
        version_data.setdefault(v, []).append(composite_score(p.get("metrics", {})))
    for v, scores in sorted(version_data.items()):
        avg = sum(scores) / len(scores)
        lines.append(f"  {v:<6} avg={avg:,.0f}  (n={len(scores)})")

    # ── Best time slots ───────────────────────────────────────────────────────
    lines.append("\n*⏰ Best Posting Hours*")
    hour_data = {}
    for p in recent:
        raw_ts = p.get("posted_at", "")
        try:
            ts = datetime.fromisoformat(raw_ts)
            hour_data.setdefault(ts.hour, []).append(composite_score(p.get("metrics", {})))
        except (ValueError, TypeError):
            pass
    hour_avgs = {h: sum(v) / len(v) for h, v in hour_data.items()}
    top_hours = sorted(hour_avgs.items(), key=lambda x: x[1], reverse=True)[:5]
    for h, avg in top_hours:
        count = len(hour_data[h])
        lines.append(f"  {h:02d}:00  avg={avg:,.0f}  (n={count})")

    lines.append(f"\n_Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}_")
    return "\n".join(lines)


# ── Telegram Sender ───────────────────────────────────────────────────────────
def send_telegram(message, creds):
    token   = creds.get("telegram", {}).get("bot_token", "").strip()
    chat_id = creds.get("telegram", {}).get("chat_id", "").strip()
    if not token or not chat_id:
        print("[INFO] Telegram credentials missing — printing report to stdout.\n")
        print(message)
        return

    url     = f"https://api.telegram.org/bot{token}/sendMessage"
    # Telegram has a 4096-char limit per message; split if needed
    chunks  = [message[i:i+4000] for i in range(0, len(message), 4000)]
    for chunk in chunks:
        payload = {
            "chat_id":    chat_id,
            "text":       chunk,
            "parse_mode": "Markdown",
        }
        try:
            resp = requests.post(url, json=payload, timeout=15)
            resp.raise_for_status()
            print(f"[Telegram] Chunk sent ({len(chunk)} chars).")
        except Exception as e:
            print(f"[Telegram] Send error: {e}")
            print("--- Falling back to stdout ---")
            print(chunk)


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("Loading credentials...")
    creds = load_json(CREDENTIALS_PATH, {})
    if not creds:
        print("[WARN] social_credentials.json missing or empty — running in limited mode.")

    print("Loading post tracker...")
    posts = load_json(TRACKER_PATH, [])
    if not isinstance(posts, list):
        print("[WARN] post_tracker.json is malformed — starting fresh.")
        posts = []

    if not posts:
        print("[INFO] No posts found in tracker.")
        msg = "📊 *BootHop Analytics*\n\nNo posts tracked yet. Add posts to post_tracker.json."
        send_telegram(msg, creds)
        return

    print(f"Fetching metrics for {len(posts)} tracked posts...")
    posts = update_metrics(posts, creds)

    print("Saving updated tracker...")
    save_json(TRACKER_PATH, posts)

    print("Building report...")
    report = build_report(posts)

    print("Sending to Telegram...")
    send_telegram(report, creds)

    print("Done.")


if __name__ == "__main__":
    main()
