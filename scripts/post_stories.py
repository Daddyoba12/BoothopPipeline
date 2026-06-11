"""
post_stories.py
Posts daily Instagram Stories at 1pm and 8:30pm.

Content is driven by:
  - Current 4-week theme (Problem Awareness / Solution / Trust / Vision)
  - Slot: 'afternoon' (1pm) = stat/fact card, 'evening' (8:30pm) = engagement question

Generates a 1080x1920 branded story card.
  - MP4 video (15s) with background music if a track is found in music/
  - Falls back to JPEG if no music available
Posts to Instagram Stories via Graph API.
Reports result to Telegram.

Usage:
  python post_stories.py --slot afternoon
  python post_stories.py --slot evening
"""

import argparse, json, random, subprocess, sys, time, requests
from datetime import datetime
from pathlib import Path

BASE = Path(r"C:\Users\babso\Desktop\BootHopPipeline")
sys.path.insert(0, str(BASE))

from config import (IG_ACCESS_TOKEN, IG_USER_ID,
                    TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, DATA)

TEMP   = BASE / "temp"
ASSETS = BASE / "assets"
TEMP.mkdir(exist_ok=True)

# ── Story content per theme × slot ────────────────────────────────────────────
STORY_CONTENT = {
    0: {  # Problem Awareness
        "afternoon": {
            "stat": [
                "Urgent parcels miss their window every single day.",
                "Traditional couriers take 2-3 days. BootHop delivers same day.",
                "Same-day delivery is broken. We built the fix.",
            ],
            "lines": ["The problem is real.", "Urgent delivery is still failing businesses."],
            "cta":   "There is a smarter way -> boothop.com",
        },
        "evening": {
            "question": [
                "Has an urgent delivery ever failed your business?",
                "How much has a missed delivery cost you this year?",
                "What is the most frustrating delivery experience you have had?",
            ],
            "lines": ["We want to hear your story.", "Drop it in the comments."],
            "cta":   "Tell us below",
        },
    },
    1: {  # Solution & Product
        "afternoon": {
            "stat": [
                "A verified operator is already flying your route right now.",
                "BootHop matches your parcel to a carrier in minutes - not days.",
                "Post. Match. Deliver. Same day.",
            ],
            "lines": ["Here is how BootHop works.", "Smarter. Faster. Operator-powered."],
            "cta":   "See how -> boothop.com",
        },
        "evening": {
            "question": [
                "Would you trust a verified operator to carry your business parcel?",
                "How much would you pay for genuine same-day B2B delivery?",
                "What would same-day delivery change for your operations?",
            ],
            "lines": ["We are building this for you.", "Let us know."],
            "cta":   "Comment below",
        },
    },
    2: {  # Trust & Credibility
        "afternoon": {
            "stat": [
                "Every BootHop carrier is identity-verified.",
                "Stripe escrow holds payment until safe delivery is confirmed.",
                "Verified identity. Confirmed route. Secure handoff.",
            ],
            "lines": ["Trust is our foundation.", "Verified operators. Secure transactions."],
            "cta":   "Learn more -> boothop.com",
        },
        "evening": {
            "question": [
                "What makes you trust a delivery service with something urgent?",
                "Who would you trust to carry something valuable for your business?",
                "Identity verification or just a tracking number - which matters more?",
            ],
            "lines": ["Trust matters in logistics.", "Your answer shapes what we build."],
            "cta":   "Share below",
        },
    },
    3: {  # Vision & CTA
        "afternoon": {
            "stat": [
                "London to Lagos. Same day. Verified operator.",
                "Frankfurt to Abuja. One trusted carrier. Zero delays.",
                "The world is already moving. BootHop coordinates it.",
            ],
            "lines": ["Global movement. Local trust.", "BootHop is live now."],
            "cta":   "Join now -> boothop.com",
        },
        "evening": {
            "question": [
                "Ready to ship? Verified operators are live on BootHop.",
                "Know a frequent traveller who could earn carrying B2B parcels?",
                "Tag a business that ships cross-border regularly.",
            ],
            "lines": ["Join the movement.", "Tag them below."],
            "cta":   "boothop.com",
        },
    },
}


def _get_theme_index():
    week_num = datetime.now().isocalendar()[1]
    return (week_num - 1) % 4


def _find_music_file():
    """Return a random MP3 from the pipeline's music library, or None."""
    for folder in ["daily", "archive"]:
        d = BASE / "music" / folder
        if d.exists():
            files = (list(d.glob("*.mp3")) + list(d.glob("*.m4a")) +
                     list(d.glob("*.wav")) + list(d.glob("*.aac")))
            if files:
                return random.choice(files)
    return None


