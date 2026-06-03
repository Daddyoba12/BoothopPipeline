"""
generate_trending_content.py
Fetches today's top Nigerian trends (Google Trends) and generates
BootHop-relevant emotional hooks + music vibe context.
Outputs to data/trending_hooks_today.json

Run before pipeline.py (e.g. 5:45am daily):
  python scripts/generate_trending_content.py
"""

import json, random, sys
from datetime import datetime
from pathlib import Path

BASE = Path(r"C:\Users\babso\Desktop\BootHopPipeline")
DATA = BASE / "data"
DATA.mkdir(exist_ok=True)


# ── Trend fetching ─────────────────────────────────────────────────────────────

def fetch_nigeria_google_trends():
    try:
        from pytrends.request import TrendReq
        pt = TrendReq(hl="en-NG", tz=60, timeout=(10, 30), retries=2, backoff_factor=0.5)
        df = pt.trending_searches(pn="nigeria")
        return [str(t).strip() for t in df[0].tolist()[:20] if str(t).strip()]
    except Exception as e:
        print(f"  [Trends] Google Trends error: {e}")
        return []


def fetch_youtube_trending_ng():
    """
    Fetch YouTube trending titles for Nigeria (no API key required for this endpoint).
    Returns list of video titles that are trending in NG.
    """
    try:
        import requests
        r = requests.get(
            "https://www.googleapis.com/youtube/v3/videos",
            params={
                "part": "snippet",
                "chart": "mostPopular",
                "regionCode": "NG",
                "maxResults": 10,
                "key": "AIzaSyD-9tSrke72PouQMnMX-a7eZSW0jkFMBWY",  # public demo key — replace with your own
            },
            timeout=10
        )
        if r.ok:
            items = r.json().get("items", [])
            return [i["snippet"]["title"] for i in items]
    except Exception:
        pass
    return []


# ── Hook template engine ───────────────────────────────────────────────────────

HOOK_TEMPLATES_TREND = [
    "POV: {trend} has the whole of Lagos buzzing and your aunty needs her {item} from London before the celebrations. BootHop gets it there same day.",
    "POV: Everyone is talking about {trend}. You promised to send {item} in time. BootHop turns a traveller already going that way into your delivery.",
    "POV: {trend} season is here. Your {family_member} in Lagos is waiting on {item} from the UK. One BootHop booking. Same day.",
    "POV: Because of {trend}, the whole family is gathering. Your {item} from London needs to be there. BootHop makes it happen.",
    "POV: {trend} energy is high right now. You have {item} to send. A trusted traveller is already going your way. That is BootHop.",
    "POV: During {trend}, the last thing you need is a delayed package. BootHop uses real people already making the journey to deliver for you.",
    "POV: {trend} has everyone buzzing. Your {family_member} needs {item} from London tonight. BootHop: trusted, same day, done.",
    "POV: With {trend} happening, you finally have a reason to send that {item} you have been holding. BootHop gets it there today.",
]

HOOK_TEMPLATES_MUSIC = [
    "POV: {artist} just dropped and your sister needs the merch from London before the Lagos concert. BootHop delivers it the same day.",
    "POV: Everyone in Lagos is vibing to {artist} right now. You have a gift to send. BootHop connects it to a traveller already going your way.",
    "POV: {artist} energy is everywhere this week. Your mum asked for something special from the UK. BootHop makes it land today.",
    "POV: The {artist} era is real. You promised your family something from London. BootHop turns that promise into a same-day delivery.",
]

FAMILY_MEMBERS = ["mum", "sister", "aunty", "grandma", "cousin", "dad", "brother"]
ITEMS = [
    "Ankara fabric", "birthday gift", "designer bag", "medication",
    "phone", "spare parts", "anniversary gift", "shoes", "documents",
    "baby items", "wig", "laptop", "fashion items", "food parcel",
]

NIGERIA_FALLBACK_TRENDS = [
    "AMVCA award season",    "Big Brother Naija finale",  "Super Eagles match",
    "Lagos Fashion Week",    "Afrobeats festival season", "Detty December prep",
    "NYSC camp season",      "Eid Mubarak celebrations",  "Christmas in Lagos",
    "Naija Tech Week",       "Nollywood premiere",        "Valentine season Lagos",
    "Mother's Day Nigeria",  "Nigerian election season",  "Easter celebrations",
]

TRENDING_NIGERIAN_ARTISTS = [
    "Asake",          "Burna Boy",      "Shallipopi",   "Odumodublvck",
    "Wizkid",         "Davido",         "Tems",         "Rema",
    "Seun Kuti",      "Ckay",           "Fireboy DML",  "Ayra Starr",
    "Kizz Daniel",    "Zinoleesky",     "Victony",      "Omah Lay",
]

