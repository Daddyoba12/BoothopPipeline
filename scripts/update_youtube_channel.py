"""
Update YouTube channel description + rename investor demo videos.
Run once.
"""
import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, __import__('os').path.dirname(__file__))
from pathlib import Path
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

TOKEN_FILE = Path(__file__).parent / "youtube_token.json"

def get_youtube():
    data  = json.loads(TOKEN_FILE.read_text(encoding='utf-8'))
    creds = Credentials(
        token=data['token'], refresh_token=data['refresh_token'],
        token_uri=data['token_uri'], client_id=data['client_id'],
        client_secret=data['client_secret'], scopes=data['scopes']
    )
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        data['token'] = creds.token
        TOKEN_FILE.write_text(json.dumps(data, indent=2), encoding='utf-8')
    return build('youtube', 'v3', credentials=creds)

yt = get_youtube()

# ── 1. Update channel description ────────────────────────────────────────────
print("Updating channel description...")
channels = yt.channels().list(part='snippet,brandingSettings', mine=True).execute()
channel  = channels['items'][0]
channel_id = channel['id']
print(f"  Channel ID: {channel_id}")

desc = """BootHop — Same-day and cross-border delivery powered by verified travellers, AI customs screening, and Stripe escrow.

Serving diaspora corridors and businesses across the UK and Europe.

Website:   https://www.boothop.co.uk
Business:  https://www.boothop.co.uk/business
TikTok:    https://www.tiktok.com/@boothop
LinkedIn:  https://www.linkedin.com/company/boothop-business
Instagram: https://www.instagram.com/boothop.com1
Contact:   +44 7506 553 755  |  titi.olufeko@boothop.com"""

yt.channels().update(
    part='brandingSettings',
    body={
        'id': channel_id,
        'brandingSettings': {
            'channel': {
                'description': desc,
                'keywords': 'boothop logistics delivery diaspora UK Nigeria same-day',
                'defaultLanguage': 'en-GB',
            }
        }
    }
).execute()
print("  Channel description updated with all social links")

# ── 2. Rename investor demo videos ───────────────────────────────────────────
print("\nRenaming investor demo videos...")
# Search for videos with 'Investor Demo' in title
videos = yt.search().list(
    part='snippet', forMine=True, type='video',
    q='Investor Demo', maxResults=10
).execute()

renamed = 0
for item in videos.get('items', []):
    vid_id = item['id']['videoId']
    old_title = item['snippet']['title']
    if 'Investor' in old_title or 'Compliance' in old_title:
        published = item['snippet']['publishedAt'][:10].replace('-', '')
        try:
            from datetime import datetime
            dt = datetime.strptime(published, '%Y%m%d')
            date_str = dt.strftime('%d %b %Y')
        except:
            date_str = published
        new_title = f"BootHop {date_str} v6"
        yt.videos().update(
            part='snippet',
            body={
                'id': vid_id,
                'snippet': {
                    'title': new_title,
                    'categoryId': '22',
                    'description': item['snippet']['description'],
                    'tags': ['boothop', 'logistics', 'delivery'],
                }
            }
        ).execute()
        print(f"  Renamed: {old_title[:50]} -> {new_title}")
        renamed += 1

if renamed == 0:
    print("  No investor demo videos found to rename (may already be renamed)")

print(f"\nDone. Channel URL: https://www.youtube.com/channel/{channel_id}")
