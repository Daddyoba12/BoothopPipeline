"""
post_tiktok.py
TikTok video auto-poster using Content Posting API v2 (direct file upload, chunked).
"""

import json
import math
import os
import time
from datetime import datetime

MAX_CHUNK  = 64 * 1024 * 1024  # 64 MB max per chunk


def _log(msg: str) -> None:
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"[{ts}] [TikTok] {msg}")


def _load_credentials():
    creds_path = os.path.join(os.path.dirname(__file__), "social_credentials.json")
    try:
        with open(creds_path, "r") as f:
            data = json.load(f)
        access_token = data.get("tiktok", {}).get("access_token", "").strip()
        return access_token
    except FileNotFoundError:
        _log(f"Credentials file not found at {creds_path}")
        return ""
    except json.JSONDecodeError as e:
        _log(f"Failed to parse credentials JSON: {e}")
        return ""


def post_video(video_path: str, caption: str) -> str | None:
    """
    Upload a video to TikTok using the Content Posting API v2 chunk-upload flow.

    Returns the publish_id string on success, or None on any error.
    """
    try:
        import requests
    except ImportError:
        _log("'requests' library is not installed. Run: pip install requests")
        return None

    # 1. Load credentials
    access_token = _load_credentials()
    if not access_token:
        _log("TikTok access_token is empty. Skipping post.")
        return None

    # Validate video file
    if not os.path.isfile(video_path):
        _log(f"Video file not found: {video_path}")
        return None

    file_size  = os.path.getsize(video_path)
    chunk_size = min(file_size, MAX_CHUNK)   # single chunk if file fits
    chunk_count = math.ceil(file_size / chunk_size)
    _log(
        f"Starting upload for '{video_path}' "
        f"({file_size} bytes, {chunk_count} chunk(s) of {chunk_size} bytes)"
    )

    auth_headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=UTF-8",
    }

    # Sanitise caption: TikTok title max 150 chars, no leading # on first line
    title = caption.split("\n")[0][:150] if caption else "BootHop — same-day delivery by trusted travellers"

    # 2a. Initialise upload — direct post flow so caption/hashtags are published immediately
    init_url = "https://open.tiktokapis.com/v2/post/publish/video/init/"
    init_body = {
        "post_info": {
            "title":            title,
            "description":      caption[:2200] if caption else title,
            "privacy_level":    "PUBLIC_TO_EVERYONE",
            "disable_duet":     False,
            "disable_comment":  False,
            "disable_stitch":   False,
        },
        "source_info": {
            "source":             "FILE_UPLOAD",
            "video_size":         file_size,
            "chunk_size":         chunk_size,
            "total_chunk_count":  chunk_count,
        },
    }

    _log("Initialising upload...")
    try:
        init_resp = requests.post(
            init_url, headers=auth_headers, json=init_body, timeout=30
        )
        init_resp.raise_for_status()
        init_data = init_resp.json()
    except Exception as e:
        _log(f"Failed to initialise upload: {e}")
        return None

    # TikTok wraps the payload under data{}
    inner = init_data.get("data", init_data)
    publish_id = inner.get("publish_id", "")
    upload_url = inner.get("upload_url", "")

    if not publish_id or not upload_url:
        _log(f"Unexpected init response: {init_data}")
        return None

    _log(f"Upload initialised. publish_id={publish_id}")
    _log(f"Upload URL: {upload_url}")

    # 2b. Upload each chunk
    _log("Uploading chunks...")
    try:
        with open(video_path, "rb") as f:
            for chunk_index in range(chunk_count):
                start = chunk_index * chunk_size
                chunk_data = f.read(chunk_size)
                end = start + len(chunk_data) - 1

                chunk_headers = {
                    "Content-Type": "video/mp4",
                    "Content-Range": f"bytes {start}-{end}/{file_size}",
                    "Content-Length": str(len(chunk_data)),
                }

                _log(
                    f"Uploading chunk {chunk_index + 1}/{chunk_count} "
                    f"(bytes {start}-{end})..."
                )
                put_resp = requests.put(
                    upload_url,
                    headers=chunk_headers,
                    data=chunk_data,
                    timeout=120,
                )
                put_resp.raise_for_status()
                _log(f"Chunk {chunk_index + 1} uploaded. Status: {put_resp.status_code}")
    except Exception as e:
        _log(f"Failed during chunk upload: {e}")
        return None

    _log("All chunks uploaded. Polling publish status...")

    # 2c. Poll until PUBLISH_COMPLETE
    status_url = "https://open.tiktokapis.com/v2/post/publish/status/fetch/"
    status_headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=UTF-8",
    }
    status_body = {"publish_id": publish_id}

    timeout_sec = 120
    poll_interval = 5
    elapsed = 0
    last_status = ""

    while elapsed < timeout_sec:
        try:
            st_resp = requests.post(
                status_url, headers=status_headers, json=status_body, timeout=15
            )
            st_resp.raise_for_status()
            st_data = st_resp.json()
            inner_st = st_data.get("data", st_data)
            last_status = inner_st.get("status", "")
            _log(f"Publish status: {last_status} (elapsed {elapsed}s)")

            if last_status in ("PUBLISH_COMPLETE", "SEND_TO_USER_INBOX", "SUCCESS"):
                break
            if last_status in ("FAILED", "CANCELLED"):
                _log(f"Publish entered terminal failure state: {last_status}")
                return None
        except Exception as e:
            _log(f"Error polling publish status: {e}")

        time.sleep(poll_interval)
        elapsed += poll_interval

    if last_status not in ("PUBLISH_COMPLETE", "SEND_TO_USER_INBOX", "SUCCESS"):
        _log(f"Timed out. Last status: {last_status}")
        return None

    _log(f"TikTok video published with caption. publish_id: {publish_id}")
    return publish_id


if __name__ == "__main__":
    result = post_video(
        video_path=r"C:\Users\babso\Desktop\BootHopPipeline\data\test_video.mp4",
        caption="Test TikTok post #boothop",
    )
    print(f"Result: {result}")
