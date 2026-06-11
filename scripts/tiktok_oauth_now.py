"""
TikTok OAuth — two-step flow.

Step 1:  python scripts/tiktok_oauth_now.py --url
         Opens browser to TikTok login page.

Step 2:  python scripts/tiktok_oauth_now.py --exchange "https://boothop.com/api/auth/tiktok/callback?code=..."
         Paste the full URL from your browser after approving.
         Run within 60 seconds of approving.
"""

import sys, json, secrets, webbrowser, urllib.parse, hashlib, base64, argparse
from pathlib import Path
import requests

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE        = Path(__file__).parent.parent
CREDS_FILE  = Path(__file__).parent / "social_credentials.json"
PKCE_FILE   = BASE / "temp" / "tiktok_pkce.json"
REDIRECT    = "https://boothop.com/api/auth/tiktok/callback"

creds         = json.loads(CREDS_FILE.read_text(encoding="utf-8"))
CLIENT_KEY    = creds["tiktok"]["client_key"]
CLIENT_SECRET = creds["tiktok"]["client_secret"]


def step_url():
    state         = secrets.token_urlsafe(16)
    code_verifier = secrets.token_urlsafe(64)
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).rstrip(b"=").decode()

    PKCE_FILE.parent.mkdir(parents=True, exist_ok=True)
    PKCE_FILE.write_text(json.dumps({
        "code_verifier": code_verifier,
        "state":         state,
    }), encoding="utf-8")

    url = (
        "https://www.tiktok.com/v2/auth/authorize/?"
        + urllib.parse.urlencode({
            "client_key":            CLIENT_KEY,
            "response_type":         "code",
            "scope":                 "video.upload",
            "redirect_uri":          REDIRECT,
            "state":                 state,
            "code_challenge":        code_challenge,
            "code_challenge_method": "S256",
        })
    )

    print("\n" + "=" * 60)
    print("  TikTok OAuth — Step 1")
    print("=" * 60)
    print(f"\n  Opening browser...")
    print(f"\n  1. Log in with your TikTok Target User account")
    print(f"  2. Tap APPROVE")
    print(f"  3. Browser goes to a 404 page — that is NORMAL")
    print(f"  4. Copy the FULL URL from the address bar")
    print(f"  5. Run Step 2 IMMEDIATELY (within 60 seconds):\n")
    print(f"     python scripts/tiktok_oauth_now.py --exchange \"<paste url>\"\n")
    print("=" * 60)

    webbrowser.open(url)
    print(f"\n  URL (if browser didn't open):\n  {url}\n")


def step_exchange(redirect_url: str):
    print("\n" + "=" * 60)
    print("  TikTok OAuth — Step 2")
    print("=" * 60)

    parsed = urllib.parse.urlparse(redirect_url)
    params = urllib.parse.parse_qs(parsed.query)

    if "error" in params:
        print(f"\n  TikTok error: {params.get('error_description', params['error'])[0]}")
        return

    code = params.get("code", [None])[0]
    if not code:
        print(f"\n  No 'code' in URL. Copy the full address bar URL after approving.")
        return

    print(f"\n  Code: {code[:20]}...")

    if not PKCE_FILE.exists():
        print("  ERROR: Run --url first to generate PKCE verifier.")
        return

    pkce          = json.loads(PKCE_FILE.read_text(encoding="utf-8"))
    code_verifier = pkce["code_verifier"]

    print("  Exchanging for access token...")
    r = requests.post(
        "https://open.tiktokapis.com/v2/oauth/token/",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "client_key":    CLIENT_KEY,
            "client_secret": CLIENT_SECRET,
            "code":          code,
            "grant_type":    "authorization_code",
            "redirect_uri":  REDIRECT,
            "code_verifier": code_verifier,
        },
        timeout=30,
    )

    data = r.json()
    print(f"\n  API response:\n  {json.dumps(data, indent=2)}\n")

    tokens        = data.get("data", data)
    access_token  = tokens.get("access_token", "")
    refresh_token = tokens.get("refresh_token", "")
    open_id       = tokens.get("open_id", "")
    expires_in    = tokens.get("expires_in", 0)

    if not access_token:
        print("  ERROR: No access token. See response above.")
        return

    creds["tiktok"].update({
        "access_token":  access_token,
        "refresh_token": refresh_token,
        "open_id":       open_id,
        "expires_in":    expires_in,
    })
    CREDS_FILE.write_text(json.dumps(creds, indent=2, ensure_ascii=False), encoding="utf-8")
    PKCE_FILE.unlink(missing_ok=True)

    print(f"  SUCCESS!")
    print(f"  Access Token : {access_token[:20]}...")
    print(f"  Open ID      : {open_id}")
    print(f"  Expires      : {expires_in // 3600}h ({expires_in}s)")
    print(f"  Saved to     : {CREDS_FILE}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url",      action="store_true", help="Step 1: open browser")
    parser.add_argument("--exchange", metavar="URL",       help="Step 2: paste redirect URL")
    args = parser.parse_args()

    if args.exchange:
        step_exchange(args.exchange)
    else:
        step_url()


if __name__ == "__main__":
    main()
