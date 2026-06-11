"""
extract_vibes.py
Downloads and clips 50 YouTube tracks from the "vibes for all" document.
Saves to music/archive/ as track_18.mp3 through track_67.mp3.

Usage:
    python scripts/extract_vibes.py              # download all missing
    python scripts/extract_vibes.py --force      # re-download everything
    python scripts/extract_vibes.py --start 18   # start from specific track number
"""

import subprocess, sys, os, time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE    = Path(r"C:\Users\babso\Desktop\BootHopPipeline")
ARCHIVE = BASE / "music" / "archive"
TMP     = BASE / "music" / "daily" / "_tmp"
ARCHIVE.mkdir(parents=True, exist_ok=True)
TMP.mkdir(parents=True, exist_ok=True)

# ── Track list: (video_id, start_sec, duration_sec, label) ───────────────────
# start_sec  = where to begin the clip
# duration_sec = how long to clip (in seconds)
TRACKS = [
    # 18
    ("PwhyTsGW7_c",  0,   45, "vibes_01"),
    # 19 — Extract from 1:05 to 2:00
    ("YTyBGFAeLqk",  65,  55, "vibes_02"),
    # 20 — Extract from 2:28 to 3:20
    ("L_cu1YqOSMQ",  148, 52, "vibes_03"),
    # 21 — Extract from 1:20 to 2:00 (second clip from same video)
    ("L_cu1YqOSMQ",  80,  40, "vibes_04"),
    # 22 — 0 to 1 min
    ("MSstgCusBbY",  0,   60, "vibes_05"),
    # 23 — 9 secs for 40 seconds
    ("qARrn7G067w",  9,   40, "vibes_06"),
    # 24 — 8 secs for 45 seconds
    ("KvByp6WpF2E",  8,   45, "vibes_07"),
    # 25 — 0 to 1 minute
    ("sGpWXwCJfyo",  0,   60, "vibes_08"),
    # 26 — 8 seconds for 45 secs
    ("P0yXXSjkUH0",  8,   45, "vibes_09"),
    # 27 — 24 seconds for 45 secs
    ("-nCnj-edeTE",  24,  45, "vibes_10"),
    # 28 — 32 seconds for 45 seconds
    ("scK6RRYEiUY",  32,  45, "vibes_11"),
    # 29 — 0 to 45 secs
    ("w0JXsqgRijw",  0,   45, "vibes_12"),
    # 30 — 0 to 45 sec
    ("4bfJKzi5vw0",  0,   45, "vibes_13"),
    # 31 — 0 for 45 seconds
    ("qdLbJIBD8DQ",  0,   45, "vibes_14"),
    # 32 — 13 seconds for 45 seconds (second clip same video)
    ("qdLbJIBD8DQ",  13,  45, "vibes_15"),
    # 33 — 1 min 15 secs for 45 seconds
    ("nYrwwEuvED4",  75,  45, "vibes_16"),
    # 34 — 0 to 35 seconds
    ("wgGa9SgxhJI",  0,   35, "vibes_17"),
    # 35 — 0 to 45 sec
    ("zMlDG1E2xSU",  0,   45, "vibes_18"),
    # 36 — 15 seconds for 45 seconds
    ("juBnNBm0cPw",  15,  45, "vibes_19"),
    # 37 — 38 seconds for 45 seconds
    ("WQFDWM-6ytA",  38,  45, "vibes_20"),
    # 38 — 0 to 45 secs
    ("MHcp9rRPIWQ",  0,   45, "vibes_21"),
    # 39 — 1 minute for 45 secs
    ("GZD53_7aFCs",  60,  45, "vibes_22"),
    # 40 — 11 secs to 54 secs
    ("bWxyVF1LJAo",  11,  43, "vibes_23"),
    # 41 — 20 seconds for 45 seconds
    ("Ra1yHDcJygY",  20,  45, "vibes_24"),
    # 42 — 2 secs for 45 seconds
    ("Hfxra_LxMoc",  2,   45, "vibes_25"),
    # 43 — 1 to 45 secs
    ("rs7PiGxBShs",  1,   44, "vibes_26"),
    # 44 — 23 seconds for 45 secs
    ("ZkR8eyL8U_Q",  23,  45, "vibes_27"),
    # 45 — 0 to 47 secs
    ("0ycogL4hY04",  0,   47, "vibes_28"),
    # 46 — 0 to 45 seconds
    ("7M2Gps9xR8g",  0,   45, "vibes_29"),
    # 47 — first 45 seconds
    ("GgeTnpTkzI0",  0,   45, "vibes_30"),
    # 48 — first 45 seconds
    ("l_-v1fNdSHs",  0,   45, "vibes_31"),
    # 49 — first 45 seconds
    ("Rxym2vuZn8M",  0,   45, "vibes_32"),
    # 50 — 45 seconds
    ("WoxN3b0jmlY",  0,   45, "vibes_33"),
    # 51 — first 45 seconds
    ("1pDQjwaH3qk",  0,   45, "vibes_34"),
    # 52 — 9 seconds for 45 seconds
    ("VwcY7PwFvMc",  9,   45, "vibes_35"),
    # 53 — 0 to 45 seconds
    ("qSGgcw3Yo6U",  0,   45, "vibes_36"),
    # 54 — 17 seconds for 45 seconds
    ("bLQXZFdVglQ",  17,  45, "vibes_37"),
    # 55 — 0 to 45 seconds
    ("NsPqutGyvDM",  0,   45, "vibes_38"),
    # 56 — 20 secs to 1:10 min
    ("3bFPDfWReN0",  20,  50, "vibes_39"),
    # 57 — 17 seconds for 45 seconds
    ("t6po97qI8kw",  17,  45, "vibes_40"),
    # 58 — 7 seconds for 45 seconds
    ("rjeoG7VcOB4",  7,   45, "vibes_41"),
    # 59 — 14 to 50 seconds
    ("EeJF4piVfMI",  14,  36, "vibes_42"),
    # 60 — from 15 seconds for 45 seconds
    ("TrpoKkP2Lo0",  15,  45, "vibes_43"),
    # 61 — 18 seconds to 58 seconds
    ("Ec7T6Buwh3g",  18,  40, "vibes_44"),
    # 62 — 10 seconds to 55 seconds
    ("EM2MMhpYLno",  10,  45, "vibes_45"),
    # 63 — 0 to 45 seconds
    ("sg6HiPSREc8",  0,   45, "vibes_46"),
    # 64 — 24 seconds for 45 seconds
    ("NPCC02SaJVg",  24,  45, "vibes_47"),
    # 65 — 23 seconds for 45 seconds
    ("Si0ZHJdlu9M",  23,  45, "vibes_48"),
    # 66 — 0 to 45 seconds
    ("Tb4X1BWNO5k",  0,   45, "vibes_49"),
    # 67 — 13 seconds to 55 seconds
    ("vj70H5g62j8",  13,  42, "vibes_50"),
]

