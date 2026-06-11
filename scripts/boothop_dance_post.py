"""
scripts/boothop_dance_post.py
Runs Tue / Wed / Sat at 10:00 via BootHop-DancePromo task.

1. Renders the weekly promo video (test/promo_weekly.py logic)
   - Rotating artists: Davido / Wizkid / Burna Boy / Asake / Kizz Daniel / Kunle Gold
   - Lifestyle Pexels clips with comic-voice BootHop hooks
   - Glass closing card + BootHop logo
2. Sends the video to Telegram as a preview with approval buttons
3. Waits up to 60 min for reply:
     [✅ Post TikTok]  → posts to TikTok
     [📸 Post Instagram] → posts to Instagram
     [📲 Post Both]    → posts to both
     [🚫 Skip]         → nothing posts
4. Auto-skips on timeout (ad-hoc only — no forced auto-post)
5. Sends confirmation message
"""

import json, subprocess, sys, time
import requests
from datetime import datetime, timedelta
from pathlib import Path

BASE    = Path(r"C:\Users\babso\Desktop\BootHopPipeline")
TEST    = BASE / "test"
SCRIPTS = BASE / "scripts"

sys.path.insert(0, str(BASE))
sys.path.insert(0, str(SCRIPTS))

from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

DANCE_SCRIPT = TEST / "promo_weekly.py"
DANCE_VIDEO  = TEST / "promo_weekly.mp4"
PYTHON       = r"C:\Python314\python.exe"

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


def _log(msg: str):
    print(f"[{datetime.utcnow().strftime('%H:%M:%S')}] [DancePromo] {msg}")


def send_telegram_text(text: str):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text[:4096],
                  "parse_mode": "Markdown"},
            timeout=15,
        )
    except Exception as e:
        _log(f"Telegram text error: {e}")


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


