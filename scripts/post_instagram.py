"""
post_instagram.py
Instagram Reels auto-poster using Meta Instagram Graph API.

Flow:
  1. Upload video to catbox.moe to get a public URL
  2. Create Instagram Reels media container with that URL
  3. Poll until container is ready
  4. Publish the container
"""

import json
import os
import time
from datetime import datetime


def _log(msg: str) -> None:
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"[{ts}] [Instagram] {msg}")


def _load_credentials():
    creds_path = os.path.join(os.path.dirname(__file__), "social_credentials.json")
    try:
        with open(creds_path, "r") as f:
            data = json.load(f)
        ig = data.get("instagram", {})
        return ig.get("access_token", "").strip(), ig.get("ig_user_id", "").strip()
    except Exception as e:
        _log(f"Failed to load credentials: {e}")
        return "", ""


def _upload_to_host(video_path: str) -> str | None:
    """Upload video to catbox.moe and return public URL."""
    import requests
    _log("Uploading video to temporary host for public URL...")
    try:
        with open(video_path, "rb") as f:
            r = requests.post(
                "https://catbox.moe/user/api.php",
                data={"reqtype": "fileupload"},
                files={"fileToUpload": (os.path.basename(video_path), f, "video/mp4")},
                timeout=120,
            )
        url = r.text.strip()
        if url.startswith("https://"):
            _log(f"Hosted at: {url}")
            return url
        _log(f"Unexpected host response: {url}")
        return None
    except Exception as e:
        _log(f"Failed to upload to host: {e}")
        return None


def post_reel(video_path: str, caption: str) -> str | None:
    """
    Upload a video as an Instagram Reel.
    Returns the published media_id on success, or None on error.
    """
    try:
        import requests
    except ImportError:
        _log("'requests' not installed. Run: pip install requests")
        return None

    access_token, ig_user_id = _load_credentials()
    if not access_token or not ig_user_id:
        _log("Instagram credentials empty. Skipping post.")
        return None

    if not os.path.isfile(video_path):
        _log(f"Video not found: {video_path}")
        return None

    # Step 1: get public URL
    video_url = _upload_to_host(video_path)
    if not video_url:
        return None

    # Step 2: create media container
    # Use POST body (data=) not params= so long captions with emojis/hashtags are
    # sent reliably — URL query params truncate or break on special characters.
    _log("Creating Instagram Reels media container...")
    safe_caption = (caption or "")[:2200]  # Instagram Reels caption limit
    try:
        r = requests.post(
            f"https://graph.instagram.com/v21.0/{ig_user_id}/media",
            data={
                "media_type":   "REELS",
                "video_url":    video_url,
                "caption":      safe_caption,
                "access_token": access_token,
            },
            timeout=30,
        )
        data = r.json()
    except Exception as e:
        _log(f"Failed to create container: {e}")
        return None

    if "error" in data:
        _log(f"Container error: {data['error']}")
        return None

    container_id = data.get("id")
    if not container_id:
        _log(f"Unexpected container response: {data}")
        return None

    _log(f"Container created: {container_id}")

    # Step 3: poll until FINISHED
    _log("Waiting for container to process...")
    timeout_sec  = 300
    poll_interval = 10
    elapsed = 0
    status_code = None

    while elapsed < timeout_sec:
        try:
            st = requests.get(
                f"https://graph.instagram.com/v21.0/{container_id}",
                params={"fields": "status_code", "access_token": access_token},
                timeout=15,
            ).json()
            status_code = st.get("status_code", "")
            _log(f"Status: {status_code} ({elapsed}s)")
            if status_code == "FINISHED":
                break
            if status_code in ("ERROR", "EXPIRED"):
                _log(f"Container failed: {status_code}")
                return None
        except Exception as e:
            _log(f"Poll error: {e}")

        time.sleep(poll_interval)
        elapsed += poll_interval

    if status_code != "FINISHED":
        _log(f"Timed out. Last status: {status_code}")
        return None

    # Step 4: publish
    _log("Publishing Reel...")
    try:
        pub = requests.post(
            f"https://graph.instagram.com/v21.0/{ig_user_id}/media_publish",
            params={"creation_id": container_id, "access_token": access_token},
            timeout=30,
        ).json()
    except Exception as e:
        _log(f"Publish failed: {e}")
        return None

    if "error" in pub:
        _log(f"Publish error: {pub['error']}")
        return None

    media_id = pub.get("id")
    if not media_id:
        _log(f"Unexpected publish response: {pub}")
        return None

    _log(f"Reel published! Media ID: {media_id}")
    return str(media_id)


if __name__ == "__main__":
    result = post_reel(
        video_path=r"C:\Users\babso\Desktop\BootHopPipeline\output\explainer\boothop_explainer_vertical.mp4",
        caption="BootHop — discover hostels near you 🌍 #travel #boothop #hostel #backpacker",
    )
    print(f"Result: {result}")
