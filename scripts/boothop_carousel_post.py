"""
boothop_carousel_post.py
Runs at 12:00 daily via BootHop-Afternoon task.

Renders 5 branded slides, stitches into video x2:
  - TikTok version  : daily music from music/daily/   (TikTok handles mainstream music fine)
  - Instagram version: original clip from music/clips/ (avoids IG copyright muting)
Both posted. Rotates 15 themes, no repeat within 7 days.
"""

import json, sys, time, random, io, subprocess, shutil
import requests
from datetime import datetime, timedelta
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

BASE       = Path(r"C:\Users\babso\Desktop\BootHopPipeline")
SCRIPTS    = BASE / "scripts"
HISTORY    = BASE / "carousel_history.json"
TMP_DIR    = BASE / "output" / "_carousel_tmp"
CLIPS_DIR  = BASE / "music" / "clips"
MUSIC_DIR  = BASE / "music" / "daily"

sys.path.insert(0, str(BASE))
sys.path.insert(0, str(SCRIPTS))

from config import PEXELS_API_KEY, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

SUPABASE_URL     = "https://zwgngbzbdvnrdnanjded.supabase.co"
SUPABASE_SERVICE = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inp3Z25nYnpiZHZucmRuYW5qZGVkIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NTI5NTA0NSwiZXhwIjoyMDkwODcxMDQ1fQ.jP_Ukh4Dwlxfiei5tyHblJ0psgCXntDwnnZBRQch9zw"

FONT_BOLD    = r"C:\Windows\Fonts\arialbd.ttf"
FONT_REGULAR = r"C:\Windows\Fonts\arial.ttf"
SLIDE_W, SLIDE_H = 1080, 1080

# ── Carousel library (15 themes) ──────────────────────────────────────────────

