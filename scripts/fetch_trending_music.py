"""
fetch_trending_music.py
Downloads 3 daily music slots — morning / midday / evening.

Priority chain (same for all slots, different picks each time):
  0. Weekly profile match — viral video last week → find music with SIMILAR
     vibe/energy/pitch (never the same track, always new)
  1. Nigeria YouTube trending (regionCode=NG, category Music)
  2. UK Grind / Urban (regionCode=GB filtered for drill/grime/afroswing)
  3. US R&B / Soul (regionCode=US filtered for rnb/soul)
  4. Archive fallback (music/archive/, rotating, no-repeat preferred)

For each slot:
  track_1.mp3 → 6am  morning  pipeline.py   (best / profile match)
  track_2.mp3 → 12pm midday   boothop-premium.ps1  (Nigeria 2nd pick)
  track_3.mp3 → 6pm  evening  boothop-premium.ps1  (UK / Urban pick)

Hook extraction: uses librosa to find the most energetic 30-second window
(the drop/chorus). Falls back to full download if librosa not installed.

7-day no-repeat: every track logged to data/music_log.json (90-day rolling).
"""

import json, subprocess, shutil, sys
from datetime import datetime, timedelta
from pathlib import Path

# Force UTF-8 output so checkmarks / em-dashes don't crash on Windows CP1252
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = Path(r"C:\Users\babso\Desktop\BootHopPipeline")
sys.path.insert(0, str(BASE))

import requests as _requests
from config import YOUTUBE_API_KEY, DATA

DAILY_DIR  = BASE / "music" / "daily"
ARCHIVE    = BASE / "music" / "archive"
TMP_DIR    = DAILY_DIR / "_tmp"
MUSIC_LOG  = DATA / "music_log.json"
INFO_FILE  = DAILY_DIR / "daily_info.json"
PERFORMANCE_WEIGHTS = DATA / "performance_weights.json"

DAILY_DIR.mkdir(parents=True, exist_ok=True)
ARCHIVE.mkdir(parents=True, exist_ok=True)
TMP_DIR.mkdir(parents=True, exist_ok=True)

# ── Filter keyword pools ────────────────────────────────────────────────────────
UK_GRIND_KW = [
    "drill", "grind", "urban", "grime", "afroswing", "afrobeats uk",
    "central cee", "stormzy", "dave ", "skepta", "headie", "steel bangg",
    "pop smoke", "giggs", "kano", "jme", "russ millions", "ivorian doll",
    "little simz", "jorja smith", "pa salieu", "ghetts", "kojey",
]

US_RNB_KW = [
    "rnb", "r&b", "neo soul", "usher", "beyonce", "sza", "frank ocean",
    "h.e.r.", "summer walker", "brent faiyaz", "giveon", "jhene aiko",
    "anderson paak", "daniel caesar", "khalid", "lucky daye", "lion babe",
]


