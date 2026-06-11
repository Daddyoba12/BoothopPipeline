"""
token_monitor.py — BootHop token health checker + auto-renewer
- Tries to auto-renew LinkedIn and YouTube tokens silently.
- If auto-renew fails AND token expires within 48 hours, sends a Telegram alert
  every 4 hours with a "Stop alerts" button.
- Run via BootHop-TokenMonitor scheduled task (every 4 hours).
"""
import json
import sys
import datetime
from pathlib import Path
import requests

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf-16"):
    sys.stdout = open(sys.stdout.fileno(), mode="w", encoding="utf-8", buffering=1, closefd=False)

# ── Config ──────────────────────────────────────────────────────────────────────
BASE           = Path("C:/Users/babso/Desktop/BootHopPipeline")
SOCIAL_CREDS   = BASE / "scripts" / "social_credentials.json"
YOUTUBE_TOKEN  = BASE / "scripts" / "youtube_token.json"
DATA           = BASE / "data"
PAUSE_FILE     = DATA / "token_alerts_paused.json"
TELEGRAM_TOKEN    = "8717698733:AAF7GI9Yw1DhdYVv_TK35fYQcwaGdk4caeA"
TELEGRAM_CHAT_ID  = "8641867751"
ALERT_HOURS       = 48   # start alerting this many hours before expiry


# ── Telegram helpers ─────────────────────────────────────────────────────────────

def tg_send(text, markup=None):
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text[:4096], "parse_mode": "Markdown"}
    if markup:
        payload["reply_markup"] = json.dumps(markup)
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                      json=payload, timeout=30)
    except Exception as e:
        print(f"  [TG] {e}")


def tg_get_updates(offset=0, timeout=0):
    try:
        r = requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates",
            params={"offset": offset, "timeout": timeout,
                    "allowed_updates": json.dumps(["callback_query"])},
            timeout=timeout + 15,
        )
        return r.json().get("result", [])
    except Exception:
        return []


def tg_ack_callback(cb_id, text="Done"):
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/answerCallbackQuery",
                      json={"callback_query_id": cb_id, "text": text}, timeout=10)
    except Exception:
        pass


# ── Pause file ───────────────────────────────────────────────────────────────────

def is_paused():
    if not PAUSE_FILE.exists():
        return False
    try:
        d = json.loads(PAUSE_FILE.read_text(encoding="utf-8"))
        return datetime.datetime.now() < datetime.datetime.fromisoformat(d["paused_until"])
    except Exception:
        return False


def set_pause(hours=24):
    DATA.mkdir(exist_ok=True)
    until = datetime.datetime.now() + datetime.timedelta(hours=hours)
    PAUSE_FILE.write_text(json.dumps({"paused_until": until.isoformat()}), encoding="utf-8")
    print(f"  [Pause] Alerts paused until {until:%Y-%m-%d %H:%M}")


def check_for_stop_press():
    """Drain stale updates + brief live poll. If user pressed Stop, pause and return True."""
    updates = tg_get_updates(timeout=0)
    offset  = (updates[-1]["update_id"] + 1) if updates else 0
    # also do a short live poll to catch a very recent press
    updates += tg_get_updates(offset=offset, timeout=5)
    for upd in updates:
        cb = upd.get("callback_query", {})
        if cb.get("data") == "stop_token_alert":
            tg_ack_callback(cb["id"], "Alerts paused for 24 hours ✅")
            set_pause(24)
            return True
    return False


# ── LinkedIn ─────────────────────────────────────────────────────────────────────

def linkedin_expiry():
    """Return (expiry: datetime, hours_left: float) or (None, None) on error."""
    if not SOCIAL_CREDS.exists():
        return None, None
    try:
        data       = json.loads(SOCIAL_CREDS.read_text(encoding="utf-8"))
        li         = data.get("linkedin", {})
        expires_in = li.get("expires_in", 0)
        # Use issued_at if stored, otherwise fall back to file mtime
        if "issued_at" in li:
            issued = datetime.datetime.fromisoformat(li["issued_at"])
        else:
            issued = datetime.datetime.fromtimestamp(SOCIAL_CREDS.stat().st_mtime)
        expiry     = issued + datetime.timedelta(seconds=expires_in)
        hours_left = (expiry - datetime.datetime.now()).total_seconds() / 3600
        return expiry, hours_left
    except Exception as e:
        print(f"  [LinkedIn] expiry check error: {e}")
        return None, None


