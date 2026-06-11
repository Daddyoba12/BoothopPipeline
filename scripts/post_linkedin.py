"""
post_linkedin.py
LinkedIn auto-poster: video, image, or text-only via UGC Posts API v2.

Usage:
  python post_linkedin.py --video path/to/video.mp4 --caption-file path/to/caption.txt
  python post_linkedin.py --image path/to/image.jpg --caption-file path/to/caption.txt
  python post_linkedin.py --text-only --caption-file path/to/caption.txt
"""

import argparse
import json
import os
from datetime import datetime, timedelta


def _log(msg: str) -> None:
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"[{ts}] [LinkedIn] {msg}")


def _auto_refresh_token(creds_path: str) -> None:
    """
    Silently refresh the LinkedIn access token if it expires within 7 days.
    Requires refresh_token in social_credentials.json (stored by linkedin_oauth_now.py).
    No-op if no refresh_token is present.
    """
    try:
        import requests as _r
        with open(creds_path, "r") as f:
            data = json.load(f)
        li = data.get("linkedin", {})
        refresh_token = li.get("refresh_token", "")
        if not refresh_token:
            return

        issued_at_str = li.get("issued_at", "")
        expires_in    = li.get("expires_in", 0)
        if issued_at_str and expires_in:
            expiry     = datetime.fromisoformat(issued_at_str) + timedelta(seconds=expires_in)
            days_left  = (expiry - datetime.now()).total_seconds() / 86400
            if days_left > 7:
                return

        resp = _r.post(
            "https://www.linkedin.com/oauth/v2/accessToken",
            data={
                "grant_type":    "refresh_token",
                "refresh_token": refresh_token,
                "client_id":     li.get("client_id", ""),
                "client_secret": li.get("client_secret", ""),
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=20,
        ).json()

        if "access_token" in resp:
            li["access_token"] = resp["access_token"]
            li["expires_in"]   = resp.get("expires_in", expires_in)
            li["issued_at"]    = datetime.now().isoformat()
            if resp.get("refresh_token"):
                li["refresh_token"] = resp["refresh_token"]
            data["linkedin"] = li
            with open(creds_path, "w") as f:
                json.dump(data, f, indent=2)
            _log("Token auto-refreshed successfully")
        else:
            _log(f"Token refresh failed: {resp.get('error_description', resp.get('error', ''))}")
    except Exception as e:
        _log(f"Token refresh (silent): {e}")


def _load_credentials():
    creds_path = os.path.join(os.path.dirname(__file__), "social_credentials.json")
    _auto_refresh_token(creds_path)
    try:
        with open(creds_path, "r") as f:
            data = json.load(f)
        li = data.get("linkedin", {})
        access_token = li.get("access_token", "").strip()
        person_urn = li.get("person_urn", "").strip()
        return access_token, person_urn
    except FileNotFoundError:
        _log(f"Credentials file not found at {creds_path}")
        return "", ""
    except json.JSONDecodeError as e:
        _log(f"Failed to parse credentials JSON: {e}")
        return "", ""


def post_video(video_path: str, caption: str) -> str | None:
    """
    Upload a video to LinkedIn and create a UGC post.

    Returns the post URN string on success, or None on any error.
    """
    try:
        import requests
    except ImportError:
        _log("'requests' library is not installed. Run: pip install requests")
        return None

    # 1. Load credentials
    access_token, person_urn = _load_credentials()
    if not access_token or not person_urn:
        _log("LinkedIn credentials are empty. Skipping post.")
        return None

    # Validate video file
    if not os.path.isfile(video_path):
        _log(f"Video file not found: {video_path}")
        return None

    file_size = os.path.getsize(video_path)
    _log(f"Starting LinkedIn video post for '{video_path}' ({file_size} bytes)")

    auth_headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
    }

    # 2a. Register upload
    register_url = "https://api.linkedin.com/v2/assets?action=registerUpload"
    register_body = {
        "registerUploadRequest": {
            "recipes": ["urn:li:digitalmediaRecipe:feedshare-video"],
            "owner": person_urn,
            "serviceRelationships": [
                {
                    "relationshipType": "OWNER",
                    "identifier": "urn:li:userGeneratedContent",
                }
            ],
        }
    }

    _log("Registering upload with LinkedIn...")
    try:
        reg_resp = requests.post(
            register_url, headers=auth_headers, json=register_body, timeout=30
        )
        reg_resp.raise_for_status()
        reg_data = reg_resp.json()
    except Exception as e:
        _log(f"Failed to register upload: {e}")
        return None

    try:
        upload_mechanism = reg_data["value"]["uploadMechanism"]
        upload_url = upload_mechanism[
            "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"
        ]["uploadUrl"]
        asset_urn = reg_data["value"]["asset"]
    except (KeyError, TypeError) as e:
        _log(f"Unexpected register response structure: {e} — {reg_data}")
        return None

    _log(f"Upload registered. Asset URN: {asset_urn}")
    _log(f"Upload URL: {upload_url}")

    # 2b. Upload video bytes
    _log("Uploading video bytes...")
    try:
        with open(video_path, "rb") as f:
            video_bytes = f.read()

        upload_headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/octet-stream",
        }
        upload_resp = requests.put(
            upload_url,
            headers=upload_headers,
            data=video_bytes,
            timeout=300,
        )
        upload_resp.raise_for_status()
        _log(f"Video bytes uploaded. HTTP {upload_resp.status_code}")
    except Exception as e:
        _log(f"Failed to upload video bytes: {e}")
        return None

    # 2c. Create the UGC post
    _log("Creating UGC post...")
    post_url = "https://api.linkedin.com/v2/ugcPosts"
    post_body = {
        "author": person_urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {
                    "text": caption,
                },
                "shareMediaCategory": "VIDEO",
                "media": [
                    {
                        "status": "READY",
                        "description": {
                            "text": caption[:200],
                        },
                        "media": asset_urn,
                        "title": {
                            "text": caption[:100],
                        },
                    }
                ],
            }
        },
        "visibility": {
            "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC",
        },
    }

    try:
        post_resp = requests.post(
            post_url, headers=auth_headers, json=post_body, timeout=30
        )
        post_resp.raise_for_status()
        post_urn = post_resp.headers.get("x-restli-id", "")
        if not post_urn:
            # Some LinkedIn API versions return the URN in the JSON body
            post_data = post_resp.json()
            post_urn = post_data.get("id", "")
    except Exception as e:
        _log(f"Failed to create UGC post: {e}")
        return None

    if not post_urn:
        _log("Post may have been created but no URN was returned in the response.")
        return None

    _log(f"Post created successfully. Post URN: {post_urn}")
    return str(post_urn)


