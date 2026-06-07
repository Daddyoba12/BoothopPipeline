"""
test/church_sunday.py
"Sunday Things" — viral Naija church vibes promo.

Music:   Nigerian gospel — Mercy Chinwo / Moses Bliss / Sinach / Tim Godfrey
         Auto-searches YouTube each week, trims 35s.

Visuals: African church, praise & worship, choir dancing, Sunday best fashion,
         congregation celebrating — joyful Naija church energy.

Comic hooks (funny Naija Sunday vibes):
  "POV: You're in church giving Sunday testimony..."
  "Pastor said: Who has a testimony? Stand up."
  "Me: My package from London reached Lagos SAME DAY."
  "Before offering time. Before the benediction."
  "BOOTHOP did that. Hallelujah somebody!"

Closing: Glass card  -  Join BootHop  -  boothop.com

Run:  python test/church_sunday.py
"""

import json, random, subprocess, sys
import requests
from datetime import datetime
from pathlib import Path

BASE   = Path(__file__).parent.parent
TEST   = Path(__file__).parent
ASSETS = BASE / "assets"
TEMP   = BASE / "temp"

sys.path.insert(0, str(BASE / "scripts"))
from media_blocklist import blocked_video_ids

TEMP.mkdir(exist_ok=True)
TEST.mkdir(exist_ok=True)

LOGO      = ASSETS / "mainlogo.png"
FONT_BOLD = str(ASSETS / "fonts" / "Oswald-Bold.ttf").replace("\\", "/").replace("C:/", "C\\:/")
FONT_BODY = str(ASSETS / "fonts" / "Montserrat-ExtraBold.ttf").replace("\\", "/").replace("C:/", "C\\:/")

OUT_MP4    = TEST / "church_sunday.mp4"
AUDIO_FILE = TEST / "church_audio.mp3"
TOTAL_DUR  = 35   # 30s story + 5s closing card

PEXELS_API_KEY  = "NY3tWysBJseeky8V1JEp2YjevIq6MTYcOCfuKNBU7iypjC7Qc5T1DTp5"
PEXELS_API_KEY2 = "OzT25PmEv1Vuj6xvOWhIAvAYyUz7kx9D2oAdmwKqWzMMzC089kxkHXnBB"
PIXABAY_API_KEY = "56176396-606d84f73894d89a364d530f0"

APPROVED_CLIPS = [
    TEST / "dance_37964256.mp4",
    TEST / "dance_37964255.mp4",
    TEST / "dance_3044531.mp4",
]

# ── Nigerian gospel artist rotation ───────────────────────────────────────────
GOSPEL_ROTATION = [
    ("Mercy Chinwo",   "Mercy Chinwo 2025 latest Nigerian gospel song"),
    ("Moses Bliss",    "Moses Bliss 2025 latest gospel hit Nigeria"),
    ("Sinach",         "Sinach 2025 latest gospel song Nigeria"),
    ("Tim Godfrey",    "Tim Godfrey 2025 latest Nigerian gospel praise"),
    ("Nathaniel Bassey","Nathaniel Bassey 2025 latest gospel Nigeria"),
    ("Frank Edwards",  "Frank Edwards 2025 latest gospel Nigeria"),
]
_week = datetime.now().isocalendar()[1]
ARTIST_NAME, ARTIST_SEARCH = GOSPEL_ROTATION[_week % len(GOSPEL_ROTATION)]

# ── Funny Naija church comic hooks ─────────────────────────────────────────────
# timing: (start_s, end_s, line, colour)
COMIC_HOOKS = [
    (1.5,   8.0,  "POV: Sunday service. Pastor says give a testimony.", "#ffffff"),
    (8.0,  15.0,  "Me: My package left London on Friday...", "#fb923c"),
    (15.0, 21.5,  "A verified traveller carried it. Same route. Same day.", "#facc15"),
    (21.5, 27.5,  "Mum got it before offering time. TRUE STORY.", "#10b981"),
    (27.5, 30.0,  "Thank God! BootHop did that!", "#ffffff"),
]

