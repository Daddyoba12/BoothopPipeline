"""
test/daily_story.py
BootHop Daily Story Reel — character-driven postcard videos.

Rotates through 10 story archetypes daily. Each story is:
  - 4 postcard cards (7.5s each) + 5s closing = 35s
  - Real character, emotional arc, Pidgin English hooks
  - Beautiful / interesting visuals matching the character

Characters:
  1. Fine Boy Goes Lagos Broke
  2. Fine Girl on the Train (funny/flirty)
  3. The Nurse (trust & care)
  4. Naija Man in Agbada (going home proud)
  5. The Student (Japa life, earning while moving)
  6. Manchester Night Train (domestic UK, funny)
  7. Newcastle to Bristol (meet random fine person)
  8. The Fashion Slay Queen
  9. The Tough Guy Who Cares
  10. Mum at the Airport (emotional)

Run: python test/daily_story.py
     python test/daily_story.py --story 3   (pick specific story)
"""

import random, subprocess, sys
import requests
from datetime import datetime, date
from pathlib import Path

BASE   = Path(__file__).parent.parent
TEST   = Path(__file__).parent
ASSETS = BASE / "assets"

sys.path.insert(0, str(BASE / "scripts"))
from media_blocklist import blocked_video_ids

LOGO      = ASSETS / "mainlogo.png"
FONT_BOLD = str(ASSETS / "fonts" / "Oswald-Bold.ttf").replace("\\", "/").replace("C:/", "C\\:/")
FONT_BODY = str(ASSETS / "fonts" / "Montserrat-ExtraBold.ttf").replace("\\", "/").replace("C:/", "C\\:/")

TOTAL_DUR = 35
CARD_DUR  = 7.5

PEXELS_API_KEY  = "NY3tWysBJseeky8V1JEp2YjevIq6MTYcOCfuKNBU7iypjC7Qc5T1DTp5"
PEXELS_API_KEY2 = "OzT25PmEv1Vuj6xvOWhIAvAYyUz7kx9D2oAdmwKqWzMMzC089kxkHXnBB"
PIXABAY_API_KEY = "56176396-606d84f73894d89a364d530f0"

# ── Music rotation — upbeat R&B / Afropop ────────────────────────────────────
MUSIC_ROTATION = [
    ("Tems",         "Tems 2025 latest R&B afrobeats"),
    ("Ayra Starr",   "Ayra Starr 2025 latest hit afrobeats"),
    ("Asake",        "Asake 2025 latest street pop"),
    ("Simi",         "Simi 2025 latest Nigeria R&B"),
    ("Rema",         "Rema 2025 latest afrobeats calm"),
    ("Yemi Alade",   "Yemi Alade 2025 latest afropop"),
    ("Fireboy DML",  "Fireboy DML 2025 latest afropop"),
    ("Omah Lay",     "Omah Lay 2025 latest afrobeats"),
    ("Tiwa Savage",  "Tiwa Savage 2025 latest R&B afrobeats"),
    ("Victony",      "Victony 2025 latest afropop Nigeria"),
]
_doy = date.today().timetuple().tm_yday
ARTIST_NAME, ARTIST_SEARCH = MUSIC_ROTATION[_doy % len(MUSIC_ROTATION)]

# ══════════════════════════════════════════════════════════════════════════════
# STORY LIBRARY
# Each story = dict with:
#   name      : story title (used for filenames)
#   cards     : list of 4 dicts (top, main, sub, color)
#   queries   : list of 4 clip query lists — one per card
#   hashtags  : closing hashtags line
#   cta       : short closing card sub-text
# ══════════════════════════════════════════════════════════════════════════════