CAROUSELS = [
    {
        "id": "how_it_works",
        "caption": "There's a smarter way to send. Someone is already going your way.\n\nMatch with a verified traveller on BootHop — same-day, fraction of the cost, funds in escrow until delivery confirmed.\n\nLink in bio to book your first delivery.\n\n#BootHop #SameDayDelivery #LondonToLagos #DiasporaDelivery #PeerToPeer #VerifiedTraveller #UKNigeria",
        "slides": [
            {"text": "Sending something\nto Lagos?\nThere's a smarter way.", "query": "london heathrow airport departure lounge"},
            {"text": "Someone travelling\nyour route already\nhas luggage space.", "query": "suitcase open packing travel airport"},
            {"text": "They carry your item.\nYou pay a fraction\nof courier prices.", "query": "person smiling luggage airport departure"},
            {"text": "Secure escrow holds\nyour money until\ndelivery is confirmed.", "query": "phone payment secure app person smiling"},
            {"text": "Match with a\ntraveller today.\nLink in bio.", "query": "happy person package delivery door smiling"},
        ],
    },
    {
        "id": "vs_dhl",
        "caption": "Sending to Nigeria shouldn't cost £80+. There's a better way.\n\nBootHop connects you to verified travellers already flying your route — at a fraction of courier prices.\n\n#BootHop #DHLAlternative #CheapDelivery #LagosDelivery #UKToNigeria #DiasporaMagic",
        "slides": [
            {"text": "Sending to Nigeria\nshouldn't cost\n£80+.", "query": "frustrated person parcel expensive price"},
            {"text": "DHL: £85+\n5 days.\nNo personal touch.", "query": "courier delivery box warehouse"},
            {"text": "BootHop: fraction\nof the cost.\nVerified traveller.", "query": "smiling traveller luggage airport boarding"},
            {"text": "Real people.\nReal routes.\nReal savings.", "query": "friends laughing smiling airport"},
            {"text": "See your\nroute price now.\nLink in bio.", "query": "phone app excited person savings"},
        ],
    },
    {
        "id": "is_it_safe",
        "caption": "We know trust is everything when you're sending something important.\n\nEvery traveller on BootHop is Stripe-verified. Escrow payment. OTP + photo proof at every handoff.\n\n#BootHop #SafeDelivery #StripeVerified #EscrowPayment #TrustedDelivery",
        "slides": [
            {"text": "We get it.\nYou want to know\nyour item is safe.", "query": "person worried thinking phone"},
            {"text": "Every traveller is\nStripe-verified before\nthey can carry.", "query": "identity verification phone security"},
            {"text": "Your money sits\nin escrow — released\nonly after delivery.", "query": "secure payment banking phone"},
            {"text": "OTP + photo proof\nconfirms every\nhandoff.", "query": "smiling person package handover doorstep"},
            {"text": "Send with\nconfidence.\nLink in bio.", "query": "happy customer delivery received smiling"},
        ],
    },
    {
        "id": "who_uses",
        "caption": "Every week, thousands of people just like you use BootHop to send back home.\n\nBirthday gifts. Documents. Food. Whatever it is — if someone's flying that route, it gets there.\n\n#BootHop #DiasporaLife #SendingHome #UKNigeria #UKGhana #AfricanDiaspora",
        "slides": [
            {"text": "These are the people\nusing BootHop\nevery week.", "query": "diverse african people smiling community"},
            {"text": "Mum sending\nfoodstuffs back\nhome to Lagos.", "query": "african woman food parcel kitchen"},
            {"text": "Student sending\ndocuments to\nfamily in Accra.", "query": "student documents folder university"},
            {"text": "Business owner\nshipping samples\nto clients in Abuja.", "query": "business professional products office"},
            {"text": "Which one\nare you?\nLink in bio.", "query": "phone app smiling person booking"},
        ],
    },
    {
        "id": "earn_as_traveller",
        "caption": "You're flying to Lagos anyway — your empty luggage space is money on the table.\n\nJoin thousands of BootHop travellers earning on every trip. Verified. Automatic payout on delivery.\n\n#BootHop #EarnWhileYouTravel #TravellerEarnings #LagosFlights #SpareCapacity",
        "slides": [
            {"text": "You're flying\nto Lagos anyway.\nWhy not get paid?", "query": "plane window seat flying africa"},
            {"text": "You already have\nspare luggage\nspace.", "query": "open suitcase empty luggage travel"},
            {"text": "Match with a sender\non your route\nbefore you fly.", "query": "person excited phone airport"},
            {"text": "Carry their item.\nEarn money.\nFunds auto-released.", "query": "person counting cash happy smiling"},
            {"text": "Register as a\ntraveller today.\nLink in bio.", "query": "traveller passport boarding gate smile"},
        ],
    },
    {
        "id": "uk_nigeria_route",
        "caption": "The UK-Nigeria route moves thousands of parcels every week. BootHop is on it daily.\n\nLondon to Lagos. London to Abuja. Verified travellers. Same-day matching.\n\n#BootHop #UKNigeria #LondonLagos #LondonAbuja #NigerianDiaspora",
        "slides": [
            {"text": "The UK-Nigeria\nroute moves\nthousands weekly.", "query": "heathrow airport busy departure lounge"},
            {"text": "London to Lagos.\nLondon to Abuja.\nEvery single day.", "query": "plane taking off london airport"},
            {"text": "Hundreds of verified\ntravellers flying\nyour exact route.", "query": "airport departure board flights africa"},
            {"text": "Your parcel goes\nwith someone\nalready going there.", "query": "person parcel airport smiling"},
            {"text": "Book your\nroute now.\nLink in bio.", "query": "excited person phone flight booking"},
        ],
    },
    {
        "id": "how_escrow_works",
        "caption": "Your money is 100% protected from the moment you book to the second your item is delivered.\n\nStripe escrow means nobody gets paid until YOU confirm delivery.\n\n#BootHop #EscrowPayment #SafeDelivery #SecurePayment #StripePayments",
        "slides": [
            {"text": "Your money is safe\nfrom the moment\nyou book.", "query": "secure vault safety lock protection"},
            {"text": "You pay into\nStripe escrow —\nnot to the traveller.", "query": "stripe payment app phone secure"},
            {"text": "Traveller picks up\nyour item and\nconfirms collection.", "query": "parcel pickup handover smiling doorstep"},
            {"text": "You confirm delivery\nwith an OTP.\nFunds released.", "query": "person phone happy notification received"},
            {"text": "Zero risk.\nBook your first\ndelivery. Link in bio.", "query": "happy customer delivery phone smiling"},
        ],
    },
    {
        "id": "diaspora_life",
        "caption": "Being diaspora means always sending something back home. We built BootHop for you.\n\nWhatever it is — if someone's flying that route today, it gets there today.\n\n#BootHop #DiasporaLife #SendingHome #AfricanDiaspora #UKNigeria",
        "slides": [
            {"text": "Being diaspora means\nalways sending\nsomething back home.", "query": "african woman UK home sending package"},
            {"text": "Birthday gifts.\nMedications.\nDocuments. Food.", "query": "gift box care package wrapping family"},
            {"text": "Couriers charge more\nthan the item\nis worth.", "query": "frustrated person expensive courier"},
            {"text": "BootHop connects\nyou to someone\nalready making the trip.", "query": "traveller departure gate luggage smiling"},
            {"text": "Send home\nfor less.\nLink in bio.", "query": "family reunion happy embrace home"},
        ],
    },
    {
        "id": "speed_matters",
        "caption": "Sometimes 5 days is 4 days too late. BootHop was built for those moments.\n\nPassport stranded. Medication running out. Contract deadline. When it needs to be there today.\n\n#BootHop #SameDayDelivery #Urgent #FastDelivery #LastMinute",
        "slides": [
            {"text": "Sometimes 5 days\nis 4 days\ntoo late.", "query": "urgent stressed person phone deadline"},
            {"text": "Passport stuck\nin the wrong city.\nFlight at 6am.", "query": "passport urgent worried person airport"},
            {"text": "Traditional couriers:\n3-7 business days.\nNo exceptions.", "query": "waiting frustrated slow delivery"},
            {"text": "BootHop: match with\na traveller flying\ntoday or tomorrow.", "query": "fast airport rush departure gate"},
            {"text": "Same-day solutions\nexist.\nLink in bio.", "query": "relief happy phone solution smiling"},
        ],
    },
    {
        "id": "traveller_story",
        "caption": "She was flying to Accra with half a suitcase empty. Now that space pays for her airport coffee.\n\nBootHop travellers earn on every trip. Verified. Automatic payout on delivery.\n\n#BootHop #EarnOnYourTrip #TravellerStory #AccraFlights #PeerDelivery",
        "slides": [
            {"text": "She was flying\nto Accra.\nHer bag was half empty.", "query": "woman airport departure gate smiling"},
            {"text": "She matched with\na sender on\nBootHop at check-in.", "query": "woman phone airport excited booking"},
            {"text": "Picked up a small\npackage. Carried it\nonto the plane.", "query": "woman small parcel boarding gate"},
            {"text": "Delivered it.\nReceived her payment\nautomatically.", "query": "woman phone happy payment reward"},
            {"text": "Earn on your\nnext trip.\nLink in bio.", "query": "traveller passport boarding happy smile"},
        ],
    },
    {
        "id": "sender_story",
        "caption": "His mum needed her medication. Lagos. Same day. BootHop made it happen.\n\nWhen it matters most — we connect you to someone already going there.\n\n#BootHop #RealStory #SameDayDelivery #LagosDelivery #DiasporaFamily",
        "slides": [
            {"text": "His mum needed\nher medication.\nShe was in Lagos.", "query": "worried son phone calling family"},
            {"text": "DHL quoted £95.\n7 working days.\nToo long.", "query": "frustrated person expensive receipt"},
            {"text": "He posted on\nBootHop at 8am.\nMatched by 10am.", "query": "person relieved phone good news"},
            {"text": "Medication delivered\nthe same day\nby a verified traveller.", "query": "happy delivery door grateful smiling"},
            {"text": "Post your\nfirst delivery.\nLink in bio.", "query": "happy video call family phone"},
        ],
    },
    {
        "id": "verification_trust",
        "caption": "Every traveller on BootHop has been identity-verified by Stripe before they carry anything.\n\nGovernment ID. Face match. Liveness check. No verification — no match.\n\n#BootHop #VerifiedTraveller #StripeIdentity #SafeDelivery #TrustedNetwork",
        "slides": [
            {"text": "How do you know\nwho's carrying\nyour item?", "query": "question identity trust security"},
            {"text": "Every traveller\ncompletes Stripe\nIdentity verification.", "query": "identity verification phone selfie"},
            {"text": "Government ID.\nFace match.\nLiveness detection.", "query": "passport id document check phone"},
            {"text": "Only verified\ntravellers appear\nin your matches.", "query": "checkmark verified badge approved"},
            {"text": "Travel with\ntrust.\nLink in bio.", "query": "handshake trust smiling people"},
        ],
    },
    {
        "id": "routes_covered",
        "caption": "Wherever you're sending — we probably cover it.\n\nLondon to Lagos, Abuja, Dubai, Accra, Toronto, New York. New routes added daily.\n\n#BootHop #GlobalDelivery #PeerDelivery #InternationalShipping #DiasporaMagic",
        "slides": [
            {"text": "Wherever you're\nsending — we\nprobably cover it.", "query": "world map routes travel connections"},
            {"text": "UK to Nigeria.\nUK to Ghana.\nUK to Kenya.", "query": "africa map flight routes connections"},
            {"text": "London to Dubai.\nLondon to Toronto.\nLondon to New York.", "query": "world destinations airport international"},
            {"text": "New routes added\nas travellers\njoin the network.", "query": "growing network expanding map"},
            {"text": "Check your\nroute now.\nLink in bio.", "query": "person phone map route excited"},
        ],
    },
    {
        "id": "cost_breakdown",
        "caption": "Sending 2kg from London to Lagos shouldn't cost £85. Let's talk numbers.\n\nBootHop average: £25-£45 on the same route. That's real money back every time.\n\n#BootHop #SaveMoney #CheapDelivery #LondonLagos #AffordableShipping",
        "slides": [
            {"text": "What does it really\ncost to send\nto Lagos?", "query": "calculator money costs comparison"},
            {"text": "DHL: £85-£120\nfor 2kg.\nLondon to Lagos.", "query": "expensive courier receipt shocked"},
            {"text": "BootHop average:\n£25-£45\nfor the same route.", "query": "phone app price comparison savings"},
            {"text": "That's money back\nin your pocket\nevery single time.", "query": "happy person savings wallet smiling"},
            {"text": "Get your\nroute price.\nLink in bio.", "query": "excited person phone great deal"},
        ],
    },
    {
        "id": "how_to_post",
        "caption": "Posting a delivery on BootHop takes under 60 seconds.\n\nRoute. Item. Reward. Done. Every verified traveller on that route responds immediately.\n\n#BootHop #HowItWorks #SameDayDelivery #QuickBooking #PeerDelivery",
        "slides": [
            {"text": "Posting a delivery\ntakes under\n60 seconds.", "query": "person quickly typing phone fast"},
            {"text": "Enter your route.\nDescribe your item.\nSet your reward.", "query": "phone app form booking delivery"},
            {"text": "Every verified\ntraveller on that\nroute gets notified.", "query": "phone notification alert people"},
            {"text": "Pick your match.\nPay into escrow.\nTrack it live.", "query": "tracking delivery map real time phone"},
            {"text": "Try it now.\nLink in bio.", "query": "excited person first time phone app"},
        ],
    },
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def _log(msg):
    print(f"[{datetime.utcnow().strftime('%H:%M:%S')}] [Carousel] {msg}")


def send_telegram(msg: str):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"},
            timeout=15,
        )
    except Exception:
        pass


