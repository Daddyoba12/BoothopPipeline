"""
scripts/quick_repost.py
Approval + posting only — uses today's existing pipeline videos.
Skips re-render entirely. Run this when you want to repost today.

Usage:
  python scripts/quick_repost.py
"""

import json, sys, time, requests
from datetime import datetime, date
from pathlib import Path

BASE    = Path(__file__).parent.parent
OUTPUT  = BASE / "output"
TEST    = BASE / "test"
SCRIPTS = BASE / "scripts"
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(SCRIPTS))

TELEGRAM_TOKEN   = "8717698733:AAF7GI9Yw1DhdYVv_TK35fYQcwaGdk4caeA"
TELEGRAM_CHAT_ID = "8641867751"

try:
    from config import WHATSAPP_ACCESS_TOKEN, WHATSAPP_PHONE_NUMBER_ID, WHATSAPP_RECIPIENT
    _WA_OK = True
except Exception:
    _WA_OK = False

import post_instagram
try:
    import post_tiktok
    _TT_OK = True
except Exception:
    _TT_OK = False


# ── Helpers ───────────────────────────────────────────────────────────────────

def tg_text(text: str):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text[:4096], "parse_mode": "Markdown"},
            timeout=20,
        )
    except Exception as e:
        print(f"  [TG] {e}")


def tg_send_video(path: str, caption: str, markup: str | None = None):
    try:
        data = {"chat_id": TELEGRAM_CHAT_ID, "caption": caption[:900], "parse_mode": "Markdown"}
        if markup:
            data["reply_markup"] = markup
        with open(path, "rb") as f:
            r = requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendVideo",
                data=data,
                files={"video": f},
                timeout=120,
            )
        return r.ok
    except Exception as e:
        print(f"  [TG video] {e}")
        return False


def wa_text(text: str):
    if not _WA_OK:
        return
    try:
        requests.post(
            f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages",
            headers={"Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}", "Content-Type": "application/json"},
            json={"messaging_product": "whatsapp", "to": WHATSAPP_RECIPIENT,
                  "type": "text", "text": {"body": text[:4096]}},
            timeout=20,
        )
    except Exception:
        pass


def check_wa_decision() -> str | None:
    try:
        r = requests.get(
            "https://boothop.com/api/pipeline-decision",
            headers={"x-pipeline-secret": "boothop_pipeline_secret_2026"},
            timeout=10,
        )
        if r.ok:
            return r.json().get("decision") or None
    except Exception:
        pass
    return None


# ── Find today's videos ───────────────────────────────────────────────────────

def find_todays_videos():
    today = date.today().isoformat()
    folder = OUTPUT / today
    if not folder.exists():
        return None, None

    v1 = next((p for p in folder.glob("v1_v1.mp4")), None)
    if not v1:
        v1 = next((p for p in folder.glob("v1_*.mp4") if "english" not in p.name), None)
    v2 = next((p for p in folder.glob("v2_v2.mp4")), None)
    if not v2:
        v2 = next((p for p in folder.glob("v2_*.mp4") if "english" not in p.name), None)

    return str(v1) if v1 else None, str(v2) if v2 else None


def find_todays_story():
    candidates = sorted(
        TEST.glob("daily_story_*.mp4"),
        key=lambda p: p.stat().st_mtime, reverse=True,
    )
    return str(candidates[0]) if candidates else None


# ── Approval loop ─────────────────────────────────────────────────────────────

