"""
telegram_commander.py
Polls Telegram every 5 minutes for BootHop control commands.
Runs as a scheduled task (BootHop-Commander, every 5 min).

Handles:
  /menu          — post the control-panel keyboard
  /rerun         — force re-run pipeline (bypasses skip guard)
  /status        — pipeline status + last run info
  /story pm      — regenerate afternoon story
  /story eve     — regenerate evening story
  Inline button callbacks (same actions without typing)
"""

import json, os, subprocess, sys, time
from datetime import datetime
from pathlib import Path

BASE = Path(r"C:\Users\babso\Desktop\BootHopPipeline")
sys.path.insert(0, str(BASE))

import requests
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

OFFSET_FILE = BASE / "data" / "tg_commander_offset.json"
PYTHON      = sys.executable

# ── helpers ───────────────────────────────────────────────────────────────────

def _load_offset():
    try:
        return json.loads(OFFSET_FILE.read_text())["offset"]
    except Exception:
        return 0


def _save_offset(offset):
    try:
        OFFSET_FILE.write_text(json.dumps({"offset": offset}))
    except Exception:
        pass


def _send(text, reply_markup=None):
    payload = {
        "chat_id":    TELEGRAM_CHAT_ID,
        "text":       text,
        "parse_mode": "Markdown",
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json=payload,
            timeout=15,
        )
    except Exception as e:
        print(f"[Cmdr] send error: {e}")


def _ack(cb_id, text="Got it"):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/answerCallbackQuery",
            json={"callback_query_id": cb_id, "text": text},
            timeout=10,
        )
    except Exception:
        pass


def _control_panel_keyboard():
    return {
        "inline_keyboard": [
            [
                {"text": "\U0001f504 Re-run Pipeline",    "callback_data": "cmd_rerun"},
                {"text": "\U0001f4ca Status",              "callback_data": "cmd_status"},
            ],
            [
                {"text": "\U0001f4f1 Story (1pm)",         "callback_data": "cmd_story_pm"},
                {"text": "\U0001f4f1 Story (8:30pm)",      "callback_data": "cmd_story_eve"},
            ],
        ]
    }


# ── actions ───────────────────────────────────────────────────────────────────

def do_menu():
    _send(
        "*BootHop Control Panel*\n\nTap a button to run a command:",
        reply_markup=_control_panel_keyboard(),
    )


def do_status():
    crash_log = BASE / "data" / "pipeline_crash.log"
    step_file = BASE / "data" / "pipeline_step.txt"
    today     = datetime.now().strftime("%Y-%m-%d")
    out_dir   = BASE / "output" / today

    # Count today's videos
    videos = list(out_dir.glob("*.mp4")) if out_dir.exists() else []

    # Last log entry
    last_entry = ""
    try:
        lines = crash_log.read_text(encoding="utf-8", errors="replace").strip().splitlines()
        for line in reversed(lines):
            if line.strip():
                last_entry = line.strip()
                break
    except Exception:
        last_entry = "unavailable"

    # Current step
    step = ""
    try:
        if step_file.exists():
            step = step_file.read_text(encoding="utf-8").strip()
    except Exception:
        pass

    status_lines = [
        f"*BootHop Pipeline Status*  {datetime.now().strftime('%H:%M')}",
        f"",
        f"Videos today: `{len(videos)}`",
        f"Last log: `{last_entry[-80:]}`",
    ]
    if step:
        status_lines.append(f"Current step: `{step[-60:]}`")

    _send("\n".join(status_lines), reply_markup=_control_panel_keyboard())


def do_rerun():
    _send("\U0001f504 *Re-running pipeline...*\nThis takes 20-35 minutes. I will report back when done.")
    today   = datetime.now().strftime("%Y-%m-%d")
    out_dir = BASE / "output" / today

    # Remove today's videos so the skip guard does not fire
    removed = 0
    if out_dir.exists():
        for f in out_dir.glob("*.mp4"):
            try:
                f.unlink()
                removed += 1
            except Exception:
                pass

    print(f"[Cmdr] Removed {removed} old videos, launching pipeline...")
    try:
        subprocess.Popen(
            [PYTHON, str(BASE / "pipeline.py")],
            cwd=str(BASE),
            creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0,
        )
        _send(f"\U0001f7e2 Pipeline started. Cleared {removed} old videos. Watch for the preview message.")
    except Exception as e:
        _send(f"❌ Failed to start pipeline: {e}")


def do_story(slot):
    label = "1pm afternoon" if slot == "afternoon" else "8:30pm evening"
    _send(f"\U0001f4f1 *Generating {label} story...*")
    try:
        result = subprocess.run(
            [PYTHON, str(BASE / "scripts" / "post_stories.py"), "--slot", slot],
            cwd=str(BASE),
            capture_output=True,
            text=True,
            timeout=180,
        )
        if result.returncode == 0:
            _send(f"✅ {label.title()} story sent to Telegram.")
        else:
            _send(f"❌ Story failed:\n`{result.stderr[-300:]}`")
    except Exception as e:
        _send(f"❌ Story error: {e}")


# ── dispatcher ────────────────────────────────────────────────────────────────

_CMD_MAP = {
    "cmd_rerun":    lambda: do_rerun(),
    "cmd_status":   lambda: do_status(),
    "cmd_story_pm": lambda: do_story("afternoon"),
    "cmd_story_eve":lambda: do_story("evening"),
}


def dispatch(text_lower):
    if text_lower.startswith("/menu"):
        do_menu()
    elif text_lower.startswith("/rerun"):
        do_rerun()
    elif text_lower.startswith("/status"):
        do_status()
    elif text_lower.startswith("/story pm") or text_lower == "/story afternoon":
        do_story("afternoon")
    elif text_lower.startswith("/story eve") or text_lower == "/story evening":
        do_story("evening")


# ── main poll loop ─────────────────────────────────────────────────────────────

def main():
    print(f"[Cmdr] {datetime.now().strftime('%H:%M')} — polling Telegram...")
    offset = _load_offset()

    try:
        resp = requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates",
            params={
                "offset":          offset,
                "timeout":         0,
                "allowed_updates": json.dumps(["message", "callback_query"]),
            },
            timeout=15,
        ).json()
    except Exception as e:
        print(f"[Cmdr] Poll failed: {e}")
        return

    updates = resp.get("result", [])
    for upd in updates:
        offset = upd["update_id"] + 1

        # Inline button tap
        cb = upd.get("callback_query")
        if cb:
            data = cb.get("data", "")
            _ack(cb["id"])
            if data in _CMD_MAP:
                print(f"[Cmdr] Callback: {data}")
                _CMD_MAP[data]()
            continue

        # Text message
        msg  = upd.get("message", {})
        text = msg.get("text", "").strip()
        chat = str(msg.get("chat", {}).get("id", ""))
        if text and chat == str(TELEGRAM_CHAT_ID):
            low = text.lower()
            print(f"[Cmdr] Message: {low[:60]}")
            dispatch(low)

    _save_offset(offset)
    print(f"[Cmdr] Done. Offset saved: {offset}")


if __name__ == "__main__":
    main()
