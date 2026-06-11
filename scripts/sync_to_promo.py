"""
sync_to_promo.py
────────────────
Uploads today's pipeline-generated videos to Supabase and creates
bd_content records so they appear in the Promo dashboard ready to post.

Run manually after the pipeline:
    python scripts/sync_to_promo.py

Or add to pipeline.py at the end of main().
"""

import json, sys, requests
from pathlib import Path
from datetime import datetime

# ── Config ────────────────────────────────────────────────────────────────────
BASE          = Path(r"C:\Users\babso\Desktop\BootHopPipeline")
SUPABASE_URL  = "https://zwgngbzbdvnrdnanjded.supabase.co"
SUPABASE_KEY  = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inp3Z25nYnpiZHZucmRuYW5qZGVkIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NTI5NTA0NSwiZXhwIjoyMDkwODcxMDQ1fQ.jP_Ukh4Dwlxfiei5tyHblJ0psgCXntDwnnZBRQch9zw"
BUCKET        = "promo-videos"
PROMO_URL     = "https://www.boothop.com/promo/publish"

HEADERS = {
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "apikey": SUPABASE_KEY,
}

PILLAR_MAP = {
    "airport":   "airport_deliveries",
    "travel":    "travel_hacks",
    "logistics": "logistics_stories",
    "supply":    "supply_chain_failures",
    "premium":   "logistics_stories",
    "history":   "logistics_stories",
    "general":   "logistics_stories",
}

HASHTAGS = (
    "#boothop #sameday #samedaydelivery #logistics #diaspora "
    "#londontolagos #NaijaUK #urgentdelivery #travelwithme "
    "#sendparcel #courier #uklogistics #nigeriauk #peertopeer "
    "#boothopdelivery #airportdelivery #carryandearn #parcels "
    "#sendandcarry #logisticstiktok"
)


def log(msg):
    print(msg.encode("ascii", errors="replace").decode("ascii"), flush=True)


def ensure_bucket():
    r = requests.post(
        f"{SUPABASE_URL}/storage/v1/bucket",
        headers={**HEADERS, "Content-Type": "application/json"},
        json={"id": BUCKET, "name": BUCKET, "public": True},
    )
    if r.status_code not in (200, 201, 409):
        log(f"  ⚠ Bucket create returned {r.status_code}: {r.text[:200]}")


def upload_video(path: Path) -> str | None:
    size_mb = path.stat().st_size / 1024 / 1024
    log(f"  Uploading {path.name} ({size_mb:.1f} MB)...")
    key = f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{path.name}"
    try:
        with open(path, "rb") as f:
            r = requests.post(
                f"{SUPABASE_URL}/storage/v1/object/{BUCKET}/{key}",
                headers={**HEADERS, "Content-Type": "video/mp4"},
                data=f,
                timeout=300,
            )
        if r.status_code in (200, 201):
            url = f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET}/{key}"
            log(f"  ✓ Uploaded → {url}")
            return url
        else:
            log(f"  ✗ Upload failed {r.status_code}: {r.text[:200]}")
            return None
    except Exception as e:
        log(f"  ✗ Upload error: {e}")
        return None


def already_exists(hook: str) -> bool:
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/bd_content",
        headers=HEADERS,
        params={"hook": f"eq.{hook}", "select": "id"},
    )
    return bool(r.json())


def insert_content(hook, script, caption, hashtags, visual_desc, pillar, platform, video_url) -> bool:
    r = requests.post(
        f"{SUPABASE_URL}/rest/v1/bd_content",
        headers={**HEADERS, "Content-Type": "application/json", "Prefer": "return=minimal"},
        json={
            "pillar":       pillar,
            "template_key": "pipeline",
            "platform":     platform,
            "hook":         hook,
            "script":       script,
            "caption":      caption,
            "hashtags":     hashtags,
            "visual_desc":  visual_desc,
            "status":       "approved",
            "video_url":    video_url,
        },
    )
    return r.status_code in (200, 201)



