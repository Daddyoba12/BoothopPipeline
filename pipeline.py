"""
BootHop TikTok Pipeline — runs at 6am daily
Generates 2 x 30-second POV-style TikTok videos + caption → Telegram

Video structure (30 seconds, 1080x1920):
  0–8s   : Movement clips + POV hook text (top, big yellow)
  8–22s  : Movement/solution key phrase (white, bottom)
  20–22s : fig1Start or fig2start brand card overlay
  27–30s : FIG4End full-screen safety/trust end card
  27–30s : Hero end line text (yellow, bottom center)
  0–30s  : BootHop logo corner (small, throughout)
  Audio  : Edge TTS voiceover (5-part brand arc story) + music

Two versions:
  video_library.mp4  — archive/library music track
  video_trending.mp4 — today's SoundCloud trending track

Optional third version:
  video_english.mp4  — English voiceover when hook is non-English

Day-of-week bucket rotation:
  Mon=business, Tue=family, Wed=airport, Thu=smart, Fri=cinematic,
  Sat=community, Sun=community

7-day memory: never repeats same hook or engagement within a week
"""

import os, json, re, random, shutil, subprocess, asyncio, sys, time, functools
from pathlib import Path
from datetime import datetime, timedelta
import requests

# Ensure ffmpeg/yt-dlp are on PATH when running as SYSTEM (Task Scheduler)
_extra_paths = [r"C:\ffmpeg\bin", r"C:\Python314", r"C:\Python314\Scripts"]
for _p in _extra_paths:
    if _p not in os.environ.get("PATH", ""):
        os.environ["PATH"] = _p + os.pathsep + os.environ.get("PATH", "")

# Force UTF-8 output on Windows (safe — SYSTEM account stdout may be non-reconfigurable)
try:
    if hasattr(sys.stdout, "reconfigure") and sys.stdout.encoding != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure") and sys.stderr.encoding != "utf-8":
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# Crash log — captures unhandled exceptions even when running headless as SYSTEM
_LOG_FILE  = Path(r"C:\Users\babso\Desktop\BootHopPipeline\data\pipeline_crash.log")
_STEP_FILE = Path(r"C:\Users\babso\Desktop\BootHopPipeline\data\pipeline_step.txt")

def _write_crash(msg: str):
    try:
        with open(_LOG_FILE, "a", encoding="utf-8", errors="replace") as _f:
            _f.write(f"\n[{datetime.now().isoformat()}] {msg}\n")
    except Exception:
        pass

def _set_step(step: str):
    """Overwrite step file with current step + timestamp.
    If the process is killed externally (e.g. battery cutoff via Task Scheduler),
    the next run reads this to report which step was running at time of death."""
    try:
        _STEP_FILE.write_text(
            f"[{datetime.now().isoformat()}] {step}", encoding="utf-8"
        )
    except Exception:
        pass

def _clear_step():
    try:
        if _STEP_FILE.exists():
            _STEP_FILE.unlink()
    except Exception:
        pass


def with_retry(retries=2, backoff=15):
    """Decorator: retry a function up to `retries` times with `backoff` second delay."""
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(1, retries + 2):
                try:
                    return fn(*args, **kwargs)
                except Exception as exc:
                    last_exc = exc
                    if attempt <= retries:
                        print(f"  [Retry {attempt}/{retries}] {fn.__name__} failed: {exc} — retrying in {backoff}s")
                        time.sleep(backoff)
            raise last_exc
        return wrapper
    return decorator


# ── Paths ──────────────────────────────────────────────────────────────────────
BASE        = Path(r"C:\Users\babso\Desktop\BootHopPipeline")
DATA        = BASE / "data"
ASSETS      = BASE / "assets"
TEMP        = BASE / "temp"
OUTPUT      = BASE / "output"
DAILY_MUSIC     = BASE / "music" / "daily"
ARCHIVE         = BASE / "music" / "archive"
TRENDING_MUSIC  = BASE / "audio" / "trending"
POST_LOG    = DATA / "post_log.json"

FIG1        = ASSETS / "fig1Start.png"
FIG2        = ASSETS / "fig2start.png"
FIG_END     = ASSETS / "FIG4End.png"
LOGO        = ASSETS / "mainlogo.png"

# Premium fonts (condensed impact titles + clean modern body)
_FONT_DIR = BASE / "assets" / "fonts"
FONT_TITLE = str(_FONT_DIR / "Oswald-Bold.ttf")       # condensed, cinematic — POV label + hero
FONT_BODY  = str(_FONT_DIR / "Montserrat-ExtraBold.ttf")  # clean, premium — content lines
# Fallback to system bold if custom fonts missing
if not (_FONT_DIR / "Oswald-Bold.ttf").exists():
    FONT_TITLE = "C\\:/Windows/Fonts/impact.ttf"
if not (_FONT_DIR / "Montserrat-ExtraBold.ttf").exists():
    FONT_BODY = "C\\:/Windows/Fonts/arialbd.ttf"
FONT = FONT_TITLE  # legacy alias

PEXELS_KEY  = "NY3tWysBJseeky8V1JEp2YjevIq6MTYcOCfuKNBU7iypjC7Qc5T1DTp5"
TELEGRAM_TOKEN   = "8717698733:AAF7GI9Yw1DhdYVv_TK35fYQcwaGdk4caeA"
TELEGRAM_CHAT_ID = "8641867751"

# WhatsApp Cloud API — operator number +44-7405-746302 receives all pipeline alerts
WHATSAPP_ACCESS_TOKEN    = ""   # set in .env: WHATSAPP_ACCESS_TOKEN=...
WHATSAPP_PHONE_NUMBER_ID = ""   # set in .env: WHATSAPP_PHONE_NUMBER_ID=...
WHATSAPP_RECIPIENT       = "447405746302"  # operator's WhatsApp (no +)

# Load .env for WHATSAPP_* tokens
_env_path = BASE / ".env"
if _env_path.exists():
    for _line in _env_path.read_text(encoding="utf-8").splitlines():
        if "=" in _line and not _line.startswith("#"):
            _k, _v = _line.split("=", 1)
            _k, _v = _k.strip(), _v.strip()
            if _k == "WHATSAPP_ACCESS_TOKEN":    WHATSAPP_ACCESS_TOKEN    = _v
            if _k == "WHATSAPP_PHONE_NUMBER_ID": WHATSAPP_PHONE_NUMBER_ID = _v

# ── Social posting modules ─────────────────────────────────────────────────────
SCRIPTS = BASE / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
try:
    import post_tiktok, post_instagram, post_linkedin
    _SOCIAL_ENABLED = True
except ImportError as _e:
    print(f"[WARNING] Social posting modules not available: {_e}")
    _SOCIAL_ENABLED = False

# ── Day-of-week bucket rotation ────────────────────────────────────────────────
DAY_BUCKETS = {
    0: "business",
    1: "family",
    2: "airport",
    3: "smart",
    4: "cinematic",
    5: "community",
    6: "community",
}

def get_day_bucket():
    return DAY_BUCKETS[datetime.now().weekday()]


# ── 4-Week Theme Cycle ─────────────────────────────────────────────────────────
# Advances automatically each ISO week. Drives hook selection and caption framing.
WEEKLY_THEMES = {
    0: {
        "name":            "Problem Awareness",
        "hook_keywords":   ["stuck", "fail", "traditional", "takes days", "expensive",
                            "broken", "late", "missed", "no courier", "delay", "can't",
                            "won't", "days", "weeks", "wrong", "problem", "struggle"],
        "caption_opener":  ["Traditional delivery failed again.",
                            "Same problem. Every time.",
                            "Sound familiar?",
                            "This keeps happening.",
                            "Still waiting? There's a smarter way."],
        "cta":             "There's a smarter way. boothop.com",
        "hashtag_boost":   "#UrgentDelivery #LogisticsFail #SameDayProblems #BrokenLogistics",
    },
    1: {
        "name":            "Solution & Product",
        "hook_keywords":   ["already flying", "traveller was", "space in the bag", "same day",
                            "verified", "earn", "smart", "match", "one tap", "already going",
                            "solution", "fixed", "sorted", "booking", "income"],
        "caption_opener":  ["Here's how BootHop works.",
                            "Someone is already going your way.",
                            "One booking. Same day.",
                            "This is how we fix it.",
                            "The smarter way to move urgent items."],
        "cta":             "Book your first delivery at boothop.com",
        "hashtag_boost":   "#SameDayDelivery #SmartLogistics #HumanPowered #BootHopWorks",
    },
    2: {
        "name":            "Trust & Credibility",
        "hook_keywords":   ["trusted", "verified", "safe", "family", "mum", "diaspora",
                            "community", "love", "protection", "secure", "real people",
                            "aunty", "grandma", "sister", "mama", "dad"],
        "caption_opener":  ["Real people. Trusted journeys.",
                            "This is more than logistics.",
                            "Not a courier. A trusted traveller.",
                            "Built on trust. Powered by community.",
                            "Because some deliveries are deeply personal."],
        "cta":             "Trusted travellers. Real people. boothop.com",
        "hashtag_boost":   "#TrustedDelivery #DiasporaMagic #CommunityFirst #RealPeople",
    },
    3: {
        "name":            "Vision & CTA",
        "hook_keywords":   ["london", "lagos", "diaspora", "global", "smarter", "movement",
                            "network", "everywhere", "future", "imagine", "world",
                            "london to lagos", "frankfurt", "new york", "abuja"],
        "caption_opener":  ["The world is already moving.",
                            "London to Lagos. Same day.",
                            "This is the future of logistics.",
                            "Join the movement.",
                            "Borders shouldn't stop connection."],
        "cta":             "Join BootHop — boothop.com",
        "hashtag_boost":   "#LondonToLagos #DiasporaMagic #FutureOfLogistics #GlobalMovement",
    },
}

def get_weekly_theme():
    """
    Returns (theme_index, theme_dict) based on ISO week number.
    Cycles 0→1→2→3→0 every 4 weeks automatically.
    """
    week_num  = datetime.now().isocalendar()[1]
    theme_idx = (week_num - 1) % 4
    return theme_idx, WEEKLY_THEMES[theme_idx]


# ── Weekly insights → dynamic bucket adjustment ────────────────────────────────
_PATTERN_TO_BUCKET = {
    "family_bucket":   "family",
    "business_bucket": "business",
    "airport_bucket":  "airport",
    "diaspora_angle":  "community",
}

def get_adjusted_bucket():
    """
    Return today's scheduled bucket, but override it if last week's
    performance_weights.json strongly recommends a different bucket.
    Override only happens if the top bucket weight is ≥ 1.6 and the
    recommended bucket differs from today's default.
    """
    base = get_day_bucket()
    wfile = DATA / "performance_weights.json"
    if not wfile.exists():
        return base
    try:
        weights = json.loads(wfile.read_text(encoding="utf-8"))
        bucket_w = weights.get("buckets", {})
        if not bucket_w:
            return base
        top_bucket  = max(bucket_w, key=bucket_w.get)
        top_weight  = bucket_w[top_bucket]
        if top_weight >= 1.6 and top_bucket != base:
            print(f"  [Weekly] Bucket override: {base} → {top_bucket} "
                  f"(performance weight {top_weight}×)")
            return top_bucket
    except Exception:
        pass
    return base


# ── Bucket keyword mapping (to filter existing POV hooks) ─────────────────────
BUCKET_KEYWORDS = {
    "family":    ["mum", "mama", "grandma", "birthday", "cake", "wedding", "bride",
                  "aso-ebi", "gele", "gift", "family", "aunty", "herbs", "medicine",
                  "meds", "baby", "photo album", "video call", "tears"],
    "business":  ["bentley", "rolls-royce", "spare part", "mechanic", "brake",
                  "engineer", "business", "document", "docs", "operation"],
    "airport":   ["heathrow", "flight", "airport", "boarding", "passport", "suitcase",
                  "luggage", "tonight", "lekki tonight", "harrods today"],
    "smart":     ["traveller was flying anyway", "already flying", "no courier",
                  "space in the bag", "earn", "income", "carry am",
                  "someone was already"],
    "cinematic": ["london luxury", "diaspora love language", "this isn't shipping",
                  "diaspora magic", "£30 instead", "not shipping"],
    "community": ["abeg", "wahala", "gbe body", "nna men", "dem say", "e don reach",
                  "don land", "no be courier", "your people dey", "one tap",
                  "BootHop dey"],
    "local_uk":  ["glasgow", "birmingham", "manchester", "nottingham", "derby",
                  "edinburgh", "leeds", "sheffield", "hull", "bristol", "cardiff",
                  "liverpool", "brighton", "newcastle", "leicester", "oxford",
                  "st pancras", "student", "lecture", "exam", "dissertation",
                  "university", "uni", "campus", "train", "driving that way",
                  "motorway", "flat", "home in london"],
    "euro":      ["berlin", "barcelona", "paris", "amsterdam", "frankfurt",
                  "lisbon", "prague", "rome", "madrid", "seville", "malaga",
                  "dublin", "dusseldorf", "eurostar", "ryanair", "stansted",
                  "luton", "car registration", "car papers", "particulars"],
}


# ── Story templates per bucket ────────────────────────────────────────────────
STORY_TEMPLATES = {
    "family": [
        {
            "problem":  "Traditional delivery would take days. And time was running out.",
            "movement": "But someone trusted was already flying that route tonight.",
            "solution": "BootHop connects urgent delivery needs with verified travellers already making the journey.",
        },
        {
            "problem":  "No fast way to get it there in time. The moment was slipping away.",
            "movement": "Then someone trusted was already heading that direction.",
            "solution": "BootHop turns existing journeys into meaningful delivery opportunities.",
        },
        {
            "problem":  "Urgent documents. Wrong city. Deadline approaching.",
            "movement": "But a trusted traveller was already making that exact journey.",
            "solution": "BootHop helps important things reach the right hands, fast.",
        },
    ],
    "business": [
        {
            "problem":  "Downtime costs businesses thousands per hour. Every minute counts.",
            "movement": "But urgent movement is already happening on that route daily.",
            "solution": "BootHop coordinates trusted movement to help critical items move faster.",
        },
        {
            "problem":  "Time-sensitive documents. Production halted. No fast courier solution.",
            "movement": "Then a trusted traveller heading the same way became the answer.",
            "solution": "BootHop transforms existing journeys into urgent business solutions.",
        },
        {
            "problem":  "One missing part can stop an entire operation.",
            "movement": "But someone was already making that journey with space in their bag.",
            "solution": "BootHop connects businesses with trusted movement already happening.",
        },
    ],
    "airport": [
        {
            "problem":  "Panic. Stress. No fast solution. Flight departing in hours.",
            "movement": "Then someone trusted was already heading to that airport.",
            "solution": "BootHop transforms existing movement into urgent delivery opportunity.",
        },
        {
            "problem":  "Wrong airport. Urgent trip at risk. No fast option.",
            "movement": "A trusted traveller was already flying that route.",
            "solution": "BootHop connects urgent needs with journeys already happening.",
        },
    ],
    "smart": [
        {
            "problem":  "Every day, thousands of journeys happen with unused delivery potential.",
            "movement": "Flights. Trains. Cars. All carrying unused capacity across cities and borders.",
            "solution": "BootHop unlocks trusted movement already happening. Smarter logistics. Human-powered.",
        },
        {
            "problem":  "Not every urgent delivery needs a new vehicle. The movement already exists.",
            "movement": "Millions of miles travel daily with unused capacity and trusted people.",
            "solution": "BootHop simply coordinates that movement intelligently. Less waste. More meaning.",
        },
    ],
    "cinematic": [
        {
            "problem":  "Every airport holds opportunity. Every departure carries unused potential.",
            "movement": "Trusted journeys move between cities, borders, and airports daily.",
            "solution": "BootHop is the intelligent layer connecting urgent needs with movement already happening.",
        },
        {
            "problem":  "The world moves every second. Flights. Trains. People already going your way.",
            "movement": "That movement has always existed. The coordination layer was missing.",
            "solution": "BootHop builds the smarter path between urgent delivery and trusted human movement.",
        },
    ],
    "community": [
        {
            "problem":  "Sending something important across borders shouldn't cost a fortune or take weeks.",
            "movement": "But someone trusted is already making that journey with space in their luggage.",
            "solution": "BootHop connects you with verified travellers already going your way. Safe. Human. Same day.",
        },
        {
            "problem":  "Your community is already moving every day. Cities. Countries. Airports.",
            "movement": "Trusted people already making the journey. Space already available.",
            "solution": "BootHop helps that community movement solve urgent delivery needs together.",
        },
    ],
}


# ── Hero end lines per bucket ─────────────────────────────────────────────────
HERO_LINES = {
    "family": [
        "Turning journeys into lifelines.",
        "Behind every urgent delivery is a human story.",
        "Someone already going there could change everything.",
        "Every journey carries more than luggage.",
        "Helping families stay connected across borders.",
        "Distance should never stop care.",
        "Moving more than parcels. Moving emotions.",
        "Because some deliveries are deeply personal.",
    ],
    "business": [
        "Helping businesses stay moving.",
        "Because operations cannot afford delay.",
        "Downtime costs more than delivery.",
        "Helping businesses avoid costly downtime.",
        "Trusted movement for critical operations.",
        "Business continuity powered by movement.",
        "When production cannot stop, movement matters.",
        "Helping supply chains move intelligently.",
    ],
    "airport": [
        "The road was already leading there.",
        "Someone nearby could save the day.",
        "The journey was happening anyway.",
        "Built around trust. Designed for urgency.",
        "Because timing changes everything.",
        "Every airport hides opportunity.",
        "A smarter path for urgent delivery.",
        "Forgotten passport. Solution already on the road.",
    ],
    "smart": [
        "The world is already moving. BootHop helps it move smarter.",
        "Movement already exists. We simply coordinate it better.",
        "Less wasted movement. More meaningful delivery.",
        "The future of logistics is shared movement.",
        "The intelligent layer behind urgent delivery.",
        "Turning spare space into opportunity.",
        "One network. Millions of journeys.",
        "Not every delivery needs new movement.",
    ],
    "cinematic": [
        "Where movement meets meaning.",
        "The journey was happening anyway.",
        "Movement creates connection.",
        "One trusted traveller can change everything.",
        "BootHop turns movement into connection.",
        "Built for a world already in motion.",
        "Move smarter. Deliver faster. Stay connected.",
        "Helping the world move with purpose.",
    ],
    "community": [
        "Not just logistics. Human logistics.",
        "Real people powering logistics.",
        "Powered by people already moving.",
        "Diaspora delivery — powered by people, not companies.",
        "Trusted travellers. Smarter logistics.",
        "Movement built on trust.",
        "Making every journey count.",
        "No be courier — na your people carrying it with love.",
    ],
}


