"""
weekly_review.py
Runs every Monday at 3am. Analyses last 7 days of content performance.
Results feed directly back into pipeline.py so next week's content
dynamically reflects what actually worked.

What it does:
  1. Fetches Instagram last-7-days posts + engagement
  2. Reads music_log.json — which sources performed well
  3. Reads daily_log.json — pipeline run history
  4. Identifies top-performing hook patterns, buckets, content types
  5. Saves data/weekly_insights.json — human-readable summary
  6. Saves data/performance_weights.json — machine-readable; pipeline.py
     reads this at 6am so V1/V2 hooks and bucket selection auto-adjust
  7. Sends full report to Telegram + Gmail email (daddyoba12@gmail.com)

Schedule (already registered):
  schtasks /create /tn "BootHopWeekly" ... /sc weekly /d MON /st 03:00
"""

import json, sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path(r"C:\Users\babso\Desktop\BootHopPipeline")
sys.path.insert(0, str(BASE))

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import smtplib
import requests as _requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from config import (TELEGRAM_TOKEN, TELEGRAM_CHAT_ID,
                    IG_ACCESS_TOKEN, IG_USER_ID,
                    YOUTUBE_API_KEY, DATA, MUSIC_LOG, DAILY_LOG,
                    EMAIL_SENDER, EMAIL_RECIPIENT, EMAIL_PASSWORD,
                    SMTP_SERVER, SMTP_PORT,
                    WEEKLY_INSIGHTS)

SOCIAL_CREDS = BASE / "scripts" / "social_credentials.json"
POST_LOG     = DATA / "post_log.json"

PERFORMANCE_WEIGHTS = DATA / "performance_weights.json"
CUTOFF_7D = (datetime.now() - timedelta(days=7)).isoformat()

# Pattern → pipeline bucket mapping
PATTERN_TO_BUCKET = {
    "family_bucket":    "family",
    "business_bucket":  "business",
    "airport_bucket":   "airport",
    "diaspora_angle":   "community",
}


# ── Data loaders ───────────────────────────────────────────────────────────────
def _load_ig_week():
    if not IG_ACCESS_TOKEN or not IG_USER_ID:
        print("  [Weekly] No Instagram credentials — skipping IG stats")
        return []
    try:
        r = _requests.get(
            f"https://graph.instagram.com/v21.0/{IG_USER_ID}/media",
            params={"fields": "id,caption,like_count,comments_count,timestamp,media_type",
                    "access_token": IG_ACCESS_TOKEN, "limit": 30},
            timeout=15,
        )
        if r.ok:
            posts = r.json().get("data", [])
            return [p for p in posts if (p.get("timestamp") or "") > CUTOFF_7D]
        print(f"  [Weekly] IG API error: {r.text[:100]}")
    except Exception as e:
        print(f"  [Weekly] IG exception: {e}")
    return []

def _load_music_week():
    if not MUSIC_LOG.exists():
        return []
    try:
        log = json.loads(MUSIC_LOG.read_text(encoding="utf-8"))
        return [e for e in log if e.get("logged_at","") > CUTOFF_7D]
    except Exception:
        return []

def _load_daily_week():
    if not DAILY_LOG.exists():
        return []
    try:
        log = json.loads(DAILY_LOG.read_text(encoding="utf-8"))
        return [e for e in log if e.get("logged_at","") > CUTOFF_7D]
    except Exception:
        return []


