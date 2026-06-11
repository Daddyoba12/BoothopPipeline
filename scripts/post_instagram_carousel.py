"""
post_instagram_carousel.py
Posts a photo carousel to Instagram using the Graph API.
Different from post_instagram.py which posts Reels (video).

Flow:
  1. Create one media container per image (is_carousel_item=true)
  2. Create a carousel container referencing all item IDs
  3. Publish the carousel container
"""

import json, time, os
import requests
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent


def _log(msg):
    print(f"[{datetime.utcnow().strftime('%H:%M:%S')}] [IG-Carousel] {msg}")


def _load_credentials():
    p = BASE / "scripts" / "social_credentials.json"
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        ig = d.get("instagram", {})
        return ig.get("access_token", ""), ig.get("ig_user_id", "")
    except Exception as e:
        _log(f"Failed to load credentials: {e}")
        return "", ""


def post_carousel(image_urls: list[str], caption: str) -> str | None:
    """
    Post a photo carousel to Instagram.
    image_urls: list of publicly accessible image URLs (2-10 images)
    Returns the published media_id or None on failure.
    """
    access_token, ig_user_id = _load_credentials()
    if not access_token or not ig_user_id:
        _log("Instagram credentials missing — skipping")
        return None

    if not image_urls:
        _log("No image URLs provided")
        return None

    # Clamp to Instagram's 2–10 carousel limit
    image_urls = image_urls[:10]
    if len(image_urls) < 2:
        _log("Need at least 2 images for a carousel")
        return None

    base_url = f"https://graph.instagram.com/v21.0/{ig_user_id}"

    # Step 1 — one container per image
    container_ids = []
    for i, url in enumerate(image_urls):
        try:
            r = requests.post(
                f"{base_url}/media",
                data={
                    "image_url":        url,
                    "is_carousel_item": "true",
                    "access_token":     access_token,
                },
                timeout=30,
            )
            data = r.json()
            if "error" in data:
                _log(f"Item {i+1} container error: {data['error']}")
                continue
            container_ids.append(data["id"])
            _log(f"Item {i+1}/{len(image_urls)} container created: {data['id']}")
            time.sleep(0.5)  # avoid rate limit
        except Exception as e:
            _log(f"Item {i+1} failed: {e}")

    if len(container_ids) < 2:
        _log(f"Only {len(container_ids)} containers created — need at least 2, aborting")
        return None

    # Step 2 — carousel container
    try:
        r = requests.post(
            f"{base_url}/media",
            data={
                "media_type":   "CAROUSEL",
                "caption":      caption[:2200],
                "children":     ",".join(container_ids),
                "access_token": access_token,
            },
            timeout=30,
        )
        data = r.json()
        if "error" in data:
            _log(f"Carousel container error: {data['error']}")
            return None
        carousel_id = data["id"]
        _log(f"Carousel container created: {carousel_id}")
    except Exception as e:
        _log(f"Carousel container failed: {e}")
        return None

    # Step 3 — publish
    try:
        r = requests.post(
            f"{base_url}/media_publish",
            data={"creation_id": carousel_id, "access_token": access_token},
            timeout=30,
        )
        data = r.json()
        if "error" in data:
            _log(f"Publish error: {data['error']}")
            return None
        media_id = data.get("id", "")
        _log(f"Carousel published — media_id: {media_id}")
        return media_id
    except Exception as e:
        _log(f"Publish failed: {e}")
        return None