# ── Bucket-specific Pexels queries ────────────────────────────────────────────
BUCKET_QUERIES = {
    "family": [
        "african mother door gift surprised emotional",
        "woman unwraps gift tears happy living room",
        "black family hug reunion home front door",
        "woman holds parcel box door smiling emotional",
        "hands hold gift box ribbon presentation",
        "elderly woman receives parcel door surprised",
        "african family video call phone smiling",
        "child runs hugs parent returning home luggage",
        "woman reads message phone crying happy",
        "family living room unbox parcel together",
        "mother opens parcel box reveals gift",
        "young woman sends gift flowers thoughtful",
        "grandma opens birthday present emotional",
        "family photo album memories together",
        "woman holding baby gift handover door",
    ],
    "business": [
        "engineer workshop spare parts urgent solution",
        "mechanic repairs luxury car close up",
        "warehouse worker scanning barcode delivery",
        "business professional boarding plane laptop",
        "supply chain worker urgent freight",
        "office team celebrates deal signed",
        "small business owner packages order focus",
        "logistics driver delivery van city",
        "professional woman phone call urgent office",
        "factory production line worker quality",
        "spare parts shelf automotive workshop tools",
        "courier hands package business recipient",
        "man suit city street walking purposeful",
        "startup office team work late night",
    ],
    "airport": [
        "stressed traveller departure board anxious",
        "passport control queue international terminal",
        "woman checks phone worried airport",
        "man overloaded luggage check-in counter",
        "traveller running airport terminal late",
        "couple embraces airport arrivals gate",
        "child waves parent departure tearful",
        "businessman phone call airport lounge",
        "boarding pass scan gate close-up",
        "flight information board delays",
        "traveller window seat plane clouds pensive",
        "airport police check security documents",
        "woman relief smile boarding gate",
        "man drags heavy suitcase corridor",
    ],
    "smart": [
        "app phone screen loading route map",
        "aerial city traffic movement drone footage",
        "digital logistics network visualisation",
        "warehouse drone aerial automated",
        "train station commuter movement time lapse",
        "city aerial golden hour traffic flow",
        "cargo plane loading runway ramp",
        "woman phone app books delivery confident",
        "man matches phone notification smile",
        "two phones side by side chat booking",
        "logistics truck motorway aerial",
        "hands tap smartphone booking confirmed",
    ],
    "cinematic": [
        "airplane window seat golden hour clouds cinematic",
        "airport terminal golden light bokeh cinematic",
        "slow motion man walking city street confident",
        "slow motion woman hair wind sunset",
        "aerial drone city river bridge golden",
        "suitcase wheels roll terminal slow motion",
        "silhouette airport departure window sunset",
        "slow motion gift box lands hands",
        "hands hold globe map cinematic concept",
        "overhead shot london rooftops aerial",
        "time lapse city night lights bokeh",
        "slow motion handshake business deal close-up",
    ],
    "community": [
        "nigerian family reunion hugging front door",
        "west african gathering outdoor celebration",
        "black community friends street outdoor party",
        "african women laughing sitting together",
        "group friends unbox parcel together living room",
        "diaspora friends reunion hug airport arrivals",
        "african grandmother grandchildren home",
        "nigerian community handover parcel doorstep",
        "church community gathering nigeria",
        "family WhatsApp video call group reaction",
        "aunty receives surprise gift door laughing",
        "cousins open package together bedroom",
        "young nigerians london gathering friends",
        "african family celebration home gathering",
    ],
}


# ── Bucket hashtags (TikTok — NG/diaspora corridor) ───────────────────────────
BUCKET_HASHTAGS = {
    "family":    "#BootHop #DiasporaMagic #SameDayDelivery #Family #LondonToLagos #UKNaija #Diaspora #DiasporaLife #AbroadLife #LondonLife #NaijaUK",
    "business":  "#BootHop #Logistics #SupplyChain #B2B #UrgentDelivery #BusinessDelivery #StartUp #Innovation #SameDayDelivery #SME #Operations",
    "airport":   "#BootHop #Airport #Travel #UrgentDelivery #TravelHack #AirportLife #SameDayDelivery #Innovation #Startup #Logistics",
    "smart":     "#BootHop #SmartLogistics #Innovation #FutureOfDelivery #SupplyChain #Startup #HumanPowered #GreenLogistics #Movement",
    "cinematic": "#BootHop #Movement #PremiumDelivery #Innovation #Startup #Logistics #CinematicTravel #HumanPowered #TrustedMovement",
    "community": "#BootHop #DiasporaMagic #NaijaUK #LondonToLagos #UKNigeria #DiasporaLife #NigerianTikTok #AfrobeatsLife #CommunityDelivery",
}

# ── Route-specific hashtags — local UK ─────────────────────────────────────────
UK_ROUTE_HASHTAGS = {
    "tiktok": (
        "#BootHop #UKDelivery #SameDayUK #StudentLife #UniLife #UKStudents "
        "#LondonToManchester #LondonToEdinburgh #LondonToGlasgow #UKLogistics "
        "#DomesticDelivery #StudentDelivery #ForgottenItems #UKStartup #BritishLife"
    ),
    "instagram": (
        "#BootHop #UKDelivery #SameDayUK #StudentLife #UniLife #UKStudents "
        "#BirminghamToLondon #LondonToGlasgow #LondonToLeeds #LondonToEdinburgh "
        "#StudentDelivery #ForgottenItems #UKStartup #BritishLife #UKLogistics "
        "#PersonalShopper #LondonLife #UKTech #TrainLife #HumanLogistics"
    ),
    "youtube": (
        "#BootHop #UKDelivery #SameDayUK #StudentLife #UniLife #UKStartup "
        "#LondonToManchester #UKLogistics #StudentDelivery #BritishLife"
    ),
}

# ── Route-specific hashtags — Euro corridor ────────────────────────────────────
EU_ROUTE_HASHTAGS = {
    "tiktok": (
        "#BootHop #UKtoEurope #EuropeanDelivery #ExpatLife #BritishAbroad "
        "#LondonToBerlin #LondonToParis #LondonToBarcelona #Expat #EuropeLife "
        "#UKEurope #DiasporaEurope #EuroTrip #SameDayDelivery #UKStartup"
    ),
    "instagram": (
        "#BootHop #UKtoEurope #EuropeanDelivery #ExpatLife #BritishAbroad "
        "#LondonToBerlin #LondonToParis #LondonToAmsterdam #LondonToBarcelona "
        "#Expat #EuropeLife #DiasporaEurope #LutonAirport #StanstedAirport "
        "#Eurostar #SameDayDelivery #UKStartup #TravelHack #HumanLogistics"
    ),
    "youtube": (
        "#BootHop #UKtoEurope #EuropeanDelivery #ExpatLife #BritishAbroad "
        "#LondonToBerlin #LondonToParis #UKEurope #DiasporaEurope #SameDayDelivery"
    ),
}


# ── Diaspora-specific queries (default pool) ──────────────────────────────────
# Large pool so the pipeline never repeats the same query for 14+ days.
# Organised by visual feel so variety is guaranteed across categories.
DIASPORA_QUERIES = [
    # ── Airport variety ──────────────────────────────────────────────────────
    "airport departure lounge window sunlight",
    "airplane wing sunrise flight above clouds",
    "boarding pass held hand close-up",
    "flight attendant aisle cabin service",
    "airport terminal wide shot busy passengers",
    "runway airplane taxiing departure",
    "airport arrivals board screen scrolling",
    "pilot cockpit window takeoff",
    "luggage carousel baggage claim arrivals",
    "airport security check shoes belt queue",
    "woman dragging suitcase airport corridor",
    "man checking phone airport gate lounge",
    "passport control queue international",
    "overhead luggage compartment airplane",
    "airport coffee shop traveler working laptop",
    # ── Gifts & delivery variety ─────────────────────────────────────────────
    "woman gasps opens gift box surprise living room",
    "hands unwrapping ribbon gift box slow motion",
    "child excited gift box birthday",
    "delivery courier hands box to door smiling",
    "woman door parcel happy surprise emotional",
    "man opens delivery box contents reveal",
    "luxury gift box ribbon gold presentation",
    "package left door step neighbours",
    "woman signs delivery tablet front door",
    "gift bag handed over shopping centre",
    "parcel brown paper string tied rustic",
    "young woman unboxing haul bedroom excited",
    "hands holding wrapped present red ribbon",
    "surprise delivery office colleague",
    "guy opens large cardboard box living room",
    # ── Emotional reactions ───────────────────────────────────────────────────
    "woman happy tears phone screen reaction",
    "man reads phone message pumps fist",
    "woman covers mouth shock happy news",
    "elderly woman receives gift emotional tears",
    "family group hug front door emotional",
    "man video call phone laughing happy",
    "woman shows phone screen excited friend",
    "young woman jumping joy good news phone",
    "man fist pump yes success happy",
    "couple hugging front door reunion emotional",
    "children run to parent returning home",
    # ── Africa / diaspora lifestyle ───────────────────────────────────────────
    "lagos nigeria market street colourful busy",
    "west africa street vendor colourful",
    "nairobi kenya city modern downtown",
    "accra ghana vibrant street life",
    "african city skyline modern buildings",
    "lagos victoria island evening lights",
    "african neighbourhood community gathering",
    "market women selling fresh produce africa",
    "african family home living room laughing",
    "young african professional phone office",
    "london multicultural street south london",
    "brixton market london diverse community",
    "peckham london african community street",
    "uk diverse neighbourhood corner shop",
    # ── Business & professional ───────────────────────────────────────────────
    "professional woman laptop coffee cafe focused",
    "man suit phone walking city street",
    "business team meeting desk discussion",
    "warehouse worker scanning barcode",
    "logistics driver truck delivery van",
    "factory floor worker production line",
    "mechanic workshop fixing car engine",
    "spare parts shelf automotive workshop",
    "engineer blueprints construction site",
    "small business owner packaging orders",
    # ── Shopping & lifestyle ──────────────────────────────────────────────────
    "woman shopping bags high street walking",
    "shopping centre escalator bags luxury",
    "supermarket aisle selecting product",
    "pharmacy counter medication purchase",
    "market stall vendor exchange goods",
    "butcher fresh fish market counter",
    "bakery display pastry selection",
    "cosmetics beauty counter selection",
    # ── Money & payment ───────────────────────────────────────────────────────
    "phone tap payment contactless terminal",
    "woman smiles phone banking app",
    "man cash wallet satisfied payment",
    "money transfer app phone receipt",
    "happy customer payment confirmed screen",
    # ── Travel lifestyle ──────────────────────────────────────────────────────
    "traveller window seat plane view clouds",
    "backpacker hostel trip adventure",
    "woman packs suitcase bedroom organised",
    "travel flat lay passport tickets phone",
    "road trip car window scenery",
    "city train commute diverse passengers",
]

# Hook keyword → specific queries (match clip to hook content)
HOOK_QUERIES = {
    # ── People / setup visuals (Phase 1 = scenario, NOT the gift-receipt payoff) ──
    "beautiful":    ["beautiful black woman casual lifestyle portrait", "elegant woman smiling phone lifestyle", "glamorous woman relaxed stylish"],
    "lady":         ["stylish woman casual lifestyle conversation", "elegant woman phone call smiling", "beautiful woman relaxed lifestyle"],
    "mummy":        ["african mother home warm family lifestyle", "nigerian mother family home relaxed", "black mother daughter casual home"],
    "sexy":         ["confident stylish woman casual lifestyle", "glamorous woman relaxed portrait", "elegant woman conversation smiling"],
    "agbada":       ["nigerian man traditional agbada outfit elegant", "yoruba man traditional attire ceremony", "nigerian man agbada regal"],
    "slippers":     ["luxury slippers hermes men gift box", "man trying luxury slippers gift", "premium slippers unboxing gift"],
    "watch":        ["man admiring luxury watch wrist smiling", "man luxury watch wrist detail closeup", "designer watch gift unboxing man"],
    "wrist":        ["man wrist luxury watch detail closeup", "man admiring watch on wrist", "luxury watch wrist man smiling"],
    "admiring":     ["man admiring luxury watch wrist smiling", "man looking at new watch happy", "man luxury item admiring detail"],
    # ── Shopping / luxury goods ────────────────────────────────────────────────
    "shoes":        ["luxury shoes heels gift box wrapped", "woman shoe shopping boutique bag", "sneaker unboxing gift"],
    "selfridges":   ["luxury department store bags shopping", "oxford street london shopping bags", "upscale london store gift"],
    "primark":      ["shopping bags high street fashion", "budget fashion shopping haul bags", "woman shopping bags street"],
    "harrods":      ["luxury gift bag knightsbridge london", "upscale gift shopping bag", "premium gift wrapped box"],
    "designer":     ["designer handbag luxury gift wrapped", "luxury brand shopping bag", "upscale boutique gift bag"],
    "hermes":       ["luxury handbag gift presentation box", "premium designer bag unboxing", "luxury brand gift delivered"],
    "victoria":     ["lingerie gift box wrapped ribbon", "beauty gift shopping bag", "woman receiving luxury gift"],
    "sephora":      ["makeup cosmetics gift bag delivered", "beauty products box delivered", "cosmetics unboxing gift"],
    "makeup":       ["makeup cosmetics gift bag beauty", "beauty counter products display", "cosmetics gift wrapped"],
    "perfume":      ["perfume luxury bottle gift box", "fragrance gift wrapped presentation", "luxury scent gift delivered"],
    "mac":          ["makeup cosmetics beauty products box", "beauty gift bag delivered", "cosmetics shopping bag"],
    "zara":         ["fashion shopping bags street style", "woman clothing haul shopping", "fashion gift bag delivered"],
    "jd sports":    ["trainers sneakers shoe shop display", "sneaker shopping bag sports store", "shoe gift box delivered"],
    "sneakers":     ["sneaker unboxing gift box shoes", "trainers collection display", "shoe shopping bag gift"],
    "trainers":     ["trainers sneakers shoe gift box", "sports shoe shopping bag", "shoe unboxing delivery"],
    "crocs":        ["crocs shoes gift box", "casual shoe shopping bag delivered", "shoe gift delivered door"],
    "crispy":       ["donut box gift delivery sweet", "krispy kreme box celebration", "pastry gift box delivered"],
    "krispy kreme": ["donut box gift celebration sweet", "bakery box delivery", "pastry sweet gift box"],
    "chocolate":    ["chocolate gift box wrapped ribbon", "cadbury chocolate gift presented", "sweet gift box delivered"],
    "cadbury":      ["chocolate gift box family", "sweet gift wrapped delivery", "chocolate celebration box"],
    "biscuit":      ["biscuit gift tin presented", "sweet snack gift box", "harrods biscuits tin gift"],
    "costco":       ["bulk snacks food shopping trolley", "american snack haul shopping bag", "food shopping delivery box"],
    "milo":         ["drinks tin gift box delivered", "grocery food item delivered", "food product gift family"],
    # ── Luxury / special items ─────────────────────────────────────────────────
    "bentley":      ["luxury car close-up detail", "upscale car garage mechanic", "luxury automobile parts workshop"],
    "rolls":        ["luxury car showroom detail", "premium automobile interior", "upscale vehicle workshop"],
    "car":          ["car mechanic workshop spare part", "automotive parts delivery", "mechanic fixing car workshop"],
    "salmon":       ["premium fish wrapped delivery box", "fresh seafood market professional", "grocery premium food box"],
    # ── Travel / airport ──────────────────────────────────────────────────────
    "flying":       ["airplane boarding gate departure", "aircraft taking off runway", "airport departure passengers"],
    "flight":       ["airplane boarding passengers gate", "airport check-in queue luggage", "airplane window seat departure"],
    "heathrow":     ["heathrow terminal passengers international", "airport departure gate crowded", "airport boarding gate"],
    "airport":      ["airport departure gate traveler luggage", "airport check-in queue passengers", "boarding gate international"],
    "tonight":      ["airplane night flight departure", "airport evening departure gate", "night flight boarding"],
    "suitcase":     ["suitcase packing gifts clothes organised", "luggage carousel airport arrivals", "woman packing suitcase items"],
    "luggage":      ["luggage suitcase airport carousel", "packing suitcase travel", "woman luggage airport walking"],
    # ── Destinations ──────────────────────────────────────────────────────────
    "lagos":        ["lagos nigeria city modern vibrant", "victoria island lagos nigeria", "lagos nigeria people street"],
    "abuja":        ["abuja nigeria modern city", "nigeria capital city street", "nigeria modern architecture"],
    "london":       ["london city multicultural people", "london heathrow airport terminal", "london street diverse community"],
    "frankfurt":    ["frankfurt germany city business", "germany european city street", "frankfurt airport terminal"],
    "amsterdam":    ["amsterdam netherlands city canal", "netherlands europe street travel", "amsterdam airport schiphol"],
    "new york":     ["new york city street diverse", "new york airport jfk departure", "manhattan street people"],
    "manchester":   ["manchester city uk street", "uk city diverse community", "north england city street"],
    "germany":      ["germany europe city street", "german city modern architecture", "europe airport departure"],
    # ── Package / delivery ────────────────────────────────────────────────────
    "package":      ["woman opening parcel box door excited", "package delivery door handoff smiling", "parcel box unwrapping gift happy"],
    "parcel":       ["parcel box delivery door happy", "woman receiving package excited", "parcel handoff smiling"],
    "box":          ["gift box unwrapping excited family", "parcel box delivered door", "box opened happy family"],
    "delivery":     ["package delivery door smiling happy", "same day delivery handoff", "parcel box gift handed"],
    "carry":        ["traveler bag luggage airport carrying", "woman carrying bag suitcase", "man carrying luggage travel"],
    "land":         ["plane landing airport runway", "airport arrivals excited", "luggage carousel arrivals"],
    "reach":        ["airport arrivals happy family reunion", "package delivered door excited", "family reunion hugging"],
    "arrived":      ["airport arrivals family reunion hugging", "package delivered door opened", "woman receiving parcel excited"],
    "door":         ["woman opening front door package", "door delivery smiling package", "package arrived front door"],
    "same day":     ["same day delivery fast handoff", "urgent package delivery door", "express delivery smiling"],
    "space":        ["luggage suitcase space packing", "traveler checking baggage allowance", "airline check-in luggage"],
    "earn":         ["phone payment earn money app", "side hustle income phone smile", "traveler earning money airport"],
    "income":       ["person earning money phone app", "side income hustle airport", "payment received phone happy"],
    # ── Events ────────────────────────────────────────────────────────────────
    "wedding":      ["nigerian wedding ceremony colourful", "african wedding bride groom joy", "wedding celebration dance"],
    "owambe":       ["nigerian party celebration outfit", "african party food dancing colourful", "west african gathering joy"],
    "birthday":     ["birthday gift box wrapped ribbon", "birthday celebration family candles", "gift delivery birthday happy"],
    "cake":         ["birthday cake celebration candles", "cake box delivery happy family", "bakery sweet celebration"],
    "party":        ["celebration party family happy", "african party colourful joy", "family celebration together"],
    # ── Nigerian culture ───────────────────────────────────────────────────────
    "gele":         ["nigerian woman headwrap traditional", "african headwrap elegant attire", "nigerian woman fashion"],
    "aso-ebi":      ["ankara fabric african fashion", "nigerian fashion colourful dress", "african fabric wedding attire"],
    "ankara":       ["ankara fabric colourful african", "nigerian fashion fabric", "african print dress fabric"],
    "egusi":        ["african food cooking pot traditional", "nigeria home cooking family", "west african kitchen food"],
    "suya":         ["nigerian grilled meat street food", "west africa street food stall", "grilled meat outdoor market"],
    "jollof":       ["nigerian food pot cooking rice", "african food jollof rice family", "west african cooking"],
    "chin-chin":    ["nigerian snack food celebration", "west african snack gift", "nigerian food gift bag"],
    "olorun":       ["nigerian woman emotional prayer", "african woman grateful spiritual", "nigeria family prayer"],
    "chineke":      ["nigerian family emotional reunion", "igbo community nigeria joy", "african family hugging"],
    "yoruba":       ["yoruba nigeria cultural celebration", "nigeria traditional attire celebration", "west africa culture"],
    "nna men":      ["nigerian friends celebration joy", "west african men laughing", "nigeria community joy"],
    "gbe body":     ["nigerian celebration dance afrobeat", "africa party dance joy outdoor", "west african party street"],
    "wahala":       ["nigeria community street life", "lagos people everyday life", "nigeria street community"],
    # ── Family / emotion ──────────────────────────────────────────────────────
    "mum":          ["african mother home family casual warm", "mother daughter conversation home", "black mother relaxed family home"],
    "mama":         ["african mother family home warm casual", "mother daughter lifestyle home", "nigerian mother family portrait"],
    "aunty":        ["african woman relaxed family home", "black woman casual family lifestyle", "nigerian woman home family"],
    "grandma":      ["elderly woman relaxed family home", "grandmother family casual portrait", "older woman family home warm"],
    "dad":          ["african father family casual home", "black man family portrait relaxed", "nigerian father family lifestyle"],
    "family":       ["african family casual home warm together", "black family relaxed home lifestyle", "family casual portrait together"],
    "video call":   ["woman smiling phone video call casual", "person phone call happy casual", "woman video call relaxed smiling"],
    "tears":        ["woman emotional video call phone", "woman phone call emotional distant", "woman missing family phone"],
    # ── Money / savings ────────────────────────────────────────────────────────
    "save":         ["phone payment app savings", "woman smiling phone payment", "money saved payment happy"],
    "cheaper":      ["payment phone app saving money", "comparing prices phone", "money saving happy phone"],
    "fraction":     ["payment received phone savings", "woman paying phone app smiling", "affordable payment happy"],
    # ── Spanish / Latin ────────────────────────────────────────────────────────
    "mamá":         ["latin mother gift door emotional", "hispanic mother daughter hug", "latin family home door happy"],
    "familia":      ["latin family gathering celebration", "hispanic family smiling together", "latin family reunion joy"],
    "madrid":       ["madrid spain city street", "spain europe city people", "european city travel"],
    "barcelona":    ["barcelona spain city people", "spain europe street", "european city travel"],
    "bogotá":       ["bogota colombia city street", "latin america city", "south america travel"],
    "lima":         ["lima peru city travel", "latin america journey", "south america city"],
    "paquete":      ["latin family receiving gift box", "hispanic family parcel delivered", "latin family door package"],
}