# ── Church & gospel clip queries ───────────────────────────────────────────────
LIFESTYLE_QUERIES = [
    "african people dancing celebration joyful",
    "african woman dancing happy excited",
    "black woman sunday best outfit fashion portrait",
    "african group celebration party dancing",
    "nigerian woman fashion portrait smiling",
    "black people celebrating together joyful",
    "african woman excited hands up happy",
    "african man dancing celebration street",
    "black woman singing joyful happy",
    "african family celebration dancing together",
    "gospel choir singing together joyful",
    "african woman worship hands raised",
    "black church fashion sunday portrait",
    "african celebration street music dance",
    "nigerian fashion portrait outdoor happy",
]

PIXABAY_QUERIES = [
    "africa celebration dance joyful",
    "african woman dancing happy",
    "gospel music choir singing",
    "black people dancing celebration",
    "nigeria street dance celebration",
    "african church worship praise",
    "african woman portrait smiling",
    "black woman excited celebration fashion",
]


# ── 1. Gospel music ────────────────────────────────────────────────────────────

def get_weekly_music() -> Path | None:
    cached = TEST / f"church_audio_{_week}_{ARTIST_NAME.replace(' ', '_')}.mp3"
    if cached.exists() and cached.stat().st_size > 80_000:
        print(f"  [Music] Cached: {cached.name}")
        import shutil; shutil.copy(cached, AUDIO_FILE)
        return AUDIO_FILE

    print(f"  [Music] Searching: {ARTIST_SEARCH}")
    try:
        r = subprocess.run(
            ["yt-dlp", "--no-playlist", "--get-id", "--no-warnings",
             "--match-filter", "duration < 600",
             f"ytsearch1:{ARTIST_SEARCH}"],
            capture_output=True, text=True, timeout=30,
        )
        vid_id = r.stdout.strip().splitlines()[0].strip() if r.stdout.strip() else ""
    except Exception as e:
        print(f"  [Music] yt-dlp error: {e}")
        return _fallback_music()

    if not vid_id:
        print("  [Music] No result")
        return _fallback_music()

    raw_template = str(TEST / f"church_raw_{_week}")
    try:
        subprocess.run(
            ["yt-dlp", "--no-playlist", "-f", "bestaudio", "--no-warnings",
             "-o", f"{raw_template}.%(ext)s",
             f"https://www.youtube.com/watch?v={vid_id}"],
            capture_output=True, text=True, timeout=120,
        )
    except Exception as e:
        print(f"  [Music] Download error: {e}")
        return _fallback_music()

    raw_file = None
    for ext in ["webm", "m4a", "opus", "ogg", "mp3", "aac"]:
        c = TEST / f"church_raw_{_week}.{ext}"
        if c.exists() and c.stat().st_size > 200_000:
            raw_file = c
            break

    if not raw_file:
        print("  [Music] Download failed — fallback")
        return _fallback_music()

    print(f"  [Music] Downloaded: {raw_file.name}")

    # Trim from 45s in (skip intro/quiet parts typical in gospel)
    subprocess.run(
        ["ffmpeg", "-y", "-ss", "45", "-t", str(TOTAL_DUR),
         "-i", str(raw_file), "-c:a", "libmp3lame", "-q:a", "2", str(cached)],
        capture_output=True,
    )

    if cached.exists() and cached.stat().st_size > 30_000:
        import shutil; shutil.copy(cached, AUDIO_FILE)
        print(f"  [Music] Trimmed -> {AUDIO_FILE.name}  ({ARTIST_NAME})")
        return AUDIO_FILE

    print("  [Music] Trim failed — fallback")
    return _fallback_music()