# ── Music log helpers ──────────────────────────────────────────────────────────
def _load_log():
    if MUSIC_LOG.exists():
        try:
            return json.loads(MUSIC_LOG.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []

def _save_log(entry):
    log = _load_log()
    log.append(entry)
    log = log[-90:]
    MUSIC_LOG.write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")

def _used_recently(title, days=7):
    log    = _load_log()
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    for e in log:
        if e.get("logged_at", "") > cutoff and e.get("title", "").lower() == title.lower():
            return True
    return False


# ── Weekly performance profile ─────────────────────────────────────────────────
def _load_music_preference():
    if not PERFORMANCE_WEIGHTS.exists():
        return {}, []
    try:
        pw = json.loads(PERFORMANCE_WEIGHTS.read_text(encoding="utf-8"))
        profile = pw.get("preferred_music_profile", {})
        queries = profile.get("search_queries", [])
        return profile, queries
    except Exception:
        return {}, []


# ── YouTube helpers ────────────────────────────────────────────────────────────
def _yt_trending(region="NG", max_results=15):
    try:
        r = _requests.get(
            "https://www.googleapis.com/youtube/v3/videos",
            params={"part": "snippet", "chart": "mostPopular",
                    "regionCode": region, "videoCategoryId": "10",
                    "maxResults": max_results, "key": YOUTUBE_API_KEY},
            timeout=10,
        )
        if r.ok:
            return [{"title": i["snippet"]["title"],
                     "channel": i["snippet"]["channelTitle"],
                     "video_id": i["id"]}
                    for i in r.json().get("items", [])]
    except Exception as e:
        print(f"  [Music] YT trending error ({region}): {e}")
    return []

def _yt_search(query, max_results=6):
    try:
        r = _requests.get(
            "https://www.googleapis.com/youtube/v3/search",
            params={"part": "snippet", "q": query, "type": "video",
                    "videoCategoryId": "10", "order": "relevance",
                    "maxResults": max_results, "key": YOUTUBE_API_KEY},
            timeout=10,
        )
        if r.ok:
            return [{"title": i["snippet"]["title"],
                     "channel": i["snippet"]["channelTitle"],
                     "video_id": i["id"]["videoId"]}
                    for i in r.json().get("items", [])]
    except Exception as e:
        print(f"  [Music] YT search error: {e}")
    return []


# ── Hook extraction (librosa) ──────────────────────────────────────────────────
def _extract_hook(src_path, out_path, duration_s=30):
    """
    Find the most energetic 30-second window (the drop / chorus).
    Uses librosa RMS energy smoothed over ~3s windows.
    Falls back to a simple time-trim if librosa is unavailable.
    """
    try:
        import librosa
        import numpy as np
        from scipy.ndimage import uniform_filter1d
        from pydub import AudioSegment

        print(f"    [Hook] Analysing energy curve...")
        y, sr    = librosa.load(str(src_path), duration=210, mono=True)
        rms      = librosa.feature.rms(y=y, frame_length=2048, hop_length=512)[0]
        smoothed = uniform_filter1d(rms, size=60)

        # Search between 20% and 75% of track (skip intro and outro)
        s_start  = int(len(smoothed) * 0.20)
        s_end    = int(len(smoothed) * 0.75)
        peak_idx = s_start + int(np.argmax(smoothed[s_start:s_end]))
        peak_ms  = int(peak_idx * 512 / sr * 1000)

        audio    = AudioSegment.from_mp3(str(src_path))
        hook_ms  = duration_s * 1000
        start_ms = max(0, peak_ms - hook_ms // 2)
        end_ms   = min(len(audio), start_ms + hook_ms)
        start_ms = max(0, end_ms - hook_ms)

        hook = audio[start_ms:end_ms].fade_in(500).fade_out(1200)
        hook = hook.set_channels(2).set_frame_rate(44100)
        hook.export(str(out_path), format="mp3", bitrate="192k")

        size = out_path.stat().st_size // 1024
        print(f"    [Hook] Peak at {start_ms//1000}s — saved {size}KB")
        return True

    except ImportError:
        # librosa / pydub not installed — use ffmpeg trim from 30s mark
        try:
            res = subprocess.run(
                ["ffmpeg", "-y", "-i", str(src_path),
                 "-ss", "30", "-t", str(duration_s),
                 "-af", "afade=t=in:st=0:d=0.5,afade=t=out:st=29:d=1.2",
                 "-b:a", "192k", str(out_path)],
                capture_output=True, timeout=60,
            )
            return out_path.exists() and out_path.stat().st_size > 5000
        except Exception as e:
            print(f"    [Hook] ffmpeg trim failed: {e}")
            return False
    except Exception as e:
        print(f"    [Hook] Extraction failed: {e}")
        return False


# ── Downloader ─────────────────────────────────────────────────────────────────
def _download_soundcloud(query, raw_out):
    """Try SoundCloud via yt-dlp scsearch. Returns True on success."""
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    for f in TMP_DIR.iterdir():
        try:
            f.unlink()
        except Exception:
            pass

    ydl_opts = {
        "format":         "bestaudio/best",
        "outtmpl":        str(TMP_DIR / "track.%(ext)s"),
        "quiet":          True,
        "no_warnings":    True,
        "default_search": "scsearch1",
        "postprocessors": [{"key": "FFmpegExtractAudio",
                            "preferredcodec": "mp3",
                            "preferredquality": "192"}],
        "postprocessor_args": ["-ar", "44100"],
    }
    try:
        import yt_dlp
        errors = []
        class ErrLogger:
            def debug(self, msg): pass
            def warning(self, msg): pass
            def error(self, msg): errors.append(msg)
        ydl_opts["logger"] = ErrLogger()
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([f"scsearch1:{query}"])
    except Exception as e:
        # Windows file-lock errors during postprocessing are non-fatal —
        # the mp3 is usually already written, so fall through and check below
        err_str = str(e)
        if "WinError 32" not in err_str and "being used by another process" not in err_str:
            print(f"    [SC] {err_str[:120]}")

    # Check for output regardless of exception (Windows file-lock is non-fatal)
    mp3 = TMP_DIR / "track.mp3"
    if mp3.exists() and mp3.stat().st_size > 50000:
        try:
            mp3.rename(raw_out)
            return True
        except Exception:
            import shutil as _shutil
            _shutil.copy2(str(mp3), str(raw_out))
            return True
    # fallback: any mp3 in tmp
    mp3s = [f for f in TMP_DIR.glob("*.mp3") if f.stat().st_size > 50000]
    if mp3s:
        try:
            mp3s[0].rename(raw_out)
        except Exception:
            import shutil as _shutil
            _shutil.copy2(str(mp3s[0]), str(raw_out))
        return True
    return False

def _download_youtube(video_id_or_search, raw_out):
    """Download from YouTube via yt-dlp. Returns True on success."""
    tmp = str(raw_out).replace(".mp3", "_ytdl")
    url = (f"https://www.youtube.com/watch?v={video_id_or_search}"
           if not video_id_or_search.startswith("ytsearch")
           else video_id_or_search)
    cmd = [
        "yt-dlp", "--no-playlist",
        "--extract-audio", "--audio-format", "mp3",
        "--audio-quality", "192K",
        "-o", f"{tmp}.%(ext)s",
        "--quiet", "--no-warnings",
        url,
    ]
    try:
        res = subprocess.run(cmd, timeout=120, capture_output=True, text=True)
        tmp_mp3 = Path(f"{tmp}.mp3")
        if res.returncode == 0 and tmp_mp3.exists():
            tmp_mp3.rename(raw_out)
            return True
        print(f"    [YT] yt-dlp failed: {(res.stderr or res.stdout)[-80:]}")
    except subprocess.TimeoutExpired:
        print("    [YT] Timeout")
    except FileNotFoundError:
        print("    [YT] yt-dlp not installed")
    return False


def _try_track(item, source_label, slot_out, used_titles):
    """
    Attempt to download + extract hook for one track.
    Returns entry dict on success, None on fail.
    used_titles: set of titles already chosen this run (cross-slot dedup).
    """
    title = item.get("title", "")
    if _used_recently(title) or title in used_titles:
        print(f"    Skip (used recently): {title[:55]}")
        return None

    vid   = item.get("video_id", "")
    query = f"{item.get('channel', '')} {title}"
    raw   = TMP_DIR / "raw_download.mp3"

    print(f"    Trying: {title[:60]}")

    # Try SoundCloud first (better hook quality), fall back to YouTube
    ok = _download_soundcloud(query, raw) or _download_youtube(vid, raw)
    if not ok:
        return None

    # Extract the 30s hook
    hooked = _extract_hook(raw, slot_out, duration_s=30)
    if raw.exists():
        try:
            raw.unlink()
        except Exception:
            pass

    if hooked or slot_out.exists():
        return {
            "title":     title,
            "artist":    item.get("channel", "?"),
            "source":    source_label,
            "logged_at": datetime.now().isoformat(),
        }
    return None


# ── Archive fallback ───────────────────────────────────────────────────────────
def _archive_fallback(slot_out, slot_num, used_titles):
    tracks = sorted(ARCHIVE.glob("*.mp3"))
    if not tracks:
        return None
    day = datetime.now().timetuple().tm_yday
    for offset in range(len(tracks)):
        t = tracks[(day * 3 + slot_num + offset) % len(tracks)]
        if not _used_recently(t.stem) and t.stem not in used_titles:
            shutil.copy2(str(t), str(slot_out))
            return {"title": t.stem, "artist": "archive",
                    "source": "archive", "logged_at": datetime.now().isoformat()}
    # All used — just rotate
    t = tracks[(day * 3 + slot_num) % len(tracks)]
    shutil.copy2(str(t), str(slot_out))
    return {"title": t.stem, "artist": "archive",
            "source": "archive", "logged_at": datetime.now().isoformat()}


# ── Per-slot search pools ──────────────────────────────────────────────────────
def _build_candidate_pool(slot_num, music_profile, profile_queries, used_titles):
    """
    Return an ordered list of (item_dict, source_label) to try for this slot.
    slot 1 = full priority chain
    slot 2 = Nigeria pool (different pick)
    slot 3 = UK/Urban pool
    """
    pool = []

    # Priority 0: profile match (slot 1 only — most premium slot)
    if slot_num == 1 and music_profile and profile_queries:
        vibe   = music_profile.get("winning_vibe", "")
        is_old = music_profile.get("is_old_school", False)
        src    = "profile_classic" if is_old else f"profile_{vibe.lower().replace(' ', '_')}"
        for q in profile_queries:
            for item in _yt_search(q, max_results=4):
                if item["title"] not in used_titles:
                    pool.append((item, src))

    if slot_num in (1, 2):
        # Nigeria trending + keyword search
        for item in _yt_trending(region="NG", max_results=15):
            pool.append((item, "nigeria"))
        for q in ("Nigeria afrobeats trending 2025 2026",
                   "Naija music trending today afrobeats"):
            for item in _yt_search(q, max_results=6):
                pool.append((item, "nigeria_search"))

    if slot_num in (1, 3):
        # UK Grind / Urban
        for item in _yt_trending(region="GB", max_results=15):
            title_lower = item["title"].lower()
            if any(kw in title_lower for kw in UK_GRIND_KW):
                pool.append((item, "uk_grind"))
        for q in ("UK Drill Grime urban music trending 2025 2026",
                   "UK rap grime afroswing chart 2025"):
            for item in _yt_search(q, max_results=5):
                pool.append((item, "uk_grind_search"))

    if slot_num == 1:
        # US R&B (slot 1 fallback)
        for item in _yt_trending(region="US", max_results=12):
            title_lower = item["title"].lower()
            if any(kw in title_lower for kw in US_RNB_KW):
                pool.append((item, "us_rnb"))
        for q in ("US RnB soul trending 2025 2026",
                   "Billboard RnB chart 2025"):
            for item in _yt_search(q, max_results=5):
                pool.append((item, "us_rnb_search"))

    if slot_num == 3:
        # Slot 3 also tries US RnB as variety
        for q in ("US RnB soul trending 2025", "neo soul smooth RnB chart"):
            for item in _yt_search(q, max_results=4):
                pool.append((item, "us_rnb_search"))

    return pool


# ── Main entry point ───────────────────────────────────────────────────────────
def fetch_trending_music():
    """
    Download 3 daily music slots to music/daily/.

    Returns info dict with all 3 slots.
    track_1.mp3 → 6am  morning  pipeline.py
    track_2.mp3 → 12pm midday   boothop-premium.ps1
    track_3.mp3 → 6pm  evening  boothop-premium.ps1
    """
    print("\n[Music] Selecting today's music — 3 slots...")

    music_profile, profile_queries = _load_music_preference()

    if music_profile:
        vibe   = music_profile.get("winning_vibe", "?")
        energy = music_profile.get("energy", "?")
        mood   = music_profile.get("mood", "?")
        is_old = music_profile.get("is_old_school", False)
        print(f"  [Profile] Last week: {vibe} / {energy} energy / {mood}"
              + (" [classic]" if is_old else " [fresh]"))
    else:
        print("  [Profile] No profile yet — running standard priority chain")

    SLOT_LABELS = {
        1: "Morning  (6am  pipeline)",
        2: "Midday   (12pm premium)",
        3: "Evening  (6pm  premium)",
    }

    info = {
        "date":   datetime.now().strftime("%Y-%m-%d"),
        "source": "youtube+soundcloud",
        "tracks": [],
    }

    # Track titles already chosen this run (cross-slot dedup)
    used_titles: set = set()
    primary_result = {}  # returned for compatibility with main.py

    for slot_num in (1, 2, 3):
        slot_out = DAILY_DIR / f"track_{slot_num}.mp3"
        print(f"\n  [Slot {slot_num}] {SLOT_LABELS[slot_num]}")

        result = None
        pool   = _build_candidate_pool(slot_num, music_profile, profile_queries, used_titles)

        # Deduplicate pool by title
        seen_pool = set()
        deduped   = []
        for (item, src) in pool:
            t = item["title"]
            if t not in seen_pool:
                seen_pool.add(t)
                deduped.append((item, src))

        for (item, src) in deduped:
            result = _try_track(item, src, slot_out, used_titles)
            if result:
                used_titles.add(result["title"])
                _save_log(result)
                size = slot_out.stat().st_size // 1024 if slot_out.exists() else 0
                print(f"  [Slot {slot_num}] OK {src}: {result['title'][:50]} ({size}KB)")
                break

        if not result:
            print(f"  [Slot {slot_num}] No online track found — using archive")
            result = _archive_fallback(slot_out, slot_num, used_titles)
            if result:
                used_titles.add(result["title"])
                _save_log(result)
                size = slot_out.stat().st_size // 1024 if slot_out.exists() else 0
                print(f"  [Slot {slot_num}] OK Archive: {result['title'][:50]} ({size}KB)")
            else:
                print(f"  [Slot {slot_num}] FAIL No music — check archive folder")
                result = {}

        info["tracks"].append({
            "slot":   slot_num,
            "title":  result.get("title", "?"),
            "artist": result.get("artist", "?"),
            "source": result.get("source", "?"),
        })

        if slot_num == 1:
            primary_result = result

    # Write daily_info.json
    INFO_FILE.write_text(
        json.dumps(info, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(f"\n  [Music] Summary:")
    for t in info["tracks"]:
        flag = ("NG" if "nigeria" in t["source"] else
                "UK" if "uk" in t["source"] else
                "US" if "us" in t["source"] else
                "P"  if "profile" in t["source"] else "A")
        print(f"    [{flag}] track_{t['slot']}.mp3 — {t['title'][:50]}")

    return primary_result


def _already_fresh_today():
    """Return True if all 3 slots already have online (non-archive) tracks from today."""
    if not INFO_FILE.exists():
        return False
    try:
        info = json.loads(INFO_FILE.read_text(encoding="utf-8"))
        if info.get("date") != datetime.now().strftime("%Y-%m-%d"):
            return False
        tracks = info.get("tracks", [])
        if len(tracks) < 3:
            return False
        return all(t.get("source", "archive") != "archive" for t in tracks)
    except Exception:
        return False


if __name__ == "__main__":
    # --skip-if-fresh: used by retry tasks — bail out if online tracks already downloaded today
    if "--skip-if-fresh" in sys.argv and _already_fresh_today():
        print("[Music] Fresh online tracks already downloaded today — skipping retry.")
        sys.exit(0)

    result = fetch_trending_music()
    if result:
        print(f"\nPrimary (track_1): {result.get('title')} [{result.get('source')}]")