def post_text(caption: str) -> str | None:
    """Post plain text to LinkedIn."""
    try:
        import requests
    except ImportError:
        _log("'requests' library not installed. Run: pip install requests")
        return None

    access_token, person_urn = _load_credentials()
    if not access_token or not person_urn:
        _log("LinkedIn credentials are empty. Skipping post.")
        return None

    _log("Creating text-only UGC post...")
    auth_headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
    }
    post_body = {
        "author": person_urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": caption},
                "shareMediaCategory": "NONE",
            }
        },
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
    }
    try:
        resp = requests.post(
            "https://api.linkedin.com/v2/ugcPosts",
            headers=auth_headers, json=post_body, timeout=30,
        )
        resp.raise_for_status()
        post_urn = resp.headers.get("x-restli-id", "") or resp.json().get("id", "")
        _log(f"Text post created. URN: {post_urn}")
        return post_urn or "ok"
    except Exception as e:
        _log(f"Failed to create text post: {e}")
        return None


def post_image(image_path: str, caption: str) -> str | None:
    """Upload an image to LinkedIn and create a UGC post."""
    try:
        import requests
    except ImportError:
        _log("'requests' library not installed. Run: pip install requests")
        return None

    access_token, person_urn = _load_credentials()
    if not access_token or not person_urn:
        _log("LinkedIn credentials are empty. Skipping post.")
        return None

    if not os.path.isfile(image_path):
        _log(f"Image file not found: {image_path}")
        return None

    _log(f"Uploading image: {image_path}")
    auth_headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
    }

    # Register upload
    reg_body = {
        "registerUploadRequest": {
            "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
            "owner": person_urn,
            "serviceRelationships": [
                {"relationshipType": "OWNER", "identifier": "urn:li:userGeneratedContent"}
            ],
        }
    }
    try:
        reg_resp = requests.post(
            "https://api.linkedin.com/v2/assets?action=registerUpload",
            headers=auth_headers, json=reg_body, timeout=30,
        )
        reg_resp.raise_for_status()
        reg_data = reg_resp.json()
        upload_url = reg_data["value"]["uploadMechanism"][
            "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"
        ]["uploadUrl"]
        asset_urn = reg_data["value"]["asset"]
    except Exception as e:
        _log(f"Failed to register image upload: {e}")
        return None

    # Upload bytes
    try:
        with open(image_path, "rb") as f:
            up_resp = requests.put(
                upload_url,
                headers={"Authorization": f"Bearer {access_token}", "Content-Type": "image/jpeg"},
                data=f.read(), timeout=120,
            )
        up_resp.raise_for_status()
        _log(f"Image uploaded. HTTP {up_resp.status_code}")
    except Exception as e:
        _log(f"Failed to upload image bytes: {e}")
        return None

    # Create post
    post_body = {
        "author": person_urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": caption},
                "shareMediaCategory": "IMAGE",
                "media": [
                    {
                        "status": "READY",
                        "description": {"text": caption[:200]},
                        "media": asset_urn,
                        "title": {"text": caption[:100]},
                    }
                ],
            }
        },
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
    }
    try:
        post_resp = requests.post(
            "https://api.linkedin.com/v2/ugcPosts",
            headers=auth_headers, json=post_body, timeout=30,
        )
        post_resp.raise_for_status()
        post_urn = post_resp.headers.get("x-restli-id", "") or post_resp.json().get("id", "")
        _log(f"Image post created. URN: {post_urn}")
        return post_urn or "ok"
    except Exception as e:
        _log(f"Failed to create image UGC post: {e}")
        return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Post to LinkedIn via UGC Posts API")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--video", help="Path to MP4 video file")
    group.add_argument("--image", help="Path to JPG/PNG image file")
    group.add_argument("--text-only", action="store_true", help="Text-only post")
    parser.add_argument("--caption-file", required=True, help="Path to .txt file with post caption")
    args = parser.parse_args()

    if not os.path.isfile(args.caption_file):
        print(f"Caption file not found: {args.caption_file}")
        raise SystemExit(1)
    with open(args.caption_file, "r", encoding="utf-8") as f:
        caption = f.read().strip()

    if args.video:
        result = post_video(args.video, caption)
    elif args.image:
        result = post_image(args.image, caption)
    else:
        result = post_text(caption)

    print(f"LinkedIn result: {result}")
