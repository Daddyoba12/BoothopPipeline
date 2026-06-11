"""
repost_linkedin_telegram.py
Re-sends the last LinkedIn post to Telegram with Post / Skip buttons.
Reads temp_li/content.json (supply chain) or temp_li/news_content.json (news image),
whichever was modified most recently.

Usage:
    python scripts/repost_linkedin_telegram.py
"""

import json, os, sys, time, subprocess
from pathlib import Path
sys.path.insert(0, str(Path(r"C:\Users\babso\Desktop\BootHopPipeline")))

from config import TELEGRAM_TOKEN as TOKEN, TELEGRAM_CHAT_ID as CHAT_ID, BASE

TEMP        = BASE / "temp_li"
POST_SCRIPT = BASE / "scripts" / "post_linkedin.py"

try:
    import requests
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "-q"])
    import requests


def send(method, **kwargs):
    return requests.post(f"https://api.telegram.org/bot{TOKEN}/{method}", timeout=60, **kwargs)


# ── Pick the most recently modified content file ──────────────────────────────
supply_file = TEMP / "content.json"
news_file   = TEMP / "news_content.json"

use_news = False
if supply_file.exists() and news_file.exists():
    use_news = news_file.stat().st_mtime > supply_file.stat().st_mtime
elif news_file.exists():
    use_news = True
elif not supply_file.exists():
    print("No LinkedIn content found in temp_li/. Run the LinkedIn pipeline first.")
    sys.exit(1)

if use_news:
    nc      = json.loads(news_file.read_text(encoding="utf-8"))
    post    = nc["post"]
    region  = nc.get("region", "LinkedIn")
    image   = TEMP / "news_card.jpg"
    video   = None
    caption_file = TEMP / "linkedin_caption.txt"
    caption_file.write_text(post, encoding="utf-8")
    header  = f"LinkedIn News Card - {region}"
    li_args = ["--image", str(image), "--caption-file", str(caption_file)]
else:
    nc      = json.loads(supply_file.read_text(encoding="utf-8"))
    post    = nc["linkedin"]
    image   = TEMP / "telegram_thumb.jpg"
    last_txt = BASE / "output" / "last_linkedin.txt"
    video_raw = last_txt.read_text(encoding="utf-8").strip() if last_txt.exists() else None
    # Prefer the output file, fall back to temp_li/joined.mp4, then text-only
    if video_raw and Path(video_raw).exists():
        video = video_raw
    elif (TEMP / "joined.mp4").exists():
        video = str(TEMP / "joined.mp4")
    else:
        video = None
    caption_file = TEMP / "linkedin_caption.txt"
    caption_file.write_text(post, encoding="utf-8")
    header  = f"LinkedIn Supply Chain - {nc.get('theme', '')}"
    if video:
        li_args = ["--video", video, "--caption-file", str(caption_file)]
    else:
        li_args = ["--text-only", "--caption-file", str(caption_file)]

print(f"Reposting: {header}")

# ── Send video preview if available ──────────────────────────────────────────
if video and Path(video).exists():
    print("Sending video preview...")
    with open(video, "rb") as f:
        r = send("sendVideo",
                 data={"chat_id": CHAT_ID, "caption": "LinkedIn video"},
                 files={"video": f})
    print("Video:", "OK" if r.ok else r.text[:80])

# ── Send image + write-up + buttons ──────────────────────────────────────────
writeup = f"{header}\n\nReview and post:\n\n{post}"
markup  = json.dumps({"inline_keyboard": [[
    {"text": "Post to LinkedIn", "callback_data": "li_post"},
    {"text": "Skip",            "callback_data": "li_skip"},
]]})

if image.exists():
    with open(image, "rb") as img:
        r = send("sendPhoto",
                 data={"chat_id": CHAT_ID, "caption": writeup[:1024], "reply_markup": markup},
                 files={"photo": img})
else:
    r = send("sendMessage",
             data={"chat_id": CHAT_ID, "text": writeup[:4096], "reply_markup": markup})

print("Write-up:", "OK" if r.ok else r.text[:80])

# ── Poll for button (30 min, auto-post on timeout) ────────────────────────────
TIMEOUT = 1800
start   = time.time()
action  = None

try:
    r = requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates",
                     params={"limit": 1, "timeout": 0, "allowed_updates": ["callback_query"]},
                     timeout=10)
    updates = r.json().get("result", [])
    last_id = (updates[-1]["update_id"] + 1) if updates else 0
except:
    last_id = 0

print("Waiting up to 30 min (auto-posts on timeout)...")
while time.time() - start < TIMEOUT and action is None:
    try:
        r = requests.get(
            f"https://api.telegram.org/bot{TOKEN}/getUpdates",
            params={"offset": last_id, "timeout": 20, "allowed_updates": ["callback_query"]},
            timeout=35
        )
        for u in r.json().get("result", []):
            last_id = u["update_id"] + 1
            cq = u.get("callback_query", {})
            if cq.get("data") in ("li_post", "li_skip"):
                action = cq["data"]
                requests.post(
                    f"https://api.telegram.org/bot{TOKEN}/answerCallbackQuery",
                    data={"callback_query_id": cq["id"],
                          "text": "Posting..." if action == "li_post" else "Skipped"},
                    timeout=10
                )
                break
    except Exception as e:
        time.sleep(5)

if action == "li_skip":
    print("Skipped.")
    send("sendMessage", data={"chat_id": CHAT_ID, "text": "LinkedIn post skipped."})
else:
    label = "Approved" if action == "li_post" else "Timeout - auto-posting"
    print(f"{label}...")
    res = subprocess.run(
        [sys.executable, str(POST_SCRIPT)] + li_args,
        capture_output=True, text=True
    )
    status = "LinkedIn posted!" if res.returncode == 0 else f"Post failed:\n{res.stderr[:300]}"
    print(status)
    send("sendMessage", data={"chat_id": CHAT_ID, "text": status})
