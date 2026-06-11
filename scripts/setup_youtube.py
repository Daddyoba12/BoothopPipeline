"""
BootHop YouTube Setup — run this ONCE to authenticate.
Credentials already saved. Just sign in with Google when the browser opens.
"""
import json
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES     = ["https://www.googleapis.com/auth/youtube.upload",
               "https://www.googleapis.com/auth/youtube"]
BASE       = Path(__file__).parent
CREDS_FILE = BASE / "youtube_credentials.json"
TOKEN_FILE = BASE / "youtube_token.json"

print()
print("=" * 60)
print("  BootHop YouTube Auto-Post Setup")
print("=" * 60)
print()
print("Opening your browser now...")
print("Sign in with daddyoba12@gmail.com and click Allow.")
print()

flow  = InstalledAppFlow.from_client_secrets_file(str(CREDS_FILE), SCOPES)
creds = flow.run_local_server(port=0, open_browser=True)

token_data = {
    "token":         creds.token,
    "refresh_token": creds.refresh_token,
    "token_uri":     creds.token_uri,
    "client_id":     creds.client_id,
    "client_secret": creds.client_secret,
    "scopes":        list(creds.scopes),
}
TOKEN_FILE.write_text(json.dumps(token_data, indent=2), encoding="utf-8")

print()
print("=" * 60)
print("  YouTube connected!")
print("  Every video the pipeline generates will now upload")
print("  to YouTube automatically. Nothing else needed.")
print("=" * 60)
print()