def _build_story(slot, theme_idx, out_base):
    """
    Build a 1080x1920 branded story card.
    Returns (out_path, success, headline).
    Outputs MP4 (15s) with background music if a track is found, else JPEG.
    """
    logo    = ASSETS / "mainlogo.png"
    content = STORY_CONTENT[theme_idx][slot]

    if slot == "afternoon":
        headline = random.choice(content["stat"])
    else:
        headline = random.choice(content["question"])

    sub1, sub2 = content["lines"][0], content["lines"][1]
    cta        = content["cta"]
    date_str   = datetime.now().strftime("%B %d")

    def esc(t):
        return (t.replace("\\", "")
                 .replace("'", "")
                 .replace(":", " ")
                 .replace("%", "pct")
                 .replace("->", "->")
                 .replace("—", "-")
                 .replace("–", "-")
                 .encode("ascii", "ignore").decode("ascii"))

    font_dir = BASE / "assets" / "fonts"
    f_bold   = str(font_dir / "Oswald-Bold.ttf").replace("\\", "/").replace("C:/", "C\\:/")
    f_body   = str(font_dir / "Montserrat-ExtraBold.ttf").replace("\\", "/").replace("C:/", "C\\:/")

    drawtext = ",".join([
        f"drawtext=fontfile='{f_bold}':text='BootHop':fontsize=72:fontcolor=#10b981"
        f":x=(w-text_w)/2:y=140:shadowcolor=black@0.8:shadowx=2:shadowy=2",
        f"drawtext=fontfile='{f_body}':text='Verified Operators. Same Day.':fontsize=30"
        f":fontcolor=#6b7280:x=(w-text_w)/2:y=240",
        f"drawtext=fontfile='{f_bold}':text='{esc(headline)}':fontsize=52"
        f":fontcolor=white:box=1:boxcolor=black@0.5:boxborderw=14"
        f":x=(w-text_w)/2:y=580",
        f"drawtext=fontfile='{f_body}':text='{esc(sub1)}':fontsize=36"
        f":fontcolor=#d1d5db:x=(w-text_w)/2:y=800",
        f"drawtext=fontfile='{f_body}':text='{esc(sub2)}':fontsize=36"
        f":fontcolor=#d1d5db:x=(w-text_w)/2:y=855",
        f"drawtext=fontfile='{f_bold}':text='{esc(cta)}':fontsize=42"
        f":fontcolor=#10b981:box=1:boxcolor=black@0.6:boxborderw=10"
        f":x=(w-text_w)/2:y=1650",
        f"drawtext=fontfile='{f_body}':text='{esc(date_str)} - {slot.title()} Story':fontsize=26"
        f":fontcolor=#4b5563:x=(w-text_w)/2:y=1830",
    ])

    music_file = _find_music_file()
    use_video  = music_file is not None
    out_path   = out_base.with_suffix(".mp4" if use_video else ".jpg")

    if logo.exists():
        if use_video:
            fc = (
                f"[1:v]scale=220:-1[logo];"
                f"[0:v][logo]overlay=(W-w)/2:360[bg];"
                f"[bg]{drawtext}[v];"
                f"[2:a]afade=t=in:st=0:d=1,afade=t=out:st=13:d=2,"
                f"atrim=0:15,asetpts=PTS-STARTPTS[a]"
            )
            cmd = [
                "ffmpeg", "-y",
                "-f", "lavfi", "-i", "color=c=#07111f:size=1080x1920:rate=25:duration=15",
                "-loop", "1", "-i", str(logo),
                "-i", str(music_file),
                "-filter_complex", fc,
                "-map", "[v]", "-map", "[a]",
                "-c:v", "libx264", "-crf", "23", "-preset", "fast",
                "-c:a", "aac", "-b:a", "128k",
                "-t", "15", str(out_path),
            ]
        else:
            cmd = [
                "ffmpeg", "-y",
                "-f", "lavfi", "-i", "color=c=#07111f:size=1080x1920:rate=1",
                "-loop", "1", "-i", str(logo),
                "-filter_complex",
                f"[1:v]scale=220:-1[logo];[0:v][logo]overlay=(W-w)/2:360[bg];[bg]{drawtext}[v]",
                "-map", "[v]",
                "-frames:v", "1", "-q:v", "2", str(out_path),
            ]
    else:
        if use_video:
            fc = (
                f"[0:v]{drawtext}[v];"
                f"[1:a]afade=t=in:st=0:d=1,afade=t=out:st=13:d=2,"
                f"atrim=0:15,asetpts=PTS-STARTPTS[a]"
            )
            cmd = [
                "ffmpeg", "-y",
                "-f", "lavfi", "-i", "color=c=#07111f:size=1080x1920:rate=25:duration=15",
                "-i", str(music_file),
                "-filter_complex", fc,
                "-map", "[v]", "-map", "[a]",
                "-c:v", "libx264", "-crf", "23", "-preset", "fast",
                "-c:a", "aac", "-b:a", "128k",
                "-t", "15", str(out_path),
            ]
        else:
            cmd = [
                "ffmpeg", "-y",
                "-f", "lavfi", "-i", "color=c=#07111f:size=1080x1920:rate=1",
                "-vf", drawtext,
                "-frames:v", "1", "-q:v", "2", str(out_path),
            ]

    subprocess.run(cmd, capture_output=True, timeout=120)
    ok = out_path.exists() and out_path.stat().st_size > 1000
    return out_path, ok, headline


