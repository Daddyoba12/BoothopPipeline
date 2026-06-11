"""
BootHop Morning Intelligence Runner
Runs at 5:45am daily (before pipeline.py at 6am).

What it does:
  1. Fetch Nigeria Google Trends
  2. Fetch YouTube trending Nigeria
  3. Fetch TikTok hashtag data
  4. Fetch own Instagram insights
  5. Analyse hooks, hashtags, engagement
  6. Generate daily blog idea
  7. Send email + Telegram briefing
  8. Write data/trending_hooks_today.json for pipeline.py

Usage:
  python main.py
Schedule (Windows Task Scheduler):
  schtasks /create /tn "BootHopMorning" /tr "python C:\\Users\\babso\\Desktop\\BootHopPipeline\\main.py" /sc daily /st 05:45
"""

import json, random, sys, os
from datetime import datetime
from pathlib import Path

BASE = Path(r"C:\Users\babso\Desktop\BootHopPipeline")
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "scripts"))

# Ensure tools are on PATH when running as SYSTEM
for _p in [r"C:\ffmpeg\bin", r"C:\Python314", r"C:\Python314\Scripts"]:
    if _p not in os.environ.get("PATH", ""):
        os.environ["PATH"] = _p + os.pathsep + os.environ.get("PATH", "")

# Force UTF-8 (safe for headless/SYSTEM)
try:
    if hasattr(sys.stdout, "reconfigure") and sys.stdout.encoding != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from config import DATA, CACHE

# ── Imports ────────────────────────────────────────────────────────────────────
from collectors.google_trends import get_trends
from collectors.youtube import get_youtube_trending
from collectors.tiktok_scraper import get_tiktok_trends
from collectors.instagram import get_instagram_insights
from analysis.hooks import extract_hooks, boothop_hook_ideas
from scripts.fetch_trending_music import fetch_trending_music
from analysis.hashtags import get_hashtag_summary, recommend_hashtags
from analysis.engagement import calculate_engagement, save_daily_entry, weekly_summary
from briefing_module.briefing import send_briefing

# ── Music vibes (for briefing) ─────────────────────────────────────────────────
MUSIC_VIBES = [
    {"vibe": "Afrobeats",   "bpm": "95-120",  "mood": "celebratory, energetic, uplifting"},
    {"vibe": "Amapiano",    "bpm": "110-115", "mood": "smooth, groovy, laid-back cool"},
    {"vibe": "Afropop",     "bpm": "90-110",  "mood": "emotional, warm, nostalgic"},
    {"vibe": "Highlife",    "bpm": "80-100",  "mood": "joyful, communal, festive"},
    {"vibe": "Afro-fusion", "bpm": "100-120", "mood": "modern, premium, aspirational"},
]

TRENDING_ARTISTS = [
    "Asake", "Burna Boy", "Shallipopi", "Odumodublvck",
    "Wizkid", "Davido", "Tems", "Rema", "Seun Kuti",
    "Ckay", "Fireboy DML", "Ayra Starr", "Kizz Daniel",
]

HOOK_TEMPLATES_TREND = [
    "{trend} has the whole of Lagos buzzing and your aunty needs her {item} from London before the celebrations. BootHop gets it there same day.",
    "Everyone is talking about {trend}. You promised to send {item} in time. BootHop turns a traveller already going that way into your delivery.",
    "{trend} season is here. Your {family_member} in Lagos is waiting on {item} from the UK. One BootHop booking. Same day.",
    "Because of {trend}, the whole family is gathering. Your {item} from London needs to be there. BootHop makes it happen.",
]
HOOK_TEMPLATES_MUSIC = [
    "{artist} just dropped and your sister needs the merch from London before the Lagos concert. BootHop delivers it the same day.",
    "Everyone in Lagos is vibing to {artist} right now. You have a gift to send. BootHop connects it to a traveller already going your way.",
]
ITEMS = ["Ankara fabric","birthday gift","designer bag","medication","phone",
         "anniversary gift","shoes","documents","baby items","wig","laptop","food parcel"]
FAMILY_MEMBERS = ["mum","sister","aunty","grandma","cousin","dad","brother"]

