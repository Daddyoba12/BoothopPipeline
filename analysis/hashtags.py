"""Analyse hashtag performance from Instagram post data."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import HASHTAGS

PLATFORM_HASHTAG_SETS = {
    "tiktok_instagram": [
        "#Logistics", "#SupplyChain", "#SameDayDelivery", "#FreightTech",
        "#DiasporaDelivery", "#AirportLogistics", "#LastMile",
        "#LagosToLondon", "#CrossBorderDelivery",
        "#BootHopPilot", "#MoveSmarter", "#PeoplePoweredNetwork",
        "#NaijaUK", "#AfrobeatsLife", "#NigerianTikTok",
    ],
    "linkedin_x": [
        "#SupplyChain", "#LogisticsInnovation", "#FreightTech", "#Resilience",
    ],
    "youtube": [
        "same-day delivery", "last mile", "supply chain", "logistics platform",
        "freight tech", "BootHop", "Nigeria UK delivery", "diaspora delivery",
    ],
}

def get_hashtag_summary(instagram_data):
    summary = []
    for post in instagram_data:
        caption = post.get("caption") or ""
        matched = [tag for tag in HASHTAGS if tag.lower() in caption.lower()]
        if matched:
            summary.append({
                "caption_snippet": caption[:80],
                "matched_tags": matched,
                "likes": post.get("like_count", 0),
                "comments": post.get("comments_count", 0),
                "timestamp": post.get("timestamp", ""),
            })
    return summary

def recommend_hashtags(platform="tiktok_instagram", count=10):
    import random
    tags = PLATFORM_HASHTAG_SETS.get(platform, PLATFORM_HASHTAG_SETS["tiktok_instagram"])
    always = ["#BootHopPilot", "#MoveSmarter", "#NaijaUK"]
    extra = [t for t in tags if t not in always]
    return always + random.sample(extra, min(count - len(always), len(extra)))