STORIES = [

    # ── 1. Fine Boy Goes Lagos Broke ──────────────────────────────────────────
    {
        "name": "fine_boy_broke",
        "cards": [
            {"top": "True story. 2024.",
             "main": "I was going Lagos.",
             "sub": "Pocket nearly empty. Ego still full.",
             "color": "#ffffff"},
            {"top": "My guy on WhatsApp said...",
             "main": "Log your trip on BootHop.",
             "sub": "Someone needs a parcel carried same route. You get paid.",
             "color": "#facc15"},
            {"top": "Me sef no believe am...",
             "main": "£140 landed in my account.",
             "sub": "For carrying one box from Heathrow to Lagos. Simple.",
             "color": "#10b981"},
            {"top": "Fine boy don land Lagos...",
             "main": "With spending money.",
             "sub": "Abi na BootHop do am? Na BootHop do am.",
             "color": "#fb923c"},
        ],
        "queries": [
            ["african man face worried close up portrait",
             "black man face sad emotional headshot",
             "young african man face stressed expression close up"],
            ["african man face phone excited smiling close up",
             "black man face laughing phone portrait",
             "young african man face happy discovery close up"],
            ["african man face confident happy portrait close up",
             "black man face joyful laughing headshot",
             "young african man face triumph smiling portrait"],
            ["african man face proud confident smiling portrait",
             "black man face fashion smiling close up",
             "nigerian man face traditional clothes smiling headshot"],
        ],
        "hashtags": "#BootHop  #FineBoySzn  #JapaLife  #EarnWhileYouTravel  #NaijaAbroad",
        "cta": "Log your next trip. Let someone's parcel pay your way.",
    },

    # ── 2. Fine Girl on the Train (funny / flirty) ────────────────────────────
    {
        "name": "fine_girl_train",
        "cards": [
            {"top": "London to Manchester. 2hrs 10.",
             "main": "Train. Headphones. Vibes.",
             "sub": "Then my BootHop app buzzed.",
             "color": "#ffffff"},
            {"top": "Someone needed a small parcel carried.",
             "main": "Same route. Same train.",
             "sub": "I said yes. Extra £60. Easy.",
             "color": "#facc15"},
            {"top": "Your package traveled in style...",
             "main": "First class vibes.",
             "sub": "Well... standard class. But I looked first class.",
             "color": "#10b981"},
            {"top": "Take am easy o... I just dey joke.",
             "main": "But your parcel arrived safe.",
             "sub": "Fine girl carried it. That is a BootHop guarantee.",
             "color": "#fb923c"},
        ],
        "queries": [
            ["black woman train travel headphones window",
             "african woman commuting train stylish",
             "young black woman train portrait relaxed"],
            ["african woman phone smiling train",
             "black woman excited phone notification",
             "young nigerian woman phone happy train"],
            ["african woman train laughing confident",
             "black woman traveling confident stylish portrait",
             "african woman commuter fashion"],
            ["african woman smiling waving confident",
             "black woman laughing beautiful portrait",
             "nigerian woman fun playful portrait"],
        ],
        "hashtags": "#BootHop  #TrainLife  #FinestCarrier  #UKNaija  #EarnOnTheGo",
        "cta": "London Manchester Bristol Newcastle. Any route. Book a BootHop traveller.",
    },

    # ── 3. The Nurse ──────────────────────────────────────────────────────────
    {
        "name": "the_nurse",
        "cards": [
            {"top": "Night shift. 12 hours. Done.",
             "main": "Flying Lagos for leave.",
             "sub": "Exhausted. Grateful. Going home.",
             "color": "#ffffff"},
            {"top": "BootHop matched me with a sender.",
             "main": "Medication. For someone's mum.",
             "sub": "Same route. I said yes immediately.",
             "color": "#facc15"},
            {"top": "I am a nurse.",
             "main": "I carried it like a nurse.",
             "sub": "Safe. Careful. On time. Delivered personally.",
             "color": "#10b981"},
            {"top": "That is BootHop.",
             "main": "Real people. Real care.",
             "sub": "Verified travellers you can trust with what matters.",
             "color": "#fb923c"},
        ],
        "queries": [
            ["african nurse face scrubs close up portrait",
             "black female nurse face smiling headshot",
             "african woman face healthcare worker portrait close up"],
            ["african woman face airport smiling close up portrait",
             "black woman face travel excited headshot",
             "african woman face confident departure close up"],
            ["african nurse face caring confident portrait",
             "black woman face nurse professional headshot",
             "african woman face proud healthcare close up"],
            ["african woman face confident beautiful portrait headshot",
             "black woman face nurse smiling close up",
             "nigerian woman face proud beautiful headshot"],
        ],
        "hashtags": "#BootHop  #TrustedTravellers  #NurseLife  #NaijaNurse  #CarryWithCare",
        "cta": "Verified. Background checked. Trusted to carry what matters.",
    },

    # ── 4. Naija Man in Agbada (going home proud) ─────────────────────────────
    {
        "name": "agbada_man",
        "cards": [
            {"top": "10 years in London.",
             "main": "Going home.",
             "sub": "Full agbada. No apologies.",
             "color": "#ffffff"},
            {"top": "My sister needed fabric from Brixton.",
             "main": "My cousin needed medicine.",
             "sub": "My mum wanted Cadbury chocolate. UK specific.",
             "color": "#facc15"},
            {"top": "One BootHop booking...",
             "main": "Three deliveries.",
             "sub": "£200 earned. Agbada looking even fresher now.",
             "color": "#10b981"},
            {"top": "Abroad man goes home in style.",
             "main": "And gets paid for it.",
             "sub": "That is the BootHop way. Log your trip today.",
             "color": "#fb923c"},
        ],
        "queries": [
            ["african man face traditional clothes portrait close up",
             "nigerian man face agbada proud smiling headshot",
             "black man face traditional fashion confident close up"],
            ["african man face smiling happy excited portrait",
             "black man face travel confident close up",
             "nigerian man face airport happy headshot"],
            ["african man face proud successful smiling close up",
             "black man face confident happy achievement portrait",
             "nigerian man face joy triumph headshot"],
            ["african man face proud homecoming smiling portrait",
             "black man face traditional fashion confident headshot",
             "nigerian man face beautiful smile close up"],
        ],
        "hashtags": "#BootHop  #AgbadaFlights  #NaijaInLondon  #EarnWhileYouTravel  #DiasporaVibes",
        "cta": "Going Nigeria? Log your trip on BootHop. Earn on the way.",
    },

    # ── 5. The Student ────────────────────────────────────────────────────────
    {
        "name": "the_student",
        "cards": [
            {"top": "Final year. No job yet.",
             "main": "Going back to uni.",
             "sub": "Train from London. Loan already finished.",
             "color": "#ffffff"},
            {"top": "Found BootHop by accident.",
             "main": "Someone needed a parcel to Manchester.",
             "sub": "Same route as my uni. Same time I was leaving.",
             "color": "#facc15"},
            {"top": "Easiest money I ever made.",
             "main": "£75 for the journey.",
             "sub": "Paid my week's food. Plus a Nando's.",
             "color": "#10b981"},
            {"top": "Abeg, who wan make side income?",
             "main": "Log your next trip.",
             "sub": "BootHop matches you with senders on your route.",
             "color": "#fb923c"},
        ],
        "queries": [
            ["african student face stressed thinking close up",
             "black woman face student portrait headshot",
             "young african woman face university tired smiling"],
            ["african student face excited phone close up",
             "young black man face phone discovery portrait",
             "african student face happy notification close up"],
            ["african student face happy success confident portrait",
             "young black woman face celebrating close up headshot",
             "nigerian student face achievement happy portrait"],
            ["young african man face confident smiling close up",
             "black student face joyful excited headshot",
             "african youth face happy outdoor portrait"],
        ],
        "hashtags": "#BootHop  #StudentLife  #SideIncome  #UniLife  #NaijaStudent",
        "cta": "Students: turn your commute into income. BootHop.com",
    },

    # ── 6. Manchester Night Train (domestic UK, funny) ─────────────────────────
    {
        "name": "manchester_night",
        "cards": [
            {"top": "11:45pm. Manchester Piccadilly.",
             "main": "London on the last train.",
             "sub": "Tired. Hungry. And apparently... a delivery agent.",
             "color": "#ffffff"},
            {"top": "BootHop notification at 11pm:",
             "main": "Abeg who wan carry box?",
             "sub": "Letter size. Same train. £40 quick.",
             "color": "#facc15"},
            {"top": "Guy at Euston met me at 1:30am.",
             "main": "Box delivered. Money in.",
             "sub": "I still had enough energy for a kebab.",
             "color": "#10b981"},
            {"top": "Any UK route. Any time.",
             "main": "Log your trip.",
             "sub": "Someone somewhere needs what you can carry.",
             "color": "#fb923c"},
        ],
        "queries": [
            ["african man face tired night portrait close up",
             "black man face commuting train window headshot",
             "young african man face night sleepy close up"],
            ["african man face phone night smiling close up",
             "black man face excited phone notification portrait",
             "young african man face late night happy headshot"],
            ["african man face handshake confident smiling portrait",
             "black man face success happy night close up",
             "young african man face satisfied smiling headshot"],
            ["african man face confident night city portrait",
             "black man face uk city smiling close up",
             "young african man face proud urban headshot"],
        ],
        "hashtags": "#BootHop  #ManchesterToLondon  #UKDelivery  #NightTrain  #EarnOnTheGo",
        "cta": "Any UK route. Real people already going your way. BootHop.",
    },

    # ── 7. Newcastle to Bristol (meet a fine person) ──────────────────────────
    {
        "name": "newcastle_bristol",
        "cards": [
            {"top": "Newcastle to Bristol.",
             "main": "Long journey.",
             "sub": "4 hours 20. But this one was different.",
             "color": "#ffffff"},
            {"top": "She posted on BootHop:",
             "main": "I be fine girl.",
             "sub": "Wey fit carry your luggage. Newcastle to Bristol.",
             "color": "#facc15"},
            {"top": "Your package got delivered in style.",
             "main": "She arrived looking amazing.",
             "sub": "Package safe. Her day sorted. Everyone satisfied.",
             "color": "#10b981"},
            {"top": "U meet fine girl...",
             "main": "Your package get delivered.",
             "sub": "Abeg, take am easy. I just dey joke. But BootHop is real.",
             "color": "#fb923c"},
        ],
        "queries": [
            ["african woman face train journey portrait close up",
             "black woman face window travel headshot",
             "young african woman face uk travel close up"],
            ["african woman face confident beautiful close up",
             "black woman face stylish portrait uk headshot",
             "nigerian woman face beautiful uk city close up"],
            ["african woman face arriving happy smiling close up",
             "black woman face success smiling portrait",
             "young african woman face happy uk city headshot"],
            ["african woman face laughing playful close up",
             "black woman face beautiful wink portrait",
             "nigerian woman face fun playful headshot"],
        ],
        "hashtags": "#BootHop  #NewcastleBristol  #FinestCarrier  #UKDelivery  #NaijaUK",
        "cta": "Any UK city. Your BootHop traveller might already be heading there.",
    },

    # ── 8. The Fashion Slay Queen ─────────────────────────────────────────────
    {
        "name": "slay_queen",
        "cards": [
            {"top": "Heathrow Terminal 5.",
             "main": "She was flying Lagos.",
             "sub": "Three suitcases. Full beat. Smelling like money.",
             "color": "#ffffff"},
            {"top": "But she also had space for one parcel.",
             "main": "Booked on BootHop.",
             "sub": "Someone needed Fenty Beauty. Specific order. Lagos.",
             "color": "#facc15"},
            {"top": "Slay queen... logistics queen.",
             "main": "That is the energy.",
             "sub": "Delivered the parcel. Got paid. Still arrived flawless.",
             "color": "#10b981"},
            {"top": "Your package does not need a courier.",
             "main": "It needs a traveller.",
             "sub": "Verified. Insured. BootHop certified.",
             "color": "#fb923c"},
        ],
        "queries": [
            ["african woman face airport glamorous close up portrait",
             "black woman face luxury fashion headshot",
             "nigerian woman face airport departure smiling close up"],
            ["african woman face glamorous confident portrait close up",
             "black woman face fashion smiling headshot",
             "african woman face luxury beautiful close up"],
            ["african woman face arrival confident beautiful close up",
             "black woman face successful glamorous headshot",
             "nigerian woman face luxury lifestyle portrait"],
            ["african woman face beautiful smiling confident close up",
             "black woman face fashion editorial headshot",
             "nigerian woman face stunning portrait close up"],
        ],
        "hashtags": "#BootHop  #SlayAndDeliver  #HeathrowVibes  #LagosGirl  #EarnWhileYouTravel",
        "cta": "Travelling Lagos? Space in your bag = money in your account.",
    },

    # ── 9. The Tough Guy Who Cares ────────────────────────────────────────────
    {
        "name": "tough_guy",
        "cards": [
            {"top": "I no be courier.",
             "main": "Make that clear.",
             "sub": "I am just a man going Lagos to see his mum.",
             "color": "#ffffff"},
            {"top": "But when I saw the BootHop request...",
             "main": "Baby food. From London.",
             "sub": "Someone's new baby needed formula. Same route as me.",
             "color": "#facc15"},
            {"top": "I am not a courier.",
             "main": "But I am a father.",
             "sub": "I carried it. Baby formula landed same day.",
             "color": "#10b981"},
            {"top": "That is BootHop.",
             "main": "People helping people.",
             "sub": "Real travellers. Real deliveries. Real love.",
             "color": "#fb923c"},
        ],
        "queries": [
            ["african man face serious confident close up portrait",
             "black man face strong determined headshot",
             "nigerian man face tough confident close up"],
            ["african man face phone thoughtful close up",
             "black man face reading concerned portrait",
             "nigerian man face decision serious headshot"],
            ["african man face gentle kind smiling close up",
             "black man face caring soft expression portrait",
             "nigerian man face kind warm headshot"],
            ["african man face proud warm smile close up",
             "black man face satisfied content portrait",
             "nigerian man face proud gentle headshot"],
        ],
        "hashtags": "#BootHop  #PeopleHelpingPeople  #RealDelivery  #NaijaLove  #TrustedTraveller",
        "cta": "Not a courier. Just someone already going your way. BootHop.",
    },

    # ── 10. Mum at the Airport (emotional) ───────────────────────────────────
    {
        "name": "mum_airport",
        "cards": [
            {"top": "She flew in from Lagos.",
             "main": "For her daughter's graduation.",
             "sub": "First time in the UK. Nervous. Excited. Everything.",
             "color": "#ffffff"},
            {"top": "Her daughter had sent gifts back.",
             "main": "Via BootHop.",
             "sub": "A verified traveller carried them home last week.",
             "color": "#facc15"},
            {"top": "At arrivals she saw the gifts had arrived.",
             "main": "Before she did.",
             "sub": "Her sister sent a photo. She cried on the plane.",
             "color": "#10b981"},
            {"top": "This is what BootHop is.",
             "main": "Love. Delivered.",
             "sub": "By real people. On real routes. Same day.",
             "color": "#fb923c"},
        ],
        "queries": [
            ["african woman face emotional arriving close up portrait",
             "african mother face airport excited headshot",
             "nigerian woman face emotional happy arrival close up"],
            ["african woman face reunion emotional crying close up",
             "black woman face happy tears portrait headshot",
             "african woman face family love emotional close up"],
            ["african woman face crying joyful close up portrait",
             "black woman face happy tearful headshot",
             "nigerian woman face emotional phone happy close up"],
            ["african woman face love proud beautiful portrait",
             "black woman face warm family proud headshot",
             "nigerian woman face emotional beautiful close up"],
        ],
        "hashtags": "#BootHop  #LoveDelivered  #DiasporaMagic  #NaijaFamily  #MumFlew",
        "cta": "Send love home. A verified traveller is already going that way.",
    },
]


