"""
BootHop OAuth Setup
====================
Walks through OAuth for TikTok, Instagram (Meta), and LinkedIn.
Runs a local server on port 8080 to catch the callback automatically.

Run:
  python scripts/setup_oauth.py --platform tiktok
  python scripts/setup_oauth.py --platform instagram
  python scripts/setup_oauth.py --platform linkedin
  python scripts/setup_oauth.py --all
"""

import sys, json, argparse, secrets, webbrowser, urllib.parse, time
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread

import requests

BASE        = Path(__file__).parent.parent
CREDS_FILE  = Path(__file__).parent / "social_credentials.json"
REDIRECT    = "http://localhost:8080/callback"

# Force UTF-8
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# ── Credentials helpers ───────────────────────────────────────────────────────

def load_creds():
    if CREDS_FILE.exists():
        return json.loads(CREDS_FILE.read_text(encoding="utf-8"))
    return {}


def save_creds(creds):
    CREDS_FILE.write_text(json.dumps(creds, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  Saved to {CREDS_FILE}")


# ── Local callback server ─────────────────────────────────────────────────────

_callback_result = {"code": None, "state": None, "error": None}


class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if "code" in params:
            _callback_result["code"]  = params["code"][0]
            _callback_result["state"] = params.get("state", [None])[0]
            body = b"<h2>Success! You can close this tab and return to the terminal.</h2>"
        elif "error" in params:
            _callback_result["error"] = params.get("error_description", params["error"])[0]
            body = b"<h2>Auth failed. Check the terminal for details.</h2>"
        else:
            body = b"<h2>Waiting...</h2>"

        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass   # suppress server logs


def wait_for_callback(timeout=120):
    """Start local server, wait for OAuth callback, return code."""
    server = HTTPServer(("localhost", 8080), CallbackHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"  Listening on http://localhost:8080/callback ...")

    start = time.time()
    while not _callback_result["code"] and not _callback_result["error"]:
        if time.time() - start > timeout:
            server.shutdown()
            raise TimeoutError("Timed out waiting for OAuth callback (2 minutes)")
        time.sleep(0.5)

    server.shutdown()

    if _callback_result["error"]:
        raise RuntimeError(f"OAuth error: {_callback_result['error']}")

    return _callback_result["code"]


# ── TikTok OAuth ──────────────────────────────────────────────────────────────

def setup_tiktok():
    creds = load_creds()
    tk    = creds.get("tiktok", {})

    print("\n" + "=" * 56)
    print("  TikTok OAuth Setup")
    print("=" * 56)
    print("""
WHERE TO GET YOUR CLIENT KEY AND SECRET:
  1. Go to: https://developers.tiktok.com/apps/
  2. Click your app (ID: 7643480133617436673)
  3. Under 'App info' → copy Client Key and Client Secret
  4. Make sure these scopes are enabled in your app:
       video.publish   video.upload   user.info.basic
  5. Add this as an allowed redirect URI in your app:
       http://localhost:8080/callback
""")

    client_key    = tk.get("client_key", "").strip()
    client_secret = tk.get("client_secret", "").strip()

    if not client_key:
        client_key = input("  Paste your TikTok Client Key:    ").strip()
    else:
        print(f"  Client Key: {client_key[:8]}... (already set)")
        use = input("  Use existing key? [Y/n]: ").strip().lower()
        if use == "n":
            client_key = input("  New Client Key: ").strip()

    if not client_secret:
        client_secret = input("  Paste your TikTok Client Secret: ").strip()
    else:
        print(f"  Client Secret: {client_secret[:4]}... (already set)")
        use = input("  Use existing secret? [Y/n]: ").strip().lower()
        if use == "n":
            client_secret = input("  New Client Secret: ").strip()

    if not client_key or not client_secret:
        print("  Client Key and Secret are required. Skipping TikTok setup.")
        return

    state   = secrets.token_urlsafe(16)
    scopes  = "video.publish,video.upload,user.info.basic"
    auth_url = (
        "https://www.tiktok.com/v2/auth/authorize/?"
        + urllib.parse.urlencode({
            "client_key":    client_key,
            "response_type": "code",
            "scope":         scopes,
            "redirect_uri":  REDIRECT,
            "state":         state,
        })
    )

    # Reset callback state
    _callback_result.update({"code": None, "state": None, "error": None})

    print(f"\n  Opening TikTok login in your browser...")
    print(f"  URL: {auth_url[:80]}...")
    webbrowser.open(auth_url)
    print("  (Log in with your TikTok account and approve access)")

    try:
        code = wait_for_callback()
    except (TimeoutError, RuntimeError) as e:
        print(f"  {e}")
        return

    # Exchange code for tokens
    print("\n  Exchanging code for access token...")
    r = requests.post(
        "https://open.tiktokapis.com/v2/oauth/token/",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "client_key":    client_key,
            "client_secret": client_secret,
            "code":          code,
            "grant_type":    "authorization_code",
            "redirect_uri":  REDIRECT,
        },
        timeout=30,
    )
    data = r.json()

    if "data" in data and "access_token" in data["data"]:
        tokens = data["data"]
        creds.setdefault("tiktok", {}).update({
            "client_key":    client_key,
            "client_secret": client_secret,
            "access_token":  tokens["access_token"],
            "refresh_token": tokens.get("refresh_token", ""),
            "open_id":       tokens.get("open_id", ""),
            "expires_in":    tokens.get("expires_in", 0),
        })
        save_creds(creds)
        print(f"  TikTok access token saved. Expires in {tokens.get('expires_in', '?')}s")
        print(f"  Open ID: {tokens.get('open_id', '?')}")
    else:
        print(f"  Token exchange failed: {data}")


# ── Instagram / Meta OAuth ────────────────────────────────────────────────────

def setup_instagram():
    creds = load_creds()
    ig    = creds.get("instagram", {})

    print("\n" + "=" * 56)
    print("  Instagram (Meta) OAuth Setup")
    print("=" * 56)
    print("""
WHERE TO GET YOUR APP ID AND SECRET:
  1. Go to: https://developers.facebook.com/apps/
  2. Create an app (type: Business) or use existing
  3. Under 'Settings' > 'Basic' → copy App ID and App Secret
  4. Add 'Instagram Graph API' product to your app
  5. Under Facebook Login > Settings, add this to
     'Valid OAuth Redirect URIs':
       http://localhost:8080/callback
  6. Your Instagram account must be a Business or Creator account
     linked to a Facebook Page.
""")

    app_id     = ig.get("app_id", "").strip()
    app_secret = ig.get("app_secret", "").strip()

    if not app_id:
        app_id = input("  Paste your Facebook App ID:     ").strip()
    else:
        print(f"  App ID: {app_id} (already set)")
        use = input("  Use existing? [Y/n]: ").strip().lower()
        if use == "n":
            app_id = input("  New App ID: ").strip()

    if not app_secret:
        app_secret = input("  Paste your Facebook App Secret: ").strip()
    else:
        print(f"  App Secret: {app_secret[:4]}... (already set)")
        use = input("  Use existing? [Y/n]: ").strip().lower()
        if use == "n":
            app_secret = input("  New App Secret: ").strip()

    if not app_id or not app_secret:
        print("  App ID and Secret required. Skipping.")
        return

    state    = secrets.token_urlsafe(16)
    scopes   = "instagram_basic,instagram_content_publish,pages_show_list,pages_read_engagement,business_management"
    auth_url = (
        "https://www.facebook.com/v19.0/dialog/oauth?"
        + urllib.parse.urlencode({
            "client_id":     app_id,
            "redirect_uri":  REDIRECT,
            "scope":         scopes,
            "response_type": "code",
            "state":         state,
        })
    )

    _callback_result.update({"code": None, "state": None, "error": None})

    print(f"\n  Opening Facebook/Instagram login in your browser...")
    webbrowser.open(auth_url)
    print("  (Log in with the Facebook account linked to your Instagram Business page)")

    try:
        code = wait_for_callback()
    except (TimeoutError, RuntimeError) as e:
        print(f"  {e}")
        return

    # Exchange for short-lived token
    print("\n  Exchanging code for access token...")
    r = requests.get(
        "https://graph.facebook.com/v19.0/oauth/access_token",
        params={
            "client_id":     app_id,
            "client_secret": app_secret,
            "redirect_uri":  REDIRECT,
            "code":          code,
        },
        timeout=30,
    )
    data = r.json()
    short_token = data.get("access_token")
    if not short_token:
        print(f"  Token exchange failed: {data}")
        return

    # Exchange for long-lived token (60 days)
    print("  Upgrading to long-lived token (60 days)...")
    r2 = requests.get(
        "https://graph.facebook.com/v19.0/oauth/access_token",
        params={
            "grant_type":        "fb_exchange_token",
            "client_id":         app_id,
            "client_secret":     app_secret,
            "fb_exchange_token": short_token,
        },
        timeout=30,
    )
    ll = r2.json()
    long_token = ll.get("access_token", short_token)

    # Get IG User ID from linked pages
    print("  Fetching Instagram Business account ID...")
    r3 = requests.get(
        "https://graph.facebook.com/v19.0/me/accounts",
        params={"access_token": long_token},
        timeout=30,
    )
    pages = r3.json().get("data", [])
    ig_user_id = ""
    for page in pages:
        r4 = requests.get(
            f"https://graph.facebook.com/v19.0/{page['id']}",
            params={"fields": "instagram_business_account", "access_token": page["access_token"]},
            timeout=30,
        )
        iba = r4.json().get("instagram_business_account", {})
        if iba.get("id"):
            ig_user_id = iba["id"]
            print(f"  Found IG Business Account: {ig_user_id}")
            break

    if not ig_user_id:
        ig_user_id = input("  Could not auto-detect IG User ID. Paste it manually (or leave blank): ").strip()

    creds.setdefault("instagram", {}).update({
        "app_id":       app_id,
        "app_secret":   app_secret,
        "access_token": long_token,
        "ig_user_id":   ig_user_id,
    })
    save_creds(creds)
    print(f"  Instagram long-lived token saved (valid ~60 days).")
    print(f"  IG User ID: {ig_user_id or '(not set — add manually)'}")
    print(f"  NOTE: Run this again before the token expires in 60 days.")


# ── LinkedIn OAuth ────────────────────────────────────────────────────────────

def setup_linkedin():
    creds = load_creds()
    li    = creds.get("linkedin", {})

    print("\n" + "=" * 56)
    print("  LinkedIn OAuth Setup")
    print("=" * 56)
    print("""
WHERE TO GET YOUR CLIENT ID AND SECRET:
  1. Go to: https://www.linkedin.com/developers/apps
  2. Create or select your app
  3. Under 'Auth' tab → copy Client ID and Client Secret
  4. Add this as an Authorized Redirect URL:
       http://localhost:8080/callback
  5. Under 'Products', request access to:
       Share on LinkedIn  +  Sign In with LinkedIn
""")

    client_id     = input("  Paste your LinkedIn Client ID:     ").strip()
    client_secret = input("  Paste your LinkedIn Client Secret: ").strip()

    if not client_id or not client_secret:
        print("  Client ID and Secret required. Skipping.")
        return

    state    = secrets.token_urlsafe(16)
    auth_url = (
        "https://www.linkedin.com/oauth/v2/authorization?"
        + urllib.parse.urlencode({
            "response_type": "code",
            "client_id":     client_id,
            "redirect_uri":  REDIRECT,
            "state":         state,
            "scope":         "w_member_social r_liteprofile",
        })
    )

    _callback_result.update({"code": None, "state": None, "error": None})

    print(f"\n  Opening LinkedIn login in your browser...")
    webbrowser.open(auth_url)

    try:
        code = wait_for_callback()
    except (TimeoutError, RuntimeError) as e:
        print(f"  {e}")
        return

    print("\n  Exchanging code for access token...")
    r = requests.post(
        "https://www.linkedin.com/oauth/v2/accessToken",
        data={
            "grant_type":    "authorization_code",
            "code":          code,
            "redirect_uri":  REDIRECT,
            "client_id":     client_id,
            "client_secret": client_secret,
        },
        timeout=30,
    )
    data = r.json()
    token = data.get("access_token")
    if not token:
        print(f"  Token exchange failed: {data}")
        return

    # Get person URN
    r2 = requests.get(
        "https://api.linkedin.com/v2/me",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    profile    = r2.json()
    person_urn = f"urn:li:person:{profile.get('id', '')}"
    print(f"  Person URN: {person_urn}")

    creds.setdefault("linkedin", {}).update({
        "client_id":     client_id,
        "client_secret": client_secret,
        "access_token":  token,
        "person_urn":    person_urn,
        "expires_in":    data.get("expires_in", 0),
    })
    save_creds(creds)
    print(f"  LinkedIn token saved. Expires in {data.get('expires_in', '?')}s (~60 days).")


# ── Status check ──────────────────────────────────────────────────────────────

def show_status():
    creds = load_creds()
    print("\n  Credential Status:")
    print("  " + "-" * 40)

    def check(platform, fields):
        cfg    = creds.get(platform, {})
        filled = [f for f in fields if cfg.get(f, "").strip()]
        status = "OK" if len(filled) == len(fields) else f"missing: {', '.join(f for f in fields if not cfg.get(f,'').strip())}"
        icon   = "✓" if len(filled) == len(fields) else "✗"
        print(f"  {icon}  {platform:<12} {status}")

    check("tiktok",    ["client_key", "client_secret", "access_token"])
    check("instagram", ["app_id", "app_secret", "access_token", "ig_user_id"])
    check("linkedin",  ["access_token", "person_urn"])
    check("youtube",   ["api_key"])
    print()


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="BootHop OAuth Setup")
    parser.add_argument("--platform", choices=["tiktok", "instagram", "linkedin", "all"],
                        default=None, help="Which platform to set up")
    parser.add_argument("--status", action="store_true", help="Show credential status")
    args = parser.parse_args()

    print("\n" + "=" * 56)
    print("  BootHop — Social Media OAuth Setup")
    print("=" * 56)

    show_status()

    if args.status:
        return

    platform = args.platform
    if not platform:
        print("  Which platform do you want to set up?")
        print("  1) TikTok")
        print("  2) Instagram")
        print("  3) LinkedIn")
        print("  4) All")
        choice = input("\n  Enter number: ").strip()
        platform = {"1": "tiktok", "2": "instagram", "3": "linkedin", "4": "all"}.get(choice)
        if not platform:
            print("  Invalid choice.")
            return

    if platform in ("tiktok", "all"):
        setup_tiktok()
    if platform in ("instagram", "all"):
        setup_instagram()
    if platform in ("linkedin", "all"):
        setup_linkedin()

    print("\n  Setup complete.")
    show_status()


if __name__ == "__main__":
    main()