def send_video_preview(video_path: Path) -> bool:
    """Send the dance video to Telegram with the approval keyboard."""
    day     = datetime.now().strftime("%A %d %B  %H:%M")
    caption = (
        f"🎵 *WEEKLY PROMO READY — {day}*\n\n"
        f"Artist rotation · Lifestyle clips · Comic hooks · 35s\n\n"
        f"_Send to TikTok, Instagram, or both — or skip for today._"
    )
    markup = {"inline_keyboard": [
        [
            {"text": "✅ Post TikTok",      "callback_data": "dp_tiktok"},
            {"text": "📸 Post Instagram",   "callback_data": "dp_instagram"},
        ],
        [
            {"text": "📲 Post Both",         "callback_data": "dp_both"},
            {"text": "🚫 Skip",             "callback_data": "dp_skip"},
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
            _log("Video preview + keyboard sent to Telegram")
            return True
        _log(f"Video send failed: {r.text[:100]}")
        return False
    except Exception as e:
        _log(f"Video send error: {e}")
        return False


def wait_for_decision(timeout_seconds: int = 3600) -> str:
    """
    Poll Telegram for dp_tiktok / dp_instagram / dp_both / dp_skip.
    Returns the decision string. Returns 'dp_skip' on timeout.
    """
    try:
        drain = requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates",
            params={"timeout": 0, "allowed_updates": json.dumps(["callback_query"])},
            timeout=10,
        ).json()
        updates = drain.get("result", [])
        offset  = (updates[-1]["update_id"] + 1) if updates else 0
    except Exception:
        offset = 0

    deadline = time.time() + timeout_seconds
    _log(f"Waiting up to {timeout_seconds // 60} min for decision...")

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

            ACK = {
                "dp_tiktok":    "✅ Posting to TikTok!",
                "dp_instagram": "📸 Posting to Instagram!",
                "dp_both":      "📲 Posting to TikTok + Instagram!",
                "dp_skip":      "🚫 Skipped for today.",
            }
            if cb_data in ACK:
                try:
                    requests.post(
                        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/answerCallbackQuery",
                        json={"callback_query_id": cb_id, "text": ACK[cb_data]},
                        timeout=10,
                    )
                except Exception:
                    pass
                _log(f"Decision: {cb_data}")
                return cb_data

    _log("Timeout — auto-skipping (dance promo is ad-hoc, no forced post)")
    return "dp_skip"


def post_to_tiktok(video_path: Path) -> bool:
    try:
        sys.path.insert(0, str(SCRIPTS))
        import post_tiktok as _tt
        caption = (
            "Someone is already going your way.\n\n"
            "BootHop — same-day delivery powered by trusted travellers.\n"
            "boothop.com\n\n"
            "#BootHop #JoinTheMovement #SameDayDelivery #DiasporaMagic #AsoEbi"
        )
        result = _tt.post_video(str(video_path), caption)
        if result:
            _log(f"TikTok posted: {result}")
            return True
        _log("TikTok post returned no ID")
        return False
    except ImportError:
        _log("post_tiktok module not available")
        return False
    except Exception as e:
        _log(f"TikTok error: {e}")
        return False


def post_to_instagram(video_path: Path) -> bool:
    try:
        sys.path.insert(0, str(SCRIPTS))
        import post_instagram as _ig
        caption = (
            "Someone is already going your way. 💚\n\n"
            "BootHop — same-day delivery powered by trusted travellers.\n"
            "boothop.com\n\n"
            "#BootHop #JoinTheMovement #SameDayDelivery #DiasporaMagic #AsoEbi #Afrobeats"
        )
        result = _ig.post_reel(str(video_path), caption)
        if result:
            _log(f"Instagram posted: {result}")
            return True
        _log("Instagram post returned no ID")
        return False
    except ImportError:
        _log("post_instagram module not available")
        return False
    except Exception as e:
        _log(f"Instagram error: {e}")
        return False


def main():
    _log(f"=== BootHop Weekly Promo — {datetime.now().strftime('%A %d %B')} ===")

    # Step 1: Render the weekly promo video
    _log("Rendering promo_weekly...")
    try:
        result = subprocess.run(
            [PYTHON, str(DANCE_SCRIPT)],
            capture_output=True, text=True,
            cwd=str(BASE), timeout=600,
        )
        if result.returncode != 0:
            _log(f"Render failed:\n{result.stderr[-400:]}")
            send_telegram_text(
                f"⚠️ *Weekly Promo render failed* — {datetime.now().strftime('%A %d %B')}\n"
                f"Check pipeline logs."
            )
            return
        _log("Render complete")
    except subprocess.TimeoutExpired:
        _log("Render timed out (10 min)")
        return

    if not DANCE_VIDEO.exists() or DANCE_VIDEO.stat().st_size < 100_000:
        _log(f"Video not found or too small: {DANCE_VIDEO}")
        send_telegram_text("⚠️ Weekly promo video not found after render.")
        return

    mb = DANCE_VIDEO.stat().st_size / 1_048_576
    _log(f"Video ready: {DANCE_VIDEO.name}  ({mb:.1f} MB)")

    # Step 2: Send preview + keyboard
    sent = send_video_preview(DANCE_VIDEO)
    if not sent:
        send_telegram_text(
            f"🎵 *Weekly Promo Ready — {datetime.now().strftime('%A %d %B  %H:%M')}*\n"
            f"Video render complete but preview upload failed.\n"
            f"Post manually from: `{DANCE_VIDEO}`"
        )
        return

    wa_msg = (f"🎵 BootHop Weekly Promo ready — {datetime.now().strftime('%A %d %B  %H:%M')}\n"
              f"Approve on Telegram to post to TikTok / Instagram.")
    send_whatsapp(wa_msg)

    # Step 3: Wait for decision
    decision = wait_for_decision(timeout_seconds=3600)

    if decision == "dp_skip":
        _log("Skipped — nothing posted")
        send_telegram_text("🎵 Weekly promo skipped for today.")
        return

    # Step 4: Post
    tt_ok = ig_ok = False

    if decision in ("dp_tiktok", "dp_both"):
        _log("Posting to TikTok...")
        tt_ok = post_to_tiktok(DANCE_VIDEO)

    if decision in ("dp_instagram", "dp_both"):
        _log("Posting to Instagram...")
        ig_ok = post_to_instagram(DANCE_VIDEO)

    # Step 5: Confirmation
    lines = [f"🎵 *WEEKLY PROMO POSTED — {datetime.now().strftime('%H:%M')}*\n"]
    if decision in ("dp_tiktok", "dp_both"):
        lines.append(f"  {'✅' if tt_ok else '⚠️'} TikTok — {'posted' if tt_ok else 'failed'}")
    if decision in ("dp_instagram", "dp_both"):
        lines.append(f"  {'✅' if ig_ok else '⚠️'} Instagram — {'posted' if ig_ok else 'failed'}")

    confirmation = "\n".join(lines)
    send_telegram_text(confirmation)
    send_whatsapp(confirmation.replace("*", "").replace("_", ""))
    _log("Done.")


if __name__ == "__main__":
    main()
