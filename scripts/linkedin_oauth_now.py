"""
LinkedIn OAuth — automatic local-server flow.
Usage:  python scripts/linkedin_oauth_now.py
"""

import sys, json, secrets, webbrowser, urllib.parse, threading
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CREDS_FILE = Path(__file__).parent / "social_credentials.json"
REDIRECT   = "http://localhost:8080/callback"

creds         = json.loads(CREDS_FILE.read_text(encoding="utf-8"))
CLIENT_ID     = creds["linkedin"]["client_id"]
CLIENT_SECRET = creds["linkedin"]["client_secret"]

_result = {}


class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()

        if "error" in params:
            _result["error"] = params.get("error_description", params["error"])[0]
            self.wfile.write(b"<h2>LinkedIn error. Close this tab.</h2>")
        elif "code" in params:
            _result["code"] = params["code"][0]
            self.wfile.write(b"<h2>Authorised! You can close this tab.</h2>")
        else:
            _result["error"] = "No code received"
            self.wfile.write(b"<h2>No code received.</h2>")

        threading.Thread(target=self.server.shutdown, daemon=True).start()

    def log_message(self, *args):
        pass


def run():
    state    = secrets.token_urlsafe(16)
    auth_url = (
        "https://www.linkedin.com/oauth/v2/authorization?"
        + urllib.parse.urlencode({
            "response_type": "code",
            "client_id":     CLIENT_ID,
            "redirect_uri":  REDIRECT,
            "state":         state,
            "scope":         "openid profile w_member_social",
        })
    )

    print("\n" + "=" * 60)
    print("  LinkedIn OAuth")
    print("=" * 60)
    print(f"\n  Opening browser — log in and click Allow...")
    print(f"\n  URL:\n  {auth_url}\n")
    print("  Waiting for LinkedIn redirect to localhost:8080...")

    webbrowser.open(auth_url)

    try:
        server = HTTPServer(("localhost", 8080), CallbackHandler)
        server.serve_forever()
    except OSError as e:
        print(f"\n  ERROR: Port 8080 in use. Close other apps and retry.\n  {e}")
        return

    if "error" in _result:
        print(f"\n  ERROR: {_result['error']}")
        return

    code = _result.get("code")
    if not code:
        print("\n  ERROR: No code received.")
        return

    print(f"\n  Code received. Exchanging for token...")

    r = requests.post(
        "https://www.linkedin.com/oauth/v2/accessToken",
        data={
            "grant_type":    "authorization_code",
            "code":          code,
            "redirect_uri":  REDIRECT,
            "client_id":     CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )

    data = r.json()
    print(f"\n  Token response: {json.dumps(data, indent=2)}\n")

    access_token = data.get("access_token", "")
    if not access_token:
        print("  ERROR: No access token returned.")
        return

    # Get person URN
    me = requests.get(
        "https://api.linkedin.com/v2/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=15,
    ).json()
    print(f"  Profile: {me}")

    person_urn = me.get("sub", "")

    import datetime
    update = {
        "access_token": access_token,
        "person_urn":   f"urn:li:person:{person_urn}" if person_urn else "",
        "expires_in":   data.get("expires_in", 0),
        "issued_at":    datetime.datetime.now().isoformat(),
    }
    if data.get("refresh_token"):
        update["refresh_token"] = data["refresh_token"]
    creds["linkedin"].update(update)
    CREDS_FILE.write_text(json.dumps(creds, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n  SUCCESS!")
    print(f"  Access Token : {access_token[:30]}...")
    print(f"  Person URN   : urn:li:person:{person_urn}")
    print(f"  Expires      : {data.get('expires_in', 0) // 86400} days")
    print(f"  Saved to     : {CREDS_FILE}")
    print("=" * 60)


if __name__ == "__main__":
    run()