def _post_ig_story(file_path):
    if not IG_ACCESS_TOKEN or not IG_USER_ID:
        print("  [Story] No Instagram credentials — skipping")
        return None

    # Upload to catbox.moe for a public URL
    try:
        with open(file_path, "rb") as f:
            up = requests.post(
                "https://catbox.moe/user/api.php",
                data={"reqtype": "fileupload", "userhash": ""},
                files={"fileToUpload": f},
                timeout=60,
            )
        public_url = up.text.strip()
        if not public_url.startswith("https://"):
            print(f"  [Story] Upload failed: {up.text[:80]}")
            return None
        print(f"  [Story] Uploaded → {public_url}")
    except Exception as e:
        print(f"  [Story] Upload error: {e}")
        return None

    base = f"https://graph.instagram.com/v21.0/{IG_USER_ID}"
    is_video = str(file_path).endswith(".mp4")

    # Step 1 — create media container
    try:
        payload = {"media_type": "STORIES", "access_token": IG_ACCESS_TOKEN}
        payload["video_url" if is_video else "image_url"] = public_url
        r = requests.post(f"{base}/media", data=payload, timeout=30)
        data = r.json()
        if "error" in data:
            print(f"  [Story] Container error: {data['error']}")
            return None
        container_id = data["id"]
        print(f"  [Story] Container: {container_id}")
    except Exception as e:
        print(f"  [Story] Container failed: {e}")
        return None

    # Step 2 — poll until ready (video only)
    if is_video:
        for _ in range(30):
            time.sleep(10)
            try:
                s = requests.get(
                    f"https://graph.instagram.com/v21.0/{container_id}",
                    params={"fields": "status_code", "access_token": IG_ACCESS_TOKEN},
                    timeout=15,
                ).json()
                status = s.get("status_code", "")
                if status == "FINISHED":
                    break
                if status == "ERROR":
                    print("  [Story] Container failed — ERROR status")
                    return None
            except Exception:
                pass
    else:
        time.sleep(2)

    # Step 3 — publish
    try:
        r = requests.post(
            f"{base}/media_publish",
            data={"creation_id": container_id, "access_token": IG_ACCESS_TOKEN},
            timeout=30,
        )
        data = r.json()
        if "error" in data:
            print(f"  [Story] Publish error: {data['error']}")
            return None
        media_id = data.get("id", "")
        print(f"  [Story] Published — media_id: {media_id}")
        return media_id
    except Exception as e:
        print(f"  [Story] Publish failed: {e}")
        return None


def _send_telegram_story(out_path, slot, theme_name, headline):
    try:
        is_video = out_path.suffix == ".mp4"
        caption  = (f"\U0001f4f1 *BootHop {slot.title()} Story  -  {datetime.now().strftime('%H:%M')}*\n"
                    f"Theme: {theme_name}\n\n"
                    f"_{headline}_\n\n"
                    f"_Auto-generated  -  post to Instagram + TikTok Stories_")
        endpoint = "sendVideo" if is_video else "sendPhoto"
        field    = "video" if is_video else "photo"
        with open(out_path, "rb") as f:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/{endpoint}",
                data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption[:1000],
                      "parse_mode": "Markdown"},
                files={field: f},
                timeout=120,
            )
        print(f"  [Story] Sent {'video' if is_video else 'image'} to Telegram")
    except Exception as e:
        print(f"  [Story] Telegram error: {e}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--slot", choices=["afternoon", "evening"], default="afternoon")
    args = parser.parse_args()

    slot        = args.slot
    theme_idx   = _get_theme_index()
    theme_names = ["Problem Awareness", "Solution & Product",
                   "Trust & Credibility", "Vision & CTA"]
    theme_name  = theme_names[theme_idx]

    print(f"\n[Stories] {slot.title()} Story  -  {datetime.now().strftime('%H:%M')}")
    print(f"  Theme : Week {theme_idx+1}/4  -  {theme_name}")

    out_base            = TEMP / f"story_{slot}"
    out_path, ok, headline = _build_story(slot, theme_idx, out_base)

    if not ok:
        print("  [Story] Build failed  -  check ffmpeg and fonts")
        return

    fmt  = "video+music" if out_path.suffix == ".mp4" else "image"
    size = out_path.stat().st_size // 1024
    print(f"  [Story] Built: {out_path.name} ({size}KB, {fmt})")

    _send_telegram_story(out_path, slot, theme_name, headline)
    media_id = _post_ig_story(out_path)

    if media_id:
        status = f"✅ Instagram Story posted — {media_id}"
    else:
        status = "⚠️ Instagram Story — not posted (check credentials or catbox)"

    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": f"[{slot.title()} Story] {status}"},
            timeout=15,
        )
    except Exception:
        pass

    print(f"  [Story] {status}")


if __name__ == "__main__":
    main()