# ── Phase-specific query pools ─────────────────────────────────────────────────
# Phase 2 (8-17s): the PROBLEM — worry, challenge, distance, gap
# Phase 2 (8-17s): the JOURNEY — gift/item being packed, handed over, travelling
# Keeps the viewer engaged between the hook and the payoff
PHASE_JOURNEY_QUERIES = [
    "traveller packing gifts suitcase carefully",
    "person handing gift package traveller airport",
    "airport passenger boarding carrying gifts bag",
    "traveller luggage gifts items checking in",
    "gift wrapped box ready for travel",
    "man suitcase packing gifts carefully",
    "courier handing package over smiling",
    "airport departure person gifts carry",
    "traveller gift bag boarding gate flight",
    "person wrapping gifts travel suitcase",
    "airport check-in bags gifts traveller",
    "diaspora traveller carrying packages gifts",
]

# Phase 3 (17-27s): the RESOLUTION — happy receipt, unboxing, gratitude, video call
# Shows the EMOTIONAL PAYOFF: delivery arrives, excitement, thank you call
PHASE_SOLUTION_QUERIES = [
    "woman happy door gift delivery smiling excited",
    "woman gift box unwrapping happy surprised",
    "woman receiving gift door big smile overjoyed",
    "person video call happy excited grateful emotional",
    "woman video call phone happy thank you emotional",
    "woman opening gift box happy tears joy",
    "person grateful gift delivered door smiling",
    "woman on phone excited happy reaction",
    "mother receiving gift door happy emotional tears",
    "woman video call happy excited screaming joy",
    "family member gift door celebration hugging",
    "woman delighted parcel arrived front door",
]

# Phase 4 (27-30s): the BRAND MOMENT — mix of family warmth AND business accomplishment
# Rotates so family hooks end on family scenes and business hooks end on professional wins
PHASE_BRAND_QUERIES = [
    # Family warmth
    "african family together happy home warmth",
    "mother daughter hugging emotional happy",
    "black family celebration smiling joy",
    "family reunion hugging togetherness love",
    "diaspora family reunion emotional joy",
    "happy family home together love warmth",
    # Business / professional accomplishment
    "mechanic car fixed satisfied smiling workshop",
    "mechanic parts installed car success happy",
    "engineer spare parts received satisfied professional",
    "plumber job complete pipes fixed satisfied",
    "technician replacement part installed success",
    "worker delivery parts on time satisfied professional",
    "businessman handshake deal done satisfied smiling",
    "professional delivery received office satisfied",
    "workshop mechanic car repaired happy customer",
    "business owner parts arrived on time relief",
]


# ── Query selection ────────────────────────────────────────────────────────────
def select_phased_queries(hook, bucket, exclude_queries=None):
    """
    Return queries split into 4 narrative phases so clip visuals match the voiceover.

    Phase 1 (2 clips, 0-8s)   — Hook scene: match the hook keyword visually
    Phase 2 (2 clips, 8-17s)  — Problem scene: worry / challenge / distance
    Phase 3 (3 clips, 17-27s) — Solution scene: delivery / happy receipt / relief
    Phase 4 (1 clip,  27-30s) — Brand moment: family together / celebration
    """
    exclude_set = set(exclude_queries or [])

    def _pick(pool: list, n: int, already_used: set) -> list:
        shuffled = list(pool)
        random.shuffle(shuffled)
        result = []
        for q in shuffled:
            if q not in already_used and q not in exclude_set:
                result.append(q)
                already_used.add(q)
                if len(result) == n:
                    break
        # If we couldn't fill n slots, relax the exclude_set constraint
        if len(result) < n:
            for q in shuffled:
                if q not in already_used:
                    result.append(q)
                    already_used.add(q)
                    if len(result) == n:
                        break
        return result

    used: set = set()

    # Phase 1 — hook-matched queries (same logic as before)
    hook_lower = hook.lower()
    hook_matched = []
    for keyword, queries in HOOK_QUERIES.items():
        if keyword in hook_lower:
            for q in queries[:2]:
                if q not in hook_matched and q not in exclude_set:
                    hook_matched.append(q)

    # Fall back to bucket queries if hook not in HOOK_QUERIES
    if not hook_matched:
        bucket_q = list(BUCKET_QUERIES.get(bucket, []))
        random.shuffle(bucket_q)
        hook_matched = [q for q in bucket_q if q not in exclude_set]

    p1 = []
    for q in hook_matched[:4]:
        if q not in used and q not in exclude_set:
            p1.append(q)
            used.add(q)
        if len(p1) == 2:
            break
    # Fill p1 from diaspora if short
    if len(p1) < 2:
        for q in random.sample(list(DIASPORA_QUERIES), min(6, len(DIASPORA_QUERIES))):
            if q not in used and q not in exclude_set:
                p1.append(q)
                used.add(q)
            if len(p1) == 2:
                break

    p2 = _pick(PHASE_JOURNEY_QUERIES, 2, used)
    p3 = _pick(PHASE_SOLUTION_QUERIES, 3, used)
    p4 = _pick(PHASE_BRAND_QUERIES, 1, used)

    return p1 + p2 + p3 + p4


def select_queries(hook, bucket, count=8, exclude_queries=None):
    """Wrapper kept for compatibility — delegates to select_phased_queries."""
    return select_phased_queries(hook, bucket, exclude_queries=exclude_queries)[:count]


# ── Text helpers ───────────────────────────────────────────────────────────────
def strip_emoji(text):
    """Remove emojis, convert smart punctuation to ASCII for ffmpeg drawtext."""
    text = text.replace("…", "...").replace("–", "-").replace("—", "-")
    text = text.replace("“", '"').replace("”", '"')
    text = text.replace("‘", "'").replace("’", "'")
    # Remove remaining non-ASCII (emojis etc.)
    clean = re.sub(r'[^\x00-\x7F]+', '', text)
    clean = clean.replace("'", "").replace(":", " ").replace('"', "").replace("&", "and")
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean


def split_text(text, max_len=28):
    """Split text into max 3 lines of max_len chars each."""
    clean = strip_emoji(text)
    words = clean.split()
    lines, cur = [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if len(test) <= max_len:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    if len(lines) > 3:
        lines = lines[:2] + [" ".join(lines[2:])]
    while len(lines) < 3:
        lines.append("")
    return lines[0], lines[1], lines[2]


def split_pov_hook(hook):
    """
    Format hook for cinematic TikTok display.
    POV hooks: 'POV :' shown alone on line 1 (yellow), content on 3 lines below.
    Non-POV hooks: no yellow label, full text split across 3 lines.
    Returns (label, line1, line2, line3).
    """
    _, hook = detect_lang(hook)
    raw   = hook.strip()
    upper = raw.upper()
    if upper.startswith("POV:"):
        label       = "POV :"
        content_raw = raw[4:].strip()
    elif upper.startswith("POV "):
        label       = "POV :"
        content_raw = raw[4:].strip()
    else:
        label       = ""       # no yellow POV label for statement/question hooks
        content_raw = raw

    content = strip_emoji(content_raw)

    words = content.split()
    total = len(words)

    # For non-POV hooks use slightly more words per display line (more text to fill the space)
    if not label:
        wpd = 5 if total > 12 else (4 if total > 7 else 3)
    else:
        wpd = 4 if total > 9 else (3 if total > 5 else 2)

    chunks = []
    while words:
        chunks.append(" ".join(words[:wpd]))
        words = words[wpd:]

    while len(chunks) < 3:
        chunks.append("")

    if len(chunks) > 3:
        chunks = chunks[:2] + [" ".join(chunks[2:])]

    return label, chunks[0], chunks[1], chunks[2]


# ── Content selection (7-day memory) ──────────────────────────────────────────
def load_lines(filename):
    path = DATA / filename
    return [l.strip() for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def load_used():
    path = DATA / "used_content.json"
    if path.exists():
        try:
            text = path.read_text(encoding="utf-8").strip()
            if text:
                return json.loads(text)
        except Exception:
            pass
    return {"hooks": [], "engagements": [], "dates": []}


def save_used(hook, engagement):
    path    = DATA / "used_content.json"
    data    = load_used()
    today   = datetime.now().strftime("%Y-%m-%d")
    cutoff  = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    data["hooks"].append(hook)
    data["engagements"].append(engagement)
    data["dates"].append(today)
    # prune entries older than 7 days
    filtered = {"hooks": [], "engagements": [], "dates": []}
    for i, d in enumerate(data["dates"]):
        if d >= cutoff:
            filtered["hooks"].append(data["hooks"][i])
            filtered["engagements"].append(data["engagements"][i])
            filtered["dates"].append(d)
    path.write_text(json.dumps(filtered, indent=2, ensure_ascii=False), encoding="utf-8")


# ── 14-day visual asset deduplication ─────────────────────────────────────────
_VISUAL_LOG = DATA / "used_visuals.json"
_VISUAL_WINDOW_DAYS = 14


def _load_visuals() -> dict:
    if _VISUAL_LOG.exists():
        try:
            return json.loads(_VISUAL_LOG.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"videos": [], "photos": []}


def _save_visuals(data: dict):
    _VISUAL_LOG.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _prune_visuals(data: dict) -> dict:
    cutoff = (datetime.now() - timedelta(days=_VISUAL_WINDOW_DAYS)).strftime("%Y-%m-%d")
    data["videos"] = [v for v in data["videos"] if v.get("date", "") >= cutoff]
    data["photos"] = [v for v in data["photos"] if v.get("date", "") >= cutoff]
    return data


def _mark_visual_used(pexels_id: int, query: str, is_photo: bool = False):
    data = _prune_visuals(_load_visuals())
    entry = {"id": pexels_id, "query": query, "date": datetime.now().strftime("%Y-%m-%d")}
    key = "photos" if is_photo else "videos"
    if not any(v["id"] == pexels_id for v in data[key]):
        data[key].append(entry)
    _save_visuals(data)


def _recently_used_ids(is_photo: bool = False) -> set:
    data = _prune_visuals(_load_visuals())
    key = "photos" if is_photo else "videos"
    return {v["id"] for v in data[key]}


def _photo_to_clip(photo_url: str, dest: Path, duration: int = 4) -> bool:
    """Download a Pexels photo and convert to a slow Ken Burns zoom video clip."""
    try:
        img_data = requests.get(photo_url, timeout=30).content
        img_path  = dest.with_suffix(".jpg")
        img_path.write_bytes(img_data)
        run_ff(
            "-loop", "1", "-i", str(img_path),
            "-t", str(duration),
            "-vf",
            "scale=1080:1920:force_original_aspect_ratio=increase,"
            "crop=1080:1920,"
            "zoompan=z='min(zoom+0.003,1.2)':d=120:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920,"
            "setsar=1",
            "-c:v", "libx264", "-crf", "22", "-preset", "fast",
            "-r", "30", "-pix_fmt", "yuv420p", "-an", str(dest)
        )
        if img_path.exists():
            img_path.unlink()
        return dest.exists()
    except Exception as e:
        print(f"  Photo-to-clip failed: {e}")
        return False


def load_performance_weights():
    """Load weekly performance weights. Returns defaults (all 1.0) if not yet generated."""
    wfile = DATA / "performance_weights.json"
    defaults = {
        "buckets":    {b: 1.0 for b in DAY_BUCKETS.values()},
        "music":      {"library": 1.0, "trending": 1.0},
        "versions":   {"v1": 1.0, "v2": 1.0},
        "hook_langs": {"EN": 1.0, "NG": 1.0, "ES": 1.0},
        "top_hooks":  [],
    }
    if not wfile.exists():
        return defaults
    try:
        return {**defaults, **json.loads(wfile.read_text(encoding="utf-8"))}
    except Exception:
        return defaults


def pick_content(bucket="community", exclude=None):
    """
    Pick one hook + engagement weighted by:
      - Route distribution: 65% NG/diaspora, 20% local UK [UK], 15% Euro [EU]
      - Current 4-week theme keywords (2.5×) — shifts tone each week automatically
      - Last week's top performers (2.0×) — keeps what's working
      - Bucket keywords (pool filter) — keeps content on-theme for the day
      - Weekly analysis gap keywords (1.8×) — applied recommendations
    """
    import random as _rnd
    exclude     = exclude or []
    hooks       = load_lines("hooks.txt")
    engagements = load_lines("engagements.txt")
    used        = load_used()
    weights     = load_performance_weights()
    top_hooks   = set(weights.get("top_hooks", []))
    _, theme    = get_weekly_theme()
    theme_kws   = [k.lower() for k in theme["hook_keywords"]]

    # Load analysis recommendations (written by weekly_analysis.py when user taps Apply)
    _wi_path = DATA / "weekly_insights.json"
    analysis_kws = []
    try:
        if _wi_path.exists():
            _wi = json.loads(_wi_path.read_text(encoding="utf-8"))
            analysis_kws = [k.lower() for k in _wi.get("gap_keywords", [])]
    except Exception:
        pass

    avail_h = [h for h in hooks if h not in used["hooks"] and h not in exclude]
    if not avail_h:
        avail_h = [h for h in hooks if h not in exclude] or hooks

    # Split pool by route category
    def _category(h):
        if h.startswith("[UK]"):
            return "uk"
        if h.startswith("[EU]"):
            return "eu"
        if h.startswith("[ES]"):
            return "es"
        return "ng"

    ng_pool = [h for h in avail_h if _category(h) == "ng"]
    uk_pool = [h for h in avail_h if _category(h) == "uk"]
    eu_pool = [h for h in avail_h if _category(h) in ("eu", "es")]

    # Route distribution: 65% NG/diaspora, 20% local UK, 15% Euro
    # Fall back gracefully if a category is empty
    roll = _rnd.random()
    if roll < 0.65 and ng_pool:
        base_pool = ng_pool
    elif roll < 0.85 and uk_pool:
        base_pool = uk_pool
    elif eu_pool:
        base_pool = eu_pool
    else:
        base_pool = ng_pool or uk_pool or avail_h  # final fallback

    # Further filter by bucket keywords if possible
    keywords = BUCKET_KEYWORDS.get(bucket, [])
    bucket_filtered = [h for h in base_pool if any(k in h.lower() for k in keywords)]
    pool = bucket_filtered if bucket_filtered else base_pool

    def _weight(h):
        h_lower = h.lower()
        w = 1.0
        if any(kw in h_lower for kw in theme_kws):
            w *= 2.5   # theme match — strongest signal
        if h in top_hooks:
            w *= 2.0   # last week's performer
        if analysis_kws and any(kw in h_lower for kw in analysis_kws):
            w *= 1.8   # weekly analysis gap keyword
        return w

    hook_weights = [_weight(h) for h in pool]
    chosen_hook  = _rnd.choices(pool, weights=hook_weights, k=1)[0]

    avail_e    = [e for e in engagements if e not in used["engagements"]]
    chosen_eng = _rnd.choice(avail_e) if avail_e else _rnd.choice(engagements)

    return chosen_hook, chosen_eng


# ── Pexels clip download ────────────────────────────────────────────────────────
def zoom_clip_if_no_face(clip_path, index):
    """Apply 15% zoom to first 0.4s if first frame has no clear face."""
    try:
        import cv2
        cap = cv2.VideoCapture(str(clip_path))
        ret, frame = cap.read()
        cap.release()
        if not ret:
            return str(clip_path)
        h, w = frame.shape[:2]
        gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        haar  = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        faces = cv2.CascadeClassifier(haar).detectMultiScale(gray, 1.1, 4, minSize=(40, 40))
        face_area = sum(fw * fh for (_, _, fw, fh) in faces) if len(faces) else 0
        has_face  = face_area > 0.06 * w * h

        if has_face:
            print(f"  Clip {index+1}: face detected — no zoom needed")
            return str(clip_path)

        zoomed = TEMP / f"pov_clip_{index}_zoomed.mp4"
        face_script = BASE / "face_detector_zoom.py"
        if face_script.exists():
            subprocess.run(
                ["python", str(face_script), str(clip_path), "--out", str(zoomed)],
                capture_output=True
            )
            if zoomed.exists():
                print(f"  Clip {index+1}: zoomed 15% (no face in frame)")
                return str(zoomed)
        # Fallback: simple ffmpeg zoom
        run_ff("-i", str(clip_path), "-t", "0.4",
               "-vf", "zoompan=z='min(zoom+0.01,1.15)':d=1:s=1080x1920",
               "-c:v", "libx264", "-crf", "22", "-an", str(zoomed))
        return str(zoomed) if zoomed.exists() else str(clip_path)
    except Exception as e:
        print(f"  Zoom check failed: {e}")
        return str(clip_path)


def download_clips(hook, bucket, count=8, prefix="", exclude_queries=None):
    """
    Download clips. Returns (clips_list, queries_used).
    - Skips Pexels video IDs used in the last 14 days.
    - Falls back to a Pexels photo (Ken Burns zoom) when all videos are exhausted.
    - exclude_queries: pass V1's queries for V2 to guarantee different scenes.
    """
    clips          = []
    used_queries   = []
    headers        = {"Authorization": PEXELS_KEY}
    queries        = select_queries(hook, bucket, count, exclude_queries=exclude_queries)
    recent_vid_ids = _recently_used_ids(is_photo=False)
    recent_img_ids = _recently_used_ids(is_photo=True)

    # Load permanent blocklist — IDs banned from all BootHop content
    try:
        from scripts.media_blocklist import blocked_video_ids as _bv, blocked_photo_ids as _bp
        _blocked_vids   = _bv()
        _blocked_photos = _bp()
    except Exception:
        _blocked_vids, _blocked_photos = set(), set()

    def _fresh_video(vids: list) -> dict | None:
        """Pick a video not used in the last 14 days and not on the blocklist."""
        allowed = [v for v in vids if int(v.get("id", 0)) not in _blocked_vids]
        fresh   = [v for v in allowed if v.get("id") not in recent_vid_ids]
        pool    = fresh if fresh else allowed
        return random.choice(pool) if pool else None

    def _try_photo_fallback(query: str, dest: Path) -> bool:
        """Try Pexels Photos API and convert to clip with Ken Burns zoom."""
        enc = requests.utils.quote(query)
        url = (f"https://api.pexels.com/v1/search?query={enc}"
               f"&per_page=15&orientation=portrait")
        try:
            res    = requests.get(url, headers=headers, timeout=15).json()
            photos = res.get("photos", [])
            allowed = [p for p in photos if int(p.get("id", 0)) not in _blocked_photos]
            fresh  = [p for p in allowed if p.get("id") not in recent_img_ids]
            pool   = fresh if fresh else allowed
            if not pool:
                return False
            photo  = random.choice(pool)
            img_url = (photo.get("src", {}).get("portrait")
                       or photo.get("src", {}).get("large2x")
                       or photo.get("src", {}).get("large"))
            if not img_url:
                return False
            ok = _photo_to_clip(img_url, dest)
            if ok:
                _mark_visual_used(photo["id"], query, is_photo=True)
                print(f"    → photo fallback: {query[:45]}")
            return ok
        except Exception as e:
            print(f"    → photo fallback failed: {e}")
            return False

    for i, query in enumerate(queries):
        enc  = requests.utils.quote(query)
        dest = TEMP / f"{prefix}clip_{i}.mp4"
        try:
            # ── 1. Try primary video search ────────────────────────────────
            res  = requests.get(
                f"https://api.pexels.com/videos/search?query={enc}"
                f"&per_page=15&orientation=portrait&size=medium",
                headers=headers, timeout=15
            ).json()
            vids = res.get("videos", [])

            # ── 2. If primary empty, try a random diaspora query ───────────
            if not vids:
                enc2 = requests.utils.quote(random.choice(DIASPORA_QUERIES))
                res  = requests.get(
                    f"https://api.pexels.com/videos/search?query={enc2}"
                    f"&per_page=15&orientation=portrait",
                    headers=headers, timeout=15
                ).json()
                vids = res.get("videos", [])

            # ── 3. Pick fresh video, track ID ──────────────────────────────
            vid = _fresh_video(vids) if vids else None
            if vid:
                mp4s = [f for f in vid["video_files"] if f["file_type"] == "video/mp4"]
                mp4s.sort(key=lambda x: x["width"], reverse=True)
                if mp4s:
                    dest.write_bytes(requests.get(mp4s[0]["link"], timeout=60).content)
                    _mark_visual_used(vid["id"], query, is_photo=False)
                    if i == 0:
                        clips.append(zoom_clip_if_no_face(dest, i))
                    else:
                        clips.append(str(dest))
                    used_queries.append(query)
                    print(f"  Clip {i+1}: {query[:55]}")
                    continue

            # ── 4. Photo fallback ──────────────────────────────────────────
            if _try_photo_fallback(query, dest):
                if i == 0:
                    clips.append(zoom_clip_if_no_face(dest, i))
                else:
                    clips.append(str(dest))
                used_queries.append(query)
                print(f"  Clip {i+1}: [photo] {query[:50]}")
            else:
                print(f"  Clip {i+1}: skipped — no video or photo found")

        except Exception as e:
            print(f"  Clip {i+1} failed ({query[:40]}): {e}")
    return clips, used_queries


# ── Voiceover ──────────────────────────────────────────────────────────────────
async def make_voiceover(text, out_path, voice="en-NG-AbeoNeural"):
    import edge_tts
    communicate = edge_tts.Communicate(text, voice=voice)
    await communicate.save(str(out_path))


# ── Voice rotation ─────────────────────────────────────────────────────────────
# Each accent has a male and female voice — gender alternates by day of month
VOICE_PAIRS = {
    "NG": ("en-NG-AbeoNeural",    "en-NG-EzinneNeural"),
    "EN": ("en-GB-RyanNeural",    "en-GB-SoniaNeural"),
    "US": ("en-US-GuyNeural",     "en-US-JennyNeural"),
    "ES": ("es-MX-JorgeNeural",   "es-MX-DaliaNeural"),
    "DE": ("de-DE-KillianNeural", "de-DE-KatjaNeural"),
    "FR": ("fr-FR-HenriNeural",   "fr-FR-DeniseNeural"),
}

# Afternoon V2 world rotation — cycles through these accents day by day
_WORLD_CYCLE = ["NG", "ES", "US", "DE", "FR"]

# Slot → (V1 accent, V2 accent or "world")
_SLOT_VOICES = {
    "morning":   ("NG",    "EN"),
    "afternoon": ("EN",    "world"),
    "evening":   ("US",    "NG"),
}


def _slot_now() -> str:
    h = datetime.now().hour
    return "morning" if h < 10 else ("afternoon" if h < 16 else "evening")


def pick_slot_voice(version_num: int) -> str:
    """Return the edge-tts voice for V1 or V2 based on current time slot.
    Gender alternates each day: even day = male (index 0), odd day = female (index 1).
    """
    slot    = _slot_now()
    day     = datetime.now().day
    gender  = day % 2          # 0 = male, 1 = female

    v1_acc, v2_acc = _SLOT_VOICES[slot]

    if version_num == 1:
        accent = v1_acc
    else:
        if v2_acc == "world":
            doy    = datetime.now().timetuple().tm_yday
            accent = _WORLD_CYCLE[doy % len(_WORLD_CYCLE)]
        else:
            accent = v2_acc

    pair  = VOICE_PAIRS[accent]
    voice = pair[gender]
    print(f"  [Voice] slot={slot}  V{version_num}  accent={accent}  {'female' if gender else 'male'}  → {voice}")
    return voice


# ── Language / voice detection ─────────────────────────────────────────────────
LANG_VOICES = {
    "ES":  "es-MX-JorgeNeural",
    "NG":  "en-NG-AbeoNeural",
    "EN":  "en-GB-RyanNeural",
}

LANG_CTA = {
    "ES": "BootHop. Alguien ya va a tu destino. Entra en boothop punto com.",
    "NG": "BootHop. Delivered by someone already going your way. Join us at boothop dot com.",
    "EN": "BootHop. Delivered by someone already going your way. Join us at boothop dot com.",
}

NIGERIAN_MARKERS = {
    "abeg", "wahala", "gbe body", "nna men", "abi", "naija", "naira",
    "owambe", "gele", "ankara", "aso-ebi", "agbada", "suya", "egusi",
    "jollof", "chin-chin", "olorun", "eledumare", "chineke", "chukwu",
    "dalu", "yoruba", "igbo", "pidgin", "oga", "baba o", "sapa",
    "e don reach", "don land", "e reach", "no wahala", "dem say",
    "nna", "ehn", "sha", "omo", "bros", "mumu", "chop", "gbas gbos",
    "dupẹ", "ẹ kààbọ̀", "mo fẹ", "mo dupẹ", "eledumare", "gozie",
}

def detect_lang(hook: str):
    """Returns (lang_code, clean_hook) — strips [XX] prefix if present."""
    hook = hook.strip()
    if hook.startswith("[") and "]" in hook[:6]:
        code = hook[1:hook.index("]")].upper()
        return code, hook[hook.index("]")+1:].strip()
    return "EN", hook

def pick_voice(hook: str, lang: str) -> str:
    """Choose TTS voice based on lang code and Nigerian marker detection."""
    if lang == "ES":
        return LANG_VOICES["ES"]
    if lang in ("UK", "EU"):
        return LANG_VOICES["EN"]  # British English for local UK and Euro routes
    hook_lower = hook.lower()
    for marker in NIGERIAN_MARKERS:
        if marker in hook_lower:
            return LANG_VOICES["NG"]
    return LANG_VOICES["EN"]


# Phonetic replacements so TTS pronounces Nigerian/Pidgin/Yoruba words correctly
PHONETICS = {
    "owambe":       "oh-wan-beh",
    "Owambe":       "oh-wan-beh",
    "OWAMBE":       "oh-wan-beh",
    "abeg":         "ah-beg",
    "Abeg":         "ah-beg",
    "abi":          "ah-bee",
    "biko":         "bee-koh",
    "naija":        "nai-jah",
    "Naija":        "nai-jah",
    "Naira":        "nai-rah",
    "gele":         "geh-leh",
    "Gele":         "geh-leh",
    "aso ebi":      "ah-soh eh-bee",
    "Aso Ebi":      "ah-soh eh-bee",
    "jollof":       "joh-lof",
    "Jollof":       "joh-lof",
    "Lekki":        "leh-kee",
    "detty":        "deh-tee",
    "Detty":        "deh-tee",
    "wahala":       "wah-hah-lah",
    "Wahala":       "wah-hah-lah",
    "gbe body":     "gbeh body",
    "nna men":      "nah men",
    "egusi":        "eh-goo-see",
    "ogbono":       "og-boh-noh",
    "eba":          "eh-bah",
    "suya":         "soo-yah",
    "Suya":         "soo-yah",
    "ankara":       "an-kah-rah",
    "Ankara":       "an-kah-rah",
    "Ibadan":       "ee-bah-dan",
    "Eledumare":    "eh-leh-doo-mah-reh",
    "Chineke":      "chee-neh-keh",
    "Chukwu":       "choo-kwoo",
    "dalu":         "dah-loo",
    "gozie":        "go-zee-eh",
    "mo dupe":      "moh doo-peh",
    "mo fe e":      "moh feh eh",
    "oyinbo":       "oh-yin-boh",
    "awon":         "ah-won",
    "pünktlich":    "puenktlich",
    "geliefert":    "geh-lee-fert",
    "Heimweh":      "hime-veh",
    "Lebkuchen":    "lep-koo-chen",
    "Stroopwafel":  "strohp-wah-fel",
    "stroopwafels": "strohp-wah-fels",
    "geen":         "khayn",
    "boothop":      "boot hop",
    "BootHop":      "boot hop",
}


def apply_phonetics(text):
    for word, pronunciation in PHONETICS.items():
        text = text.replace(word, pronunciation)
    return text


def build_story_script(hook: str, bucket: str):
    """Build full ~30s voiceover following the 5-part brand arc."""
    lang, clean_hook = detect_lang(hook)
    raw = clean_hook.strip()
    if raw.upper().startswith("POV:"):
        opening = raw[4:].strip()
    elif raw.upper().startswith("POV "):
        opening = raw[4:].strip()
    else:
        opening = raw
    # Strip emojis/symbols — TTS should read words only, not ":)" or "💊"
    opening = strip_emoji(opening)

    templates = STORY_TEMPLATES.get(bucket, STORY_TEMPLATES["community"])
    template  = random.choice(templates)
    hero      = random.choice(HERO_LINES.get(bucket, HERO_LINES["community"]))

    cta = LANG_CTA.get(lang, LANG_CTA["EN"])

    script = (
        f"{opening}. "
        f"{template['problem']} "
        f"{template['movement']} "
        f"{template['solution']} "
        f"{hero} "
        f"{cta}"
    )
    return script, hero, template["problem"], template["solution"]


def generate_voiceover(hook, out_path, bucket="community", force_lang=None, force_voice=None):
    """Generate voiceover using the 5-part brand arc story script."""
    lang, clean_hook = detect_lang(hook)
    if force_lang:
        lang = force_lang

    story_script, hero_line, problem, solution = build_story_script(hook, bucket)
    # force_voice = slot-based rotation; fallback to hook-language detection
    voice = force_voice if force_voice else pick_voice(clean_hook, lang)

    # Strip emojis/symbols then apply phonetics — TTS must receive clean ASCII
    story_script = strip_emoji(story_script)
    if lang in ("EN", "NG"):
        story_script = apply_phonetics(story_script)

    asyncio.run(make_voiceover(story_script, out_path, voice=voice))

    # Trim leading silence so voice starts at exactly t=0
    trimmed = out_path.with_suffix(".trimmed.mp3")
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(out_path),
             "-af", "silenceremove=start_periods=1:start_silence=0.03:start_threshold=-50dB",
             str(trimmed)],
            capture_output=True
        )
        if trimmed.exists() and trimmed.stat().st_size > 1000:
            trimmed.replace(out_path)
    except Exception:
        pass

    return hero_line, problem, solution


# ── ffmpeg helpers ─────────────────────────────────────────────────────────────
def run_ff(*args):
    cmd = ["ffmpeg", "-y"] + list(args)
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        err = result.stderr.decode("utf-8", errors="replace")[-800:]
        raise RuntimeError(f"ffmpeg failed (exit {result.returncode}):\n{err}")


# ── Cover / thumbnail generator ───────────────────────────────────────────────
_COVER_COLORS = {
    "family":    [(255, 140, 0),   (200, 60, 0)],     # warm gold → deep orange
    "business":  [(0, 100, 220),   (0, 30, 120)],     # bright blue → navy
    "airport":   [(0, 195, 215),   (0, 90, 155)],     # cyan → ocean blue
    "smart":     [(0, 210, 100),   (0, 110, 40)],     # lime green → forest
    "cinematic": [(180, 0, 100),   (70, 0, 50)],      # vivid magenta → deep plum
    "community": [(0, 170, 70),    (210, 110, 0)],    # Nigerian green → gold
}