# ── Select today's story ──────────────────────────────────────────────────────

def pick_story(override: int | None = None) -> dict:
    if override is not None:
        idx = (override - 1) % len(STORIES)
    else:
        idx = _doy % len(STORIES)
    return STORIES[idx]


# ── Music ─────────────────────────────────────────────────────────────────────

def get_music(story_name: str) -> Path | None:
    audio_file = TEST / f"story_{story_name}_audio.mp3"
    cached     = TEST / f"story_music_{_doy % 10}_{ARTIST_NAME.replace(' ', '_')}.mp3"

    if cached.exists() and cached.stat().st_size > 80_000:
        print(f"  [Music] Cached: {cached.name}")
        import shutil; shutil.copy(cached, audio_file)
        return audio_file

    print(f"  [Music] Searching: {ARTIST_SEARCH}")
    try:
        r = subprocess.run(
            ["yt-dlp", "--no-playlist", "--get-id", "--no-warnings",
             "--match-filter", "duration < 600",
             f"ytsearch1:{ARTIST_SEARCH}"],
            capture_output=True, text=True, timeout=30,
        )
        vid_id = r.stdout.strip().splitlines()[0].strip() if r.stdout.strip() else ""
    except Exception as e:
        print(f"  [Music] Error: {e}"); return _fallback_music()

    if not vid_id:
        return _fallback_music()

    raw = str(TEST / f"story_raw_{_doy % 10}")
    try:
        subprocess.run(
            ["yt-dlp", "--no-playlist", "-f", "bestaudio", "--no-warnings",
             "-o", f"{raw}.%(ext)s",
             f"https://www.youtube.com/watch?v={vid_id}"],
            capture_output=True, text=True, timeout=120,
        )
    except Exception as e:
        print(f"  [Music] Download error: {e}"); return _fallback_music()

    raw_file = None
    for ext in ["webm", "m4a", "opus", "ogg", "mp3", "aac"]:
        c = TEST / f"story_raw_{_doy % 10}.{ext}"
        if c.exists() and c.stat().st_size > 200_000:
            raw_file = c; break

    if not raw_file:
        return _fallback_music()

    subprocess.run(
        ["ffmpeg", "-y", "-ss", "45", "-t", str(TOTAL_DUR),
         "-i", str(raw_file), "-c:a", "libmp3lame", "-q:a", "2", str(cached)],
        capture_output=True,
    )

    if cached.exists() and cached.stat().st_size > 30_000:
        import shutil; shutil.copy(cached, audio_file)
        print(f"  [Music] Ready: {ARTIST_NAME}")
        return audio_file

    return _fallback_music()