def _load_linkedin_week():
    """Fetch LinkedIn UGC posts from last 7 days + reaction/comment counts."""
    try:
        if not SOCIAL_CREDS.exists():
            return []
        sc = json.loads(SOCIAL_CREDS.read_text(encoding="utf-8"))
        li = sc.get("linkedin", {})
        token      = li.get("access_token", "")
        person_urn = li.get("person_urn", "")
        if not token or not person_urn:
            print("  [LinkedIn] No credentials — skipping LinkedIn stats")
            return []

        headers = {
            "Authorization": f"Bearer {token}",
            "X-Restli-Protocol-Version": "2.0.0",
        }
        # Fetch recent posts
        r = _requests.get(
            "https://api.linkedin.com/v2/ugcPosts",
            params={"q": "authors", "authors": f"List({person_urn})", "count": 20},
            headers=headers, timeout=15,
        )
        if not r.ok:
            print(f"  [LinkedIn] API error: {r.status_code} {r.text[:80]}")
            return []

        posts = r.json().get("elements", [])
        results = []
        for post in posts:
            created_ms = post.get("created", {}).get("time", 0)
            if not created_ms:
                continue
            created_dt = datetime.fromtimestamp(created_ms / 1000)
            if created_dt.isoformat() < CUTOFF_7D:
                continue

            urn = post.get("id", "")
            likes = comments = 0
            try:
                sa = _requests.get(
                    f"https://api.linkedin.com/v2/socialMetadata?ids=List({urn})",
                    headers=headers, timeout=10,
                )
                if sa.ok:
                    elem = sa.json().get("results", {}).get(urn, {})
                    likes    = elem.get("numLikes", 0)
                    comments = elem.get("numComments", 0)
            except Exception:
                pass

            text = ""
            try:
                text = (post.get("specificContent", {})
                            .get("com.linkedin.ugc.ShareContent", {})
                            .get("shareCommentary", {})
                            .get("text", ""))[:120]
            except Exception:
                pass

            results.append({
                "timestamp": created_dt.isoformat(),
                "like_count": likes,
                "comments_count": comments,
                "caption": text,
                "media_type": "VIDEO" if post.get("specificContent", {}).get(
                    "com.linkedin.ugc.ShareContent", {}).get("shareMediaCategory") == "VIDEO"
                    else "POST",
            })
        return results
    except Exception as e:
        print(f"  [LinkedIn] Exception: {e}")
        return []


def _analyse_linkedin(posts):
    if not posts:
        return {"total": 0, "avg_likes": 0.0, "avg_comments": 0.0, "top_posts": []}
    total = len(posts)
    avg_l = round(sum(p.get("like_count", 0) for p in posts) / total, 1)
    avg_c = round(sum(p.get("comments_count", 0) for p in posts) / total, 1)
    ranked = sorted(posts,
                    key=lambda p: p.get("like_count", 0) + p.get("comments_count", 0),
                    reverse=True)
    top = [{"caption": p["caption"][:80], "likes": p["like_count"],
            "comments": p["comments_count"], "type": p["media_type"]}
           for p in ranked[:3]]
    return {"total": total, "avg_likes": avg_l, "avg_comments": avg_c, "top_posts": top}


def _load_post_log_week():
    """Load post_log.json entries from last 7 days (cross-platform archive)."""
    if not POST_LOG.exists():
        return []
    try:
        log = json.loads(POST_LOG.read_text(encoding="utf-8"))
        return [e for e in log if e.get("posted_at", "") > CUTOFF_7D]
    except Exception:
        return []


# ── Analysis ───────────────────────────────────────────────────────────────────
def _analyse_ig(posts):
    if not posts:
        return {"total":0,"avg_likes":0.0,"avg_comments":0.0,"top_posts":[],"best_day":None}

    likes_list    = [p.get("like_count",0) or 0 for p in posts]
    comments_list = [p.get("comments_count",0) or 0 for p in posts]
    total  = len(posts)
    avg_l  = round(sum(likes_list) / total, 1)
    avg_c  = round(sum(comments_list) / total, 1)

    ranked = sorted(posts,
                    key=lambda p: (p.get("like_count",0) or 0) + (p.get("comments_count",0) or 0),
                    reverse=True)
    top_posts = [{
        "caption":   (p.get("caption") or "")[:120],
        "likes":     p.get("like_count",0) or 0,
        "comments":  p.get("comments_count",0) or 0,
        "type":      p.get("media_type",""),
        "timestamp": p.get("timestamp",""),
    } for p in ranked[:5]]

    # Best day of week
    day_eng = {}
    for p in posts:
        ts = p.get("timestamp","")
        if len(ts) >= 10:
            try:
                day_name = datetime.fromisoformat(ts[:19]).strftime("%A")
                eng = (p.get("like_count",0) or 0) + (p.get("comments_count",0) or 0)
                day_eng[day_name] = day_eng.get(day_name, 0) + eng
            except Exception:
                pass
    best_day = max(day_eng, key=day_eng.get) if day_eng else None

    return {"total":total,"avg_likes":avg_l,"avg_comments":avg_c,
            "top_posts":top_posts,"best_day":best_day,"day_engagement":day_eng}