FORCE = "--force" in sys.argv
START = 18
for arg in sys.argv[1:]:
    if arg.startswith("--start="):
        START = int(arg.split("=")[1])
    elif arg.startswith("--start") and arg != "--start":
        try:
            START = int(sys.argv[sys.argv.index(arg) + 1])
        except Exception:
            pass


def _clean_tmp():
    for f in TMP.iterdir():
        try:
            f.unlink()
        except Exception:
            pass


def download_audio(video_id, raw_out):
    """Download best audio from YouTube to raw_out (mp3). Returns True on success."""
    _clean_tmp()
    url = f"https://www.youtube.com/watch?v={video_id}"
    tmp_stem = str(TMP / "raw")

    cmd = [
        "yt-dlp",
        "--no-playlist",
        "--extract-audio",
        "--audio-format", "mp3",
        "--audio-quality", "192K",
        "-o", f"{tmp_stem}.%(ext)s",
        "--quiet",
        "--no-warnings",
        url,
    ]
    try:
        res = subprocess.run(cmd, timeout=180, capture_output=True, text=True)
        mp3 = Path(f"{tmp_stem}.mp3")
        if mp3.exists() and mp3.stat().st_size > 10000:
            import shutil
            shutil.copy2(str(mp3), str(raw_out))
            return True
        # yt-dlp may write with different extension first
        candidates = [f for f in TMP.glob("raw.*") if f.suffix in (".mp3", ".m4a", ".webm", ".opus")]
        if candidates:
            biggest = max(candidates, key=lambda f: f.stat().st_size)
            if biggest.stat().st_size > 10000:
                # Convert to mp3 with ffmpeg
                r2 = subprocess.run(
                    ["ffmpeg", "-y", "-i", str(biggest),
                     "-b:a", "192k", "-ar", "44100", str(raw_out)],
                    capture_output=True, timeout=60
                )
                if raw_out.exists():
                    return True
        err = (res.stderr or res.stdout or "")[-200:]
        print(f"    [DL] yt-dlp error: {err}")
    except subprocess.TimeoutExpired:
        print("    [DL] Timeout (180s)")
    except FileNotFoundError:
        print("    [DL] yt-dlp not found — install with: pip install yt-dlp")
    return False


