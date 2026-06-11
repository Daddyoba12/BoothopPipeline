"""
boothop_evening_post.py
Runs at 18:00 daily via BootHop-Evening task.

Evening slot — hits 7pm-9pm UK prime time for TikTok.

TikTok → posts V2 from today's morning render (different hook from V1 already
          on TikTok at 07:30 — catches the evening audience segment).

Instagram Stories are handled separately:
  BootHop-Stories-Afternoon at 13:00 (post_stories.py --slot afternoon)
  BootHop-Stories-Evening   at 20:30 (post_stories.py --slot evening)

Approval sent to Telegram + WhatsApp at ~18:05:
  [✅ Post Now]    → posts TikTok V2 immediately
  [⏰ Post in 1hr] → waits 60 min → posts at ~19:05 (deep in 7-9pm prime)
  [🚫 Ignore]      → nothing posts tonight

60-min window — auto-posts at ~19:05 if no reply.
"""

import json, sys, time
import requests
from datetime import datetime, timedelta
from pathlib import Path

BASE       = Path(r"C:\Users\babso\Desktop\BootHopPipeline")
OUTPUT     = BASE / "output"
SCRIPTS    = BASE / "scripts"
CLIPS_DIR  = BASE / "music" / "clips"

sys.path.insert(0, str(BASE))
sys.path.insert(0, str(SCRIPTS))

from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

WHATSAPP_ACCESS_TOKEN    = ""
WHATSAPP_PHONE_NUMBER_ID = ""
WHATSAPP_RECIPIENT       = "447405746302"
_env = BASE / ".env"
if _env.exists():
    for _line in _env.read_text(encoding="utf-8").splitlines():
        if "=" in _line and not _line.startswith("#"):
            _k, _v = _line.split("=", 1)
            if _k.strip() == "WHATSAPP_ACCESS_TOKEN":    WHATSAPP_ACCESS_TOKEN    = _v.strip()
            if _k.strip() == "WHATSAPP_PHONE_NUMBER_ID": WHATSAPP_PHONE_NUMBER_ID = _v.strip()


def _log(msg):
    print(f"[{datetime.utcnow().strftime('%H:%M:%S')}] [Evening] {msg}")


def send_telegram(msg: str, markup=None):
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": msg[:4096], "parse_mode": "Markdown"}
    if markup:
        payload["reply_markup"] = json.dumps(markup)
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json=payload, timeout=15,
        )
        return r.json().get("result", {}).get("message_id")
    except Exception as e:
        _log(f"Telegram error: {e}")
        return None


def send_whatsapp(text: str):
    if not WHATSAPP_ACCESS_TOKEN or not WHATSAPP_PHONE_NUMBER_ID:
        return
    try:
        requests.post(
            f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages",
            headers={"Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
                     "Content-Type": "application/json"},
            json={"messaging_product": "whatsapp", "to": WHATSAPP_RECIPIENT,
                  "type": "text", "text": {"body": text[:4096]}},
            timeout=20,
        )
    except Exception as e:
        _log(f"WhatsApp error: {e}")


def _load_ig_creds():
    p = SCRIPTS / "social_credentials.json"
    try:
        d  = json.loads(p.read_text(encoding="utf-8"))
        ig = d.get("instagram", {})
        return ig.get("access_token", ""), ig.get("ig_user_id", "")
    except Exception:
        return "", ""


def find_todays_v2() -> Path | None:
    """Find V2 video from today's morning pipeline render."""
    today   = datetime.now().strftime("%Y-%m-%d")
    out_dir = OUTPUT / today
    if not out_dir.exists():
        return None
    for f in sorted(out_dir.glob("*.mp4")):
        if "v2" in f.stem and "english" not in f.stem:
            return f
    return None


def pick_ig_music() -> Path | None:
    """Pick a random original clip for IG Reels only."""
    clips = sorted(CLIPS_DIR.glob("boothop_clip_*.mp3"))
    return random.choice(clips) if clips else None


def post_tiktok(video_path: Path, caption: str) -> str | None:
    try:
        import post_tiktok as _tt
        return _tt.post_video(str(video_path), caption)
    except ImportError:
        _log("post_tiktok module not available")
        return None
    except Exception as e:
        _log(f"TikTok post failed: {e}")
        return None