def _extract_patterns(ig_stats):
    """
    Read the top posts' captions and tag which hook/bucket patterns appeared.
    Returns a list of {pattern, count} dicts, sorted by count.
    """
    pattern_hits = []
    for post in ig_stats.get("top_posts", []):
        caption = (post.get("caption") or "").lower()
        if "pov:" in caption or caption.startswith("pov "):
            pattern_hits.append("pov_hook")
        if "same day" in caption or "today" in caption or "now" in caption:
            pattern_hits.append("urgency_message")
        if any(w in caption for w in ["mum","sister","aunty","family","grandma","cousin"]):
            pattern_hits.append("family_bucket")
        if any(w in caption for w in ["london","lagos","naija","nigeria","uk naija","diaspora"]):
            pattern_hits.append("diaspora_angle")
        if any(w in caption for w in ["business","sme","startup","entrepreneur","logistics"]):
            pattern_hits.append("business_bucket")
        if any(w in caption for w in ["afrobeats","amapiano","music","vibe","banger"]):
            pattern_hits.append("music_angle")
        if "airport" in caption or "traveller" in caption or "journey" in caption:
            pattern_hits.append("airport_bucket")
    counts = Counter(pattern_hits)
    return [{"pattern":k,"count":v} for k,v in counts.most_common()]

def _music_summary(music_week):
    if not music_week:
        return {"total":0,"sources":{}}
    source_counts = Counter(e.get("source","archive") for e in music_week)
    return {"total": len(music_week),
            "sources": dict(source_counts),
            "top_source": source_counts.most_common(1)[0][0] if source_counts else "archive",
            "tracks": [{"title":e.get("title","?"),"source":e.get("source","?")}
                       for e in music_week[-7:]]}