def _fallback_music() -> Path | None:
    for folder in [BASE / "music" / "daily", BASE / "music" / "archive"]:
        if folder.exists():
            tracks = list(folder.glob("*.mp3")) + list(folder.glob("*.m4a"))
            if tracks:
                t = random.choice(tracks)
                print(f"  [Music] Fallback: {t.name}")
                return t
    return None


# ── Clip download ─────────────────────────────────────────────────────────────

def _best_portrait_url(video: dict) -> str | None:
    files = video.get("video_files", [])
    portrait = sorted(
        [f for f in files if f.get("height", 0) > f.get("width", 0)],
        key=lambda x: x.get("height", 0), reverse=True,
    )
    if not portrait:
        portrait = sorted(files, key=lambda x: x.get("height", 0), reverse=True)
    for f in portrait:
        if f.get("height", 0) >= 720:
            return f["link"]
    return portrait[0]["link"] if portrait else None


def _dl(url: str, dest: Path) -> bool:
    try:
        r = requests.get(url, stream=True, timeout=60)
        with open(dest, "wb") as fh:
            for chunk in r.iter_content(65536):
                fh.write(chunk)
        return dest.stat().st_size > 50_000
    except Exception as e:
        dest.unlink(missing_ok=True); print(f"    DL error: {e}"); return False


