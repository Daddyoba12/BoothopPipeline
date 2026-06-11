"""Upload all of today's BootHop videos to YouTube."""
import sys, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(__file__))
from upload_to_youtube import upload_video
from pathlib import Path
from datetime import datetime

OUT = Path(r"C:\Users\babso\Desktop\BootHopPipeline\output")
today = datetime.now().strftime("%Y%m%d")

videos = [
    (f"boothop_premium_{today}_081343_v1_archive.mp4",   "BootHop | Same-Day Delivery | Morning Reel (Archive Mix)"),
    (f"boothop_premium_{today}_081343_v2_trending.mp4",  "BootHop | Same-Day Delivery | Morning Reel (Trending Mix)"),
    (f"boothop_story_{today}_081415.mp4",                "BootHop | London to Lagos | City Story"),
    (f"boothop_linkedin_{today}_113307.mp4",             "BootHop | Supply Chain Insights | 18 May 2026"),
    (f"boothop_premium_{today}_140217_v1_archive.mp4",   "BootHop | Verified Delivery | Afternoon Reel (Archive Mix)"),
    (f"boothop_premium_{today}_140217_v2_trending.mp4",  "BootHop | Verified Delivery | Afternoon Reel (Trending Mix)"),
    (f"boothop_story_{today}_140238.mp4",                "BootHop | Community Delivery | City Story"),
]

print(f"Uploading {len(videos)} videos to YouTube...\n")
for filename, title in videos:
    path = OUT / filename
    if path.exists():
        url = upload_video(str(path), title)
        if url:
            print(f"✓ {title}")
            print(f"  {url}\n")
    else:
        print(f"✗ Not found: {filename}")

print("All done. Check your YouTube channel.")