# ── Report builder ─────────────────────────────────────────────────────────────
def _build_telegram_report(ig_stats, patterns, music_summary, daily_week, li_stats=None):
    date_str = datetime.now().strftime("%d %b %Y")
    lines = [f"📊 *BootHop Weekly Review — w/e {date_str}*\n"]

    # IG Stats
    lines.append("*Instagram (last 7 days)*")
    lines.append(f"• Posts: {ig_stats['total']}  |  Avg likes: {ig_stats['avg_likes']}  |  Avg comments: {ig_stats['avg_comments']}")
    if ig_stats.get("best_day"):
        lines.append(f"• Best day to post: *{ig_stats['best_day']}*")

    # Top posts
    if ig_stats.get("top_posts"):
        lines.append("\n*Top Posts This Week*")
        for i, p in enumerate(ig_stats["top_posts"][:3], 1):
            lines.append(f"{i}. {p['likes']} likes, {p['comments']} comments")
            lines.append(f"   _{p['caption'][:80]}_")

    # Winning patterns
    if patterns:
        lines.append("\n*Patterns Driving Top Posts* (repeat next week)")
        for p in patterns[:4]:
            lines.append(f"• `{p['pattern']}` — appeared {p['count']}x")

    # Music this week + winning profile
    lines.append(f"\n*Music This Week* ({music_summary['total']} tracks selected)")
    for src, count in music_summary.get("sources",{}).items():
        lines.append(f"• {src}: {count} day(s)")
    if music_summary.get("top_source") != "archive":
        lines.append(f"✅ Trending music sourced ({music_summary['top_source']})")
    else:
        lines.append("⚠️ Mostly archive — check yt-dlp + YouTube API key")

    # LinkedIn Stats
    lines.append("\n*LinkedIn (last 7 days)*")
    ls = li_stats or {}
    if ls.get("total"):
        lines.append(f"• Posts: {ls['total']}  |  Avg likes: {ls['avg_likes']}  |  Avg comments: {ls['avg_comments']}")
        if ls.get("top_posts"):
            lines.append(f"• Top post: {ls['top_posts'][0]['likes']} likes — _{ls['top_posts'][0]['caption'][:60]}_")
    else:
        lines.append("• No data — token may need refreshing")

    # Pipeline runs
    lines.append(f"\n*Pipeline Runs*: {len(daily_week)} in last 7 days")

    # Recommendations — based on music profile analysis, not content re-use
    lines.append("\n*Next Week Auto-Adjustments*")
    lines.append("_(new content every day — adjustments are about style, not re-posting)_")
    if patterns:
        top = patterns[0]["pattern"].replace("_"," ")
        lines.append(f"• Content theme: *{top}* → higher bucket weight next week")
    if ig_stats.get("best_day"):
        lines.append(f"• Best posting day: *{ig_stats['best_day']}* → prioritise scheduling")

    # Music profile insight
    winning_vibe   = ""
    winning_energy = ""
    winning_mood   = ""
    is_old_school  = False
    try:
        if PERFORMANCE_WEIGHTS.exists():
            pw = json.loads(PERFORMANCE_WEIGHTS.read_text(encoding="utf-8"))
            mp = pw.get("preferred_music_profile", {})
            winning_vibe   = mp.get("winning_vibe","")
            winning_energy = mp.get("energy","")
            winning_mood   = mp.get("mood","")
            is_old_school  = mp.get("is_old_school", False)
    except Exception:
        pass

    if winning_vibe:
        age_desc = "classic/old school" if is_old_school else "fresh/trending"
        lines.append(f"• Winning music: *{winning_vibe}* ({age_desc}) — {winning_energy} energy, {winning_mood}")
        lines.append(f"  → Next week: searching for *similar* {winning_vibe} tracks (same vibe, different song)")
    else:
        lines.append("• Music profile: no viral post data yet — running default priority")

    if not ig_stats["total"]:
        lines.append("⚠️ No Instagram data — verify Graph API token is not expired")

    return "\n".join(lines)


# ── Vibe → music characteristics map ──────────────────────────────────────────
# Used to find *similar* music to what worked — NOT to repeat the same track
VIBE_PROFILES = {
    "Afrobeats": {
        "energy": "high", "pitch": "varied", "mood": "celebratory/energetic",
        "queries": [
            "Nigeria afrobeats viral banger 2025",
            "Naija high energy music trending today",
            "afrobeats upbeat Nigeria chart",
        ],
    },
    "Amapiano": {
        "energy": "medium", "pitch": "mid-low", "mood": "smooth/groovy",
        "queries": [
            "amapiano trending Nigeria 2025",
            "amapiano log drum smooth groove",
            "South Africa amapiano viral hit",
        ],
    },
    "Afropop": {
        "energy": "medium", "pitch": "high", "mood": "emotional/warm",
        "queries": [
            "Nigeria afropop emotional trending 2025",
            "Naija love song sentimental viral",
            "afropop heartfelt Nigeria chart",
        ],
    },
    "Highlife": {
        "energy": "high", "pitch": "high", "mood": "joyful/communal",
        "queries": [
            "Nigeria highlife joyful music 2025",
            "Ghana Nigeria highlife trending",
            "highlife festive upbeat Nigeria",
        ],
    },
    "Afro-fusion": {
        "energy": "medium", "pitch": "varied", "mood": "modern/premium",
        "queries": [
            "Nigeria afro fusion modern 2025",
            "premium afrobeats contemporary Nigeria",
            "afro fusion cinematic trending",
        ],
    },
}