def generate_cover_frame(hook: str, bucket: str, out_path: Path) -> bool:
    """
    Create a vibrant 1080×1920 cover PNG using PIL.
    Gradient background → BootHop logo → hook text → URL.
    Returns True on success, False if PIL unavailable.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
        import textwrap as _tw

        W, H = 1080, 1920
        c1, c2 = _COVER_COLORS.get(bucket, [(220, 80, 0), (100, 0, 80)])

        # Vertical gradient background
        img = Image.new("RGB", (W, H))
        draw = ImageDraw.Draw(img)
        for y in range(H):
            r = int(c1[0] + (c2[0] - c1[0]) * y / H)
            g = int(c1[1] + (c2[1] - c1[1]) * y / H)
            b = int(c1[2] + (c2[2] - c1[2]) * y / H)
            draw.line([(0, y), (W, y)], fill=(r, g, b))

        # Dark vignette on lower half for text contrast
        vign = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        vd   = ImageDraw.Draw(vign)
        for y in range(H // 2, H):
            a = int(185 * (y - H // 2) / (H // 2))
            vd.line([(0, y), (W, y)], fill=(0, 0, 0, a))
        img.paste(Image.new("RGB", (W, H), (0, 0, 0)), mask=vign.split()[3])

        # Horizontal shine stripe near top
        shine = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        sd    = ImageDraw.Draw(shine)
        for y in range(80, 200):
            a = int(55 * (1 - abs(y - 140) / 60))
            sd.line([(0, y), (W, y)], fill=(255, 255, 255, max(0, a)))
        img.paste(Image.new("RGB", (W, H), (255, 255, 255)), mask=shine.split()[3])

        draw = ImageDraw.Draw(img)

        # Logo — centred in upper third
        logo_candidates = [ASSETS / "boothop-icon-512.png", ASSETS / "boothop-icon-1024.png", LOGO]
        logo_img = None
        for lp in logo_candidates:
            if lp.exists():
                try:
                    logo_img = Image.open(lp).convert("RGBA")
                    break
                except Exception:
                    pass
        if logo_img:
            logo_img.thumbnail((240, 240))
            lx = (W - logo_img.width) // 2
            ly = 220
            img.paste(logo_img, (lx, ly), logo_img)

        # Fonts
        def _font(path_str, size):
            try:
                return ImageFont.truetype(path_str, size)
            except Exception:
                return ImageFont.load_default()

        f_brand = _font(str(_FONT_DIR / "Oswald-Bold.ttf"), 130)
        f_hook  = _font(str(_FONT_DIR / "Montserrat-ExtraBold.ttf"), 68)
        f_url   = _font(str(_FONT_DIR / "Oswald-Bold.ttf"), 52)

        # "BootHop" brand name
        brand = "BootHop"
        bb    = draw.textbbox((0, 0), brand, font=f_brand)
        draw.text(((W - (bb[2]-bb[0])) // 2, 490), brand,
                  fill=(255, 225, 0), font=f_brand,
                  stroke_width=4, stroke_fill=(0, 0, 0))

        # Hook text — clean, stripped, wrapped
        clean = strip_emoji(hook).strip()
        for pfx in ("POV:", "POV "):
            if clean.upper().startswith(pfx.upper()):
                clean = clean[len(pfx):].strip()
                break
        lines = _tw.wrap(clean, width=20)[:4]
        hy = 700
        for ln in lines:
            lb = draw.textbbox((0, 0), ln, font=f_hook)
            lw = lb[2] - lb[0]
            # White text with black stroke for pop
            draw.text(((W - lw) // 2, hy), ln, font=f_hook,
                      fill=(255, 255, 255),
                      stroke_width=4, stroke_fill=(0, 0, 0))
            hy += 86

        # Yellow accent bar
        bar_y = hy + 30
        draw.rounded_rectangle([(W//2 - 180, bar_y), (W//2 + 180, bar_y + 8)],
                                radius=4, fill=(255, 225, 0))

        # URL
        url = "boothop.com"
        ub  = draw.textbbox((0, 0), url, font=f_url)
        draw.text(((W - (ub[2]-ub[0])) // 2, H - 140), url,
                  fill=(255, 225, 0), font=f_url,
                  stroke_width=3, stroke_fill=(0, 0, 0))

        img.save(str(out_path), "PNG", optimize=False)
        return True

    except Exception as _e:
        print(f"  [Cover] Generation failed: {_e}")
        return False


def process_clips(clips, out_path, prefix=""):
    """Scale all clips to 1080x1920, trim to 3.75s each, concat 8 clips → 30s."""
    processed = []
    for i, clip in enumerate(clips[:8]):
        dest = TEMP / f"{prefix}proc_{i}.mp4"
        run_ff(
            "-i", clip, "-t", "3.75",
            "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30",
            "-an", str(dest)
        )
        processed.append(str(dest))

    while len(processed) < 8:
        processed.append(processed[-1])

    list_file = TEMP / f"{prefix}list.txt"
    list_file.write_text("\n".join(f"file '{p}'" for p in processed))
    run_ff("-f", "concat", "-safe", "0", "-i", str(list_file),
           "-c:v", "libx264", "-crf", "23", "-preset", "fast", "-an", str(out_path))


def render_video(base_mp4, voiceover_mp3, music_mp3, hook, hero_line, out_path,
                 problem="", solution="", cover_path=None):
    """Composite all layers: clips + text + overlays + audio. 30-second video.

    3-phase text layout (premium white-on-dark style):
      0–8s  : POV hook — the scenario (top of frame)
      8–17s : The problem — what went wrong (center)
      17–27s: How BootHop helps — the solution (center)
      27–30s: Hero end line (cinematic shadow, bottom)
    Colorful cover card overlaid at t=0–1.2s (first frame = platform thumbnail).
    """
    pov_label, h1, h2, h3 = split_pov_hook(hook)

    # Hero line split into 2 lines for end card
    hero_clean = strip_emoji(hero_line)
    hero_words = hero_clean.split()
    mid        = len(hero_words) // 2
    hero_line1 = " ".join(hero_words[:mid]) if mid > 0 else hero_clean
    hero_line2 = " ".join(hero_words[mid:]) if mid < len(hero_words) else ""

    # Problem/solution — 2 display lines each
    _pb_default = "Traditional delivery takes too long and costs too much."
    _sl_default = "BootHop connects your delivery to someone already going your way."
    pb1, pb2, _ = split_text(problem  or _pb_default,  max_len=26)
    sl1, sl2, _ = split_text(solution or _sl_default, max_len=26)

    fig = str(FIG1 if random.random() > 0.5 else FIG2)

    # No black stinger needed — the cover card fills t=0–1.2s with a colourful branded frame
    stinger = ""

    # Hook layout — top of frame
    # Non-POV hooks: no label row, so shift all 3 content lines up to fill the space
    if pov_label:
        pov_y = 155
        h1_y  = pov_y + 78
    else:
        pov_y = 155   # unused (empty label → dt() renders nothing)
        h1_y  = 155   # start text higher since no "POV :" label above
    h2_y = h1_y + 68
    h3_y = h2_y + 68

    # Problem/solution — centered vertically (1080×1920 screen)
    pb_y1, pb_y2 = 820, 918
    sl_y1, sl_y2 = 820, 918

    # Hero end line — near bottom
    hero_y1 = "h-270"
    hero_y2 = "h-185"

    def dt(text, y, t_start, t_end, size=56, title_font=False):
        """Clean stroke style: white text with black outline — no ugly box rectangles."""
        if not str(text).strip():
            return ""
        ff      = FONT_TITLE if title_font else FONT_BODY
        ff_path = ff.replace("\\", "/").replace("C:/", "C\\:/")
        safe = (str(text)
                .replace("\\", "\\\\")
                .replace("'",  "\\'")
                .replace(":",  "\\:")
                .replace("%",  "%%"))
        return (f"drawtext=fontfile='{ff_path}':text='{safe}':fontsize={size}"
                f":fontcolor=white:borderw=4:bordercolor=black@1.0"
                f":x=(w-text_w)/2:y={y}:enable='between(t,{t_start},{t_end})'")

    filters = [f for f in [
        # Phase 1 — POV hook (1.5–8s): start AFTER cover card fades (cover shows 0–1.2s)
        # so the hook text isn't competing with the cover thumbnail
        dt(pov_label, pov_y, 1.5, 8, size=72, title_font=True),
        dt(h1, h1_y,  1.5, 8, size=60),
        dt(h2, h2_y,  1.5, 8, size=60),
        dt(h3, h3_y,  1.5, 8, size=60),
        # Phase 2 — The problem (8–17s): center
        dt(pb1, pb_y1, 8, 17, size=52) if pb1 else "",
        dt(pb2, pb_y2, 8, 17, size=48) if pb2 else "",
        # Phase 3 — How BootHop helps (17–27s): center
        dt(sl1, sl_y1, 17, 27, size=52) if sl1 else "",
        dt(sl2, sl_y2, 17, 27, size=48) if sl2 else "",
        dt("boothop.com", "h-130", 21, 27, size=38),
        # Phase 4 — Hero end card (27–30s): cinematic stroke
        dt(hero_line1, hero_y1, 27, 30, size=60, title_font=True),
        dt(hero_line2, hero_y2, 27, 30, size=56, title_font=True),
    ] if f]

    text_filter = ",".join(f for f in [stinger] + filters if f)

    # Step 1: overlay brand card (20–22s) + FIG4End (27–30s) + logo corner + cover (0–1.2s)
    overlay_out = TEMP / "pov_overlaid.mp4"
    use_cover = cover_path and Path(cover_path).exists()
    if use_cover:
        run_ff(
            "-i", str(base_mp4),
            "-loop", "1", "-i", fig,
            "-loop", "1", "-i", str(FIG_END),
            "-loop", "1", "-i", str(LOGO),
            "-loop", "1", "-i", str(cover_path),
            "-filter_complex",
            # Cover card full-screen for first 1.2 s (this becomes the platform thumbnail)
            "[0:v][4:v]overlay=0:0:enable='between(t,0,1.2)'[v_intro];"
            "[v_intro][1:v]overlay=0:(H-h)/2:enable='between(t,20,22)'[v1];"
            "[v1][2:v]overlay=0:0:enable='between(t,27,30)'[v2];"
            "[3:v]scale=180:-1[logo];"
            "[v2][logo]overlay=W-w-20:20[v]",
            "-map", "[v]",
            "-c:v", "libx264", "-crf", "23", "-preset", "fast", "-an",
            "-t", "30", str(overlay_out)
        )
    else:
        run_ff(
            "-i", str(base_mp4),
            "-loop", "1", "-i", fig,
            "-loop", "1", "-i", str(FIG_END),
            "-loop", "1", "-i", str(LOGO),
            "-filter_complex",
            "[0:v][1:v]overlay=0:(H-h)/2:enable='between(t,20,22)'[v1];"
            "[v1][2:v]overlay=0:0:enable='between(t,27,30)'[v2];"
            "[3:v]scale=180:-1[logo];"
            "[v2][logo]overlay=W-w-20:20[v]",
            "-map", "[v]",
            "-c:v", "libx264", "-crf", "23", "-preset", "fast", "-an",
            "-t", "30", str(overlay_out)
        )

    # Step 2: burn text ON TOP of overlays so text is always the top layer
    # Write filter to a script file to avoid Windows command-line length/parsing limits
    text_out    = TEMP / "pov_text.mp4"
    filter_file = TEMP / "text_filter.txt"
    filter_file.write_text(text_filter, encoding="utf-8")
    run_ff("-i", str(overlay_out),
           "-filter_script:v", str(filter_file),
           "-c:v", "libx264", "-crf", "23", "-preset", "fast", "-an", str(text_out))

    # Step 3: mix voiceover + music
    audio_out = TEMP / "pov_audio.aac"
    run_ff(
        "-i", str(voiceover_mp3),
        "-i", str(music_mp3),
        "-filter_complex", "[1:a]volume=0.18[m];[0:a][m]amix=inputs=2:duration=longest:normalize=0[out]",
        "-map", "[out]", "-t", "30", "-c:a", "aac", "-b:a", "192k", str(audio_out)
    )

    # Step 4: mux video + audio
    run_ff(
        "-i", str(text_out),
        "-i", str(audio_out),
        "-c:v", "copy", "-c:a", "copy", "-t", "30",
        str(out_path)
    )


# ── Content archive helpers ────────────────────────────────────────────────────
def _log_post(platform, hook, bucket, music_track, media_id=None):
    """Append a successful post to post_log.json for dedup and audit."""
    h = datetime.now().hour
    slot = "morning" if h < 10 else ("afternoon" if h < 16 else "evening")
    entry = {
        "posted_at":   datetime.now().isoformat(),
        "date":        datetime.now().strftime("%Y-%m-%d"),
        "slot":        slot,
        "platform":    platform,
        "hook":        (hook or "")[:120],
        "bucket":      bucket,
        "music_track": Path(music_track).name if music_track else "",
        "media_id":    media_id or "",
    }
    log = []
    if POST_LOG.exists():
        try:
            log = json.loads(POST_LOG.read_text(encoding="utf-8"))
        except Exception:
            pass
    log.append(entry)
    cutoff = (datetime.now() - timedelta(days=90)).isoformat()
    log = [e for e in log if e.get("posted_at", "") >= cutoff]
    try:
        POST_LOG.write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as _e:
        print(f"  [PostLog] Write error: {_e}")


_MUSIC_LOG          = DATA / "used_music.json"
_MUSIC_WINDOW_DAYS  = 14
AUDIO_LOG           = DATA / "audio_log.json"


def _load_used_music() -> list:
    if not _MUSIC_LOG.exists():
        return []
    try:
        return json.loads(_MUSIC_LOG.read_text(encoding="utf-8"))
    except Exception:
        return []


def _prune_used_music(entries: list) -> list:
    cutoff = (datetime.now() - timedelta(days=_MUSIC_WINDOW_DAYS)).strftime("%Y-%m-%d")
    return [e for e in entries if e.get("date", "") >= cutoff]


def _mark_music_used(track_path) -> None:
    entries = _prune_used_music(_load_used_music())
    track_name = Path(track_path).name
    today = datetime.now().strftime("%Y-%m-%d")
    if not any(e.get("track") == track_name and e.get("date") == today for e in entries):
        entries.append({"track": track_name, "date": today})
    try:
        _MUSIC_LOG.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        print(f"  [MusicLog] Write error: {e}")


def score_music_file(filepath) -> int:
    """Freshness score for a music file based on use count in the last 7 days.
    0 uses = 3 (freshest), 1-2 uses = 2, 3+ uses = 1 (stale).
    """
    try:
        if not AUDIO_LOG.exists():
            return 3
        entries = json.loads(AUDIO_LOG.read_text(encoding="utf-8"))
        cutoff = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        name = Path(filepath).name
        uses = sum(1 for e in entries if e.get("track") == name and e.get("date", "") >= cutoff)
        if uses == 0:
            return 3
        if uses <= 2:
            return 2
        return 1
    except Exception:
        return 3


def _log_audio(filepath) -> None:
    """Append a play entry to audio_log.json (30-day rolling window)."""
    try:
        entries = json.loads(AUDIO_LOG.read_text(encoding="utf-8")) if AUDIO_LOG.exists() else []
        cutoff  = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        entries = [e for e in entries if e.get("date", "") >= cutoff]
        entries.append({
            "track": Path(filepath).name,
            "date":  datetime.now().strftime("%Y-%m-%d"),
            "ts":    datetime.now().isoformat(),
        })
        AUDIO_LOG.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        print(f"  [AudioLog] Write error: {e}")


# ── Music selection ────────────────────────────────────────────────────────────
def get_music():
    """
    Pick two DISTINCT tracks — one for V1, one for V2.
    Priority: TRENDING_MUSIC (scored by freshness) → ARCHIVE/DAILY_MUSIC fallback.
    If only 1 trending track exists, V1 gets it and V2 pulls from archive so they
    are never the same file. Logs all choices to audio_log.json.
    """
    import random as _random

    def _archive_pick(exclude_name=""):
        """Return one fresh archive track, excluding exclude_name."""
        all_t = sorted(ARCHIVE.glob("*.mp3")) + sorted(DAILY_MUSIC.glob("track_*.mp3"))
        if not all_t:
            return None
        recent = {e["track"] for e in _prune_used_music(_load_used_music())}
        fresh  = [t for t in all_t if t.name not in recent and t.name != exclude_name]
        if not fresh:
            fresh = [t for t in all_t if t.name != exclude_name] or all_t
        _random.shuffle(fresh)
        pick = fresh[0]
        _mark_music_used(pick)
        _log_audio(pick)
        return pick

    # 1. TRENDING_MUSIC — prefer freshest files
    TRENDING_MUSIC.mkdir(parents=True, exist_ok=True)
    trending = sorted(TRENDING_MUSIC.glob("*.mp3"))

    if len(trending) >= 2:
        scored = sorted(trending, key=lambda f: score_music_file(f), reverse=True)
        v1, v2 = scored[0], scored[1]
        _log_audio(v1)
        _log_audio(v2)
        print(f"  [Music] Trending — V1: {v1.name}  V2: {v2.name}")
        return v1, v2

    if len(trending) == 1:
        v1 = trending[0]
        _log_audio(v1)
        v2 = _archive_pick(exclude_name=v1.name)
        if v2:
            print(f"  [Music] V1 trending: {v1.name}  V2 archive: {v2.name}")
            return v1, v2
        print(f"  [Music] Only 1 trending track, archive empty — both use {v1.name}")
        return v1, v1

    # 2. ARCHIVE + DAILY_MUSIC — guarantee two different tracks
    all_tracks = sorted(ARCHIVE.glob("*.mp3")) + sorted(DAILY_MUSIC.glob("track_*.mp3"))
    if not all_tracks:
        return None, None

    recent = {e["track"] for e in _prune_used_music(_load_used_music())}
    fresh  = [t for t in all_tracks if t.name not in recent]
    if len(fresh) < 2:
        fresh = list(all_tracks)

    _random.shuffle(fresh)
    v1 = fresh[0]
    v2 = fresh[1] if len(fresh) > 1 else fresh[0]

    _mark_music_used(v1)
    if v2.name != v1.name:
        _mark_music_used(v2)
    _log_audio(v1)
    if v2.name != v1.name:
        _log_audio(v2)

    print(f"  [Music] Archive — V1: {v1.name}  V2: {v2.name}")
    return v1, v2


def refresh_trending_music() -> list:
    """
    Report TRENDING_MUSIC files that have been used 3+ times this week.
    Prints a stale-file list. Does NOT delete anything.
    Returns list of stale filenames.
    """
    try:
        entries = json.loads(AUDIO_LOG.read_text(encoding="utf-8")) if AUDIO_LOG.exists() else []
    except Exception:
        entries = []

    cutoff = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    week_uses: dict = {}
    for e in entries:
        if e.get("date", "") >= cutoff:
            name = e.get("track", "")
            week_uses[name] = week_uses.get(name, 0) + 1

    trending_files = {f.name for f in TRENDING_MUSIC.glob("*.mp3")} if TRENDING_MUSIC.exists() else set()

    stale = sorted(n for n, c in week_uses.items() if c >= 3 and n in trending_files)
    fresh = sorted(n for n in trending_files if week_uses.get(n, 0) < 3)

    print("\n[Trending Music Refresh Report]")
    print(f"  Trending files : {len(trending_files)}")
    print(f"  Fresh (< 3 uses this week) : {len(fresh)}")
    if stale:
        print(f"  Stale (3+ uses — replace these):")
        for name in stale:
            print(f"    - {name}  ({week_uses[name]} uses this week)")
    else:
        print("  No stale files this week — trending pool is fresh.")

    return stale


# ── Caption builder ────────────────────────────────────────────────────────────
INSTAGRAM_HASHTAGS = {
    "family":    "#BootHop #Family #DiasporaLife #LondonToLagos #SameDayDelivery #UKNaija #AfricanDiaspora #Diaspora #HomeDelivery #TrustedMovement #HumanLogistics #MovementWithPurpose",
    "business":  "#BootHop #Logistics #SupplyChain #BusinessDelivery #UrgentLogistics #SMELogistics #HumanPowered #StartupLife #B2BLogistics #OperationalExcellence #FutureOfDelivery",
    "airport":   "#BootHop #AirportLife #TravelHack #UrgentDelivery #SameDayDelivery #TravelTips #TrustedMovement #Startup #Innovation #AirportStories #HumanLogistics",
    "smart":     "#BootHop #SmartLogistics #GreenDelivery #SustainableLogistics #Innovation #FutureOfMovement #HumanPowered #IntelligentMovement #TechStartup #LogisticsInnovation",
    "cinematic": "#BootHop #PremiumDelivery #HumanMovement #TrustedJourneys #ModernLogistics #MovementWithPurpose #Startup #Innovation #CinematicDelivery #TrustedMovement",
    "community": "#BootHop #DiasporaMagic #NaijaUK #LondonToLagos #AfrobeatsLife #CommunityFirst #NigerianDiaspora #DiasporaDelivery #UKNigeria #TrustedTravellers #HumanLogistics",
}

def _get_daily_5_hashtags(bucket, route="ng"):
    """
    Load today's exactly-5 hashtags for this bucket+route from trending_hooks_today.json.
    Key format: '{bucket}_{route}' e.g. 'community_ng', 'family_uk', 'business_eu'.
    Returns a string of 5 space-separated hashtags, or None if unavailable.
    """
    try:
        f = DATA / "trending_hooks_today.json"
        if not f.exists():
            return None
        data = json.loads(f.read_text(encoding="utf-8"))
        if data.get("date") != datetime.now().strftime("%Y-%m-%d"):
            return None
        key = f"{bucket}_{route}"
        tags_str = data.get("hashtag_sets", {}).get(key)
        if not tags_str:
            return None
        # Safety: enforce max 5 regardless
        tags = tags_str.split()[:5]
        return " ".join(tags)
    except Exception:
        return None


def _fallback_5_hashtags(bucket, route="ng"):
    """Static fallback when daily file isn't available — always returns exactly 5 tags."""
    _static = {
        "ng": {
            "family":    "#BootHop #LondonToLagos #DiasporaLife #NaijaFamily #SameDayDelivery",
            "business":  "#BootHop #LondonToLagos #UrgentDelivery #LogisticsNigeria #B2BDelivery",
            "airport":   "#BootHop #LondonToLagos #TravelHack #AirportLife #UrgentDelivery",
            "smart":     "#BootHop #DiasporaMagic #SmartLogistics #HumanPowered #Startup",
            "cinematic": "#BootHop #DiasporaMagic #TrustedMovement #PremiumDelivery #HumanLogistics",
            "community": "#BootHop #NaijaUK #DiasporaMagic #LondonToLagos #NigerianTikTok",
        },
        "uk": {
            "family":    "#BootHop #SameDayUK #UKDelivery #StudentLife #BritishLife",
            "business":  "#BootHop #SameDayUK #UKDelivery #UrgentDelivery #UKStartup",
            "airport":   "#BootHop #SameDayUK #UKDelivery #TravelHack #AirportLife",
            "smart":     "#BootHop #SameDayUK #UKLogistics #Innovation #UKStartup",
            "cinematic": "#BootHop #SameDayUK #HumanLogistics #TrustedMovement #UKLife",
            "community": "#BootHop #SameDayUK #UKDelivery #StudentLife #UniLife",
        },
        "eu": {
            "family":    "#BootHop #UKtoEurope #ExpatLife #BritishAbroad #EuropeanDelivery",
            "business":  "#BootHop #UKtoEurope #ExpatLife #B2BDelivery #EuropeanLogistics",
            "airport":   "#BootHop #UKtoEurope #ExpatLife #LutonAirport #TravelHack",
            "smart":     "#BootHop #UKtoEurope #DiasporaEurope #HumanPowered #Startup",
            "cinematic": "#BootHop #UKtoEurope #BritishAbroad #TrustedMovement #ExpatLife",
            "community": "#BootHop #UKtoEurope #DiasporaEurope #ExpatLife #BritishAbroad",
        },
        "es": {
            "family":    "#BootHop #DiasporaEspana #LondresAMadrid #UKEspana #EnvioDesdeUK",
            "business":  "#BootHop #DiasporaEspana #UKEspana #EnvioDesdeUK #LogisticaUK",
            "airport":   "#BootHop #DiasporaEspana #LondresAMadrid #ViajesUK #UKEspana",
            "smart":     "#BootHop #DiasporaEspana #EnvioDesdeUK #Startup #Logistica",
            "cinematic": "#BootHop #DiasporaEspana #DiasporaLatina #UKEspana #MoverConProposito",
            "community": "#BootHop #DiasporaEspana #DiasporaLatina #LondresAMadrid #EnvioDesdeUK",
        },
    }
    route_map = _static.get(route, _static["ng"])
    return route_map.get(bucket, route_map.get("community", "#BootHop #LondonToLagos #DiasporaMagic #SameDayDelivery #HumanLogistics"))


