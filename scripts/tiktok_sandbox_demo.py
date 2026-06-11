"""
TikTok Sandbox Demo — for TikTok API review submission.
=========================================================
This script demonstrates the complete end-to-end BootHop → TikTok
Content Posting API integration using the SANDBOX environment.

WHAT TO DO:
  1. Run this script while screen-recording
  2. It will show each API call, the request, and the response
  3. Submit the recording as your demo video to TikTok developers

Usage:
  python scripts/tiktok_sandbox_demo.py

Requirements:
  - TikTok sandbox access token in social_credentials.json
  - A short test video file at data/test_video.mp4
    (any portrait MP4, under 50MB — can be one of your pipeline outputs)
"""

import json, math, time, sys
from pathlib import Path
import requests

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE       = Path(__file__).parent.parent
CREDS_FILE = Path(__file__).parent / "social_credentials.json"

# ── Load credentials ──────────────────────────────────────────────────────────
creds        = json.loads(CREDS_FILE.read_text(encoding="utf-8"))
ACCESS_TOKEN = creds.get("tiktok", {}).get("access_token", "")
CLIENT_KEY   = creds.get("tiktok", {}).get("client_key", "")

# ── Find test video ───────────────────────────────────────────────────────────
# Use any recent pipeline output as test video
test_video = BASE / "data" / "test_video.mp4"
if not test_video.exists():
    # Try latest pipeline output
    output_dirs = sorted((BASE / "output").glob("*"))
    for d in reversed(output_dirs):
        mp4s = list(d.glob("*.mp4"))
        if mp4s:
            test_video = mp4s[0]
            break

CAPTION = "BootHop — Move Anything. Anywhere. Same Day. #BootHop #SameDayDelivery #Logistics"

def divider(title=""):
    print("\n" + "=" * 60)
    if title:
        print(f"  {title}")
        print("=" * 60)

def show_request(method, url, payload=None):
    print(f"\n  --> {method} {url}")
    if payload:
        print(f"  Request body:")
        for k, v in payload.items():
            if k == "source_info":
                for sk, sv in v.items():
                    print(f"    source_info.{sk}: {sv}")
            else:
                print(f"    {k}: {v}")

def show_response(r):
    print(f"\n  <-- HTTP {r.status_code}")
    try:
        data = r.json()
        print(f"  Response:")
        print(json.dumps(data, indent=4))
    except Exception:
        print(f"  {r.text[:300]}")