SOURCE_PROFILES = {
    "archive": {
        "energy": "nostalgic", "mood": "classic/timeless",
        "queries": [
            "Nigeria classic old school music",
            "90s 2000s Nigeria legendary songs",
            "timeless Naija music nostalgia",
        ],
    },
    "uk_grind": {
        "energy": "high", "pitch": "low/bass", "mood": "gritty/urban",
        "queries": [
            "UK drill trending 2025",
            "UK grime urban rap chart",
            "UK road music bass heavy",
        ],
    },
    "us_rnb": {
        "energy": "medium", "pitch": "high", "mood": "soulful/smooth",
        "queries": [
            "US RnB soul trending 2025",
            "neo soul emotional RnB chart",
            "smooth RnB soulful vocals",
        ],
    },
    "nigeria": {
        "energy": "high", "mood": "celebratory",
        "queries": [
            "Nigeria afrobeats trending viral 2025",
            "Naija banger music today",
            "Nigeria TikTok trending music",
        ],
    },
}


def _get_winning_music_profile(ig_stats):
    """
    Cross-reference top-performing post dates with music_log.json and
    daily_log.json to identify what music characteristics backed the
    viral content. Returns a profile dict for fetch_trending_music.py to use.
    """
    top_posts = ig_stats.get("top_posts", [])
    if not top_posts:
        return {}

    # Load logs
    music_log = []
    daily_log = []
    try:
        if MUSIC_LOG.exists():
            music_log = json.loads(MUSIC_LOG.read_text(encoding="utf-8"))
    except Exception:
        pass
    try:
        if DAILY_LOG.exists():
            daily_log = json.loads(DAILY_LOG.read_text(encoding="utf-8"))
    except Exception:
        pass

    winning_vibes   = []
    winning_sources = []
    winning_titles  = []

    for post in top_posts[:2]:  # analyse top 2 posts
        ts = post.get("timestamp","")
        if not ts or len(ts) < 10:
            continue
        post_date = ts[:10]  # "YYYY-MM-DD"

        # Find music used on that day in music_log
        for entry in music_log:
            if entry.get("logged_at","")[:10] == post_date:
                src   = entry.get("source","")
                title = entry.get("title","")
                if src:
                    winning_sources.append(src)
                if title:
                    winning_titles.append(title)
                break

        # Find vibe from daily_log
        for entry in daily_log:
            if entry.get("logged_at","")[:10] == post_date or entry.get("date","") == post_date:
                vibe = entry.get("music_vibe","")
                if vibe:
                    winning_vibes.append(vibe)
                break

    if not winning_sources and not winning_vibes:
        return {}

    # Build profile
    top_source = winning_sources[0] if winning_sources else "nigeria"
    top_vibe   = winning_vibes[0]   if winning_vibes   else "Afrobeats"

    # Get search queries — prefer vibe profile, fall back to source profile
    vibe_profile   = VIBE_PROFILES.get(top_vibe, {})
    source_profile = SOURCE_PROFILES.get(top_source.split("_")[0] if "_" in top_source else top_source, {})

    profile = {
        "winning_source":  top_source,
        "winning_vibe":    top_vibe,
        "energy":          vibe_profile.get("energy",   source_profile.get("energy","??")),
        "mood":            vibe_profile.get("mood",     source_profile.get("mood","??")),
        "pitch":           vibe_profile.get("pitch",    source_profile.get("pitch","??")),
        "is_old_school":   top_source == "archive",
        "search_queries":  vibe_profile.get("queries",  source_profile.get("queries",[])),
        "winning_titles":  winning_titles,
    }

    print(f"  [Music Profile] Source: {top_source} | Vibe: {top_vibe} | "
          f"Energy: {profile['energy']} | Mood: {profile['mood']}")
    return profile