def sync_daily_videos(today: str, out_dir: Path):
    meta_file = out_dir / "metadata_tiktok_0600.json"
    meta = {}
    if meta_file.exists():
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        log(f"  Loaded metadata: bucket={meta.get('bucket')}")

    bucket  = meta.get("bucket", "general")
    pillar  = PILLAR_MAP.get(bucket, "logistics_stories")
    uploaded = []

    for version in ["v1", "v2"]:
        mp4 = out_dir / f"{version}_{version}.mp4"
        if not mp4.exists():
            log(f"  {mp4.name} not found, skipping")
            continue

        v_meta     = meta.get(version, {})
        hook       = v_meta.get("hook", f"BootHop {version} — {today}")
        engagement = v_meta.get("engagement", "")

        if already_exists(hook):
            log(f"  ⟳ {version} already in dashboard, skipping")
            continue

        video_url = upload_video(mp4)
        if not video_url:
            continue

        caption = (
            f"{hook}\n\n"
            f"{engagement}\n\n"
            f"Send anything. Carry and earn. No depot. No queues. 📦✈️\n"
            f"👉 www.boothop.com"
        )
        script = (
            f"HOOK:\n{hook}\n\n"
            f"ENGAGEMENT:\n{engagement}\n\n"
            f"CTA:\nVisit boothop.com — send and carry smarter."
        )
        visual_desc = f"Pipeline video. Date: {today}. Bucket: {bucket}. Version: {version}."

        ok = insert_content(hook, script, caption, HASHTAGS, visual_desc, pillar, "tiktok", video_url)
        if ok:
            log(f"  ✓ {version} added to Promo dashboard")
            uploaded.append({"label": version, "hook": hook, "url": video_url, "caption": caption})
        else:
            log(f"  ✗ Failed to insert {version} into bd_content")

    return uploaded


def sync_walkthrough_videos(out_dir: Path):
    uploaded = []
    for mp4 in sorted(out_dir.glob("boothop_walkthrough_v*.mp4")):
        hook = "See how BootHop works in 60 seconds 👀📦"
        if already_exists(hook):
            log(f"  ⟳ Walkthrough already in dashboard, skipping")
            continue
        video_url = upload_video(mp4)
        if not video_url:
            continue
        caption = (
            "This is how BootHop works 👇\n\n"
            "✅ Post a send request\n"
            "✅ Match with a verified traveller\n"
            "✅ Delivered door-to-door\n\n"
            "Send and carry smarter. Link in bio!"
        )
        ok = insert_content(
            hook, "BootHop walkthrough — how sending and carrying works.",
            caption, HASHTAGS,
            f"App walkthrough. File: {mp4.name}",
            "logistics_stories", "all", video_url,
        )
        if ok:
            log(f"  ✓ Walkthrough added to Promo dashboard")
            uploaded.append({"label": "walkthrough", "hook": hook, "url": video_url, "caption": caption})
    return uploaded


def main():
    today   = datetime.now().strftime("%Y-%m-%d")
    out_dir = BASE / "output" / today

    # Allow passing a specific date: python sync_to_promo.py 2026-06-09
    if len(sys.argv) > 1:
        today   = sys.argv[1]
        out_dir = BASE / "output" / today

    log(f"\n🔄 BootHop Promo Sync — {today}")
    log(f"   Output folder: {out_dir}")

    if not out_dir.exists():
        log(f"❌ No output folder found for {today}")
        sys.exit(1)

    ensure_bucket()

    all_uploaded = []
    all_uploaded += sync_daily_videos(today, out_dir)
    all_uploaded += sync_walkthrough_videos(out_dir)

    if all_uploaded:
        log(f"\n✅ Done — {len(all_uploaded)} video(s) synced.")
        log(f"   Open {PROMO_URL} to review and post them.")
        for u in all_uploaded:
            log(f"   • [{u['label']}] {u['hook'][:80]}")
    else:
        log("\n⚠ No new videos to sync (already synced or no MP4s found).")


if __name__ == "__main__":
    main()