MUSIC_VIBES = [
    {"vibe": "Afrobeats",   "bpm": "95-120",  "mood": "celebratory, energetic, uplifting"},
    {"vibe": "Amapiano",    "bpm": "110-115", "mood": "smooth, groovy, laid-back cool"},
    {"vibe": "Afropop",     "bpm": "90-110",  "mood": "emotional, warm, nostalgic"},
    {"vibe": "Highlife",    "bpm": "80-100",  "mood": "joyful, communal, festive"},
    {"vibe": "Afro-fusion", "bpm": "100-120", "mood": "modern, premium, aspirational"},
]

# ── Hashtag pools — scored by reach potential (order = priority) ──────────────

# NG/Diaspora pools per bucket (slot 3 candidates — pick index by day-of-year)
HASHTAG_POOL_NG = {
    "family":    ["#NaijaFamily",      "#AfricanDiaspora",  "#DiasporaLife",
                  "#UKNaija",          "#HomeDelivery",     "#NaijaAbroad"],
    "business":  ["#UrgentDelivery",   "#LogisticsNigeria", "#SMELogistics",
                  "#B2BDelivery",      "#NaijaStartup",     "#AfricanBusiness"],
    "airport":   ["#TravelHack",       "#AirportLife",      "#NaijaTravel",
                  "#UrgentDelivery",   "#TravelTips",       "#LondonHeathrow"],
    "smart":     ["#SmartLogistics",   "#HumanPowered",     "#FutureDelivery",
                  "#GreenLogistics",   "#StartupAfrica",    "#TechNaija"],
    "cinematic": ["#TrustedMovement",  "#PremiumDelivery",  "#HumanLogistics",
                  "#MovementWithPurpose", "#DiasporaMagic",  "#LuxuryLogistics"],
    "community": ["#NaijaUK",          "#LagosLife",        "#NigerianTikTok",
                  "#AfricanTikTok",    "#NaijaVibes",       "#NaijaCommunity"],
}

# Route anchor — slot 2 (one per route, rotates weekly)
ROUTE_ANCHORS = {
    "ng": ["#LondonToLagos",  "#DiasporaMagic",   "#UKNigeria",
           "#NaijaDelivery",  "#DiasporaDelivery", "#LagosLondon"],
    "uk": ["#SameDayUK",      "#UKDelivery",       "#StudentLife",
           "#UniLife",        "#LondonToManchester","#UKStudents"],
    "eu": ["#UKtoEurope",     "#ExpatLife",        "#LondonToBerlin",
           "#DiasporaEurope", "#BritishAbroad",    "#EuropeanDelivery"],
    "es": ["#DiasporaEspana", "#LondresAMadrid",   "#UKEspana",
           "#EnvioDesdeUK",   "#DiasporaLatina",   "#ExpatsUK"],
}

# Discovery pool — slot 4 (broad reach, rotates daily)
DISCOVERY_POOL = [
    "#SameDayDelivery", "#HumanLogistics",   "#TrustedTraveller",
    "#PeoplePowered",   "#Startup",          "#Innovation",
    "#DeliveryApp",     "#TravelAndDeliver",  "#PackageDone",
    "#LogisticsLife",   "#CarryItForward",   "#MoveWithPurpose",
    "#TrustTheProcess", "#AbroadLife",       "#DiasporaPower",
    "#TechStartup",     "#AfricanStartup",   "#NaijaStartup",
    "#GigEconomy",      "#TravelHack",       "#PassportLife",
]


def generate_hooks_from_trends(trends):
    hooks = []
    for trend in trends[:12]:
        if not trend or len(trend) < 4:
            continue
        template = random.choice(HOOK_TEMPLATES_TREND)
        hook = template.format(
            trend=trend,
            item=random.choice(ITEMS),
            family_member=random.choice(FAMILY_MEMBERS),
        )
        hooks.append({"hook": hook, "source": "google_trend", "trend": trend,
                       "generated": datetime.now().isoformat()})
    return hooks


def generate_music_trend_hooks():
    artists = random.sample(TRENDING_NIGERIAN_ARTISTS, min(4, len(TRENDING_NIGERIAN_ARTISTS)))
    hooks = []
    for artist in artists:
        template = random.choice(HOOK_TEMPLATES_MUSIC)
        hook = template.format(artist=artist)
        hooks.append({"hook": hook, "source": "music_trend", "trend": artist,
                       "generated": datetime.now().isoformat()})
    return hooks