def wait_for_approval(timeout_min=60):
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
    }

    def _apply(choices, cb):
        if cb not in _CB_MAP:
            return False
        platform, version = _CB_MAP[cb]
        if platform == "all":
            if version == "ignore":
                choices["ignore"] = True
            elif version == "delay":
                choices["delay"] = True
            else:
                choices["tiktok"] = choices["instagram"] = version
            return True
        choices[platform] = version
        return False

    # Drain stale Telegram callbacks
    try:
        drain = requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates",
            params={"timeout": 0, "allowed_updates": json.dumps(["callback_query"])},
            timeout=10,
        ).json()
        updates = drain.get("result", [])
        offset = (updates[-1]["update_id"] + 1) if updates else 0
        # Confirm drain by calling with offset
        if updates:
            requests.get(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates",
                params={"offset": offset, "timeout": 0},
                timeout=10,
            )
            print(f"  [Approval] Drained {len(updates)} stale callback(s)")
    except Exception:
        offset = 0

    choices  = {"tiktok": None, "instagram": None, "ignore": False, "delay": False}
    deadline = datetime.now().timestamp() + timeout_min * 60
    confirmed = False

    print(f"  [Approval] Waiting up to {timeout_min}min — Telegram + WhatsApp")

    while datetime.now().timestamp() < deadline and not confirmed:
        # WhatsApp check
        wa = check_wa_decision()
        if wa:
            confirmed = _apply(choices, wa)
            print(f"  [WA] {wa} -> {choices}")
            if confirmed:
                break

        # Telegram long-poll
        remaining = deadline - datetime.now().timestamp()
        wait_secs = int(min(30, remaining))
        if wait_secs <= 0:
            break
        try:
            resp = requests.get(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates",
                params={"offset": offset, "timeout": wait_secs,
                        "allowed_updates": json.dumps(["callback_query"])},
                timeout=wait_secs + 10,
            ).json()
        except Exception:
            time.sleep(5)
            continue

        for upd in resp.get("result", []):
            offset = upd["update_id"] + 1
            cb = upd.get("callback_query", {})
            if not cb:
                continue
            cb_id   = cb["id"]
            cb_data = cb.get("data", "")
            try:
                requests.post(
                    f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/answerCallbackQuery",
                    json={"callback_query_id": cb_id, "text": "Got it!"},
                    timeout=10,
                )
            except Exception:
                pass
            confirmed = _apply(choices, cb_data)
            print(f"  [TG] {cb_data} -> {choices}")
            if confirmed:
                break

    # Auto-post defaults if no reply
    if not choices["tiktok"] and not choices["instagram"] and not choices["ignore"]:
        print("  [Approval] Timeout — applying defaults: TikTok=V1, Instagram=V2")
        choices["tiktok"] = "v1"
        choices["instagram"] = "v2"

    return choices


# ── Post ──────────────────────────────────────────────────────────────────────