def build_caption(hook, hero_line, bucket, platform="tiktok"):
    _, theme   = get_weekly_theme()
    opener     = random.choice(theme["caption_opener"])
    cta_line   = theme["cta"]

    # Detect route from hook prefix → drives hashtag set
    lang, _    = detect_lang(hook)
    route      = {"UK": "uk", "EU": "eu", "ES": "es"}.get(lang, "ng")

    # Always exactly 5 hashtags — daily file first, static fallback second
    hashtags   = (_get_daily_5_hashtags(bucket, route)
                  or _fallback_5_hashtags(bucket, route))

    if platform == "instagram":
        geo_lines = {
            "uk": "London to Glasgow. Birmingham to Heathrow. St Pancras to Hull.",
            "eu": "London to Berlin. Paris to London. Barcelona to Heathrow.",
            "es": "Londres a Madrid. Heathrow a Barcelona. UK a tu familia.",
        }
        geo_line = geo_lines.get(route, "London to Lagos. Frankfurt to Abuja. New York to beyond.")
        return (
            f"{opener}\n\n"
            f"{hook}\n\n"
            f"{hero_line}\n\n"
            f"BootHop — someone is already going your way.\n"
            f"Same-day delivery powered by trusted travellers.\n"
            f"{geo_line}\n"
            f"{cta_line}\n\n"
            f"{hashtags}"
        )

    if platform == "youtube":
        return (
            f"{opener}\n\n"
            f"{hook}\n\n"
            f"{hero_line}\n\n"
            f"BootHop — someone is already going your way.\n"
            f"Same-day delivery powered by trusted travellers.\n"
            f"boothop.com\n\n"
            f"{hashtags}\n\n"
            f"Subscribe for more: https://www.youtube.com/@boothop"
        )

    if platform == "linkedin":
        return (
            f"{hook}\n\n"
            f"{hero_line}\n\n"
            f"BootHop — trusted travellers. Real deliveries.\n"
            f"{cta_line}\n\n"
            f"{hashtags}"
        )

    # TikTok / default
    return (
        f"{hook}\n\n"
        f"{hero_line}\n\n"
        f"{cta_line}\n\n"
        f"{hashtags}"
    )


# ── Telegram sender ────────────────────────────────────────────────────────────
def send_telegram_video(video_path, caption, label):
    try:
        with open(video_path, "rb") as f:
            r = requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendVideo",
                data={"chat_id": TELEGRAM_CHAT_ID, "caption": f"{label}\n\n{caption[:900]}"},
                files={"video": f},
                timeout=180
            )
        print(f"  Telegram {label}: {'OK' if r.ok else r.text[:80]}")
    except Exception as e:
        print(f"  Telegram {label} failed: {e}")


def send_telegram_video_approval(video_path: str, caption: str) -> bool:
    """
    Send a preview video to Telegram WITH the approval keyboard attached.
    User sees the actual content + can tap approve/delay/ignore in one message.
    Falls back to text-only keyboard if video send fails.
    """
    markup = {"inline_keyboard": [
        [
            {"text": "✅ Post All V1",   "callback_data": "all_v1"},
            {"text": "✅ Post All V2",   "callback_data": "all_v2"},
            {"text": "⏰ Post in 1hr",   "callback_data": "delay_1hr"},
        ],
        [
            {"text": "TikTok V1",        "callback_data": "tt_v1"},
            {"text": "TikTok V2",        "callback_data": "tt_v2"},
            {"text": "TikTok Skip",      "callback_data": "tt_skip"},
        ],
        [
            {"text": "IG V1",            "callback_data": "ig_v1"},
            {"text": "IG V2",            "callback_data": "ig_v2"},
            {"text": "IG Skip",          "callback_data": "ig_skip"},
        ],
        [
            {"text": "🚫 Ignore — post nothing", "callback_data": "ignore_all"},
        ],
    ]}
    try:
        with open(video_path, "rb") as f:
            r = requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendVideo",
                data={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "caption": caption[:1024],
                    "parse_mode": "Markdown",
                    "reply_markup": json.dumps(markup),
                },
                files={"video": f},
                timeout=180,
            )
        if r.ok and r.json().get("ok"):
            print("  [Approval] Video preview + keyboard sent to Telegram")
            return True
        print(f"  [Approval] Video send failed: {r.text[:120]} — falling back to text keyboard")
        return False
    except Exception as e:
        print(f"  [Approval] Video send error: {e} — falling back to text keyboard")
        return False


def send_telegram_text(text):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": TELEGRAM_CHAT_ID, "text": text[:4096]},
            timeout=30
        )
        print("  Caption message sent")
    except Exception as e:
        print(f"  Caption send failed: {e}")


def send_whatsapp_text(text: str):
    """Send a plain-text notification to the operator's WhatsApp (+44-7405-746302).
    Runs alongside Telegram — both channels stay active."""
    if not WHATSAPP_ACCESS_TOKEN or not WHATSAPP_PHONE_NUMBER_ID:
        return
    try:
        requests.post(
            f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages",
            headers={
                "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
                "Content-Type": "application/json",
            },
            json={
                "messaging_product": "whatsapp",
                "to": WHATSAPP_RECIPIENT,
                "type": "text",
                "text": {"body": text[:4096]},
            },
            timeout=20,
        )
    except Exception as e:
        print(f"  [WhatsApp notify] {e}")


def check_whatsapp_approval(approval_id: str) -> str | None:
    """
    Poll Vercel /api/pipeline-decision for a WhatsApp reply decision.
    Returns: 'all_v1' | 'all_v2' | 'tt_ig' | 'ignore' | 'tt_v1' | 'tt_v2' |
             'ig_v1' | 'ig_v2' | None (no reply yet)
    approval_id is ignored — endpoint always returns the oldest unprocessed decision.
    """
    try:
        r = requests.get(
            "https://boothop.com/api/pipeline-decision",
            headers={"x-pipeline-secret": "boothop_pipeline_secret_2026"},
            timeout=10,
        )
        if r.ok:
            data = r.json()
            return data.get("decision") or None
    except Exception:
        pass
    return None


def send_telegram_approval_request(approval_id: str):
    """
    Send per-platform approval keyboard to Telegram.
    Approval ID is embedded so WhatsApp bridge can also route replies.

    Row 1 (quick): Post All V1 | Post All V2 | Ignore
    Rows 2-3:      TikTok / Instagram  with V1 | V2 | Skip each
    YouTube auto-follows TikTok. LinkedIn runs separately.
    Ignore overrides 90-min auto-post — nothing posts.
    """
    markup = json.dumps({"inline_keyboard": [
        [
            {"text": "Post All V1",   "callback_data": "all_v1"},
            {"text": "Post All V2",   "callback_data": "all_v2"},
            {"text": "⏰ Post in 1hr", "callback_data": "delay_1hr"},
        ],
        [
            {"text": "TikTok V1",    "callback_data": "tt_v1"},
            {"text": "TikTok V2",    "callback_data": "tt_v2"},
            {"text": "TikTok Skip",  "callback_data": "tt_skip"},
        ],
        [
            {"text": "IG V1",        "callback_data": "ig_v1"},
            {"text": "IG V2",        "callback_data": "ig_v2"},
            {"text": "IG Skip",      "callback_data": "ig_skip"},
        ],
        [
            {"text": "📖 IG = Story",  "callback_data": "ig_story"},
            {"text": "🚫 Ignore",      "callback_data": "ignore_all"},
        ],
    ]})
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": (
                    "*Content ready — your call:*\n\n"
                    "Row 1: Post same version to all platforms now, or delay 1hr.\n"
                    "Rows 2-3: Choose per platform independently.\n"
                    "YouTube auto-follows TikTok.\n"
                    "⏰ *Post in 1hr* = posts at prime time (still in the 7-9am window).\n"
                    "🚫 *Ignore* = nothing posts today.\n\n"
                    "_No reply in 60 min = TikTok V1, Instagram V2, YouTube V1 auto-post._"
                ),
                "parse_mode": "Markdown",
                "reply_markup": markup,
            },
            timeout=30,
        )
        data = r.json()
        if r.ok and data.get("ok"):
            print("  [Approval] Keyboard sent to Telegram")
            return data["result"]["message_id"]
        print(f"  [Approval] Keyboard send failed: {data}")
        return None
    except Exception as e:
        print(f"  [Approval] Request error: {e}")
        return None


def wait_for_approval(approval_id: str, timeout_seconds=3600):
    """
    Polls BOTH Telegram (inline keyboard) and WhatsApp (bridge file) for approval.

    Telegram: real-time inline keyboard callbacks (active now).
    WhatsApp:  reads DATA/whatsapp_approvals.json written by the webhook bridge (stub — ready to wire).

    Returns dict:
        {
            "tiktok":    "v1" | "v2" | "skip" | None,
            "instagram": "v1" | "v2" | "skip" | None,
            "ignore":    True | False,   ← Ignore cancels 90-min auto-post
        }
    None = not explicitly set → posting logic applies platform default.
    ignore=True → nothing posts, 90-min auto is suppressed.
    """
    _CB_MAP = {
        "all_v1":     ("all",       "v1"),
        "all_v2":     ("all",       "v2"),
        "ignore_all": ("all",       "ignore"),
        "delay_1hr":  ("all",       "delay"),
        "tt_v1":      ("tiktok",    "v1"),
        "tt_v2":      ("tiktok",    "v2"),
        "tt_skip":    ("tiktok",    "skip"),
        "ig_v1":      ("instagram", "v1"),
        "ig_v2":      ("instagram", "v2"),
        "ig_skip":    ("instagram", "skip"),
        "ig_story":   ("instagram", "story"),
        "choose_v1":  ("all",       "v1"),
        "choose_v2":  ("all",       "v2"),
    }

    def _apply(choices, cb_data):
        """Apply a callback decision to the choices dict. Returns confirmed=True if terminal."""
        if cb_data not in _CB_MAP:
            return False
        platform, version = _CB_MAP[cb_data]
        if platform == "all":
            if version == "ignore":
                choices["ignore"] = True
            elif version == "delay":
                choices["delay"] = True
            else:
                choices["tiktok"]    = version
                choices["instagram"] = version
            return True
        else:
            choices[platform] = version
            return False  # per-platform — keep waiting for other platforms

    def _ack_telegram(cb_id, text="Got it!"):
        try:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/answerCallbackQuery",
                json={"callback_query_id": cb_id, "text": text},
                timeout=10,
            )
        except Exception:
            pass

    # Drain stale Telegram updates before starting
    try:
        drain = requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates",
            params={"timeout": 0, "allowed_updates": json.dumps(["callback_query"])},
            timeout=10,
        ).json()
        updates = drain.get("result", [])
        offset = (updates[-1]["update_id"] + 1) if updates else 0
    except Exception:
        offset = 0

    choices   = {"tiktok": None, "instagram": None, "ignore": False, "delay": False}
    deadline  = datetime.now().timestamp() + timeout_seconds
    confirmed = False

    print(f"  [Approval] Waiting up to {timeout_seconds // 60}min — Telegram + WhatsApp (id={approval_id})")

    while datetime.now().timestamp() < deadline and not confirmed:
        # ── WhatsApp bridge check (runs every poll cycle) ──────────────────────
        wa_decision = check_whatsapp_approval(approval_id)
        if wa_decision:
            confirmed = _apply(choices, wa_decision)
            print(f"  [Approval/WA] Received: {wa_decision} → choices={choices}")
            if confirmed:
                break

        # ── Telegram long-poll ─────────────────────────────────────────────────
        remaining = deadline - datetime.now().timestamp()
        wait = int(min(30, remaining))
        if wait <= 0:
            break
        try:
            resp = requests.get(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates",
                params={"offset": offset, "timeout": wait,
                        "allowed_updates": json.dumps(["callback_query"])},
                timeout=wait + 15,
            ).json()
        except Exception as e:
            print(f"  [Approval] Poll error: {e}")
            continue

        for upd in resp.get("result", []):
            offset  = upd["update_id"] + 1
            cb      = upd.get("callback_query", {})
            cb_data = cb.get("data", "")
            if cb_data not in _CB_MAP:
                continue
            terminal = _apply(choices, cb_data)
            platform, version = _CB_MAP[cb_data]
            if version == "ignore":
                _ack_telegram(cb["id"], "🚫 Ignored — nothing will post today.")
            elif version == "delay":
                _ack_telegram(cb["id"], "⏰ Got it — posting in 60 min, right in prime time.")
            elif platform == "all":
                _ack_telegram(cb["id"], f"✅ All platforms → {version.upper()} — posting now!")
            else:
                _ack_telegram(cb["id"], f"✅ {platform.capitalize()} → {version.upper()}")
            print(f"  [Approval/TG] {cb_data} → choices={choices}")
            if terminal:
                confirmed = True
                break

    # ── Timeout handling ───────────────────────────────────────────────────────
    if not confirmed:
        if choices["ignore"]:
            print("  [Approval] Ignore was set — suppressing auto-post")
        else:
            print("  [Approval] Timed out — platform defaults will apply")

    return choices


# ── YouTube upload ─────────────────────────────────────────────────────────────
YOUTUBE_UPLOADER   = BASE / "scripts" / "upload_to_youtube.py"
YOUTUBE_SEQ_FILE   = DATA / "youtube_sequence.json"