def _fallback_music() -> Path | None:
    trim = TEST / "audio_trim.mp3"
    if trim.exists() and trim.stat().st_size > 30_000:
        print("  [Music] Fallback: audio_trim.mp3")
        return trim
    for folder in [BASE / "music" / "daily", BASE / "music" / "archive"]:
        if folder.exists():
            tracks = list(folder.glob("*.mp3")) + list(folder.glob("*.m4a"))
            if tracks:
                t = random.choice(tracks)
                print(f"  [Music] Fallback: {t.name}")
                return t
    return None


# ── 2. Church clips (Pexels + Pixabay) ────────────────────────────────────────

def _best_portrait_url(video: dict) -> str | None:
    files = video.get("video_files", [])
    portrait = sorted(
        [f for f in files if f.get("height", 0) > f.get("width", 0)],
        key=lambda x: x.get("height", 0), reverse=True,
    )
    if not portrait:
        portrait = sorted(files, key=lambda x: x.get("height", 0), reverse=True)
    for f in portrait:
        if f.get("height", 0) >= 720:
            return f["link"]
    return portrait[0]["link"] if portrait else None


def _download_clip(url: str, dest: Path) -> bool:
    try:
        r = requests.get(url, stream=True, timeout=60)
        with open(dest, "wb") as fh:
            for chunk in r.iter_content(65536):
                fh.write(chunk)
        if dest.stat().st_size > 50_000:
            return True
        dest.unlink(missing_ok=True)
        return False
    except Exception as e:
        print(f"    Download error: {e}")
        return False


def download_church_clips(want: int = 7) -> list[Path]:
    clips, tried = [], set()
    _blocked = blocked_video_ids()

    for key_label, api_key in [("Pexels-1", PEXELS_API_KEY), ("Pexels-2", PEXELS_API_KEY2)]:
        if len(clips) >= want:
            break
        for query in LIFESTYLE_QUERIES:
            if len(clips) >= want:
                break
            print(f"  [{key_label}] {query}")
            try:
                resp = requests.get(
                    "https://api.pexels.com/videos/search",
                    headers={"Authorization": api_key},
                    params={"query": query, "per_page": 6, "orientation": "portrait"},
                    timeout=15,
                )
                videos = resp.json().get("videos", [])
                if not videos:
                    print(f"    0 results ({resp.status_code})")
            except Exception as e:
                print(f"    {e}")
                continue

            for vid in videos:
                if len(clips) >= want:
                    break
                vid_id = vid["id"]
                if vid_id in tried or int(vid_id) in _blocked:
                    continue
                tried.add(vid_id)
                url = _best_portrait_url(vid)
                if not url:
                    continue
                dest = TEST / f"church_{vid_id}.mp4"
                if dest.exists() and dest.stat().st_size > 50_000:
                    clips.append(dest)
                    print(f"    Cached -> {dest.name}")
                    continue
                if _download_clip(url, dest):
                    clips.append(dest)
                    print(f"    Got    -> {dest.name}  ({dest.stat().st_size // 1024} KB)")

    if len(clips) < want:
        for query in PIXABAY_QUERIES:
            if len(clips) >= want:
                break
            print(f"  [Pixabay] {query}")
            try:
                resp = requests.get(
                    "https://pixabay.com/api/videos/",
                    params={
                        "key": PIXABAY_API_KEY,
                        "q": query,
                        "per_page": 6,
                        "video_type": "film",
                        "orientation": "vertical",
                    },
                    timeout=15,
                )
                hits = resp.json().get("hits", [])
                if not hits:
                    print(f"    0 results ({resp.status_code})")
            except Exception as e:
                print(f"    {e}")
                continue

            for hit in hits:
                if len(clips) >= want:
                    break
                vid_id = hit["id"]
                if vid_id in tried or int(vid_id) in _blocked:
                    continue
                tried.add(vid_id)
                videos_map = hit.get("videos", {})
                url = None
                for quality in ("large", "medium", "small", "tiny"):
                    q = videos_map.get(quality, {})
                    if q.get("url"):
                        url = q["url"]
                        break
                if not url:
                    continue
                dest = TEST / f"church_pb_{vid_id}.mp4"
                if dest.exists() and dest.stat().st_size > 50_000:
                    clips.append(dest)
                    print(f"    Cached -> {dest.name}")
                    continue
                if _download_clip(url, dest):
                    clips.append(dest)
                    print(f"    Got    -> {dest.name}  ({dest.stat().st_size // 1024} KB)")

    return clips


