# weekly_optimizer.py
# Analyses last 7 days of posts, computes performance weights,
# writes performance_weights.json, and sends a weekly Telegram report.

import sys
import io
import json
import os
import requests
from datetime import datetime, timedelta, timezone
from collections import defaultdict

# Force UTF-8 output on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

# ── Paths ────────────────────────────────────────────────────────────────────
SCRIPT_DIR       = os.path.dirname(os.path.abspath(__file__))
PIPELINE_DIR     = os.path.dirname(SCRIPT_DIR)
TRACKER_PATH     = os.path.join(PIPELINE_DIR, "data", "post_tracker.json")
WEIGHTS_PATH     = os.path.join(PIPELINE_DIR, "data", "performance_weights.json")
CREDENTIALS_PATH = os.path.join(SCRIPT_DIR, "social_credentials.json")

MIN_POSTS = 5  # minimum posts required for data-driven weights

# ── Default weights (neutral baseline) ────────────────────────────────────────
DEFAULT_WEIGHTS = {
    "buckets":    {"family": 1.0, "airport": 1.0, "business": 1.0, "smart": 1.0, "cinematic": 1.0, "community": 1.0},
    "music":      {"library": 1.0, "trending": 1.0},
    "versions":   {"v1": 1.0, "v2": 1.0},
    "hours":      {"6": 1.0, "10": 1.0, "11": 1.0, "17": 1.0, "18": 1.0},
    "hook_langs": {"EN": 1.0, "NG": 1.0, "ES": 1.0},
    "top_hooks":  [],
    "updated":    datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    "sample_size": 0,
    "note":       "Default weights — not enough data yet.",
}


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


def normalise(mapping, lo=0.5, hi=2.0):
    """
    Given {key: avg_score}, normalise values to [lo, hi] range,
    scaled so the overall mean maps to 1.0.
    Returns {key: weight} rounded to 2dp.
    """
    if not mapping:
        return {}
    values = list(mapping.values())
    mean   = sum(values) / len(values)
    if mean == 0:
        return {k: 1.0 for k in mapping}

    # Scale around the mean so mean → 1.0
    raw = {k: v / mean for k, v in mapping.items()}

    # Clamp to [lo, hi]
    clamped = {k: max(lo, min(hi, v)) for k, v in raw.items()}
    return {k: round(v, 2) for k, v in clamped.items()}


def group_avg(posts, key_fn):
    """Group posts by key_fn(post) and return {group: average_composite_score}."""
    groups = defaultdict(list)
    for p in posts:
        k = key_fn(p)
        if k is not None:
            groups[k].append(composite_score(p.get("metrics", {})))
    return {k: sum(v) / len(v) for k, v in groups.items()}


# ── Weight Calculator ─────────────────────────────────────────────────────────
def calculate_weights(recent_posts, all_known_buckets, start_date, end_date):
    bucket_avgs   = group_avg(recent_posts, lambda p: p.get("bucket"))
    music_avgs    = group_avg(recent_posts, lambda p: p.get("music"))
    version_avgs  = group_avg(recent_posts, lambda p: p.get("version"))
    lang_avgs     = group_avg(recent_posts, lambda p: p.get("hook_lang"))

    def hour_key(p):
        raw_ts = p.get("posted_at", "")
        try:
            ts = datetime.fromisoformat(raw_ts)
            return str(ts.hour)
        except (ValueError, TypeError):
            return None

    hour_avgs = group_avg(recent_posts, hour_key)

    # Ensure all known buckets appear (use 0 if unseen this week)
    for b in all_known_buckets:
        bucket_avgs.setdefault(b, 0)

    # Top 5 hooks by score
    sorted_by_score = sorted(
        recent_posts,
        key=lambda p: composite_score(p.get("metrics", {})),
        reverse=True
    )
    top_hooks = [p.get("hook", "") for p in sorted_by_score[:5] if p.get("hook")]

    weights = {
        "buckets":    normalise(bucket_avgs),
        "music":      normalise(music_avgs),
        "versions":   normalise(version_avgs),
        "hours":      normalise(hour_avgs),
        "hook_langs": normalise(lang_avgs),
        "top_hooks":  top_hooks,
        "updated":    datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "sample_size": len(recent_posts),
        "note":       f"Based on posts from {start_date} to {end_date}",
    }
    return weights, bucket_avgs, music_avgs, version_avgs


