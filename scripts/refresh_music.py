"""
refresh_music.py
Auto-downloads trending audio for BootHop video backgrounds.

Sources (in order):
  1. YouTube — Afrobeats, Amapiano, Nigerian artists, US RnB
     (searches target "type beat / no copyright" to reduce copyright risk)
  2. TikTok  — trending hashtag sounds via yt-dlp + browser cookies

Trimming is source-aware:
  - TikTok  → no trim (sounds are already short and hit from second 0)
  - YouTube → capped at YT_TRIM_SECS from the start (type beats drop immediately)

NOTE: "type beat / no copyright" results are generally safe for TikTok + IG.
YouTube Shorts may still flag some tracks — the pipeline's ARCHIVE folder
(royalty-free library tracks) remains the fallback for YouTube uploads.

Run manually:   python scripts/refresh_music.py
Scheduled:      Monday 08:00 via BootHop-WeeklyAnalysis (called automatically)
"""

import json, subprocess, re, sys
from pathlib import Path
from datetime import datetime

BASE         = Path(__file__).resolve().parent.parent
TRENDING_DIR = BASE / "audio" / "trending"
TEMP_DL      = BASE / "temp" / "music_dl"
MAX_FILES    = 15
YT_TRIM_SECS = 40    # YouTube: cap at 40s from position 0 (type beats hit immediately)

# ── Search queries ─────────────────────────────────────────────────────────────
# Each entry: (yt-dlp query string, max tracks to pull from this query)

YT_QUERIES = [
    # Nigerian Afrobeats
    ("ytsearch4:afrobeats 2026 no copyright free background music",        2),
    ("ytsearch4:nigerian afrobeats instrumental 2026 free use",            2),
    ("ytsearch4:afrobeats type beat 2026 free download",                   2),
    # Amapiano
    ("ytsearch4:amapiano 2026 no copyright royalty free",                  2),
    ("ytsearch4:amapiano instrumental 2026 free background",               1),
    # Artist type beats (usually royalty-free on YouTube)
    ("ytsearch3:asake type beat 2026 free afrobeats",                      1),
    ("ytsearch3:burna boy type beat 2026 free",                            1),
    ("ytsearch3:wizkid type beat afrobeats 2026 free",                     1),
    ("ytsearch3:shallipopi type beat 2026 afrobeats free",                 1),
    # US RnB
    ("ytsearch4:rnb 2026 no copyright free background music",              2),
    ("ytsearch4:rnb soul beats 2026 free use instrumental",                2),
    ("ytsearch3:smooth rnb type beat 2026 free",                           1),
]

# TikTok hashtags to try extracting audio from
TIKTOK_TAGS = [
    "afrobeats",
    "amapiano",
    "afropop",
    "rnbmusic",
]


# ── Helpers ────────────────────────────────────────────────────────────────────

def _safe_name(raw: str) -> str:
    return re.sub(r"[^\w\-]", "_", raw)[:55]


def _already_have(video_id: str) -> bool:
    return any(video_id in f.stem for f in TRENDING_DIR.glob("*.mp3"))


def _trim_yt(src: Path, dst: Path) -> bool:
    """Cap a YouTube track at YT_TRIM_SECS from position 0."""
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(src),
             "-t", str(YT_TRIM_SECS), "-c", "copy", str(dst)],
            capture_output=True, timeout=30
        )
        return dst.exists() and dst.stat().st_size > 10_000
    except Exception:
        return False


def _save_track(raw_path: Path, stem: str, source: str = "yt") -> Path | None:
    """
    Save raw_path → audio/trending/{stem}.mp3.
    source='yt'  → trim to YT_TRIM_SECS from 0
    source='tt'  → keep full track (TikTok sounds are already short and start immediately)
    """
    final = TRENDING_DIR / f"{stem}.mp3"

    if source == "tt":
        # TikTok: move as-is, no trimming
        if raw_path.exists() and raw_path.stat().st_size > 10_000:
            raw_path.replace(final)
        else:
            return None
    else:
        # YouTube: cap length, keep from second 0
        trimmed = TEMP_DL / f"{stem}_trim.mp3"
        if _trim_yt(raw_path, trimmed):
            trimmed.replace(final)
        elif raw_path.exists():
            raw_path.replace(final)
        else:
            return None
        raw_path.unlink(missing_ok=True)

    return final


def prune_oldest(keep: int = MAX_FILES) -> list:
    files   = sorted(TRENDING_DIR.glob("*.mp3"), key=lambda f: f.stat().st_mtime)
    removed = []
    while len(files) > keep:
        files[0].unlink(missing_ok=True)
        removed.append(files[0].name)
        files = files[1:]
    return removed


# ── Downloaders ────────────────────────────────────────────────────────────────