def wait_for_approval(timeout_seconds: int = 3600) -> dict:
    """
    Poll Telegram for [Post Now] / [Post in 1hr] / [Ignore].
    Auto-posts on timeout.
    """
    try:
        drain   = requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates",
            params={"timeout": 0, "allowed_updates": json.dumps(["callback_query"])},
            timeout=10,
        ).json()
        updates = drain.get("result", [])
        offset  = (updates[-1]["update_id"] + 1) if updates else 0
    except Exception:
        offset = 0

    result   = {"post": False, "delay": False, "ignore": False}
    deadline = time.time() + timeout_seconds
    _log(f"Waiting up to {timeout_seconds // 60} min for approval...")

    while time.time() < deadline:
        remaining = deadline - time.time()
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
            _log(f"Poll error: {e}")
            time.sleep(10)
            continue

        for upd in resp.get("result", []):
            offset  = upd["update_id"] + 1
            cb      = upd.get("callback_query", {})
            cb_data = cb.get("data", "")
            cb_id   = cb.get("id", "")

            def _ack(text):
                try:
                    requests.post(
                        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/answerCallbackQuery",
                        json={"callback_query_id": cb_id, "text": text},
                        timeout=10,
                    )
                except Exception:
                    pass

            if cb_data == "ev_post":
                _ack("✅ Posting TikTok V2 now!")
                result["post"] = True
                _log("Approved — posting now")
                return result
            elif cb_data == "ev_delay":
                _ack("⏰ Posting in 60 min — deep in 7-9pm prime.")
                result["delay"] = True
                _log("Delay selected")
                return result
            elif cb_data == "ev_ignore":
                _ack("🚫 Ignored — nothing posts tonight.")
                result["ignore"] = True
                _log("Ignored")
                return result

    _log("60-min window elapsed — auto-posting")
    result["post"] = True
    return result


def main():
    _log("=== BootHop Evening Post (18:00) ===")

    v2_video   = find_todays_v2()
    _auto_time = (datetime.now() + timedelta(minutes=60)).strftime("%H:%M")

    tt_line = f"🎬 TikTok Reel — V2 (`{v2_video.name}`)" if v2_video else "⚠️ TikTok — V2 not found (morning pipeline may not have run)"

    preview = (
        f"🌆 *EVENING POST READY — {datetime.now().strftime('%A %d %B  %H:%M')}*\n\n"
        f"*TONIGHT (7-9pm prime):*\n"
        f"  {tt_line}\n\n"
        f"_IG Stories handled at 13:00 + 20:30 separately._\n"
        f"_Auto-posts at ~{_auto_time} if no reply._"
    )

    markup = {"inline_keyboard": [[
        {"text": "✅ Post Now",      "callback_data": "ev_post"},
        {"text": "⏰ Post in 1hr",  "callback_data": "ev_delay"},
        {"text": "🚫 Ignore",       "callback_data": "ev_ignore"},
    ]]}

    send_telegram(preview, markup=markup)
    send_whatsapp(preview)

    decision = wait_for_approval(timeout_seconds=3600)

    if decision["ignore"]:
        send_telegram("🚫 Evening post ignored for tonight.")
        _log("Ignored — done.")
        return

    if decision["delay"]:
        _post_at = (datetime.now() + timedelta(minutes=60)).strftime("%H:%M")
        msg = f"⏰ TikTok V2 delayed — posting at ~{_post_at} (7-9pm prime window)."
        send_telegram(msg)
        send_whatsapp(msg)
        _log("Sleeping 60 min...")
        time.sleep(3600)

    if not v2_video:
        msg = "⚠️ Evening post skipped — V2 video not found in today's output."
        send_telegram(msg)
        send_whatsapp(msg)
        _log("V2 not found — done.")
        return

    caption = (
        f"Someone is already going your way.\n\n"
        f"BootHop — same-day delivery powered by trusted travellers.\n"
        f"boothop.com\n\n"
        f"#BootHop #SameDayDelivery #DiasporaMagic #LondonToLagos #HumanLogistics #TrustedTravellers"
    )

    # TikTok — send to Telegram for manual posting (API key pending)
    try:
        with open(v2_video, "rb") as f:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendVideo",
                data={"chat_id": TELEGRAM_CHAT_ID, "caption": f"TikTok evening — post manually\n\n{caption[:900]}"},
                files={"video": (v2_video.name, f, "video/mp4")},
                timeout=120,
            )
        _log("TikTok video sent to Telegram")
    except Exception as e:
        _log(f"Telegram send failed: {e}")

    # Instagram — mix V2 with original clip to avoid muting
    ig_music = pick_ig_music()
    ig_id    = None
    if ig_music:
        import subprocess, shutil as _shutil
        tmp_ig = v2_video.parent / f"_ig_evening_{v2_video.stem}.mp4"
        cmd = [
            "ffmpeg", "-y", "-i", str(v2_video), "-i", str(ig_music),
            "-map", "0:v", "-map", "1:a",
            "-shortest", "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
            str(tmp_ig),
        ]
        res = subprocess.run(cmd, capture_output=True, timeout=60)
        if res.returncode == 0:
            from post_instagram import post_reel as _post_ig_reel
            ig_id = _post_ig_reel(str(tmp_ig), caption)
            _log(f"Instagram Reel (original music): {ig_id or 'failed'}")
            try: tmp_ig.unlink()
            except Exception: pass
        else:
            _log("FFmpeg mix for IG failed — skipping IG Reel")
    else:
        _log("No original clips found — skipping Instagram Reel")

    tt_line  = f"TikTok: {tt_id}" if tt_id else "TikTok: failed"
    ig_line  = f"Instagram: {ig_id}" if ig_id else "Instagram: skipped"
    result_msg = f"{tt_line}\n{ig_line}"

    confirmation = (
        f"EVENING COMPLETE — {datetime.now().strftime('%H:%M')}\n\n"
        f"  {result_msg}"
    )
    send_telegram(confirmation)
    send_whatsapp(confirmation)
    _log("Done.")


if __name__ == "__main__":
    main()