# 2-letter bucket codes for video IDs
BUCKET_CODES = {
    "family":    "FD",
    "business":  "BD",
    "airport":   "AD",
    "smart":     "SD",
    "cinematic": "CD",
    "community": "CM",
}

YOUTUBE_HASHTAGS = {
    "family":    "#BootHop #DiasporaDelivery #LondonToLagos #SameDayDelivery #UKNigeria",
    "business":  "#BootHop #LogisticsInnovation #SupplyChain #B2BDelivery #UrgentLogistics",
    "airport":   "#BootHop #AirportDelivery #UrgentDelivery #TravelHack #SameDayDelivery",
    "smart":     "#BootHop #SmartLogistics #FutureOfDelivery #HumanPowered #Innovation",
    "cinematic": "#BootHop #PremiumDelivery #TrustedMovement #HumanLogistics #Movement",
    "community": "#BootHop #DiasporaMagic #NaijaUK #LondonToLagos #CommunityDelivery",
}


def next_youtube_id(bucket):
    """
    Returns the next sequential YouTube video ID and increments the counter.
    Format: BootHop-BD0001  (bucket code + 4-digit zero-padded sequence)
    Counter persists in data/youtube_sequence.json across runs.
    """
    code = BUCKET_CODES.get(bucket, "BH")
    if YOUTUBE_SEQ_FILE.exists():
        try:
            data = json.loads(YOUTUBE_SEQ_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    else:
        data = {}
    seq = data.get("seq", 0) + 1
    if seq > 9999:
        seq = 1
    data["seq"] = seq
    YOUTUBE_SEQ_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return f"BootHop-{code}{seq:04d}"


def upload_to_youtube(video_path, hook, hero_line, bucket, version_letter="A"):
    """
    Upload one video to YouTube.
    version_letter: uppercase = primary language, lowercase = English translation
    Title format: BootHop-BD0001A  (catalogue ID + version letter)
    """
    if not YOUTUBE_UPLOADER.exists():
        print("  [YouTube] Uploader script not found — skipping")
        return
    if not Path(video_path).exists():
        print(f"  [YouTube] Video file missing: {video_path}")
        return

    lang, clean_hook = detect_lang(hook)
    clean_hook = strip_emoji(clean_hook)
    if clean_hook.upper().startswith("POV:"):
        clean_hook = clean_hook[4:].strip()
    elif clean_hook.upper().startswith("POV "):
        clean_hook = clean_hook[4:].strip()

    video_id = next_youtube_id(bucket)
    title    = f"{video_id}{version_letter}"   # e.g. BootHop-BD0001A

    hashtags = YOUTUBE_HASHTAGS.get(bucket, YOUTUBE_HASHTAGS["community"])
    description = (
        f"{title}\n\n"
        f"{clean_hook}\n\n"
        f"{hero_line}\n\n"
        f"BootHop — someone is already going your way.\n"
        f"Same-day delivery powered by trusted travellers.\n"
        f"London to Lagos. Frankfurt to Abuja. New York to beyond.\n"
        f"boothop.com\n\n"
        f"{hashtags}\n\n"
        f"BootHop — Compliance-First Distributed Logistics Network.\n"
        f"Verified travellers. AI-assisted customs. Stripe escrow.\n"
        f"Get started: https://www.boothop.co.uk"
    )

    print(f"  [YouTube] Uploading {title} ({Path(video_path).name})...")
    try:
        result = subprocess.run(
            ["python", str(YOUTUBE_UPLOADER), video_path, title, description],
            capture_output=True, text=True, timeout=300
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if "UPLOADED" in line or "YouTube URL" in line:
                    print(f"  [YouTube] {line.strip()}")
        else:
            err = (result.stderr or result.stdout)[-200:]
            print(f"  [YouTube] Upload failed: {err}")
    except subprocess.TimeoutExpired:
        print("  [YouTube] Upload timed out")
    except Exception as e:
        print(f"  [YouTube] Error: {e}")


# ── Cleanup: rolling 21-day output retention ───────────────────────────────────
def cleanup_old_outputs():
    cutoff = datetime.now() - timedelta(days=21)
    removed = 0
    for folder in OUTPUT.iterdir():
        if not folder.is_dir():
            continue
        try:
            folder_date = datetime.strptime(folder.name, "%Y-%m-%d")
            if folder_date < cutoff:
                shutil.rmtree(str(folder))
                print(f"  Removed old output: {folder.name}")
                removed += 1
        except ValueError:
            pass
    if removed:
        print(f"  Cleaned up {removed} old output folder(s) (>21 days)")


# ── Main pipeline ──────────────────────────────────────────────────────────────
def render_version(base_mp4, hook, bucket, platform, version_num,
                   music, out_dir, suffix=""):
    """
    Render 1 video for one narrative using the supplied music track.
    Returns list of (path, label, caption) tuples for Telegram.
    suffix: 'v1' or 'v2'
    """
    lang, clean_hook = detect_lang(hook)
    voice_mp3   = TEMP / f"voice_{suffix}.mp3"
    slot_voice  = pick_slot_voice(version_num)  # slot + version → accent + gender
    hero_line = problem = solution = ""

    try:
        hero_line, problem, solution = generate_voiceover(
            hook, voice_mp3, bucket=bucket, force_voice=slot_voice
        )
        print(f"  [{suffix}] Voiceover ready — {hero_line[:50]}")
    except Exception as e:
        print(f"  [{suffix}] Voiceover failed: {e} — using fallback")
        hero_line = random.choice(HERO_LINES.get(bucket, ["Turning journeys into lifelines."]))
        problem   = "Traditional delivery takes too long and costs too much."
        solution  = "BootHop connects your delivery to someone already going your way."
        try:
            fb = apply_phonetics(strip_emoji(clean_hook)) + ". BootHop. Delivered by someone already going your way. Join us at boothop dot com."
            asyncio.run(make_voiceover(fb, voice_mp3, voice=slot_voice))
        except Exception:
            subprocess.run(["python", "-m", "edge_tts", "--voice", slot_voice,
                            "--text", strip_emoji(clean_hook) + ". BootHop dot com.",
                            "--write-media", str(voice_mp3)], capture_output=True)

    caption = build_caption(hook, hero_line, bucket, platform=platform)
    results = []

    # Generate vibrant cover frame (shared across all renders for this version)
    cover_png = TEMP / f"cover_{suffix}.png"
    cover_ok  = generate_cover_frame(hook, bucket, cover_png)
    if cover_ok:
        print(f"  [{suffix}] Cover generated: {cover_png.name}")
    else:
        cover_png = None

    if not music or not Path(music).exists():
        print(f"  [{suffix}] No music file — skipping render")
    else:
        out = out_dir / f"v{version_num}_{suffix}.mp4"
        try:
            render_video(base_mp4, voice_mp3, music, hook, hero_line, out,
                         problem=problem, solution=solution, cover_path=cover_png)
            size = out.stat().st_size // (1024 * 1024)
            label = f"V{version_num} — {platform.upper()}"
            print(f"  [{suffix}] {label}: {out.name} ({size}MB)")
            # Save cover thumbnail alongside each video for platform uploads
            if cover_png and cover_png.exists():
                import shutil as _sh
                thumb = out.with_suffix(".jpg")
                try:
                    from PIL import Image as _PilImg
                    _PilImg.open(cover_png).convert("RGB").save(str(thumb), "JPEG", quality=92)
                except Exception:
                    _sh.copy2(str(cover_png), str(thumb))
            results.append((str(out), label, caption))
        except Exception as e:
            print(f"  [{suffix}] Render failed: {e}")

    # English version if non-English hook
    needs_en = (lang == "ES") or (pick_voice(clean_hook, lang) == LANG_VOICES["NG"])
    if needs_en:
        voice_en = TEMP / f"voice_{suffix}_en.mp3"
        try:
            en_script, hero_en, en_problem, en_solution = build_story_script(clean_hook, bucket)
            asyncio.run(make_voiceover(apply_phonetics(en_script), voice_en, voice=pick_slot_voice(version_num)))
            trimmed = voice_en.with_suffix(".trimmed.mp3")
            subprocess.run(["ffmpeg", "-y", "-i", str(voice_en),
                            "-af", "silenceremove=start_periods=1:start_silence=0.03:start_threshold=-50dB",
                            str(trimmed)], capture_output=True)
            if trimmed.exists() and trimmed.stat().st_size > 1000:
                trimmed.replace(voice_en)
            if music and Path(music).exists():
                out_en = out_dir / f"v{version_num}_english_{suffix}.mp4"
                render_video(base_mp4, voice_en, music, clean_hook, hero_en, out_en,
                             problem=en_problem, solution=en_solution, cover_path=cover_png)
                caption_en = build_caption(clean_hook, hero_en, bucket, platform=platform)
                label_en = f"V{version_num} English — {platform.upper()}"
                results.append((str(out_en), label_en, caption_en))
                print(f"  [{suffix}] English version ready")
        except Exception as e:
            print(f"  [{suffix}] English version failed: {e}")

    return results, hero_line, caption


# ── Brand overlay card generator ──────────────────────────────────────────────
def ensure_fig_assets():
    """Generate FIG1, FIG2 (mid-roll brand cards) and FIG_END (end card) if missing."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("  [WARN] Pillow not installed — FIG overlay cards will be missing")
        return

    W = 1080

    def _load_font(path, size):
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            return ImageFont.load_default()

    font_big   = _load_font(FONT_TITLE, 72)
    font_small = _load_font(FONT_BODY,  44)

    # ── fig1Start & fig2start (brand strip overlaid at video centre, 20-22s) ──
    strip_configs = [
        (FIG1, (10, 10, 30),  "#FFD700", "REAL PEOPLE. REAL ROUTES."),
        (FIG2, (20, 8,  40),  "#FF9500", "TRUSTED BY THE DIASPORA."),
    ]
    for path, bg_rgb, accent, tagline in strip_configs:
        if path.exists():
            continue
        H = 320
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d   = ImageDraw.Draw(img)

        # Dark semi-transparent bar
        d.rectangle([0, 0, W, H], fill=(*bg_rgb, 210))

        # Left accent stripe
        d.rectangle([0, 0, 12, H], fill=accent)

        # BootHop logo (small, left-aligned)
        logo_path = ASSETS / "boothop-icon-512.png"
        if logo_path.exists():
            try:
                logo = Image.open(logo_path).convert("RGBA")
                logo_h = H - 60
                logo_w = int(logo.width * (logo_h / logo.height))
                logo = logo.resize((logo_w, logo_h), Image.LANCZOS)
                img.paste(logo, (30, 30), logo)
                text_x = 30 + logo_w + 24
            except Exception:
                text_x = 50
        else:
            text_x = 50

        # Brand name
        d.text((text_x, 30), "BootHop", font=font_big, fill="#FFD700")
        d.text((text_x, 118), tagline, font=font_small, fill="#FFFFFF")
        d.text((text_x, 180), "boothop.com", font=font_small, fill=accent)

        img.save(str(path), "PNG")
        print(f"  [Setup] Generated {path.name}")

    # ── FIG4End (full-screen end card 1080×1920, shown at 27-30s) ────────────
    if not FIG_END.exists():
        H = 1920
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d   = ImageDraw.Draw(img)

        # Deep navy background
        d.rectangle([0, 0, W, H], fill=(8, 12, 28, 230))

        # Gradient-like horizontal bands at bottom
        for i in range(300):
            alpha = int(80 * (i / 300))
            d.rectangle([0, H - 300 + i, W, H - 299 + i], fill=(255, 180, 0, alpha))

        # Thin gold accent line at top
        d.rectangle([0, 0, W, 8], fill="#FFD700")

        # Logo centred
        logo_path = ASSETS / "boothop-icon-512.png"
        logo_y = 380
        if logo_path.exists():
            try:
                logo = Image.open(logo_path).convert("RGBA")
                lw, lh = 240, 240
                logo = logo.resize((lw, lh), Image.LANCZOS)
                img.paste(logo, ((W - lw) // 2, logo_y), logo)
            except Exception:
                pass

        # "BootHop" brand
        font_hero  = _load_font(FONT_TITLE, 130)
        font_url   = _load_font(FONT_BODY,   60)
        font_tag   = _load_font(FONT_BODY,   46)

        brand_text = "BootHop"
        bb = d.textbbox((0, 0), brand_text, font=font_hero)
        bw = bb[2] - bb[0]
        d.text(((W - bw) // 2, 680), brand_text, font=font_hero, fill="#FFD700")

        tagline2 = "Move anything. With someone going anyway."
        # word-wrap to two lines
        words = tagline2.split()
        line1, line2 = " ".join(words[:5]), " ".join(words[5:])
        for i, ln_txt in enumerate([line1, line2]):
            tb = d.textbbox((0, 0), ln_txt, font=font_tag)
            tw = tb[2] - tb[0]
            d.text(((W - tw) // 2, 860 + i * 60), ln_txt, font=font_tag, fill="#CCCCCC")

        url_text = "boothop.com"
        ub = d.textbbox((0, 0), url_text, font=font_url)
        uw = ub[2] - ub[0]
        d.text(((W - uw) // 2, 1020), url_text, font=font_url, fill="#FFD700")

        img.save(str(FIG_END), "PNG")
        print(f"  [Setup] Generated {FIG_END.name}")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", default="tiktok", choices=["tiktok", "instagram"],
                        help="Platform to generate captions for")
    parser.add_argument("--skip-if-ran-today", action="store_true",
                        help="Exit silently if videos already exist in today's output folder")
    args = parser.parse_args()
    platform = args.platform

    today = datetime.now().strftime("%Y-%m-%d")

    # Startup catchup guard — don't double-run on days pipeline already completed
    if args.skip_if_ran_today:
        existing = list((OUTPUT / today).glob("*.mp4")) if (OUTPUT / today).exists() else []
        if len(existing) >= 2:
            print(f"[Skip] Pipeline already ran today ({len(existing)} videos in output/{today}/) — exiting.")
            _write_crash(f"SKIP (--skip-if-ran-today): {len(existing)} videos already in output/{today}/")
            return
    run_time = datetime.now().strftime("%H%M")

    print(f"\n{'='*58}")
    print(f"  BootHop Pipeline — {platform.upper()}")
    print(f"  {datetime.now().strftime('%A %d %B %Y  %H:%M')}")
    print(f"{'='*58}\n")

    TEMP.mkdir(exist_ok=True)
    ensure_fig_assets()
    out_dir = OUTPUT / today
    out_dir.mkdir(parents=True, exist_ok=True)
    cleanup_old_outputs()

    _set_step("init: bucket/music/theme")
    bucket = get_adjusted_bucket()
    music_v1, music_v2 = get_music()
    theme_idx, theme = get_weekly_theme()
    print(f"  Bucket   : {bucket}  |  Platform: {platform}")
    print(f"  Theme    : Week {theme_idx+1}/4 — {theme['name']}")
    print(f"  Posting  : TikTok Reel  |  Instagram Reel  |  YouTube Short")

    # ── VERSION 1 ──────────────────────────────────────────────────────────────
    _set_step("V1: pick_content")
    print(f"\n[V1] Selecting hook...")
    hook1, eng1 = pick_content(bucket)
    print(f"  Hook: {hook1[:70]}")

    _set_step("V1: download_clips")
    print(f"\n[V1] Downloading clips...")
    clips1, queries1 = download_clips(hook1, bucket, count=8, prefix="v1_")
    if len(clips1) < 2:
        print("  [V1] Not enough clips — skipping V1")
        clips1 = []

    base1 = TEMP / "base_v1.mp4"
    if clips1:
        _set_step("V1: process_clips")
        print(f"\n[V1] Processing clips...")
        process_clips(clips1, base1, prefix="v1_")

    # ── VERSION 2 ──────────────────────────────────────────────────────────────
    _set_step("V2: pick_content")
    print(f"\n[V2] Selecting hook (different narrative)...")
    hook2, eng2 = pick_content(bucket, exclude=[hook1])
    print(f"  Hook: {hook2[:70]}")

    _set_step("V2: download_clips")
    print(f"\n[V2] Downloading clips (different scenes from V1)...")
    clips2, queries2 = download_clips(hook2, bucket, count=8, prefix="v2_", exclude_queries=queries1)
    if len(clips2) < 2:
        print("  [V2] Not enough clips — skipping V2")
        clips2 = []

    base2 = TEMP / "base_v2.mp4"
    if clips2:
        _set_step("V2: process_clips")
        print(f"\n[V2] Processing clips...")
        process_clips(clips2, base2, prefix="v2_")

    # ── RENDER 2 VIDEOS (V1 + V2, one music track each) ───────────────────────
    _set_step("render: building videos")
    print(f"\n[RENDER] Building videos...")
    all_videos = []  # (path, label, caption)
    hero1, hero2, caption1, caption2 = "", "", "", ""

    if clips1 and base1.exists():
        v1_videos, hero1, caption1 = render_version(
            base1, hook1, bucket, platform, 1, music_v1, out_dir, suffix="v1"
        )
        all_videos.extend(v1_videos)
        save_used(hook1, eng1)

    if clips2 and base2.exists():
        v2_videos, hero2, caption2 = render_version(
            base2, hook2, bucket, platform, 2, music_v2, out_dir, suffix="v2"
        )
        all_videos.extend(v2_videos)
        save_used(hook2, eng2)

    # ── TELEGRAM ───────────────────────────────────────────────────────────────
    _set_step("telegram: sending videos")
    print(f"\n[TELEGRAM] Sending {len(all_videos)} videos...")
    if not all_videos:
        _alert = (
            f"⚠️ PIPELINE RAN BUT NO VIDEOS RENDERED\n"
            f"📅 {datetime.now().strftime('%A %d %B  %H:%M')}\n"
            f"Check pipeline logs — render_video() likely failed.\n"
            f"Clips1 ready: {bool(clips1 and base1.exists())} | Clips2 ready: {bool(clips2 and base2.exists())}"
        )
        send_telegram_text(_alert)
        send_whatsapp_text(_alert)
        return

    for path, label, caption in all_videos:
        send_telegram_video(path, caption, label)

    # Daily plan + content briefing — sent to Telegram + WhatsApp before approval keyboard
    theme_idx, theme = get_weekly_theme()
    _auto_post_str = (datetime.now() + timedelta(minutes=60)).strftime("%H:%M")

    _plan = (
        f"📅 *BOOTHOP DAILY PLAN — {datetime.now().strftime('%A %d %B  %H:%M')}*\n"
        f"🪣 *{bucket.upper()}* bucket  ·  Theme Wk{theme_idx+1}/4: _{theme['name']}_\n\n"
        f"*WHAT'S POSTING TODAY:*\n"
        f"  ~{_auto_post_str}  🎬 TikTok — Reel V1 (library music)\n"
        f"  ~{_auto_post_str}  🎬 Instagram — Reel V2 (trending music)\n"
        f"  ~{_auto_post_str}  📺 YouTube — Short (follows TikTok)\n"
        f"  12:00     🖼️  Instagram — Carousel (auto)\n\n"
        f"*TODAY'S CONTENT:*\n"
    )
    if clips1:
        _plan += f"  V1 → _{hook1[:70]}_\n"
    if clips2:
        _plan += f"  V2 → _{hook2[:70]}_\n"
    _plan += f"\n⏱ _Approve below within 60 min or auto-posts at {_auto_post_str}._"

    send_telegram_text(_plan)
    send_whatsapp_text(_plan)

    # ── YOUTUBE ────────────────────────────────────────────────────────────────
    # Day alternation: odd day-of-year → V1, even day → V2
    # Non-English hooks: upload primary (local) version + English translation version
    # Naming: BootHop-BD0001A (primary/local), BootHop-BD0001a (English translation)
    _set_step("youtube: preparing upload")
    print(f"\n[YOUTUBE] Preparing upload...")
    day_of_year  = datetime.now().timetuple().tm_yday
    use_v1       = (day_of_year % 2 == 1)   # odd days = V1, even days = V2
    version_num  = "1" if use_v1 else "2"
    yt_hook      = hook1 if use_v1 else hook2
    yt_hero      = hero1 if use_v1 else hero2
    yt_suffix    = "v1" if use_v1 else "v2"
    yt_target    = f"V{version_num}"

    # Find primary video (local language — not the English translation)
    yt_primary = None
    for path, label, _ in all_videos:
        if yt_target in label and "english" not in Path(path).stem.lower():
            yt_primary = path
            break

    # Find English translation video (stem contains 'english')
    yt_english = None
    lang, _ = detect_lang(yt_hook)
    hook_needs_english = (lang == "ES") or (pick_voice(detect_lang(yt_hook)[1], lang) == LANG_VOICES["NG"])
    if hook_needs_english:
        en_stem = f"v{version_num}_english_{yt_suffix}"
        for path, label, _ in all_videos:
            if "english" in Path(path).stem.lower() and yt_suffix in Path(path).stem.lower():
                yt_english = path
                break

    # Fallback: any video of the right version
    if not yt_primary:
        for path, label, _ in all_videos:
            if f"V{version_num}" in label and "english" not in Path(path).stem.lower():
                yt_primary = path
                break

    youtube_ok = False  # track whether YouTube upload succeeded this run
    _yt_flag   = DATA / "youtube_token_ok.txt"

    # ── SOCIAL + YOUTUBE POSTING (approval-gated, 90-min window) ───────────────
    # All platforms (TikTok, Instagram, YouTube) wait for approval together.
    # If no response in 90 min → auto-posts V1 to all platforms.
    def _find_social_video(version_num):
        for path, label, cap in all_videos:
            if f"V{version_num}" in label and "english" not in Path(path).stem.lower():
                return path, cap
        return None, ""

    soc_v1_path, soc_v1_caption = _find_social_video(1)
    soc_v2_path, soc_v2_caption = _find_social_video(2)

    # ── Daily Story — generate alongside V1/V2 ────────────────────────────────
    _story_path = None
    try:
        _story_script = BASE / "test" / "daily_story.py"
        if _story_script.exists():
            print("\n[STORY] Generating daily story reel...")
            _sr = subprocess.run(
                [sys.executable, str(_story_script)],
                cwd=str(BASE), capture_output=True, text=True, timeout=420,
            )
            # Find output — daily_story_<name>.mp4
            _story_candidates = sorted(
                (BASE / "test").glob("daily_story_*.mp4"),
                key=lambda p: p.stat().st_mtime, reverse=True,
            )
            if _story_candidates:
                _story_path = str(_story_candidates[0])
                print(f"  [STORY] Ready: {Path(_story_path).name}")
            else:
                print(f"  [STORY] Script ran but no output found")
        else:
            print("  [STORY] daily_story.py not found — skipping")
    except Exception as _se:
        print(f"  [STORY] Error generating story: {_se}")

    ig_ok = False  # track whether Instagram succeeded this run
    li_ok = False  # track whether LinkedIn succeeded this run

    def _try_post(fn, *args, retries=2, backoff=15):
        last_exc = None
        for attempt in range(1, retries + 2):
            try:
                return fn(*args)
            except Exception as exc:
                last_exc = exc
                if attempt <= retries:
                    print(f"  [Retry {attempt}/{retries}] {fn.__name__} failed: {exc} — retrying in {backoff}s")
                    time.sleep(backoff)
        raise last_exc

    def _do_youtube_upload(chosen_version_num, chosen_hook, chosen_hero):
        """Upload YouTube after approval — gates on same 90-min window."""
        nonlocal youtube_ok
        _primary = None
        _english = None
        for path, label, _ in all_videos:
            if f"V{chosen_version_num}" in label and "english" not in Path(path).stem.lower():
                _primary = path
                break
        _lang, _ = detect_lang(chosen_hook)
        if (_lang == "ES") or (pick_voice(detect_lang(chosen_hook)[1], _lang) == LANG_VOICES["NG"]):
            _sfx = f"v{chosen_version_num}"
            for path, label, _ in all_videos:
                if "english" in Path(path).stem.lower() and _sfx in Path(path).stem.lower():
                    _english = path
                    break
        if _primary:
            print(f"  [YouTube Short] Uploading — {Path(_primary).name}")
            try:
                upload_to_youtube(_primary, chosen_hook, chosen_hero, bucket, version_letter="A")
                if _english:
                    upload_to_youtube(_english, chosen_hook, chosen_hero, bucket, version_letter="a")
                youtube_ok = True
                _yt_flag.write_text("ok")
                _log_post("youtube", chosen_hook, bucket, music_v1 if chosen_version_num == 1 else music_v2)
            except Exception as _yt_e:
                print(f"  [YouTube] Upload error: {_yt_e}")
                try:
                    _yt_flag.unlink(missing_ok=True)
                except Exception:
                    pass
        else:
            print("  [YouTube] No video available to upload")

    def _post_platform(platform, version_num, label=""):
        """Post to a single platform with the specified version."""
        nonlocal ig_ok, li_ok
        vpath   = soc_v1_path   if version_num == 1 else soc_v2_path
        caption = soc_v1_caption if version_num == 1 else soc_v2_caption
        _hook   = hook1 if version_num == 1 else hook2
        _hero   = hero1 if version_num == 1 else hero2
        _music  = music_v1 if version_num == 1 else music_v2

        if not vpath or not Path(vpath).exists():
            print(f"  [{platform}] Video not found for V{version_num}")
            return

        if platform == "tiktok":
            try:
                tt_id = _try_post(post_tiktok.post_video, vpath, caption)
                msg = f"TikTok {label} sent — publish_id: {tt_id}" if tt_id else f"TikTok {label} failed"
                print(f"  {msg}"); send_telegram_text(msg)
                if tt_id:
                    _log_post("tiktok", _hook, bucket, _music, media_id=str(tt_id))
            except Exception as _e:
                send_telegram_text(f"TikTok {label} error: {_e}")

        elif platform == "instagram":
            try:
                ig_id = _try_post(post_instagram.post_reel, vpath, caption)
                if ig_id:
                    ig_ok = True
                    msg = f"Instagram {label} published — media_id: {ig_id}"
                    _log_post("instagram", _hook, bucket, _music, media_id=str(ig_id))
                else:
                    msg = f"Instagram {label} failed"
                print(f"  {msg}"); send_telegram_text(msg)
            except Exception as _e:
                send_telegram_text(f"Instagram {label} error: {_e}")

        elif platform == "youtube":
            print(f"\n[YOUTUBE] Uploading V{version_num} (post-approval)...")
            _do_youtube_upload(version_num, _hook, _hero)

        elif platform == "linkedin":
            try:
                li_urn = post_linkedin.post_video(vpath, caption)
                if li_urn:
                    li_ok = True
                    msg = f"LinkedIn {label} published — URN: {li_urn}"
                    _log_post("linkedin", _hook, bucket, _music, media_id=str(li_urn))
                else:
                    msg = f"LinkedIn {label} failed"
                print(f"  {msg}"); send_telegram_text(msg)
            except Exception as _e:
                send_telegram_text(f"LinkedIn {label} error: {_e}")

    if not _SOCIAL_ENABLED:
        print("\n[SOCIAL] Skipped — posting modules not loaded.")
    elif not soc_v1_path and not soc_v2_path:
        print("\n[SOCIAL] No videos available for social posting.")
    else:
        import random as _rand
        _approval_id = _rand.randint(10000, 99999)
        print(f"\n[SOCIAL] Sending approval request (id={_approval_id})...")

        # Send preview video WITH approval keyboard so user sees content + buttons together
        # Prefer V2 (trending music) as the preview; fall back to V1
        _preview_path = soc_v2_path or soc_v1_path
        _story_label  = f"\n*Story:* _{Path(_story_path).stem.replace('daily_story_','').replace('_',' ').title()}_" if _story_path else ""
        _preview_caption = (
            f"🎬 *PREVIEW — tap to approve*\n\n"
            f"*V1:* _{hook1[:60]}_\n"
            f"*V2:* _{hook2[:60]}_"
            f"{_story_label}\n\n"
            f"⏱ _Auto-posts at {_auto_post_str} if no reply._"
        )
        _video_sent = False
        if _preview_path and Path(_preview_path).exists():
            _video_sent = send_telegram_video_approval(_preview_path, _preview_caption)
        if not _video_sent:
            send_telegram_approval_request(str(_approval_id))

        # Send story preview separately so user can see it before deciding
        if _story_path and Path(_story_path).exists():
            try:
                _story_name = Path(_story_path).stem.replace("daily_story_","").replace("_"," ").title()
                send_telegram_video_approval(
                    _story_path,
                    f"📖 *Today's Story Reel — {_story_name}*\n_Tap '📖 IG = Story' to post this to Instagram instead of V2._"
                )
                print("  [STORY] Preview sent to Telegram")
            except Exception as _sp_e:
                print(f"  [STORY] Preview send error: {_sp_e}")

        # WhatsApp reply instructions
        _story_wa = "\n  5 or STORY   - Instagram = story reel" if _story_path else ""
        send_whatsapp_text(
            "BootHop pipeline ready!\n\n"
            "Reply to approve today's post:\n"
            "  1 or TT      - TikTok only (V1)\n"
            "  2 or IG      - Instagram only (V2)\n"
            "  3 or BOTH    - Post to both\n"
            f"  4 or SKIP    - Ignore, post nothing"
            f"{_story_wa}\n\n"
            "Or use Telegram for more options."
        )

        choices = wait_for_approval(str(_approval_id), timeout_seconds=3600)

        # Handle ignore
        if choices.get("ignore"):
            send_telegram_text("🚫 Pipeline ignored — nothing posted today.")
            send_whatsapp_text("🚫 Pipeline ignored — nothing posted today.")
            _clear_step()
            return

        # Handle delay — sleep 60 min then post with platform defaults
        if choices.get("delay"):
            _delay_post_time = (datetime.now() + timedelta(minutes=60)).strftime("%H:%M")
            _delay_msg = f"⏰ Posting in 60 min at ~{_delay_post_time} — right in the 7-9am prime window."
            send_telegram_text(_delay_msg)
            send_whatsapp_text(_delay_msg)
            print(f"  [Delay] Sleeping 60 min — will post at ~{_delay_post_time}")
            time.sleep(3600)

        # Default: TikTok=V1 (library, copyright-safe), Instagram=V2 (trending music)
        # YouTube auto-follows TikTok's version — no separate approval needed
        _platform_defaults = {"tiktok": 1, "instagram": 2}
        _tt_version_used = None

        for _plat in ("tiktok", "instagram"):
            _ver = choices.get(_plat)
            if _ver == "skip":
                send_telegram_text(f"{_plat.capitalize()} skipped.")
                continue
            # Story reel — post daily_story.mp4 to Instagram instead of V1/V2
            if _ver == "story" and _plat == "instagram" and _story_path and Path(_story_path).exists():
                print(f"\n[Instagram] Posting daily story reel: {Path(_story_path).name}")
                try:
                    _story_caption = (
                        "Which route are you doing next? Drop it below 👇\n\n"
                        "#BootHop #EarnWhileYouTravel #NaijaUK #JapaToJapada #TrustedTraveller"
                    )
                    post_instagram_reel(_story_path, _story_caption)
                    ig_ok = True
                    send_telegram_text("✅ Instagram — Story Reel posted!")
                    _log_post("instagram_story", "daily_story_reel", bucket, "story")
                except Exception as _st_e:
                    send_telegram_text(f"❌ Instagram Story post failed: {_st_e}")
                    print(f"  [Instagram Story] Error: {_st_e}")
                continue
            _vnum = 2 if _ver == "v2" else (1 if _ver == "v1" else _platform_defaults[_plat])
            _post_platform(_plat, _vnum, f"V{_vnum}")
            if _plat == "tiktok":
                _tt_version_used = _vnum

        # YouTube follows TikTok automatically
        if choices.get("tiktok") != "skip":
            _yt_vnum = _tt_version_used if _tt_version_used else 1
            print(f"\n[YOUTUBE] Auto-uploading V{_yt_vnum} (follows TikTok)...")
            _do_youtube_upload(_yt_vnum, hook1 if _yt_vnum == 1 else hook2, hero1 if _yt_vnum == 1 else hero2)

    # ── STATUS / ACTION REQUIRED REPORT ───────────────────────────────────────
    try:
        _sc_path = SCRIPTS / "social_credentials.json"
        _li_days_left = None
        if _sc_path.exists():
            import os as _os
            _sc_data   = json.loads(_sc_path.read_text(encoding="utf-8"))
            _li_exp_in = _sc_data.get("linkedin", {}).get("expires_in", 0)
            _li_mtime  = _sc_path.stat().st_mtime
            from datetime import timezone as _tz
            _li_expiry = datetime.fromtimestamp(_li_mtime) + timedelta(seconds=_li_exp_in)
            _li_days_left = max(0, int((_li_expiry - datetime.now()).total_seconds() // 86400))

        _yt_token_path = SCRIPTS / "youtube_token.json"
        if youtube_ok:
            _yt_status = "✅ Uploaded this run"
        elif _yt_token_path.exists():
            _yt_data = json.loads(_yt_token_path.read_text(encoding="utf-8"))
            if _yt_data.get("token") and not _yt_data.get("expiry"):
                _yt_status = "⚠️ Token needs verification — run: python scripts/auth_youtube.py"
            else:
                _yt_status = "⚠️ Check token — run: python scripts/auth_youtube.py"
        else:
            _yt_status = "❌ youtube_token.json missing — run: python scripts/auth_youtube.py"

        if li_ok:
            _li_status = f"✅ Posted this run" + (f" (~{_li_days_left}d token left)" if _li_days_left else "")
        elif _li_days_left is not None:
            _li_status = f"⚠️ Not posted this run — token healthy (~{_li_days_left}d left)"
        else:
            _li_status = "❓ social_credentials.json not found"

        _ig_status = "✅ Active" if ig_ok else "⚠️ Not posted this run"

        status_block = (
            "\n\n📋 *ACTION REQUIRED:*\n"
            f"• YouTube: {_yt_status}\n"
            "• TikTok: ⏳ Pending Content Posting API approval\n"
            f"• Instagram: {_ig_status}\n"
            f"• LinkedIn: {_li_status}\n"
            "• Blog: check blog/pending/ folder for posts to publish"
        )
        send_telegram_text(status_block[:4096])
        send_whatsapp_text(status_block[:4096])
        print(f"\n[STATUS] Report sent to Telegram + WhatsApp.")
    except Exception as _st_e:
        print(f"  [STATUS] Failed to send status report: {_st_e}")

    # ── METADATA ───────────────────────────────────────────────────────────────
    meta = {
        "date": today, "time": run_time, "platform": platform, "bucket": bucket,
        "v1": {"hook": hook1, "engagement": eng1},
        "v2": {"hook": hook2, "engagement": eng2},
        "music_v1": str(music_v1), "music_v2": str(music_v2),
    }
    (out_dir / f"metadata_{platform}_{run_time}.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    _clear_step()
    print(f"\n{'='*58}")
    print(f"  Done! {len(all_videos)} videos sent to Telegram.")
    print(f"  Platform : {platform}  |  Bucket: {bucket}")
    print(f"  V1 Hook  : {strip_emoji(hook1)[:55]}")
    print(f"  V2 Hook  : {strip_emoji(hook2)[:55]}")
    print(f"  Output   : {out_dir}")
    print(f"{'='*58}\n")


if __name__ == "__main__":
    import traceback, atexit

    # If a step file exists from a previous run, that run was killed externally
    # (e.g. Task Scheduler stopped it due to battery). Log what it was doing.
    if _STEP_FILE.exists():
        try:
            _last_step = _STEP_FILE.read_text(encoding="utf-8").strip()
            _write_crash(f"PREV-RUN KILLED at step: {_last_step}")
            try:
                import requests as _req
                _req.post(
                    f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                    data={"chat_id": TELEGRAM_CHAT_ID,
                          "text": f"[pipeline.py] Previous run was killed externally.\nLast step: {_last_step}\n\nLikely cause: battery cutoff (StopIfGoingOnBatteries)."},
                    timeout=10,
                )
            except Exception:
                pass
        except Exception:
            pass
        _clear_step()

    atexit.register(_clear_step)  # clean up on normal or exception exit

    _write_crash(f"START — PID {os.getpid()}")
    try:
        main()
        _write_crash("DONE — exit 0")
    except Exception as _top_exc:
        _tb = traceback.format_exc()
        _write_crash(f"CRASH:\n{_tb}")
        _clear_step()
        try:
            import requests as _req
            _req.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                data={"chat_id": TELEGRAM_CHAT_ID,
                      "text": f"[pipeline.py CRASH]\n{str(_top_exc)[:800]}\n\nFull trace: data/pipeline_crash.log"},
                timeout=15,
            )
        except Exception:
            pass
        raise