# ── Performance weights writer ─────────────────────────────────────────────────
def _write_performance_weights(ig_stats, patterns, music_sum):
    """
    Write performance_weights.json — read by pipeline.py at 6am.

    What this changes for next week:
    - Bucket weights: content themes that drove engagement get higher selection probability
    - Music profile: characteristics of the music that backed viral content →
      fetch_trending_music.py will search for SIMILAR music (same energy/vibe/pitch),
      NOT the same track. New content every day, but matched to what worked.
    - top_hooks: intentionally empty — we never re-use old captions/hooks.
    """
    weights = {
        "buckets":    {"family":1.0,"business":1.0,"airport":1.0,
                       "smart":1.0,"cinematic":1.0,"community":1.0},
        "music":      {"library":1.0, "trending":1.0},
        "versions":   {"v1":1.0, "v2":1.0},
        "hook_langs": {"EN":1.0, "NG":1.5, "ES":1.0},
        "top_hooks":  [],   # always empty — do NOT re-use old content
        "preferred_music_profile": {},
        "generated":  datetime.now().isoformat(),
    }

    # Boost buckets that matched winning content patterns
    for rank, pat in enumerate(patterns[:3]):
        bucket = PATTERN_TO_BUCKET.get(pat["pattern"])
        if bucket:
            boost = 1.8 if rank == 0 else (1.4 if rank == 1 else 1.2)
            weights["buckets"][bucket] = boost
            print(f"  [Weights] {bucket} bucket → {boost}× (pattern: {pat['pattern']})")

    # Music weighting — trending vs library
    top_src = music_sum.get("top_source", "archive")
    if top_src in ("nigeria","nigeria_search","uk_grind","uk_grind_search","us_rnb","us_rnb_search"):
        weights["music"]["trending"] = 1.5
        print(f"  [Weights] Trending music → 1.5× (source: {top_src})")
    else:
        weights["music"]["library"] = 1.3
        print("  [Weights] Library music → 1.3× (trending was mostly archive)")

    # Music profile — what made the viral video FEEL the way it did
    music_profile = _get_winning_music_profile(ig_stats)
    if music_profile:
        weights["preferred_music_profile"] = music_profile
        print(f"  [Weights] Music profile: {music_profile.get('winning_vibe')} / "
              f"{music_profile.get('energy')} energy / {music_profile.get('mood')}")
        if music_profile.get("is_old_school"):
            print("  [Weights] Old school music worked — will search for classic/nostalgic tracks")
        else:
            print("  [Weights] New trending music worked — will search for similar fresh tracks")

    PERFORMANCE_WEIGHTS.write_text(
        json.dumps(weights, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"  [Weights] Saved → {PERFORMANCE_WEIGHTS.name}")
    return weights


def _send_gmail_email(subject, html_body):
    """Send weekly report email via Gmail SMTP."""
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"BootHop Weekly <{EMAIL_SENDER}>"
        msg["To"]      = EMAIL_RECIPIENT
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(EMAIL_SENDER, EMAIL_PASSWORD)
            smtp.sendmail(EMAIL_SENDER, EMAIL_RECIPIENT, msg.as_string())
        print(f"  [Email] Weekly report sent via Gmail to {EMAIL_RECIPIENT}")
    except Exception as e:
        print(f"  [Email] Gmail error: {e}")


def _build_html_report(ig_stats, patterns, music_sum, daily_week, weights, li_stats=None):
    """Build a clean HTML email for the weekly review."""
    date_str = datetime.now().strftime("%d %B %Y")

    def _row(label, value):
        return (f"<tr><td style='padding:7px 14px;color:#6b7280;width:160px'>{label}</td>"
                f"<td style='padding:7px 14px;color:#111827;font-weight:600'>{value}</td></tr>")

    # Pattern rows
    pattern_rows = "".join(
        f"<li style='padding:3px 0;color:#374151'><strong>{p['pattern'].replace('_',' ')}</strong>"
        f" — appeared {p['count']}× in top posts</li>"
        for p in patterns[:4]
    ) or "<li style='color:#9ca3af'>No pattern data this week</li>"

    # Top posts
    top_post_rows = ""
    for i, p in enumerate(ig_stats.get("top_posts",[])[:3], 1):
        top_post_rows += (
            f"<tr style='border-bottom:1px solid #e5e7eb'>"
            f"<td style='padding:8px 12px;color:#6b7280'>{i}</td>"
            f"<td style='padding:8px 12px;color:#374151'>{p['caption'][:90]}...</td>"
            f"<td style='padding:8px 12px;text-align:center;color:#10b981;font-weight:600'>{p['likes']}</td>"
            f"<td style='padding:8px 12px;text-align:center;color:#374151'>{p['comments']}</td>"
            f"</tr>"
        )

    # Boosted buckets
    boosted = {k:v for k,v in weights.get("buckets",{}).items() if v > 1.1}
    boost_items = " ".join(
        f"<span style='background:#d1fae5;color:#065f46;padding:3px 8px;border-radius:4px;font-size:12px;margin:2px'>"
        f"{k} {v}×</span>"
        for k,v in sorted(boosted.items(), key=lambda x: -x[1])
    ) or "<span style='color:#9ca3af;font-size:13px'>All buckets neutral</span>"

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:Arial,sans-serif;max-width:660px;margin:auto;background:#f4f4f4;padding:20px">
<div style="background:#07111f;padding:28px 32px;border-radius:10px 10px 0 0">
  <h1 style="color:#fff;margin:0;font-size:22px">BootHop Weekly Review</h1>
  <p style="color:#6b8ca4;margin:6px 0 0;font-size:14px">Week ending {date_str}</p>
</div>
<div style="background:#fff;padding:28px 32px">

  <h2 style="font-size:15px;color:#07111f;border-left:4px solid #10b981;padding-left:10px;margin-top:0">Instagram Performance</h2>
  <table style="width:100%;border-collapse:collapse;background:#f9fafb;border-radius:6px">
    {_row("Posts tracked", ig_stats.get("total",0))}
    {_row("Avg likes", ig_stats.get("avg_likes",0))}
    {_row("Avg comments", ig_stats.get("avg_comments",0))}
    {_row("Best posting day", ig_stats.get("best_day","?") or "N/A")}
    {_row("Pipeline runs", len(daily_week))}
  </table>

  <h2 style="font-size:15px;color:#07111f;border-left:4px solid #10b981;padding-left:10px;margin-top:24px">Top Posts</h2>
  <table style="width:100%;border-collapse:collapse;font-size:13px">
    <tr style="background:#f3f4f6;color:#6b7280"><th style="padding:8px 12px;text-align:left">#</th><th style="padding:8px 12px;text-align:left">Caption</th><th style="padding:8px 12px">Likes</th><th style="padding:8px 12px">Comments</th></tr>
    {top_post_rows or "<tr><td colspan='4' style='padding:12px;color:#9ca3af;text-align:center'>No posts this week</td></tr>"}
  </table>

  <h2 style="font-size:15px;color:#07111f;border-left:4px solid #10b981;padding-left:10px;margin-top:24px">Winning Patterns (auto-applied next week)</h2>
  <ul style="padding-left:20px;margin:0">{pattern_rows}</ul>

  <h2 style="font-size:15px;color:#07111f;border-left:4px solid #10b981;padding-left:10px;margin-top:24px">Next Week — Auto-Adjusted Bucket Weights</h2>
  <p style="margin:0;font-size:13px;color:#374151">These buckets get higher selection probability in next week's pipeline:</p>
  <div style="margin-top:8px">{boost_items}</div>

  <h2 style="font-size:15px;color:#07111f;border-left:4px solid #10b981;padding-left:10px;margin-top:24px">LinkedIn Performance</h2>
  <table style="width:100%;border-collapse:collapse;background:#f9fafb;border-radius:6px">
    {_row("Posts tracked", (li_stats or {}).get("total",0))}
    {_row("Avg likes", (li_stats or {}).get("avg_likes",0))}
    {_row("Avg comments", (li_stats or {}).get("avg_comments",0))}
  </table>

  <h2 style="font-size:15px;color:#07111f;border-left:4px solid #10b981;padding-left:10px;margin-top:24px">Music This Week</h2>
  <table style="width:100%;border-collapse:collapse;background:#f9fafb;border-radius:6px">
    {_row("Top source", music_sum.get("top_source","archive"))}
    {_row("Tracks selected", music_sum.get("total",0))}
    {_row("Trending weight", weights.get("music",{}).get("trending",1.0))}
  </table>

</div>
<div style="background:#07111f;padding:16px 32px;border-radius:0 0 10px 10px;text-align:center">
  <p style="color:#4b5563;font-size:12px;margin:0">BootHop Weekly Intelligence — auto-generated {date_str}</p>
</div>
</body></html>"""


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    print(f"\n{'='*58}")
    print(f"  BootHop Weekly Review — {datetime.now().strftime('%A %d %B %Y  %H:%M')}")
    print(f"{'='*58}")

    print("\n[1] Loading Instagram last 7 days...")
    ig_posts     = _load_ig_week()
    print(f"  {len(ig_posts)} posts found")

    print("\n[2] Loading music + pipeline logs...")
    music_week   = _load_music_week()
    daily_week   = _load_daily_week()

    print("\n[3] Analysing...")
    ig_stats     = _analyse_ig(ig_posts)
    patterns     = _extract_patterns(ig_stats)
    music_sum    = _music_summary(music_week)

    print(f"  Top pattern  : {patterns[0]['pattern'] if patterns else 'none'}")
    print(f"  Best post day: {ig_stats.get('best_day','?')}")
    print(f"  Music sources: {list(music_sum.get('sources',{}).keys())}")

    print("\n[1b] Loading LinkedIn last 7 days...")
    li_posts  = _load_linkedin_week()
    li_stats  = _analyse_linkedin(li_posts)
    post_log  = _load_post_log_week()
    print(f"  LinkedIn: {li_stats['total']} posts | Avg likes: {li_stats['avg_likes']}")

    # Save weekly_insights.json (human-readable summary)
    insights = {
        "week_ending":      datetime.now().strftime("%Y-%m-%d"),
        "ig_stats":         ig_stats,
        "li_stats":         li_stats,
        "winning_patterns": patterns,
        "music_summary":    music_sum,
        "pipeline_runs":    len(daily_week),
        "post_log_entries": len(post_log),
        "recommendations": {
            "prioritise_pattern": patterns[0]["pattern"] if patterns else "pov_hook",
            "best_posting_day":   ig_stats.get("best_day",""),
            "music_priority":     music_sum.get("top_source","archive"),
        },
    }
    WEEKLY_INSIGHTS.write_text(
        json.dumps(insights, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\n  Saved insights: {WEEKLY_INSIGHTS.name}")

    # Write performance_weights.json — pipeline.py reads this at 6am
    print("\n[4] Writing performance weights for next week...")
    weights = _write_performance_weights(ig_stats, patterns, music_sum)

    # Send Telegram report
    print("\n[5] Sending Telegram report...")
    report = _build_telegram_report(ig_stats, patterns, music_sum, daily_week, li_stats=li_stats)
    try:
        _requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": report[:4096], "parse_mode": "Markdown"},
            timeout=20,
        )
        print("  Telegram weekly report sent")
    except Exception as e:
        print(f"  Telegram error: {e}")

    # Send Gmail email report
    print("\n[6] Sending email report via Gmail...")
    html_report = _build_html_report(ig_stats, patterns, music_sum, daily_week, weights, li_stats=li_stats)
    _send_gmail_email(
        subject=f"BootHop Weekly Review — w/e {datetime.now().strftime('%d %b %Y')}",
        html_body=html_report,
    )

    print(f"\n{'='*58}")
    print(f"  Weekly review complete!")
    print(f"  Posts analysed  : {ig_stats['total']}")
    print(f"  Patterns found  : {len(patterns)}")
    print(f"  Weights written : {PERFORMANCE_WEIGHTS.name}")
    print(f"{'='*58}\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as _crash:
        import traceback
        _tb = traceback.format_exc()
        print(f"\n[CRASH] weekly_review.py failed:\n{_tb}")
        try:
            _requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                json={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": (
                        f"🚨 *BootHopWeekly CRASHED*\n\n"
                        f"`{str(_crash)[:300]}`\n\n"
                        f"→ Check logs and re-run:\n"
                        f"`python scripts/weekly_review.py`"
                    ),
                    "parse_mode": "Markdown",
                },
                timeout=20,
            )
        except Exception:
            pass
        sys.exit(1)
