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
sys.path.insert(0, str(BASE))

def _get_yt_key():
    try:
        from config import YOUTUBE_API_KEY
        return YOUTUBE_API_KEY
    except Exception:
        return ""


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
                "key": _get_yt_key(),
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
    # High energy — problem/solution
    "POV: {trend} is everywhere. You have {item} sitting in London for your {family_member}. One verified traveller is already going. That is BootHop.",
    "POV: It is {trend} season and your {family_member} is calling every hour. The {item} is in London. BootHop already found someone going today.",
    "POV: {trend} week and you forgot to send {item} to Lagos. A BootHop traveller is at the airport RIGHT NOW. Book in 5 minutes.",
    # Emotional
    "POV: Your {family_member} has been waiting since January for that {item}. {trend} is the push you needed. BootHop gets it there today. No courier. Real person.",
    "POV: {trend} is happening and your {family_member} in Lagos is watching everyone celebrate while YOUR package is still in London. Not anymore. BootHop.",
    # Viral/funny
    "POV: You told your {family_member} the {item} is coming for {trend}. You lied. Now BootHop has to save you. It will.",
    "POV: Abroad life is real. {trend} hits different when your {family_member} can not enjoy it without the {item} you promised from London. BootHop, go.",
    # Trust / proof
    "POV: {trend} 2026. A real verified traveller carried my {family_member} {item} from London to Lagos in one day. That is BootHop. Not DHL. Not FedEx. A person.",
    "POV: During {trend} someone trusted a stranger to carry mum {item} across two countries. Verified. Tracked. Delivered. That stranger was a BootHop traveller.",
]

HOOK_TEMPLATES_MUSIC = [
    "POV: {artist} is playing everywhere in Lagos. You are in London watching it live on Instagram. But the gift you promised is still here. BootHop. Send it today.",
    "POV: {artist} just dropped and your people in Lagos are going crazy. You have been saying you will send {item}. A traveller leaves tonight. Book now. BootHop.",
    "POV: {artist} era. Your whole family is in Lagos having the time of their lives and your {item} is still in your hallway in London. BootHop. Today.",
    "POV: Everyone is vibing to {artist}. Your {family_member} asked for ONE thing from London. You have not sent it. A verified BootHop traveller is boarding in 3 hours.",
]

FAMILY_MEMBERS = ["mum", "sister", "aunty", "grandma", "cousin", "dad", "brother", "wife", "baby"]
ITEMS = [
    "Ankara fabric", "birthday gift", "designer bag", "medication",
    "phone", "spare parts", "anniversary gift", "shoes", "documents",
    "baby items", "wig", "laptop", "fashion items", "food parcel",
    "jewellery", "small chops ingredients", "birthday cake topper",
]

# Month-aware fallbacks — picks list matching current month
import datetime as _dt_module
_MONTH_TRENDS = {
    1:  ["New Year Lagos parties", "January detox challenge", "Super Eagles AFCON"],
    2:  ["Valentine season Lagos", "Afrobeats February", "Super Eagles qualifiers"],
    3:  ["Holi Lagos", "March madness Nigeria", "Nollywood premiere"],
    4:  ["Easter celebrations", "AMVCA award season", "Lagos Fashion Week"],
    5:  ["Mother's Day Nigeria", "Afrobeats festival season", "Naija Tech Week"],
    6:  ["Eid al-Adha celebrations", "Super Eagles match", "Detty June Lagos",
         "Afrobeats summer season", "Japa movement Nigeria", "NYSC camp season",
         "Big Brother Naija announcement", "Afropop summer Lagos"],
    7:  ["Big Brother Naija premiere", "Lagos summer events", "Super Eagles match"],
    8:  ["Independence Day prep Nigeria", "Detty August Lagos", "Big Brother Naija"],
    9:  ["Nigerian Independence Month", "Afrobeats Grammy buzz", "Big Brother Naija"],
    10: ["Detty October Lagos", "Nigerian Tech Week", "Halloween Lagos"],
    11: ["Detty December prep", "Big Brother Naija finale", "Black Friday Lagos"],
    12: ["Detty December Lagos", "Christmas in Lagos", "New Year countdown"],
}
_current_month = _dt_module.date.today().month
NIGERIA_FALLBACK_TRENDS = _MONTH_TRENDS.get(_current_month, [
    "Afrobeats festival season", "Super Eagles match", "Lagos Fashion Week",
    "Naija Tech Week", "Nollywood premiere", "NYSC camp season",
])

# Sunday-specific high-energy hooks (injected when today is Sunday)
SUNDAY_HOOKS = [
    {"hook": "POV: It is Sunday. You are in London. Mum is in church in Lagos waiting for her package from you. A BootHop traveller already flew it over. She got it before service ended.",
     "source": "sunday_special", "trend": "Sunday Naija vibes"},
    {"hook": "POV: Sunday service in Lagos. Pastor says who has testimony? Your cousin stands up. My package from London arrived SAME DAY. That is BootHop testimony.",
     "source": "sunday_special", "trend": "Sunday Things"},
    {"hook": "POV: It is Sunday morning. The family WhatsApp is going crazy. The package you sent with a BootHop traveller reached Lagos overnight. You did not even know it landed.",
     "source": "sunday_special", "trend": "Sunday Naija vibes"},
    {"hook": "POV: Everyone is in their Sunday best in Lagos. Your aunty is wearing the wig you sent with a BootHop traveller on Friday. She is the most glamorous in church today.",
     "source": "sunday_special", "trend": "Sunday Things"},
    {"hook": "POV: Sunday afternoon. Jollof is on. Family is together. The shoes you sent from London with a BootHop traveller are already being shown off. Same day. Real person.",
     "source": "sunday_special", "trend": "Sunday Naija vibes"},
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
        hook = template.format(
            artist=artist,
            item=random.choice(ITEMS),
            family_member=random.choice(FAMILY_MEMBERS),
        )
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
        trends = random.sample(NIGERIA_FALLBACK_TRENDS, min(10, len(NIGERIA_FALLBACK_TRENDS)))

    # 2. Generate hooks
    trend_hooks = generate_hooks_from_trends(trends)
    music_hooks = generate_music_trend_hooks()
    # Inject Sunday hooks when today is Sunday (weekday 6)
    sunday_hooks = []
    if datetime.now().weekday() == 6:
        print("  Sunday detected — injecting Sunday Naija hooks")
        sunday_hooks = [dict(h, generated=datetime.now().isoformat()) for h in SUNDAY_HOOKS]
    all_hooks = sunday_hooks + trend_hooks + music_hooks

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
