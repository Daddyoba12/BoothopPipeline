"""
Upload ALL past BootHop pipeline videos to YouTube.
Skips any already uploaded (checks for _youtube.txt sidecar file).
"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(__file__))
from upload_to_youtube import upload_video
from pathlib import Path
import re, time

OUT = Path(r"C:\Users\babso\Desktop\BootHopPipeline\output")

def make_title(filename):
    name = filename.stem
    m = re.search(r'(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})', name)
    date_str = ""
    version  = ""
    if m:
        y, mo, d, h, mi = m.groups()
        try:
            from datetime import datetime
            dt = datetime.strptime(f"{y}{mo}{d}", "%Y%m%d")
            date_str = dt.strftime("%d %b %Y")
        except:
            date_str = f"{d}/{mo}/{y}"

    if "v1_archive" in name:
        version = "v1"
    elif "v2_trending" in name:
        version = "v2"
    elif "story" in name:
        version = "v3"
    elif "linkedin" in name:
        version = "v4"
    elif "history" in name:
        version = "v5"
    elif "investor" in name:
        version = "v6"

    if date_str and version:
        return f"BootHop {date_str} {version}"
    elif date_str:
        return f"BootHop {date_str}"
    else:
        return f"BootHop Demo"

# Collect all MP4s, oldest first
all_videos = sorted(
    [f for f in OUT.rglob("*.mp4")],
    key=lambda f: f.stat().st_mtime
)

# Skip already uploaded
to_upload = []
for v in all_videos:
    sidecar = v.parent / (v.stem + "_youtube.txt")
    if not sidecar.exists():
        to_upload.append(v)

print(f"Found {len(all_videos)} total videos.")
print(f"Already uploaded: {len(all_videos) - len(to_upload)}")
print(f"To upload now:    {len(to_upload)}")
print()

if not to_upload:
    print("All videos already on YouTube.")
    sys.exit(0)

for i, video in enumerate(to_upload, 1):
    title = make_title(video)
    print(f"[{i}/{len(to_upload)}] {video.name}")
    print(f"  Title: {title}")
    url = upload_video(str(video), title)
    if url:
        print(f"  ✓ {url}")
    else:
        print(f"  ✗ Failed — will retry next run")
    print()
    # Small pause between uploads to avoid rate limits
    if i < len(to_upload):
        time.sleep(3)

print("Batch upload complete.")