# ── 3. Beat detection ──────────────────────────────────────────────────────────

def detect_beats(audio_path: Path) -> list[float]:
    try:
        import librosa
        y, sr = librosa.load(str(audio_path), duration=float(TOTAL_DUR))
        tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
        all_beats = librosa.frames_to_time(beat_frames, sr=sr).tolist()
        cuts = [0.0]
        for t in all_beats:
            if float(t) - cuts[-1] >= 1.5 and float(t) < TOTAL_DUR - 1.5:
                cuts.append(round(float(t), 3))
        bpm = float(tempo) if hasattr(tempo, "__float__") else 90.0
        print(f"  [Beats] {len(cuts)} cuts  ~{bpm:.0f} BPM")
        return cuts
    except Exception as e:
        print(f"  [Beats] {e} — 2.4s grid")
        cuts, t = [0.0], 0.0
        while t + 2.4 < TOTAL_DUR - 1.5:
            t += 2.4; cuts.append(round(t, 3))
        return cuts


# ── 4. Render ──────────────────────────────────────────────────────────────────

def render(clips: list[Path], audio: Path | None, beat_cuts: list[float]) -> bool:
    if not clips:
        print("  [Render] No clips")
        return False

    safe = [c for c in APPROVED_CLIPS if c.exists()]
    pool = clips + safe
    random.shuffle(pool)

    segments: list[tuple[Path, float, float]] = []
    for i in range(len(beat_cuts)):
        t0  = beat_cuts[i]
        t1  = beat_cuts[i + 1] if i + 1 < len(beat_cuts) else TOTAL_DUR
        dur = round(t1 - t0, 3)
        if dur < 0.3:
            continue
        clip = pool[i % len(pool)]
        seek = round(random.uniform(0.5, 6.0), 2)
        segments.append((clip, seek, dur))

    n_segs = len(segments)
    print(f"  [Render] {n_segs} beat segments")

    inputs: list[str] = []
    for clip, seek, _ in segments:
        inputs += ["-ss", str(seek), "-i", str(clip)]

    audio_idx = None
    if audio and audio.exists():
        audio_idx = n_segs
        inputs += ["-i", str(audio)]

    logo_s_idx = logo_b_idx = None
    if LOGO.exists():
        _b = n_segs + (1 if audio_idx is not None else 0)
        logo_s_idx, logo_b_idx = _b, _b + 1
        inputs += ["-loop", "1", "-i", str(LOGO)]
        inputs += ["-loop", "1", "-i", str(LOGO)]

    parts: list[str] = []

    for i, (_, _, dur) in enumerate(segments):
        parts.append(
            f"[{i}:v]trim=duration={dur:.3f},setpts=PTS-STARTPTS,"
            f"scale=1080:1920:force_original_aspect_ratio=increase,"
            f"crop=1080:1920,setsar=1,fps=30,"
            f"eq=saturation=1.35:brightness=0.04:contrast=1.08,"
            f"hue=h=6:s=1.08[seg{i}]"
        )

    concat_in = "".join(f"[seg{i}]" for i in range(n_segs))
    parts.append(f"{concat_in}concat=n={n_segs}:v=1:a=0[base]")
    parts.append("[base]vignette=PI/4:eval=frame[vign]")
    base = "[vign]"

    if logo_s_idx is not None:
        parts.append(
            f"[{logo_s_idx}:v]scale=280:-1,format=rgba,colorchannelmixer=aa=0.93[logo_s]"
        )
        parts.append(
            f"[{logo_b_idx}:v]scale=460:-1,format=rgba,colorchannelmixer=aa=0.98[logo_b]"
        )
        parts.append(
            f"{base}[logo_s]overlay=(W-w)/2:80:enable='lt(t,30)'[_s1]"
        )
        parts.append(
            f"[_s1][logo_b]overlay=(W-w)/2:55:enable='gte(t,30)'[with_logo]"
        )
        base = "[with_logo]"

    draw: list[str] = []

    # Artist credit
    artist_safe = ARTIST_NAME.replace("'", "").replace("\\", "")
    draw.append(
        f"drawtext=fontfile='{FONT_BODY}':text='Gospel  {artist_safe}'"
        f":fontsize=26:fontcolor=white@0.60"
        f":borderw=1:bordercolor=black@0.5"
        f":x=w-text_w-20:y=h-44"
        f":enable='lt(t,30)'"
    )

    # "Sunday Things" banner — top of screen, church vibe
    draw.append(
        f"drawtext=fontfile='{FONT_BOLD}':text='SUNDAY THINGS'"
        f":fontsize=54:fontcolor=#facc15"
        f":borderw=4:bordercolor=black@0.90"
        f":box=1:boxcolor=black@0.55:boxborderw=14"
        f":x=(w-text_w)/2:y=210"
        f":enable='lt(t,30)'"
    )

    # Comic hooks
    for (t_start, t_end, line, color) in COMIC_HOOKS:
        safe_line = (line.replace("\\", "").replace("'", "")
                     .replace(":", " ").replace("...", "...")
                     .encode("ascii", "ignore").decode("ascii"))
        draw.append(
            f"drawtext=fontfile='{FONT_BOLD}':text='{safe_line}'"
            f":fontsize=52:fontcolor=black@0"
            f":box=1:boxcolor=#0a0a1a@0.80:boxborderw=24"
            f":x=(w-text_w)/2:y=h/2+80"
            f":enable='between(t,{t_start},{t_end})'"
        )
        draw.append(
            f"drawtext=fontfile='{FONT_BOLD}':text='{safe_line}'"
            f":fontsize=52:fontcolor={color}"
            f":borderw=4:bordercolor=black@0.90"
            f":x=(w-text_w)/2:y=h/2+80"
            f":enable='between(t,{t_start},{t_end})'"
        )

    # Call to action before closing card
    draw.append(
        f"drawtext=fontfile='{FONT_BODY}':text='Have you got your BootHop testimony?'"
        f":fontsize=32:fontcolor=#facc15"
        f":borderw=3:bordercolor=black@0.80"
        f":box=1:boxcolor=black@0.45:boxborderw=12"
        f":x=(w-text_w)/2:y=h/2+200"
        f":enable='between(t,27,30)'"
    )

    # Glass closing card
    draw.append(
        "drawbox=x=0:y=0:w=iw:h=ih"
        ":color=black@0.68:t=fill"
        ":enable='gte(t,30)'"
    )
    draw.append(
        f"drawtext=fontfile='{FONT_BOLD}':text='Join BootHop'"
        f":fontsize=100:fontcolor=white"
        f":borderw=5:bordercolor=black@0.95"
        f":x=(w-text_w)/2:y=480"
        f":enable='between(t,30,{TOTAL_DUR})'"
    )
    draw.append(
        f"drawtext=fontfile='{FONT_BOLD}':text='Your Package. Your Testimony.'"
        f":fontsize=58:fontcolor=#10b981"
        f":borderw=4:bordercolor=black@0.90"
        f":x=(w-text_w)/2:y=600"
        f":enable='between(t,30.8,{TOTAL_DUR})'"
    )
    draw.append(
        f"drawtext=fontfile='{FONT_BODY}':text='Same day delivery. Trusted travellers.'"
        f":fontsize=30:fontcolor=#d1d5db"
        f":borderw=2:bordercolor=black@0.70"
        f":x=(w-text_w)/2:y=700"
        f":enable='between(t,31.5,{TOTAL_DUR})'"
    )
    draw.append(
        f"drawtext=fontfile='{FONT_BOLD}':text='>> Earn money while you travel!'"
        f":fontsize=50:fontcolor=#facc15"
        f":borderw=4:bordercolor=black@0.90"
        f":box=1:boxcolor=black@0.55:boxborderw=16"
        f":x=(w-text_w)/2:y=810"
        f":enable='between(t,32,{TOTAL_DUR})'"
    )
    draw.append(
        f"drawtext=fontfile='{FONT_BOLD}':text='boothop.com'"
        f":fontsize=62:fontcolor=#10b981"
        f":borderw=4:bordercolor=black@0.88"
        f":box=1:boxcolor=black@0.60:boxborderw=16"
        f":x=(w-text_w)/2:y=h-280"
        f":enable='between(t,32.5,{TOTAL_DUR})'"
    )
    draw.append(
        f"drawtext=fontfile='{FONT_BODY}':text='info@boothop.com  |  +44 115 661 2825'"
        f":fontsize=30:fontcolor=white@0.88"
        f":borderw=2:bordercolor=black@0.80"
        f":x=(w-text_w)/2:y=h-176"
        f":enable='between(t,32.5,{TOTAL_DUR})'"
    )
    draw.append(
        f"drawtext=fontfile='{FONT_BODY}':text='#SundayThings  #BootHop  #NaijaVibes  #GospelDelivery'"
        f":fontsize=22:fontcolor=white@0.62"
        f":borderw=1:bordercolor=black@0.5"
        f":x=(w-text_w)/2:y=h-36"
        f":enable='between(t,33,{TOTAL_DUR})'"
    )

    parts.append(f"{base}{','.join(draw)}[out]")
    filter_complex = ";".join(parts)

    cmd = ["ffmpeg", "-y"] + inputs + [
        "-filter_complex", filter_complex,
        "-map", "[out]",
    ]
    if audio_idx is not None:
        cmd += [
            "-map", f"{audio_idx}:a",
            "-c:a", "aac", "-b:a", "192k",
            "-af", (f"atrim=0:{TOTAL_DUR},asetpts=PTS-STARTPTS,"
                    f"afade=t=out:st={TOTAL_DUR - 2}:d=2"),
        ]
    cmd += [
        "-c:v", "libx264", "-preset", "fast", "-crf", "19",
        "-t", str(TOTAL_DUR),
        "-movflags", "+faststart",
        str(OUT_MP4),
    ]

    print("  [Render] Running ffmpeg...")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0 and OUT_MP4.exists() and OUT_MP4.stat().st_size > 10_000:
        mb = OUT_MP4.stat().st_size / 1_048_576
        print(f"  [Render] Done  ->  {OUT_MP4.name}  ({mb:.1f} MB)")
        return True

    print(f"  [Render] ffmpeg failed (exit {result.returncode}):")
    print(result.stderr[-1200:])
    return False


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    week_num = datetime.now().isocalendar()[1]
    print("\n" + "=" * 60)
    print(f"  BootHop  SUNDAY THINGS  -  Week {week_num}  -  {ARTIST_NAME}")
    print("=" * 60)
    print(f"  Music search: {ARTIST_SEARCH}")
    print(f"  Hooks: {len(COMIC_HOOKS)} church vibes")
    print()

    print("[1] Gospel music...")
    audio = get_weekly_music()

    print("\n[2] Church clips (Pexels + Pixabay)...")
    clips = download_church_clips(want=7)
    safe  = [c for c in APPROVED_CLIPS if c.exists()]
    all_clips = clips + safe

    if not all_clips:
        print("  No clips found — aborting")
        return

    print(f"\n[3] Beat detection...")
    beat_cuts = detect_beats(audio) if audio else [0.0]

    print(f"\n[4] Render...")
    ok = render(all_clips, audio, beat_cuts)

    if ok:
        print(f"\nDone!  ->  {OUT_MP4}")
    else:
        print("\nRender failed.")


if __name__ == "__main__":
    main()