def _pexels(query, api_key, label, tried, blocked, story_name, card_idx):
    print(f"  [{label}] {query}")
    try:
        resp = requests.get(
            "https://api.pexels.com/videos/search",
            headers={"Authorization": api_key},
            params={"query": query, "per_page": 8, "orientation": "portrait"},
            timeout=15,
        )
        videos = resp.json().get("videos", [])
    except Exception as e:
        print(f"    {e}"); return None
    for vid in videos:
        vid_id = vid["id"]
        if vid_id in tried or int(vid_id) in blocked:
            continue
        tried.add(vid_id)
        url = _best_portrait_url(vid)
        if not url:
            continue
        dest = TEST / f"ds_{story_name}_c{card_idx}_{vid_id}.mp4"
        if dest.exists() and dest.stat().st_size > 50_000:
            print(f"    Cached -> {dest.name}"); return dest
        if _dl(url, dest):
            print(f"    Got    -> {dest.name}  ({dest.stat().st_size // 1024} KB)")
            return dest
    return None


def _pixabay(query, tried, blocked, story_name, card_idx):
    print(f"  [Pixabay] {query}")
    try:
        resp = requests.get(
            "https://pixabay.com/api/videos/",
            params={"key": PIXABAY_API_KEY, "q": query,
                    "per_page": 6, "video_type": "film", "orientation": "vertical"},
            timeout=15,
        )
        hits = resp.json().get("hits", [])
    except Exception as e:
        print(f"    {e}"); return None
    for hit in hits:
        vid_id = hit["id"]
        if vid_id in tried or int(vid_id) in blocked:
            continue
        tried.add(vid_id)
        videos_map = hit.get("videos", {})
        url = None
        for q in ("large", "medium", "small", "tiny"):
            if videos_map.get(q, {}).get("url"):
                url = videos_map[q]["url"]; break
        if not url:
            continue
        dest = TEST / f"ds_{story_name}_c{card_idx}_pb_{vid_id}.mp4"
        if dest.exists() and dest.stat().st_size > 50_000:
            print(f"    Cached -> {dest.name}"); return dest
        if _dl(url, dest):
            print(f"    Got    -> {dest.name}  ({dest.stat().st_size // 1024} KB)")
            return dest
    return None