TRENDING_HASHTAGS = {
    "always": ["#BootHop","#NaijaUK","#LondonToLagos","#DiasporaMagic","#SameDayDelivery","#NigerianTikTok"],
    "afrobeats": ["#AfrobeatsLife","#Afrobeats","#NaijaMusic","#Banger","#NaijaVibes"],
    "family": ["#NaijaFamily","#DiasporaLife","#UKNaija","#NigeriaUK","#AfricanDiaspora"],
    "community": ["#Lagos","#Abuja","#NaijaCommunity","#AfricanTikTok","#LagosLife"],
}

# ── Blog idea generator ────────────────────────────────────────────────────────
BLOG_ANGLES = [
    ("Why {trend} is revealing a gap in UK-Nigeria logistics",
     "While Nigeria is buzzing about {trend}, diaspora families are still struggling with unreliable deliveries.",
     "Peer-to-peer platforms like BootHop fill that gap by turning travellers into couriers.",
     "Try BootHop today — same-day delivery, trusted community, no missed windows."),
    ("The hidden cost of missed deliveries during {trend} season",
     "Every year, {trend} season highlights the same problem: packages stuck in transit when families need them most.",
     "BootHop routes your delivery through real people already making the journey.",
     "Book your first delivery at boothop.com — it takes 2 minutes."),
    ("How {trend} is changing what Nigerians need delivered from the UK",
     "Demand spikes every time {trend} trends. But traditional couriers haven't caught up.",
     "BootHop connects senders with travellers already going your way — no middleman, same day.",
     "Join the waitlist at boothop.com and never miss a delivery window again."),
]

def generate_blog_idea(trends):
    trend = trends[0] if trends else "supply chain disruption"
    angle = random.choice(BLOG_ANGLES)
    return {
        "headline": angle[0].format(trend=trend),
        "opening":  angle[1].format(trend=trend),
        "angle":    angle[2].format(trend=trend),
        "cta":      angle[3],
    }

def build_hooks(trends):
    hooks = []
    for trend in trends[:8]:
        tmpl = random.choice(HOOK_TEMPLATES_TREND)
        hooks.append({"hook": tmpl.format(trend=trend, item=random.choice(ITEMS),
                                           family_member=random.choice(FAMILY_MEMBERS)),
                      "source": "google_trend", "trend": trend,
                      "generated": datetime.now().isoformat()})
    artists = random.sample(TRENDING_ARTISTS, 4)
    for artist in artists:
        tmpl = random.choice(HOOK_TEMPLATES_MUSIC)
        hooks.append({"hook": tmpl.format(artist=artist),
                      "source": "music_trend", "trend": artist,
                      "generated": datetime.now().isoformat()})
    return hooks

def build_hashtag_sets():
    base  = TRENDING_HASHTAGS["always"]
    afro  = random.sample(TRENDING_HASHTAGS["afrobeats"], 3)
    fam   = random.sample(TRENDING_HASHTAGS["family"],  3)
    comm  = random.sample(TRENDING_HASHTAGS["community"], 3)
    return {b: " ".join(base + random.sample(TRENDING_HASHTAGS.get(b, TRENDING_HASHTAGS["community"]), min(4, 3)) + afro)
            for b in ["family","business","airport","smart","cinematic","community"]}


def trending_to_hashtags(trends, count=5):
    """Convert today's Google Trends topics into 5 hashtags for captions."""
    tags = []
    for trend in trends[:count * 2]:
        clean = trend.strip().title()
        tag   = "#" + "".join(w.capitalize() for w in clean.split())
        tag   = tag.replace("'","").replace("-","").replace(".","")
        if len(tag) <= 32 and tag not in tags:
            tags.append(tag)
        if len(tags) >= count:
            break
    return tags

# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    print(f"\n{'='*60}")
    print(f"  BootHop Morning Intelligence  {datetime.now().strftime('%A %d %B %Y  %H:%M')}")
    print(f"{'='*60}")

    # 0. Music first — downloads to music/daily/track_1.mp3 for pipeline.py at 6am
    print("\n[0] Fetching trending music (Nigeria → UK Grind → US RnB → Archive)...")
    music_result = fetch_trending_music()
    music_source = music_result.get("source", "archive")
    music_title  = music_result.get("title", "?")
    print(f"  Music selected: [{music_source}] {music_title[:55]}")

    # 1. Collect
    print("\n[1] Fetching Nigeria Google Trends...")
    trends = get_trends()
    print(f"  {len(trends)} trends: {', '.join(trends[:5])}")

    print("\n[2] Fetching YouTube trending Nigeria...")
    youtube_data = get_youtube_trending()
    print(f"  {len(youtube_data)} videos fetched")

    print("\n[3] Fetching TikTok hashtag data...")
    tiktok_data = get_tiktok_trends()
    print(f"  {len(tiktok_data)} results")

    print("\n[4] Fetching Instagram insights...")
    ig_data = get_instagram_insights()
    print(f"  {len(ig_data)} posts fetched")

    # 2. Analyse
    print("\n[5] Analysing...")
    hooks       = extract_hooks(youtube_data)
    hook_ideas  = boothop_hook_ideas(trends)
    hashtag_sum = get_hashtag_summary(ig_data)
    engagement  = calculate_engagement(ig_data)
    weekly      = weekly_summary()
    hashtag_rec = recommend_hashtags("tiktok_instagram", count=12)
    music_vibe  = random.choice(MUSIC_VIBES)
    blog        = generate_blog_idea(trends)

    # 3. Save trending_hooks_today.json (consumed by pipeline.py)
    print("\n[6] Writing trending_hooks_today.json...")
    full_hooks      = build_hooks(trends)
    hashtag_sets    = build_hashtag_sets()
    trending_tags   = trending_to_hashtags(trends, count=5)
    print(f"  Trending hashtags: {' '.join(trending_tags)}")
    out = {
        "date":               datetime.now().strftime("%Y-%m-%d"),
        "trends":             trends,
        "hooks":              full_hooks,
        "hook_count":         len(full_hooks),
        "music_vibe":         music_vibe,
        "hashtag_sets":       hashtag_sets,
        "trending_hashtags":  trending_tags,
    }
    (DATA / "trending_hooks_today.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"  {len(full_hooks)} hooks written")

    # 4. Log today's run
    save_daily_entry({
        "date":            datetime.now().strftime("%Y-%m-%d"),
        "platform":        "pipeline",
        "trends_count":    len(trends),
        "youtube_count":   len(youtube_data),
        "ig_posts":        len(ig_data),
        "hooks_generated": len(full_hooks),
        "music_vibe":      music_vibe["vibe"],
        "music_source":    music_source,
        "music_title":     music_title,
    })

    # 5. Send briefing (include music selection info)
    music_vibe["selected_track"] = music_title
    music_vibe["track_source"]   = music_source
    print("\n[7] Sending daily briefing...")
    send_briefing(
        trends=trends,
        hooks=hooks,
        hook_ideas=hook_ideas[:6],
        engagement=engagement[:8],
        hashtag_rec=hashtag_rec,
        weekly=weekly,
        music_vibe=music_vibe,
        blog=blog,
    )

    print(f"\n{'='*60}")
    print(f"  Morning intelligence complete!")
    print(f"  Top trend  : {trends[0] if trends else 'N/A'}")
    print(f"  Music      : [{music_source}] {music_title[:45]}")
    print(f"  Music vibe : {music_vibe['vibe']} — {music_vibe['mood']}")
    print(f"  Blog idea  : {blog['headline'][:70]}")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    import traceback
    _CRASH_LOG = BASE / "data" / "pipeline_crash.log"

    def _log(msg):
        try:
            with open(_CRASH_LOG, "a", encoding="utf-8", errors="replace") as _f:
                _f.write(f"\n[{datetime.now().isoformat()}] [main.py] {msg}\n")
        except Exception:
            pass

    _log(f"START — PID {os.getpid()}")
    try:
        main()
        _log("DONE — exit 0")
    except Exception as _exc:
        _tb = traceback.format_exc()
        _log(f"CRASH:\n{_tb}")
        try:
            from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
            import requests as _req
            _req.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                data={"chat_id": TELEGRAM_CHAT_ID,
                      "text": f"[main.py CRASH]\n{str(_exc)[:600]}\n\nFull trace in data/pipeline_crash.log"},
                timeout=15,
            )
        except Exception:
            pass
        raise