def linkedin_auto_renew():
    """
    Try to refresh the LinkedIn access token using stored refresh_token.
    Returns (success: bool, message: str).
    """
    if not SOCIAL_CREDS.exists():
        return False, "credentials file missing"
    try:
        data = json.loads(SOCIAL_CREDS.read_text(encoding="utf-8"))
        li   = data.get("linkedin", {})
        refresh_token = li.get("refresh_token", "")
        client_id     = li.get("client_id", "")
        client_secret = li.get("client_secret", "")
        if not refresh_token:
            return False, "no refresh_token stored — re-run linkedin_oauth_now.py once"

        r = requests.post(
            "https://www.linkedin.com/oauth/v2/accessToken",
            data={
                "grant_type":    "refresh_token",
                "refresh_token": refresh_token,
                "client_id":     client_id,
                "client_secret": client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=20,
        )
        resp = r.json()
        if "access_token" not in resp:
            return False, resp.get("error_description", resp.get("error", str(resp)))

        li["access_token"]  = resp["access_token"]
        li["expires_in"]    = resp.get("expires_in", li["expires_in"])
        li["issued_at"]     = datetime.datetime.now().isoformat()
        if resp.get("refresh_token"):
            li["refresh_token"] = resp["refresh_token"]
        data["linkedin"] = li
        SOCIAL_CREDS.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        days = li["expires_in"] // 86400
        return True, f"renewed — new token valid for ~{days} days"
    except Exception as e:
        return False, str(e)


# ── YouTube ──────────────────────────────────────────────────────────────────────

def youtube_auto_renew():
    """
    Try to refresh the YouTube access token using the stored refresh_token.
    Returns (success: bool, message: str).
    """
    if not YOUTUBE_TOKEN.exists():
        return False, "youtube_token.json not found"
    try:
        td            = json.loads(YOUTUBE_TOKEN.read_text(encoding="utf-8"))
        refresh_token = td.get("refresh_token")
        client_id     = td.get("client_id")
        client_secret = td.get("client_secret")
        token_uri     = td.get("token_uri", "https://oauth2.googleapis.com/token")
        if not refresh_token:
            return False, "no refresh_token in youtube_token.json"

        # Try google-auth library first
        try:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request as GRequest
            creds = Credentials(
                token=td.get("token"), refresh_token=refresh_token,
                token_uri=token_uri, client_id=client_id, client_secret=client_secret,
                scopes=td.get("scopes"),
            )
            creds.refresh(GRequest())
            td["token"]         = creds.token
            td["refresh_token"] = creds.refresh_token or refresh_token
            YOUTUBE_TOKEN.write_text(json.dumps(td, indent=2), encoding="utf-8")
            return True, "access token refreshed (google-auth)"
        except ImportError:
            pass
        except Exception as e:
            if "invalid_grant" in str(e):
                return False, "invalid_grant — refresh token revoked, run auth_youtube.py"
            raise

        # Fallback: raw HTTP
        resp = requests.post(token_uri, data={
            "client_id": client_id, "client_secret": client_secret,
            "refresh_token": refresh_token, "grant_type": "refresh_token",
        }, timeout=20).json()
        if "error" in resp:
            if resp["error"] == "invalid_grant":
                return False, "invalid_grant — refresh token revoked, run auth_youtube.py"
            return False, f"{resp['error']}: {resp.get('error_description','')}"
        td["token"] = resp.get("access_token", td.get("token"))
        YOUTUBE_TOKEN.write_text(json.dumps(td, indent=2), encoding="utf-8")
        return True, "access token refreshed (HTTP)"
    except Exception as e:
        return False, str(e)


# ── Main ─────────────────────────────────────────────────────────────────────────

def main():
    print(f"\n{'='*52}")
    print(f"  BootHop Token Monitor — {datetime.datetime.now():%Y-%m-%d %H:%M}")
    print(f"{'='*52}\n")

    DATA.mkdir(exist_ok=True)

    # Check if user pressed Stop in Telegram since last run
    check_for_stop_press()

    alert_needed = False

    # ── YouTube — silent auto-renew only, no time-based expiry window ─────────
    # YouTube refresh tokens don't expire on a schedule; just keep them fresh.
    # No Telegram alert — if it ever breaks, the pipeline action report flags it.
    print("[YouTube] Auto-refreshing access token...")
    yt_ok, yt_msg = youtube_auto_renew()
    if yt_ok:
        print(f"  YouTube: ✅ {yt_msg}")
    else:
        print(f"  YouTube: ❌ {yt_msg} (no alert — fix via setup_youtube.py)")

    # ── LinkedIn — alert ONLY if within 48 hrs AND auto-renew can't save it ──
    print("[LinkedIn] Checking expiry...")
    li_expiry, li_hours = linkedin_expiry()

    if li_hours is None:
        print("  LinkedIn: unable to determine expiry")

    elif li_hours > ALERT_HOURS:
        days = int(li_hours // 24)
        print(f"  LinkedIn: healthy ({days}d left) — no action needed")

    else:
        # Within 48 hours: try auto-renew first
        print(f"  LinkedIn: expiring in {li_hours:.0f}h — attempting auto-renew...")
        ok, msg = linkedin_auto_renew()
        if ok:
            # Auto-renew succeeded — token extended, no alert needed
            print(f"  LinkedIn: ✅ auto-renewed — {msg}")
        else:
            # Auto-renew failed and we're in the 48-hour window — alert
            print(f"  LinkedIn: ⚠️  auto-renew failed — {msg}")
            alert_needed = True

            if not is_paused():
                hours_str = f"{li_hours:.0f}h" if li_hours > 0 else "EXPIRED"
                text = (
                    f"🔑 *LinkedIn token alert*\n\n"
                    f"Expires in *{hours_str}* — auto-renew failed.\n"
                    f"{msg}\n\n"
                    f"→ Run `python scripts/linkedin_oauth_now.py` to re-authenticate."
                )
                stop_btn = {"inline_keyboard": [[
                    {"text": "🔇 Stop alerts (24h)", "callback_data": "stop_token_alert"}
                ]]}
                tg_send(text, markup=stop_btn)
                print("  [Alert] Sent to Telegram.")
            else:
                print("  [Alerts] Paused — skipping Telegram message.")

    if not alert_needed:
        print("\n  All tokens healthy — no alert sent.")

    print(f"\n{'='*52}\n")


if __name__ == "__main__":
    main()