def clip_audio(raw, out, start_sec, duration_sec):
    """Extract a segment from raw mp3, apply fade in/out, save to out."""
    cmd = [
        "ffmpeg", "-y",
        "-i", str(raw),
        "-ss", str(start_sec),
        "-t",  str(duration_sec),
        "-af", f"afade=t=in:st=0:d=0.4,afade=t=out:st={max(0, duration_sec - 1.2):.1f}:d=1.2",
        "-b:a", "192k",
        "-ar", "44100",
        str(out),
    ]
    try:
        res = subprocess.run(cmd, timeout=60, capture_output=True)
        return out.exists() and out.stat().st_size > 5000
    except Exception as e:
        print(f"    [CLIP] ffmpeg error: {e}")
        return False


def main():
    force = FORCE
    start_num = START

    total   = len(TRACKS)
    done    = 0
    skipped = 0
    failed  = []

    print(f"\n{'='*60}")
    print(f"  BootHop Vibes Extractor — {total} tracks")
    print(f"  Output: music/archive/track_18.mp3 → track_67.mp3")
    print(f"{'='*60}\n")

    for idx, (vid_id, start_s, dur_s, label) in enumerate(TRACKS):
        track_num = 18 + idx
        if track_num < start_num:
            continue

        out_file = ARCHIVE / f"track_{track_num:02d}.mp3"

        if out_file.exists() and not force:
            size = out_file.stat().st_size // 1024
            print(f"  [{track_num:02d}] SKIP  {label} — already exists ({size}KB)")
            skipped += 1
            continue

        print(f"  [{track_num:02d}] {label}  ({vid_id})  {start_s}s + {dur_s}s")

        raw = TMP / "download_raw.mp3"
        raw.unlink(missing_ok=True)

        ok = download_audio(vid_id, raw)
        if not ok:
            print(f"    FAIL — download failed, skipping")
            failed.append((track_num, vid_id, label))
            continue

        raw_size = raw.stat().st_size // 1024
        print(f"    Downloaded {raw_size}KB, clipping {start_s}s–{start_s+dur_s}s...")

        clipped = clip_audio(raw, out_file, start_s, dur_s)
        if clipped:
            clip_size = out_file.stat().st_size // 1024
            print(f"    OK  saved {clip_size}KB → {out_file.name}")
            done += 1
        else:
            print(f"    FAIL — clip failed")
            failed.append((track_num, vid_id, label))

        raw.unlink(missing_ok=True)
        time.sleep(1)  # be polite to YouTube

    print(f"\n{'='*60}")
    print(f"  Done:    {done}")
    print(f"  Skipped: {skipped}")
    print(f"  Failed:  {len(failed)}")
    if failed:
        print(f"\n  Failed tracks (re-run with --force --start=N to retry):")
        for num, vid, lbl in failed:
            print(f"    track_{num:02d}  {vid}  ({lbl})")
    print(f"\n  Archive now has {len(list(ARCHIVE.glob('*.mp3')))} tracks total")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