def load_history() -> list:
    if HISTORY.exists():
        try:
            return json.loads(HISTORY.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def save_history(history: list):
    HISTORY.write_text(json.dumps(history, indent=2), encoding="utf-8")


def pick_carousel(history: list) -> dict:
    cutoff    = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")
    recent    = {h["id"] for h in history if h["date"] >= cutoff}
    available = [c for c in CAROUSELS if c["id"] not in recent]
    if not available:
        available = CAROUSELS
    return random.choice(available)


# ── Image fetching ────────────────────────────────────────────────────────────

FALLBACKS = [
    "https://images.pexels.com/photos/3769021/pexels-photo-3769021.jpeg",
    "https://images.pexels.com/photos/2007401/pexels-photo-2007401.jpeg",
    "https://images.pexels.com/photos/1371360/pexels-photo-1371360.jpeg",
    "https://images.pexels.com/photos/1056553/pexels-photo-1056553.jpeg",
    "https://images.pexels.com/photos/3943726/pexels-photo-3943726.jpeg",
]


def fetch_image(query: str, index: int) -> Image.Image:
    url = None
    if PEXELS_API_KEY:
        # Try query, then simplified fallback query
        for attempt_query in [query, query.split()[0] + " travel"]:
            try:
                r = requests.get(
                    "https://api.pexels.com/v1/search",
                    params={"query": attempt_query, "per_page": 10, "orientation": "square", "size": "large"},
                    headers={"Authorization": PEXELS_API_KEY},
                    timeout=15,
                )
                photos = r.json().get("photos", [])
                if photos:
                    photo = photos[random.randint(0, min(len(photos) - 1, 4))]
                    url   = photo["src"].get("large2x") or photo["src"].get("large")
                    break
            except Exception:
                pass
    if not url:
        url = FALLBACKS[index % len(FALLBACKS)]
    try:
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        img  = Image.open(io.BytesIO(resp.content)).convert("RGB")
        w, h = img.size
        s    = min(w, h)
        img  = img.crop(((w - s) // 2, (h - s) // 2, (w + s) // 2, (h + s) // 2))
        return img.resize((SLIDE_W, SLIDE_H), Image.LANCZOS)
    except Exception:
        bg = Image.new("RGB", (SLIDE_W, SLIDE_H), (10, 25, 60))
        return bg


# ── Slide rendering ───────────────────────────────────────────────────────────

def render_slide(text: str, bg_img: Image.Image, slide_num: int, total: int) -> Image.Image:
    img  = bg_img.copy()
    draw = ImageDraw.Draw(img, "RGBA")

    # Dark overlay
    overlay_alpha = 175 if slide_num in (1, total) else 150
    draw.rectangle([(0, 0), (SLIDE_W, SLIDE_H)], fill=(0, 0, 0, overlay_alpha))

    # Bottom gradient for branding strip
    for i in range(110):
        a = int(210 * (i / 110))
        draw.rectangle([(0, SLIDE_H - 110 + i), (SLIDE_W, SLIDE_H - 109 + i)], fill=(0, 0, 0, a))

    # BootHop wordmark — top left
    try:
        font_brand = ImageFont.truetype(FONT_BOLD, 30)
    except Exception:
        font_brand = ImageFont.load_default()
    draw.text((34, 34), "BootHop", font=font_brand, fill=(37, 99, 235, 235))

    # Slide progress dots — top right
    dot_r, spacing = 5, 20
    dot_x = SLIDE_W - 34 - total * spacing
    dot_y = 48
    for i in range(total):
        colour = (255, 255, 255, 235) if i == slide_num - 1 else (255, 255, 255, 75)
        draw.ellipse([(dot_x + i * spacing, dot_y - dot_r), (dot_x + i * spacing + dot_r * 2, dot_y + dot_r)], fill=colour)

    # Main text — centred
    lines    = text.strip().split("\n")
    max_len  = max(len(l) for l in lines)
    size     = 84 if max_len <= 16 else 70 if max_len <= 22 else 58
    try:
        font_main = ImageFont.truetype(FONT_BOLD, size)
    except Exception:
        font_main = ImageFont.load_default()

    line_h      = int(size * 1.30)
    total_text_h = len(lines) * line_h
    y           = (SLIDE_H - total_text_h) // 2 - 16

    for line in lines:
        bbox   = draw.textbbox((0, 0), line, font=font_main)
        text_w = bbox[2] - bbox[0]
        x      = (SLIDE_W - text_w) // 2
        # Drop shadow
        draw.text((x + 3, y + 3), line, font=font_main, fill=(0, 0, 0, 180))
        # White text
        draw.text((x, y), line, font=font_main, fill=(255, 255, 255, 255))
        y += line_h

    # URL — bottom centre
    try:
        font_url = ImageFont.truetype(FONT_REGULAR, 22)
    except Exception:
        font_url = ImageFont.load_default()
    url_text = "boothop.com"
    bbox     = draw.textbbox((0, 0), url_text, font=font_url)
    draw.text(((SLIDE_W - (bbox[2] - bbox[0])) // 2, SLIDE_H - 44), url_text, font=font_url, fill=(255, 255, 255, 115))

    return img.convert("RGB")


# ── Music pickers ─────────────────────────────────────────────────────────────

def pick_tiktok_music() -> Path | None:
    """Daily tracks for TikTok — mainstream music, TikTok handles licensing."""
    tracks = list(MUSIC_DIR.glob("track_*.mp3"))
    if not tracks:
        tracks = list((BASE / "music").rglob("*.mp3"))
    return random.choice(tracks) if tracks else None


def pick_ig_music() -> Path | None:
    """Original clips only for Instagram — zero copyright muting risk."""
    clips = list(CLIPS_DIR.glob("boothop_clip_*.mp3"))
    return random.choice(clips) if clips else None


# ── Video builder ─────────────────────────────────────────────────────────────

def build_video(slide_paths: list[Path], music: Path | None, output: Path) -> bool:
    seconds_per_slide = 4
    inputs = []
    for s in slide_paths:
        inputs += ["-loop", "1", "-t", str(seconds_per_slide), "-i", str(s)]

    filter_complex = (
        "".join(f"[{i}:v]" for i in range(len(slide_paths)))
        + f"concat=n={len(slide_paths)}:v=1:a=0,format=yuv420p[outv]"
    )
    cmd = ["ffmpeg", "-y"] + inputs
    if music:
        cmd += ["-i", str(music)]
        cmd += [
            "-filter_complex", filter_complex,
            "-map", "[outv]", "-map", f"{len(slide_paths)}:a",
            "-shortest",
            "-c:v", "libx264", "-preset", "fast", "-crf", "22",
            "-c:a", "aac", "-b:a", "128k", "-r", "30",
            str(output),
        ]
    else:
        cmd += [
            "-filter_complex", filter_complex,
            "-map", "[outv]",
            "-c:v", "libx264", "-preset", "fast", "-crf", "22",
            "-r", "30", str(output),
        ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        _log(f"FFmpeg error: {result.stderr[-300:]}")
        return False
    return True


# ── Supabase upload ───────────────────────────────────────────────────────────

def upload_to_supabase(file_path: Path, content_type: str = "image/jpeg") -> str | None:
    bucket = "carousel-images"
    key    = f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{file_path.name}"
    url    = f"{SUPABASE_URL}/storage/v1/object/{bucket}/{key}"
    headers = {
        "Authorization": f"Bearer {SUPABASE_SERVICE}",
        "apikey":        SUPABASE_SERVICE,
        "Content-Type":  content_type,
        "Cache-Control": "3600",
    }
    try:
        with open(file_path, "rb") as f:
            r = requests.post(url, headers=headers, data=f, timeout=120)
        if r.status_code in (200, 201):
            return f"{SUPABASE_URL}/storage/v1/object/public/{bucket}/{key}"
        _log(f"Upload error: {r.status_code} {r.text[:150]}")
        return None
    except Exception as e:
        _log(f"Upload failed: {e}")
        return None


# ── TikTok — send to Telegram for manual posting ─────────────────────────────

def send_tiktok_to_telegram(video_path: Path, caption: str):
    """Upload video to Telegram so it can be manually posted to TikTok."""
    try:
        with open(video_path, "rb") as f:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendVideo",
                data={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "caption": f"TikTok — post manually\n\n{caption[:900]}",
                },
                files={"video": (video_path.name, f, "video/mp4")},
                timeout=120,
            )
        _log("TikTok video sent to Telegram for manual posting")
    except Exception as e:
        _log(f"Telegram video send failed: {e}")


# ── Instagram Reel posting ────────────────────────────────────────────────────

def post_ig_reel(video_url: str, caption: str) -> str | None:
    token, user_id = _ig_creds()
    if not token or not user_id:
        _log("Instagram credentials missing")
        return None
    base = f"https://graph.instagram.com/v21.0/{user_id}"

    r = requests.post(f"{base}/media", data={
        "media_type": "REELS", "video_url": video_url,
        "caption": caption[:2200], "share_to_feed": "true",
        "access_token": token,
    }, timeout=30)
    data = r.json()
    if "error" in data:
        _log(f"Reel container error: {data['error'].get('message','')}")
        return None
    container_id = data["id"]
    _log(f"Reel container: {container_id} — processing...")

    for _ in range(18):
        time.sleep(10)
        s = requests.get(
            f"https://graph.instagram.com/v21.0/{container_id}",
            params={"fields": "status_code", "access_token": token}, timeout=15,
        ).json()
        status = s.get("status_code", "")
        _log(f"  Status: {status}")
        if status == "FINISHED":
            break
        if status == "ERROR":
            _log(f"  Processing error: {s}")
            return None

    r = requests.post(f"{base}/media_publish", data={
        "creation_id": container_id, "access_token": token,
    }, timeout=30)
    data = r.json()
    if "error" in data:
        _log(f"Publish error: {data['error']}")
        return None
    return data.get("id")


# ── Instagram carousel posting ────────────────────────────────────────────────

def _ig_creds():
    p = SCRIPTS / "social_credentials.json"
    try:
        d  = json.loads(p.read_text(encoding="utf-8"))
        ig = d.get("instagram", {})
        return ig.get("access_token", ""), ig.get("ig_user_id", "")
    except Exception:
        return "", ""


def post_carousel(image_urls: list[str], caption: str) -> str | None:
    token, user_id = _ig_creds()
    if not token or not user_id:
        _log("Instagram credentials missing")
        return None

    base = f"https://graph.instagram.com/v21.0/{user_id}"

    # Create one container per image
    container_ids = []
    for i, img_url in enumerate(image_urls):
        r = requests.post(f"{base}/media", data={
            "image_url":        img_url,
            "is_carousel_item": "true",
            "access_token":     token,
        }, timeout=30)
        data = r.json()
        if "error" in data:
            _log(f"Slide {i+1} container error: {data['error'].get('message','')}")
            continue
        container_ids.append(data["id"])
        _log(f"Slide {i+1}/{len(image_urls)} container: {data['id']}")
        time.sleep(0.5)

    if len(container_ids) < 2:
        _log(f"Only {len(container_ids)} containers — aborting")
        return None

    # Carousel container
    r = requests.post(f"{base}/media", data={
        "media_type":   "CAROUSEL",
        "caption":      caption[:2200],
        "children":     ",".join(container_ids),
        "access_token": token,
    }, timeout=30)
    data = r.json()
    if "error" in data:
        _log(f"Carousel container error: {data['error']}")
        return None
    carousel_id = data["id"]
    _log(f"Carousel container: {carousel_id}")

    # Publish
    r = requests.post(f"{base}/media_publish", data={
        "creation_id": carousel_id,
        "access_token": token,
    }, timeout=30)
    data = r.json()
    if "error" in data:
        _log(f"Publish error: {data['error']}")
        return None
    return data.get("id")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    _log("=== BootHop Carousel Post (12:00) ===")

    TMP_DIR.mkdir(parents=True, exist_ok=True)
    for f in TMP_DIR.glob("*"):
        try: f.unlink()
        except Exception: pass

    history  = load_history()
    carousel = pick_carousel(history)
    _log(f"Theme: {carousel['id']}")

    # ── Render slides ─────────────────────────────────────────────────────────
    slide_paths = []
    for i, slide in enumerate(carousel["slides"], 1):
        _log(f"Rendering slide {i}/{len(carousel['slides'])}")
        bg  = fetch_image(slide["query"], i - 1)
        img = render_slide(slide["text"], bg, i, len(carousel["slides"]))
        out = TMP_DIR / f"slide_{i:02d}.jpg"
        img.save(out, "JPEG", quality=92)
        slide_paths.append(out)

    # ── TikTok — video with daily music ──────────────────────────────────────
    tt_music = pick_tiktok_music()
    tt_video = TMP_DIR / f"carousel_tiktok_{carousel['id']}.mp4"
    _log(f"Building TikTok video (music: {tt_music.name if tt_music else 'none'})")
    tt_ok = build_video(slide_paths, tt_music, tt_video)

    if tt_ok:
        tt_caption = (
            f"{carousel['slides'][0]['text'].replace(chr(10), ' ')}\n\n"
            f"BootHop — same-day delivery via verified travellers.\nboothop.com\n\n"
            f"#BootHop #SameDayDelivery #DiasporaMagic #LondonToLagos #VerifiedTraveller"
        )
        send_tiktok_to_telegram(tt_video, tt_caption)
    else:
        _log("TikTok video build failed")

    # ── Instagram — Reel with original music (no muting risk) ────────────────
    ig_music = pick_ig_music()
    ig_video = TMP_DIR / f"carousel_ig_{carousel['id']}.mp4"
    _log(f"Building Instagram Reel (music: {ig_music.name if ig_music else 'none'})")
    ig_ok = build_video(slide_paths, ig_music, ig_video)

    ig_id = None
    if ig_ok:
        video_url = upload_to_supabase(ig_video, "video/mp4")
        if video_url:
            ig_id = post_ig_reel(video_url, carousel["caption"])
            _log(f"Instagram Reel: {'posted ' + ig_id if ig_id else 'failed'}")
        else:
            _log("Instagram video upload failed")
    else:
        _log("Instagram video build failed")

    # ── Summary ───────────────────────────────────────────────────────────────
    if ig_id:
        send_telegram(
            f"Carousel posted (12:00)\n"
            f"Theme: {carousel['id']}\n"
            f"Instagram Reel: {ig_id}\n"
            f"TikTok: video sent above — post manually"
        )
        history.append({"id": carousel["id"], "date": datetime.utcnow().strftime("%Y-%m-%d")})
        save_history(history)
    elif tt_ok:
        send_telegram(f"Instagram Reel failed — {carousel['id']}\nTikTok video sent above")
    else:
        send_telegram(f"Carousel failed — {carousel['id']}")

    shutil.rmtree(TMP_DIR, ignore_errors=True)
    _log("Done.")


if __name__ == "__main__":
    main()
