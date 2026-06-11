"""
post_job.py  — Post a new BootHop job listing to Facebook + WhatsApp

Usage:
    python scripts/post_job.py "Courier Driver Needed - London" "Full description..."
    python scripts/post_job.py  (uses interactive prompt)

Posts to:
  • Facebook Page (requires PAGE_ACCESS_TOKEN + PAGE_ID in .env)
  • WhatsApp broadcast to operator number (+44-7405-746302)

.env keys required:
    WHATSAPP_ACCESS_TOKEN=...
    WHATSAPP_PHONE_NUMBER_ID=...
    FACEBOOK_PAGE_ACCESS_TOKEN=...
    FACEBOOK_PAGE_ID=...
"""

import sys
import json
import requests
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).resolve().parent.parent

# Load .env
_wa_token = _wa_phone_id = _fb_token = _fb_page_id = ""
_env = BASE / ".env"
if _env.exists():
    for _line in _env.read_text(encoding="utf-8").splitlines():
        if "=" in _line and not _line.startswith("#"):
            k, v = _line.split("=", 1)
            k, v = k.strip(), v.strip()
            if k == "WHATSAPP_ACCESS_TOKEN":        _wa_token    = v
            if k == "WHATSAPP_PHONE_NUMBER_ID":     _wa_phone_id = v
            if k == "FACEBOOK_PAGE_ACCESS_TOKEN":   _fb_token    = v
            if k == "FACEBOOK_PAGE_ID":             _fb_page_id  = v

OPERATOR_WA = "447405746302"


def post_to_facebook(title: str, body: str) -> bool:
    if not _fb_token or not _fb_page_id:
        print("  [Facebook] Not configured — set FACEBOOK_PAGE_ACCESS_TOKEN and FACEBOOK_PAGE_ID in .env")
        return False
    message = f"{title}\n\n{body}\n\nApply at: https://www.boothop.com/couriers"
    try:
        r = requests.post(
            f"https://graph.facebook.com/v18.0/{_fb_page_id}/feed",
            params={"access_token": _fb_token},
            json={"message": message},
            timeout=20,
        )
        if r.ok:
            post_id = r.json().get("id", "")
            print(f"  [Facebook] Posted: {post_id}")
            return True
        print(f"  [Facebook] Failed ({r.status_code}): {r.text[:200]}")
        return False
    except Exception as e:
        print(f"  [Facebook] Error: {e}")
        return False


def post_to_whatsapp(title: str, body: str) -> bool:
    if not _wa_token or not _wa_phone_id:
        print("  [WhatsApp] Not configured — set WHATSAPP_ACCESS_TOKEN and WHATSAPP_PHONE_NUMBER_ID in .env")
        return False
    text = (
        f"🚀 NEW JOB — BootHop\n\n"
        f"{title}\n\n"
        f"{body}\n\n"
        f"Apply: https://www.boothop.com/couriers\n"
        f"📅 {datetime.now().strftime('%d %b %Y')}"
    )
    try:
        r = requests.post(
            f"https://graph.facebook.com/v18.0/{_wa_phone_id}/messages",
            headers={
                "Authorization": f"Bearer {_wa_token}",
                "Content-Type": "application/json",
            },
            json={
                "messaging_product": "whatsapp",
                "to": OPERATOR_WA,
                "type": "text",
                "text": {"body": text[:4096]},
            },
            timeout=20,
        )
        if r.ok:
            print(f"  [WhatsApp] Sent to +44-7405-746302")
            return True
        print(f"  [WhatsApp] Failed ({r.status_code}): {r.text[:200]}")
        return False
    except Exception as e:
        print(f"  [WhatsApp] Error: {e}")
        return False


def main():
    if len(sys.argv) >= 3:
        title = sys.argv[1]
        body  = sys.argv[2]
    elif len(sys.argv) == 2:
        title = sys.argv[1]
        body  = input("Job description: ").strip()
    else:
        print("BootHop Job Poster")
        title = input("Job title: ").strip()
        body  = input("Description: ").strip()

    if not title:
        print("No title — nothing posted.")
        return

    print(f"\n[Job Post] {datetime.now().strftime('%d %b %Y %H:%M')}")
    print(f"  Title: {title}")

    fb_ok = post_to_facebook(title, body)
    wa_ok = post_to_whatsapp(title, body)

    print(f"\n  Facebook : {'✅' if fb_ok else '❌'}")
    print(f"  WhatsApp : {'✅' if wa_ok else '❌'}")


if __name__ == "__main__":
    main()