# ── Report Builder ────────────────────────────────────────────────────────────
def build_weekly_report(weights, bucket_avgs, music_avgs, version_avgs, recent_posts, prev_weights):
    lines = ["📈 *BootHop Weekly Optimizer Report*\n"]

    # ── WHAT WORKED ───────────────────────────────────────────────────────────
    lines.append("*✅ WHAT WORKED*")
    if bucket_avgs:
        top_bucket = max(bucket_avgs, key=bucket_avgs.get)
        lines.append(f"  Best bucket: *{top_bucket}* (avg score {bucket_avgs[top_bucket]:,.0f})")

    if weights.get("top_hooks"):
        lines.append("  Top hooks this week:")
        for i, hook in enumerate(weights["top_hooks"][:3], 1):
            # Find score for this hook
            score = next(
                (composite_score(p.get("metrics", {})) for p in recent_posts if p.get("hook") == hook),
                0
            )
            lines.append(f"    {i}. [{score:,}] {hook[:60]}")

    if music_avgs:
        best_music = max(music_avgs, key=music_avgs.get)
        lines.append(f"  Best music type: *{best_music}* (avg {music_avgs[best_music]:,.0f})")

    if version_avgs:
        best_ver = max(version_avgs, key=version_avgs.get)
        lines.append(f"  Best version: *{best_ver}* (avg {version_avgs[best_ver]:,.0f})")

    # ── WHAT DIDN'T ───────────────────────────────────────────────────────────
    lines.append("\n*❌ WHAT DIDN'T WORK*")
    if bucket_avgs:
        low_bucket = min(bucket_avgs, key=bucket_avgs.get)
        lines.append(f"  Weakest bucket: *{low_bucket}* (avg score {bucket_avgs[low_bucket]:,.0f})")

    if music_avgs:
        worst_music = min(music_avgs, key=music_avgs.get)
        lines.append(f"  Weakest music type: *{worst_music}* (avg {music_avgs[worst_music]:,.0f})")

    # Low hook examples
    sorted_asc = sorted(recent_posts, key=lambda p: composite_score(p.get("metrics", {})))
    low_hooks  = [p.get("hook", "") for p in sorted_asc[:2] if p.get("hook")]
    if low_hooks:
        lines.append("  Underperforming hooks:")
        for h in low_hooks:
            score = next(
                (composite_score(p.get("metrics", {})) for p in recent_posts if p.get("hook") == h),
                0
            )
            lines.append(f"    • [{score:,}] {h[:60]}")

    # ── WEIGHT CHANGES ────────────────────────────────────────────────────────
    lines.append("\n*⚙️ WEIGHT CHANGES*")
    if prev_weights:
        any_change = False
        for category in ("buckets", "music", "versions", "hook_langs"):
            old_cat = prev_weights.get(category, {})
            new_cat = weights.get(category, {})
            for key in set(list(old_cat.keys()) + list(new_cat.keys())):
                old_v = old_cat.get(key, 1.0)
                new_v = new_cat.get(key, 1.0)
                delta = new_v - old_v
                if abs(delta) >= 0.05:
                    arrow = "↑" if delta > 0 else "↓"
                    lines.append(f"  {category[:-1].title()} *{key}*: {old_v} → {new_v} ({arrow}{abs(delta):.2f})")
                    any_change = True
        if not any_change:
            lines.append("  No significant changes from last week.")
    else:
        lines.append("  No previous weights to compare against — baseline established.")

    # ── NEXT WEEK PRIORITY ────────────────────────────────────────────────────
    lines.append("\n*🎯 NEXT WEEK PRIORITY*")
    if bucket_avgs and music_avgs:
        top_b  = max(bucket_avgs, key=bucket_avgs.get)
        best_m = max(music_avgs, key=music_avgs.get)
        lines.append(
            f"  Focus on *{top_b}* bucket content with *{best_m}* music. "
            f"Double down on hooks that open with a direct question or bold statement — "
            f"they outperformed this week."
        )
    else:
        lines.append("  Keep posting consistently — more data needed for targeted recommendations.")

    lines.append(f"\n_Sample size: {weights['sample_size']} posts | {weights['note']}_")
    return "\n".join(lines)


# ── Telegram Sender ───────────────────────────────────────────────────────────
def send_telegram(message, creds):
    token   = creds.get("telegram", {}).get("bot_token", "").strip()
    chat_id = creds.get("telegram", {}).get("chat_id", "").strip()
    if not token or not chat_id:
        print("[INFO] Telegram credentials missing — printing report to stdout.\n")
        print(message)
        return

    url    = f"https://api.telegram.org/bot{token}/sendMessage"
    chunks = [message[i:i+4000] for i in range(0, len(message), 4000)]
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

    print("Loading post tracker...")
    posts = load_json(TRACKER_PATH, [])
    if not isinstance(posts, list):
        print("[WARN] post_tracker.json malformed — treating as empty.")
        posts = []

    # Filter to last 7 days
    cutoff     = datetime.now(timezone.utc) - timedelta(days=7)
    end_date   = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    start_date = cutoff.strftime("%Y-%m-%d")

    recent = []
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

    print(f"Found {len(recent)} posts in last 7 days.")

    # Load previous weights for diff report
    prev_weights = load_json(WEIGHTS_PATH, None)

    if len(recent) < MIN_POSTS:
        print(f"[INFO] Only {len(recent)} posts — below minimum of {MIN_POSTS}. Using defaults.")
        weights = dict(DEFAULT_WEIGHTS)
        weights["sample_size"] = len(recent)
        weights["updated"]     = end_date
        weights["note"]        = f"Default weights — only {len(recent)} post(s) tracked this week."
        save_json(WEIGHTS_PATH, weights)

        msg = (
            f"📈 *BootHop Weekly Optimizer*\n\n"
            f"Not enough data yet ({len(recent)} post(s) tracked, need {MIN_POSTS}+).\n"
            f"Default weights applied. Keep posting and check back next week!"
        )
        send_telegram(msg, creds)
        print("Done.")
        return

    # Gather all known bucket names across all tracked posts (for completeness)
    all_known_buckets = list({p.get("bucket") for p in posts if p.get("bucket")})

    print("Calculating weights...")
    weights, bucket_avgs, music_avgs, version_avgs = calculate_weights(
        recent, all_known_buckets, start_date, end_date
    )

    print("Saving performance weights...")
    save_json(WEIGHTS_PATH, weights)
    print(f"  Written to {WEIGHTS_PATH}")

    print("Building weekly report...")
    report = build_weekly_report(weights, bucket_avgs, music_avgs, version_avgs, recent, prev_weights)

    print("Sending to Telegram...")
    send_telegram(report, creds)

    print("Done.")


if __name__ == "__main__":
    main()