def download_yt_query(query: str, max_tracks: int, downloaded: list) -> int:
    """Download up to max_tracks audio files from a yt-dlp search query."""
    TEMP_DL.mkdir(parents=True, exist_ok=True)
    added = 0
    try:
        meta = subprocess.run(
            ["yt-dlp", "--dump-json", "--flat-playlist",
             "--playlist-end", str(max_tracks + 2),
             "--no-warnings", "--quiet", query],
            capture_output=True, text=True, timeout=30,
            encoding="utf-8", errors="replace"
        )
        candidates = []
        for line in meta.stdout.strip().splitlines():
            try:
                item     = json.loads(line)
                vid_id   = item.get("id", "")
                title    = _safe_name(item.get("title", vid_id))
                duration = item.get("duration") or 0
                if vid_id and not _already_have(vid_id) and 60 < duration < 600:
                    candidates.append((vid_id, title))
            except Exception:
                continue

        for vid_id, title in candidates[:max_tracks]:
            stem    = f"{title}_{vid_id}"
            raw_out = TEMP_DL / f"{stem}.%(ext)s"
            raw_mp3 = TEMP_DL / f"{stem}.mp3"

            subprocess.run(
                ["yt-dlp",
                 "--extract-audio", "--audio-format", "mp3", "--audio-quality", "5",
                 "--output", str(raw_out),
                 "--no-playlist", "--quiet",
                 f"https://www.youtube.com/watch?v={vid_id}"],
                capture_output=True, timeout=120
            )

            if raw_mp3.exists():
                final = _save_track(raw_mp3, stem, source="yt")
                if final:
                    print(f"    + {final.name}")
                    downloaded.append(final.name)
                    added += 1

    except Exception as e:
        print(f"    [YT error] {e}")

    return added


def download_tiktok_tag(tag: str, downloaded: list) -> int:
    """Extract audio from TikTok trending tag videos via browser cookies."""
    TEMP_DL.mkdir(parents=True, exist_ok=True)
    added = 0
    for browser in ("chrome", "edge", "firefox"):
        try:
            out_tmpl = str(TEMP_DL / f"tt_{tag}_%(id)s.%(ext)s")
            subprocess.run(
                ["yt-dlp",
                 "--cookies-from-browser", browser,
                 "--extract-audio", "--audio-format", "mp3", "--audio-quality", "5",
                 "--playlist-end", "3",
                 "--output", out_tmpl,
                 "--quiet", "--no-warnings",
                 f"https://www.tiktok.com/tag/{tag}"],
                capture_output=True, timeout=90
            )
            for raw in TEMP_DL.glob(f"tt_{tag}_*.mp3"):
                vid_id = raw.stem.split("_")[-1]
                if _already_have(vid_id):
                    raw.unlink(missing_ok=True)
                    continue
                stem  = f"tt_{tag}_{vid_id}"
                final = _save_track(raw, stem, source="tt")
                if final:
                    print(f"    + TikTok #{tag}: {final.name}")
                    downloaded.append(final.name)
                    added += 1
            if added:
                break
        except Exception:
            continue
    return added


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> list:
    TRENDING_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_DL.mkdir(parents=True, exist_ok=True)

    print(f"\n[Music Refresh] {datetime.now().strftime('%A %d %B %Y  %H:%M')}")
    existing = list(TRENDING_DIR.glob("*.mp3"))
    print(f"  Trending folder: {len(existing)} files currently")

    downloaded: list = []

    # ── YouTube ────────────────────────────────────────────────────────────────
    print("\n  [YouTube] Fetching trending audio...")
    for query, max_t in YT_QUERIES:
        label = query.split(":", 1)[-1][:55]
        print(f"  {label}...", end=" ", flush=True)
        n = download_yt_query(query, max_t, downloaded)
        print(f"{n} added" if n else "nothing new")
        if len(downloaded) >= 10:
            print("  (target reached — skipping remaining queries)")
            break

    # ── TikTok (best-effort) ───────────────────────────────────────────────────
    print("\n  [TikTok] Attempting trending sounds (needs browser session)...")
    for tag in TIKTOK_TAGS:
        n = download_tiktok_tag(tag, downloaded)
        if not n:
            print(f"  #{tag}: no audio extracted (browser cookies unavailable or blocked)")

    # ── Prune ──────────────────────────────────────────────────────────────────
    removed = prune_oldest(MAX_FILES)
    if removed:
        print(f"\n  Pruned {len(removed)} old file(s): {', '.join(removed)}")

    # ── Summary ────────────────────────────────────────────────────────────────
    final_count = len(list(TRENDING_DIR.glob("*.mp3")))
    print(f"\n  Done — {len(downloaded)} new track(s) added, {final_count} total in audio/trending/")
    for name in downloaded:
        print(f"    • {name}")

    # Telegram notification if run as part of weekly schedule
    if downloaded or removed:
        try:
            sys.path.insert(0, str(BASE))
            from pipeline import send_telegram_text
            lines = [f"🎵 *Music Refresh — {datetime.now().strftime('%a %d %b')}*"]
            if downloaded:
                lines.append(f"\n✅ {len(downloaded)} new track(s) added:")
                lines += [f"  • {n}" for n in downloaded]
            if removed:
                lines.append(f"\n🗑 {len(removed)} old track(s) pruned")
            lines.append(f"\n📁 Total in trending/: {final_count}")
            send_telegram_text("\n".join(lines))
        except Exception:
            pass

    return downloaded


if __name__ == "__main__":
    main()