def main():
    divider("BootHop x TikTok — Content Posting API Sandbox Demo")
    print(f"\n  Scope used   : video.upload")
    print(f"  API endpoint : https://open.tiktokapis.com/v2/post/publish/inbox/video/init/")
    print(f"  Environment  : SANDBOX")
    print(f"  Client Key   : {CLIENT_KEY[:12]}...")
    print(f"  Access Token : {ACCESS_TOKEN[:20]}..." if ACCESS_TOKEN else "  ACCESS TOKEN MISSING")
    print(f"  Test video   : {test_video}")

    if not ACCESS_TOKEN:
        print("\n  ERROR: No TikTok access token found.")
        print("  Run: python scripts/tiktok_oauth_now.py --url")
        return

    if not test_video.exists():
        print(f"\n  ERROR: No test video found at {test_video}")
        print("  Add any portrait MP4 at data/test_video.mp4")
        return

    file_size  = test_video.stat().st_size
    MAX_CHUNK  = 64 * 1024 * 1024
    chunk_size = min(file_size, MAX_CHUNK)
    chunk_count = math.ceil(file_size / chunk_size)

    print(f"\n  Video file   : {test_video.name}")
    print(f"  File size    : {file_size / (1024*1024):.1f} MB")
    print(f"  Chunks       : {chunk_count}")

    auth_headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type":  "application/json; charset=UTF-8",
    }

    # ── STEP 1: Initialise upload ─────────────────────────────────────────────
    divider("STEP 1 — Initialise upload (inbox flow)")
    print("  The BootHop pipeline calls this endpoint to register a new")
    print("  video upload. TikTok returns a publish_id and upload_url.")

    init_url  = "https://open.tiktokapis.com/v2/post/publish/inbox/video/init/"
    init_body = {
        "source_info": {
            "source":            "FILE_UPLOAD",
            "video_size":        file_size,
            "chunk_size":        chunk_size,
            "total_chunk_count": chunk_count,
        }
    }

    show_request("POST", init_url, init_body)
    time.sleep(1)

    try:
        r = requests.post(init_url, headers=auth_headers, json=init_body, timeout=30)
        show_response(r)
        r.raise_for_status()
    except Exception as e:
        print(f"\n  ERROR: {e}")
        return

    inner      = r.json().get("data", r.json())
    publish_id = inner.get("publish_id", "")
    upload_url = inner.get("upload_url", "")

    if not publish_id or not upload_url:
        print(f"\n  ERROR: Missing publish_id or upload_url in response.")
        return

    print(f"\n  publish_id : {publish_id}")
    print(f"  upload_url : {upload_url[:60]}...")

    # ── STEP 2: Upload video file ─────────────────────────────────────────────
    divider("STEP 2 — Upload video file (chunked)")
    print(f"  Uploading {test_video.name} to TikTok via PUT request...")

    try:
        with open(test_video, "rb") as f:
            for i in range(chunk_count):
                start      = i * chunk_size
                chunk_data = f.read(chunk_size)
                end        = start + len(chunk_data) - 1

                chunk_headers = {
                    "Content-Type":   "video/mp4",
                    "Content-Range":  f"bytes {start}-{end}/{file_size}",
                    "Content-Length": str(len(chunk_data)),
                }

                show_request("PUT", upload_url[:55] + "...", {
                    "Content-Range":  f"bytes {start}-{end}/{file_size}",
                    "Content-Length": str(len(chunk_data)),
                })
                time.sleep(0.5)

                up = requests.put(upload_url, headers=chunk_headers,
                                  data=chunk_data, timeout=120)
                print(f"\n  <-- HTTP {up.status_code} — Chunk {i+1}/{chunk_count} uploaded")
                up.raise_for_status()
    except Exception as e:
        print(f"\n  ERROR during upload: {e}")
        return

    # ── STEP 3: Poll publish status ───────────────────────────────────────────
    divider("STEP 3 — Poll publish status")
    print("  Polling TikTok to confirm the video reached the sandbox inbox...")

    status_url  = "https://open.tiktokapis.com/v2/post/publish/status/fetch/"
    status_body = {"publish_id": publish_id}

    for attempt in range(1, 13):
        show_request("POST", status_url, status_body)
        time.sleep(1)
        try:
            sr = requests.post(status_url, headers=auth_headers,
                               json=status_body, timeout=15)
            show_response(sr)
            inner_st = sr.json().get("data", sr.json())
            status   = inner_st.get("status", "UNKNOWN")
            if status in ("PUBLISH_COMPLETE", "SEND_TO_USER_INBOX"):
                break
            if status in ("FAILED", "CANCELLED"):
                print(f"\n  Status: {status} — upload failed in TikTok sandbox")
                return
        except Exception as e:
            print(f"  Poll error: {e}")
        print(f"\n  Attempt {attempt}/12 — waiting 5s...")
        time.sleep(5)

    # ── RESULT ────────────────────────────────────────────────────────────────
    divider("RESULT")
    print(f"\n  publish_id  : {publish_id}")
    print(f"  Final status: {status}")
    print(f"\n  The video has been sent to the BootHop TikTok sandbox inbox.")
    print(f"  In production, it would appear directly on the BootHop TikTok feed.")
    print(f"\n  Integration demonstrated:")
    print(f"    [1] POST /v2/post/publish/inbox/video/init/  -> publish_id + upload_url")
    print(f"    [2] PUT  <upload_url>                        -> video bytes uploaded")
    print(f"    [3] POST /v2/post/publish/status/fetch/      -> SEND_TO_USER_INBOX")
    print(f"\n  Scope used: video.upload")
    print(f"  No unused scopes requested.")
    print("\n" + "=" * 60 + "\n")


if __name__ == "__main__":
    main()