BROAD_FALLBACKS = [
    "african woman face beautiful confident portrait close up",
    "black man face stylish confident headshot",
    "african person face happy smiling portrait close up",
    "black woman face fashion close up portrait",
    "african man face outdoor smiling headshot",
]


def download_clips(story: dict) -> list[Path | None]:
    blocked = blocked_video_ids()
    clips = []
    for card_idx, card_queries in enumerate(story["queries"]):
        print(f"\n  [Card {card_idx + 1}] Finding clip...")
        tried: set = set()
        clip = None
        sn = story["name"]

        for q in card_queries:
            clip = _pexels(q, PEXELS_API_KEY, "Pexels-1", tried, blocked, sn, card_idx)
            if clip: break
        if not clip:
            for q in card_queries:
                clip = _pexels(q, PEXELS_API_KEY2, "Pexels-2", tried, blocked, sn, card_idx)
                if clip: break
        if not clip:
            for q in BROAD_FALLBACKS:
                clip = _pexels(q, PEXELS_API_KEY, "Fallback", tried, blocked, sn, card_idx)
                if clip: break
        if not clip:
            for q in card_queries + BROAD_FALLBACKS[:2]:
                clip = _pixabay(q, tried, blocked, sn, card_idx)
                if clip: break

        status = f"OK: {clip.name}" if clip else "WARNING: no clip"
        print(f"  [Card {card_idx + 1}] {status}")
        clips.append(clip)
    return clips


# ── Render ────────────────────────────────────────────────────────────────────

