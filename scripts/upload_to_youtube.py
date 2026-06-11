"""
BootHop YouTube Uploader
Called automatically by the pipeline after every video render.
Usage: python upload_to_youtube.py <video_file> <title> <description> <tags>
"""
import sys, json, time
from pathlib import Path
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

BASE       = Path(__file__).parent
TOKEN_FILE = BASE / "youtube_token.json"
LOG_FILE   = BASE.parent / "output" / "youtube_log.txt"

# ── Default channel metadata ───────────────────────────────────────────────
DEFAULT_TAGS = [
    "BootHop", "logistics", "same day delivery", "cross border delivery",
    "UK Nigeria delivery", "diaspora delivery", "London Lagos",
    "compliance logistics", "verified delivery", "boothop.com",
]

DEFAULT_DESC = """BootHop — Compliance-First Distributed Logistics Network.

Same-day and cross-border delivery powered by verified movement partners,
AI-assisted customs screening, and Stripe escrow.

🌍 Serving the UK–Nigeria corridor and beyond.
✅ AI-powered customs compliance on every movement.
🔐 Stripe escrow — funds held until delivery confirmed.
📦 Verified travellers and carriers on every route.

👉 Get started: https://www.boothop.co.uk
💼 Business logistics: https://www.boothop.co.uk/business
📞 Call us: +44 7506 553 755
📧 titi.olufeko@boothop.com

#BootHop #Logistics #SameDayDelivery #UKNigeria #LondonLagos
#DiasporaDelivery #CrossBorderLogistics #AILogistics
"""

def log(msg):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def get_credentials():
    if not TOKEN_FILE.exists():
        log("ERROR: youtube_token.json not found. Run setup_youtube.py first.")
        sys.exit(1)
    token_data = json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
    creds = Credentials(
        token=         token_data["token"],
        refresh_token= token_data["refresh_token"],
        token_uri=     token_data["token_uri"],
        client_id=     token_data["client_id"],
        client_secret= token_data["client_secret"],
        scopes=        token_data["scopes"],
    )
    # Refresh if expired
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            token_data["token"] = creds.token
            TOKEN_FILE.write_text(json.dumps(token_data, indent=2), encoding="utf-8")
        except Exception as e:
            log(f"ERROR: YouTube token refresh failed — {e}")
            log("Run: python scripts/setup_youtube.py  to re-authenticate")
            sys.exit(1)
    return creds

def upload_video(video_path, title, description=None, tags=None, category_id="22", privacy="public"):
    """
    Upload a video to YouTube.
    category_id 22 = People & Blogs (good for business/lifestyle content)
    category_id 19 = Travel & Events
    category_id 28 = Science & Technology
    privacy: 'public', 'unlisted', 'private'
    """
    if not Path(video_path).exists():
        log(f"ERROR: Video file not found: {video_path}")
        return None

    log(f"Uploading to YouTube: {Path(video_path).name}")
    log(f"  Title: {title}")

    creds   = get_credentials()
    youtube = build("youtube", "v3", credentials=creds)

    body = {
        "snippet": {
            "title":       title[:100],   # YouTube max 100 chars
            "description": description or DEFAULT_DESC,
            "tags":        tags or DEFAULT_TAGS,
            "categoryId":  category_id,
        },
        "status": {
            "privacyStatus":          privacy,
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(
        video_path,
        mimetype="video/mp4",
        resumable=True,
        chunksize=5 * 1024 * 1024,  # 5 MB chunks
    )

    request = youtube.videos().insert(
        part=",".join(body.keys()),
        body=body,
        media_body=media,
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            pct = int(status.progress() * 100)
            log(f"  Uploading... {pct}%")

    video_id  = response["id"]
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    log(f"  UPLOADED: {video_url}")

    # Save URL to a file for the pipeline to reference
    url_file = Path(video_path).parent / (Path(video_path).stem + "_youtube.txt")
    url_file.write_text(video_url, encoding="utf-8")

    return video_url

# ── CLI entry point ────────────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python upload_to_youtube.py <video_file> <title> [description]")
        sys.exit(1)

    video_file  = sys.argv[1]
    title       = sys.argv[2]
    description = sys.argv[3] if len(sys.argv) > 3 else DEFAULT_DESC

    url = upload_video(video_file, title, description)
    if url:
        print(f"YouTube URL: {url}")
    else:
        sys.exit(1)