def trend_to_hashtag(trend_text):
    """Convert a Google Trends phrase into a usable hashtag."""
    import re
    clean = re.sub(r"[^\w\s]", "", trend_text).strip()
    words = clean.split()
    if not words:
        return ""
    tag = "#" + "".join(w.capitalize() for w in words[:3])
    if len(tag) > 30:
        tag = "#" + "".join(w.capitalize() for w in words[:2])
    return tag if len(tag) > 3 else ""


def pick_5_hashtags(bucket="community", route="ng", trend_tag="", day_of_year=None):
    """
    Return exactly 5 hashtags for one video caption.

    Slot 1 — #BootHop (always)
    Slot 2 — Route anchor, rotated weekly
    Slot 3 — Bucket-specific, rotated daily within pool
    Slot 4 — Discovery tag, rotated daily
    Slot 5 — Trend-derived (from Google Trends today), or fallback discovery
    """
    import datetime as _dt
    if day_of_year is None:
        day_of_year = _dt.date.today().timetuple().tm_yday

    # Slot 1
    tags = ["#BootHop"]

    # Slot 2 — route anchor, rotates weekly
    anchors = ROUTE_ANCHORS.get(route, ROUTE_ANCHORS["ng"])
    tags.append(anchors[(day_of_year // 7) % len(anchors)])

    # Slot 3 — bucket pool, rotates daily
    pool3 = HASHTAG_POOL_NG.get(bucket, HASHTAG_POOL_NG["community"])
    tags.append(pool3[day_of_year % len(pool3)])

    # Slot 4 — discovery, rotates daily (offset so it differs from slot 3)
    tags.append(DISCOVERY_POOL[(day_of_year + 7) % len(DISCOVERY_POOL)])

    # Slot 5 — trend-derived if valid, else next discovery tag
    if trend_tag and len(trend_tag) > 3 and trend_tag not in tags:
        tags.append(trend_tag)
    else:
        tags.append(DISCOVERY_POOL[(day_of_year + 14) % len(DISCOVERY_POOL)])

    return tags  # always exactly 5


def build_daily_hashtag_sets(trends=None):
    """
    Build the full set of 5-hashtag lists for today, covering all
    bucket × route combinations.  Saved into trending_hooks_today.json.
    """
    import datetime as _dt
    doy      = _dt.date.today().timetuple().tm_yday
    buckets  = ["family", "business", "airport", "smart", "cinematic", "community"]
    routes   = ["ng", "uk", "eu", "es"]

    # Best trend tag: first Google Trend that converts to a short hashtag
    trend_tag = ""
    for t in (trends or []):
        candidate = trend_to_hashtag(t)
        if candidate and len(candidate) <= 25:
            trend_tag = candidate
            break

    sets = {}
    for bucket in buckets:
        for route in routes:
            key       = f"{bucket}_{route}"
            five_tags = pick_5_hashtags(bucket, route, trend_tag, doy)
            sets[key] = " ".join(five_tags)

    return sets, trend_tag


def main():
    print(f"\n[Trending Content] {datetime.now().strftime('%A %d %B %Y  %H:%M')}")

    # 1. Fetch trends
    print("  Fetching Nigeria Google Trends...")
    trends = fetch_nigeria_google_trends()
    if trends:
        print(f"  {len(trends)} trends: {', '.join(trends[:6])}")
    else:
        print("  Using cultural fallbacks (pytrends unavailable)")
        trends = random.sample(NIGERIA_FALLBACK_TRENDS, 10)

    # 2. Generate hooks
    trend_hooks = generate_hooks_from_trends(trends)
    music_hooks = generate_music_trend_hooks()
    all_hooks   = trend_hooks + music_hooks

    # 3. Pick today's music vibe
    music_vibe  = random.choice(MUSIC_VIBES)

    # 4. Build exactly-5 hashtag sets — all bucket × route combinations
    hashtag_sets, trend_tag = build_daily_hashtag_sets(trends)

    # 5. Save output
    out = {
        "date":         datetime.now().strftime("%Y-%m-%d"),
        "trends":       trends,
        "hooks":        all_hooks,
        "hook_count":   len(all_hooks),
        "music_vibe":   music_vibe,
        "hashtag_sets": hashtag_sets,
        "trend_tag":    trend_tag,
    }
    out_path = DATA / "trending_hooks_today.json"
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"  Generated {len(all_hooks)} hooks -> {out_path.name}")
    print(f"  Music vibe: {music_vibe['vibe']} — {music_vibe['mood']}")
    print(f"  Top trends: {', '.join(trends[:5])}")
    print(f"  Trend hashtag: {trend_tag or '(none derived)'}")
    # Preview today's hashtags for community_ng
    preview = hashtag_sets.get("community_ng", "")
    print(f"  Sample (community NG): {preview}")
    return out


if __name__ == "__main__":
    main()