def post(choices, v1_path, v2_path, story_path):
    defaults = {"tiktok": 1, "instagram": 2}

    caption_v1 = "Verified travellers. Same day. Real people. BootHop. #BootHop #SameDayDelivery #TrustedTraveller #NaijaUK #DiasporaLife"
    caption_v2 = "Same route. Same day. A BootHop traveller already going your way. #BootHop #EarnWhileYouTravel #NaijaAbroad #JapaLife #LondonToLagos"
    caption_story = "Which route are you doing next? Drop it below 👇\n\n#BootHop #EarnWhileYouTravel #NaijaUK #JapaToJapada #TrustedTraveller"

    for plat in ("tiktok", "instagram"):
        ver = choices.get(plat)
        if ver == "skip":
            tg_text(f"{plat.capitalize()} skipped.")
            continue

        if ver == "story" and plat == "instagram":
            if story_path and Path(story_path).exists():
                print(f"\n[Instagram] Posting story reel...")
                try:
                    ig_id = post_instagram.post_reel(story_path, caption_story)
                    tg_text(f"✅ Instagram Story Reel posted! media_id: {ig_id}")
                    print(f"  [Instagram] media_id: {ig_id}")
                except Exception as e:
                    tg_text(f"❌ Instagram Story failed: {e}")
                    print(f"  [Instagram Story] Error: {e}")
            else:
                tg_text("❌ Instagram Story: no story video found")
            continue

        vnum = 2 if ver == "v2" else (1 if ver == "v1" else defaults[plat])
        vpath   = v1_path if vnum == 1 else v2_path
        caption = caption_v1 if vnum == 1 else caption_v2

        if not vpath or not Path(vpath).exists():
            tg_text(f"❌ {plat.capitalize()}: V{vnum} video not found")
            continue

        if plat == "tiktok":
            if not _TT_OK:
                tg_text("⚠️ TikTok module not loaded — skipped")
                continue
            print(f"\n[TikTok] Posting V{vnum}...")
            try:
                tt_id = post_tiktok.post_video(vpath, caption)
                tg_text(f"✅ TikTok V{vnum} sent — publish_id: {tt_id}")
            except Exception as e:
                tg_text(f"❌ TikTok V{vnum} error: {e}")
                print(f"  [TikTok] Error: {e}")

        elif plat == "instagram":
            print(f"\n[Instagram] Posting V{vnum}...")
            try:
                ig_id = post_instagram.post_reel(vpath, caption)
                tg_text(f"✅ Instagram V{vnum} posted — media_id: {ig_id}")
                print(f"  [Instagram] media_id: {ig_id}")
            except Exception as e:
                tg_text(f"❌ Instagram V{vnum} error: {e}")
                print(f"  [Instagram] Error: {e}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("\n" + "=" * 55)
    print(f"  BootHop Quick Repost  —  {date.today().isoformat()}")
    print("=" * 55 + "\n")

    v1, v2 = find_todays_videos()
    story  = find_todays_story()

    print(f"  V1:    {Path(v1).name if v1 else 'NOT FOUND'}")
    print(f"  V2:    {Path(v2).name if v2 else 'NOT FOUND'}")
    print(f"  Story: {Path(story).name if story else 'NOT FOUND'}")

    if not v1 and not v2:
        print("\nNo videos found for today — run pipeline.py first")
        return

    # Build Telegram keyboard
    markup = json.dumps({"inline_keyboard": [
        [
            {"text": "Post All V1",    "callback_data": "all_v1"},
            {"text": "Post All V2",    "callback_data": "all_v2"},
        ],
        [
            {"text": "TikTok V1",     "callback_data": "tt_v1"},
            {"text": "TikTok V2",     "callback_data": "tt_v2"},
            {"text": "TikTok Skip",   "callback_data": "tt_skip"},
        ],
        [
            {"text": "IG V1",         "callback_data": "ig_v1"},
            {"text": "IG V2",         "callback_data": "ig_v2"},
            {"text": "IG Skip",       "callback_data": "ig_skip"},
        ],
        [
            {"text": "📖 IG = Story", "callback_data": "ig_story"},
            {"text": "🚫 Ignore",     "callback_data": "ignore_all"},
        ],
    ]})

    # Send V2 preview + keyboard
    preview = v2 or v1
    _story_label = f"\n*Story:* _{Path(story).stem.replace('daily_story_','').replace('_',' ').title()}_" if story else ""
    caption = (
        f"🔁 *REPOST — choose what to post now:*\n\n"
        f"*V1:* today's POV hook (archive music)\n"
        f"*V2:* today's POV hook (trending music)"
        f"{_story_label}\n\n"
        f"_Timeout 60min = TikTok V1 + Instagram V2 auto-post._"
    )
    print("\n[Sending] Telegram approval request...")
    tg_send_video(preview, caption, markup)

    # Send story preview separately
    if story:
        story_name = Path(story).stem.replace("daily_story_","").replace("_"," ").title()
        tg_send_video(story, f"📖 *Story Reel — {story_name}*\n_Choose '📖 IG = Story' to post this to Instagram._")

    # WhatsApp nudge
    wa_text(
        "BootHop repost ready!\n\n"
        "Reply:\n"
        "  1 = TikTok only (V1)\n"
        "  2 = Instagram only (V2)\n"
        "  3 = Both\n"
        "  4 = Ignore\n"
        "  5 = Instagram story reel\n\n"
        "Or use Telegram buttons."
    )

    choices = wait_for_approval(timeout_min=60)
    print(f"\n[Choices] {choices}")

    if choices.get("ignore"):
        tg_text("🚫 Repost ignored — nothing posted.")
        print("Ignored.")
        return

    if choices.get("delay"):
        print("Delay requested — sleeping 60 min...")
        tg_text("⏰ Posting in 60 min...")
        time.sleep(3600)
        choices["tiktok"]    = choices.get("tiktok")    or "v1"
        choices["instagram"] = choices.get("instagram") or "v2"

    post(choices, v1, v2, story)
    print("\nDone.")


if __name__ == "__main__":
    main()