def render(story: dict, clips: list[Path | None], audio: Path | None) -> Path | None:
    available = [c for c in clips if c and c.exists()]
    if not available:
        print("  [Render] No clips — aborting"); return None

    card_clips = [c if (c and c.exists()) else random.choice(available) for c in clips]
    out_mp4 = TEST / f"daily_story_{story['name']}.mp4"

    inputs: list[str] = []
    for clip in card_clips:
        inputs += ["-i", str(clip)]

    audio_idx = None
    if audio and audio.exists():
        audio_idx = 4
        inputs += ["-i", str(audio)]

    logo_s_idx = logo_b_idx = None
    if LOGO.exists():
        _b = 4 + (1 if audio_idx is not None else 0)
        logo_s_idx, logo_b_idx = _b, _b + 1
        inputs += ["-loop", "1", "-i", str(LOGO)]
        inputs += ["-loop", "1", "-i", str(LOGO)]

    parts: list[str] = []

    # 4 cinematic portrait clips (slow Ken Burns)
    for i in range(4):
        dur = CARD_DUR
        parts.append(
            f"[{i}:v]trim=duration={dur:.1f},setpts=PTS-STARTPTS,"
            f"scale=1180:2100:force_original_aspect_ratio=increase,"
            f"crop=1080:1920,setsar=1,fps=30,"
            f"eq=saturation=1.25:brightness=0.02:contrast=1.08,"
            f"zoompan=z='min(zoom+0.0004,1.06)':d={int(dur * 30)}:s=1080x1920[seg{i}]"
        )

    concat_in = "".join(f"[seg{i}]" for i in range(4))
    parts.append(f"{concat_in}concat=n=4:v=1:a=0[story]")

    # Closing card reuses last clip (darkened)
    parts.append(
        "[3:v]trim=duration=5,setpts=PTS-STARTPTS,"
        "scale=1180:2100:force_original_aspect_ratio=increase,"
        "crop=1080:1920,setsar=1,fps=30,"
        "eq=saturation=1.0:brightness=-0.08:contrast=1.0[closing_clip]"
    )
    parts.append("[story][closing_clip]concat=n=2:v=1:a=0[base]")
    parts.append("[base]vignette=PI/5:eval=frame[vign]")
    base = "[vign]"

    if logo_s_idx is not None:
        parts.append(
            f"[{logo_s_idx}:v]scale=230:-1,format=rgba,colorchannelmixer=aa=0.90[logo_s]"
        )
        parts.append(
            f"[{logo_b_idx}:v]scale=430:-1,format=rgba,colorchannelmixer=aa=0.97[logo_b]"
        )
        parts.append(f"{base}[logo_s]overlay=(W-w)/2:70:enable='lt(t,30)'[_s1]")
        parts.append(f"[_s1][logo_b]overlay=(W-w)/2:55:enable='gte(t,30)'[with_logo]")
        base = "[with_logo]"

    draw: list[str] = []

    # Artist credit
    artist_safe = ARTIST_NAME.replace("'", "").replace("\\", "")
    draw.append(
        f"drawtext=fontfile='{FONT_BODY}':text='Music  {artist_safe}'"
        f":fontsize=24:fontcolor=white@0.50"
        f":borderw=1:bordercolor=black@0.4"
        f":x=w-text_w-18:y=h-38:enable='lt(t,30)'"
    )

    # Card number pill
    for i in range(4):
        t0, t1 = i * CARD_DUR, (i + 1) * CARD_DUR
        draw.append(
            f"drawtext=fontfile='{FONT_BOLD}':text='0{i+1} / 04'"
            f":fontsize=26:fontcolor=white@0.65"
            f":borderw=2:bordercolor=black@0.5"
            f":x=w-text_w-28:y=118:enable='between(t,{t0:.1f},{t1:.1f})'"
        )

    # Postcard text for each card
    for i, card in enumerate(story["cards"]):
        t0 = i * CARD_DUR + 0.5
        t1 = (i + 1) * CARD_DUR

        safe_top  = card["top"].replace("'", "").replace("\\", "").encode("ascii","ignore").decode()
        safe_main = card["main"].replace("'", "").replace("\\", "").encode("ascii","ignore").decode()
        safe_sub  = card["sub"].replace("'", "").replace("\\", "").encode("ascii","ignore").decode()
        color     = card["color"]

        # Top small italic line
        draw.append(
            f"drawtext=fontfile='{FONT_BODY}':text='{safe_top}'"
            f":fontsize=30:fontcolor=white@0.92"
            f":borderw=3:bordercolor=black@0.80"
            f":x=(w-text_w)/2:y=h*0.54"
            f":enable='between(t,{t0:.1f},{t1:.1f})'"
        )
        # Big main line
        draw.append(
            f"drawtext=fontfile='{FONT_BOLD}':text='{safe_main}'"
            f":fontsize=82:fontcolor={color}"
            f":borderw=7:bordercolor=black@0.95"
            f":x=(w-text_w)/2:y=h*0.61"
            f":enable='between(t,{t0:.1f},{t1:.1f})'"
        )
        # Sub line (wrap at ~36 chars)
        if len(safe_sub) > 36:
            words = safe_sub.split()
            mid = len(words) // 2
            line1 = " ".join(words[:mid])
            line2 = " ".join(words[mid:])
            draw.append(
                f"drawtext=fontfile='{FONT_BODY}':text='{line1}'"
                f":fontsize=28:fontcolor=white@0.96"
                f":borderw=3:bordercolor=black@0.85"
                f":x=(w-text_w)/2:y=h*0.79"
                f":enable='between(t,{t0:.1f},{t1:.1f})'"
            )
            draw.append(
                f"drawtext=fontfile='{FONT_BODY}':text='{line2}'"
                f":fontsize=28:fontcolor=white@0.96"
                f":borderw=3:bordercolor=black@0.85"
                f":x=(w-text_w)/2:y=h*0.84"
                f":enable='between(t,{t0:.1f},{t1:.1f})'"
            )
        else:
            draw.append(
                f"drawtext=fontfile='{FONT_BODY}':text='{safe_sub}'"
                f":fontsize=28:fontcolor=white@0.96"
                f":borderw=3:bordercolor=black@0.85"
                f":x=(w-text_w)/2:y=h*0.81"
                f":enable='between(t,{t0:.1f},{t1:.1f})'"
            )

    # Glass closing card
    draw.append(
        "drawbox=x=0:y=0:w=iw:h=ih:color=black@0.38:t=fill:enable='gte(t,30)'"
    )
    draw.append(
        f"drawtext=fontfile='{FONT_BOLD}':text='Join the Movement'"
        f":fontsize=76:fontcolor=white"
        f":borderw=5:bordercolor=black@0.95"
        f":x=(w-text_w)/2:y=400:enable='gte(t,30.5)'"
    )
    draw.append(
        f"drawtext=fontfile='{FONT_BOLD}':text='Join BootHop'"
        f":fontsize=94:fontcolor=#10b981"
        f":borderw=5:bordercolor=black@0.95"
        f":x=(w-text_w)/2:y=510:enable='gte(t,31)'"
    )

    safe_cta = story["cta"].replace("'","").replace("\\","").encode("ascii","ignore").decode()
    draw.append(
        f"drawtext=fontfile='{FONT_BODY}':text='{safe_cta}'"
        f":fontsize=30:fontcolor=#d1d5db"
        f":borderw=2:bordercolor=black@0.70"
        f":x=(w-text_w)/2:y=650:enable='gte(t,31.5)'"
    )
    draw.append(
        f"drawtext=fontfile='{FONT_BOLD}':text='>> Earn money while you travel!'"
        f":fontsize=46:fontcolor=#facc15"
        f":borderw=4:bordercolor=black@0.90"
        f":box=1:boxcolor=black@0.50:boxborderw=12"
        f":x=(w-text_w)/2:y=780:enable='gte(t,32)'"
    )
    draw.append(
        f"drawtext=fontfile='{FONT_BOLD}':text='boothop.com'"
        f":fontsize=60:fontcolor=#10b981"
        f":borderw=4:bordercolor=black@0.88"
        f":box=1:boxcolor=black@0.55:boxborderw=14"
        f":x=(w-text_w)/2:y=h-295:enable='gte(t,32.5)'"
    )
    draw.append(
        f"drawtext=fontfile='{FONT_BODY}':text='info@boothop.com'"
        f":fontsize=27:fontcolor=white@0.85"
        f":borderw=2:bordercolor=black@0.80"
        f":x=(w-text_w)/2:y=h-210:enable='gte(t,32.5)'"
    )
    draw.append(
        f"drawtext=fontfile='{FONT_BOLD}':text='WhatsApp  +44 7405 746302'"
        f":fontsize=27:fontcolor=#25D366"
        f":borderw=2:bordercolor=black@0.80"
        f":x=(w-text_w)/2:y=h-170:enable='gte(t,32.5)'"
    )

    safe_tags = story["hashtags"].replace("'","").replace("\\","")
    draw.append(
        f"drawtext=fontfile='{FONT_BODY}':text='{safe_tags}'"
        f":fontsize=21:fontcolor=white@0.58"
        f":borderw=1:bordercolor=black@0.4"
        f":x=(w-text_w)/2:y=h-38:enable='gte(t,33)'"
    )

    parts.append(f"{base}{','.join(draw)}[out]")

    cmd = ["ffmpeg", "-y"] + inputs + [
        "-filter_complex", ";".join(parts),
        "-map", "[out]",
    ]
    if audio_idx is not None:
        cmd += [
            "-map", f"{audio_idx}:a",
            "-c:a", "aac", "-b:a", "192k",
            "-af", f"atrim=0:{TOTAL_DUR},asetpts=PTS-STARTPTS,afade=t=out:st={TOTAL_DUR-2.5}:d=2.5",
        ]
    cmd += [
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-t", str(TOTAL_DUR), "-movflags", "+faststart",
        str(out_mp4),
    ]

    print("  [Render] Running ffmpeg...")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=400)

    if result.returncode == 0 and out_mp4.exists() and out_mp4.stat().st_size > 10_000:
        mb = out_mp4.stat().st_size / 1_048_576
        print(f"  [Render] Done  ->  {out_mp4.name}  ({mb:.1f} MB)")
        return out_mp4

    print(f"  [Render] ffmpeg failed (exit {result.returncode}):")
    print(result.stderr[-2000:])
    return None


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    override = None
    if "--story" in sys.argv:
        try:
            override = int(sys.argv[sys.argv.index("--story") + 1])
        except (IndexError, ValueError):
            pass

    story = pick_story(override)
    out_mp4 = TEST / f"daily_story_{story['name']}.mp4"

    print("\n" + "=" * 60)
    print(f"  BootHop Daily Story  -  {story['name'].upper().replace('_',' ')}")
    print(f"  Music: {ARTIST_NAME}  |  Day {_doy} of year")
    print("=" * 60 + "\n")

    print("[1] Music...")
    audio = get_music(story["name"])

    print("\n[2] Story clips (4 cards)...")
    clips = download_clips(story)

    print("\n[3] Rendering...")
    result = render(story, clips, audio)

    if result:
        print(f"\nDone!  ->  {result}")
        print(f"Story:     {story['name'].replace('_',' ').title()}")
        print(f"Hashtags:  {story['hashtags']}")
    else:
        print("\nRender failed.")


if __name__ == "__main__":
    main()
