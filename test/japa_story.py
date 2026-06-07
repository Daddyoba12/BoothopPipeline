"""
test/japa_story.py
"Japa to Japada" — postcard story reel with beautiful African women.

4 postcard slides + closing card:
  Card 1 (0-7.5s)  : "First... I was broke."
  Card 2 (7.5-15s) : "Then someone showed me BootHop."
  Card 3 (15-22.5s): "From Japa to Japada. Running my own thing."
  Card 4 (22.5-30s): "Earn while you travel. Every trip pays."
  Closing (30-35s) : Glass card — Join BootHop / boothop.com

Music: R&B Afrobeats — Tems / Ayra Starr / Simi / Teni / Tiwa Savage
       Auto-searches YouTube weekly, trims 35s from 60s in (skip intros).

Run: python test/japa_story.py
"""

import random, subprocess, sys
import requests
from datetime import datetime
from pathlib import Path

BASE   = Path(__file__).parent.parent
TEST   = Path(__file__).parent
ASSETS = BASE / "assets"

sys.path.insert(0, str(BASE / "scripts"))
from media_blocklist import blocked_video_ids

LOGO      = ASSETS / "mainlogo.png"
FONT_BOLD = str(ASSETS / "fonts" / "Oswald-Bold.ttf").replace("\\", "/").replace("C:/", "C\\:/")
FONT_BODY = str(ASSETS / "fonts" / "Montserrat-ExtraBold.ttf").replace("\\", "/").replace("C:/", "C\\:/")

OUT_MP4    = TEST / "japa_story.mp4"
AUDIO_FILE = TEST / "japa_audio.mp3"
TOTAL_DUR  = 35
CARD_DUR   = 7.5   # each postcard = 7.5s  (4 cards = 30s)

PEXELS_API_KEY  = "NY3tWysBJseeky8V1JEp2YjevIq6MTYcOCfuKNBU7iypjC7Qc5T1DTp5"
PEXELS_API_KEY2 = "OzT25PmEv1Vuj6xvOWhIAvAYyUz7kx9D2oAdmwKqWzMMzC089kxkHXnBB"
PIXABAY_API_KEY = "56176396-606d84f73894d89a364d530f0"

# ── R&B / Afrobeats female artist rotation ────────────────────────────────────
RNB_ROTATION = [
    ("Tems",         "Tems 2025 latest R&B afrobeats song"),
    ("Ayra Starr",   "Ayra Starr 2025 latest hit afrobeats"),
    ("Simi",         "Simi 2025 latest song Nigeria R&B"),
    ("Teni",         "Teni 2025 latest afropop song Nigeria"),
    ("Tiwa Savage",  "Tiwa Savage 2025 latest R&B afrobeats"),
    ("Yemi Alade",   "Yemi Alade 2025 latest afropop song"),
]
_week = datetime.now().isocalendar()[1]
ARTIST_NAME, ARTIST_SEARCH = RNB_ROTATION[_week % len(RNB_ROTATION)]

# ── Postcard story text ────────────────────────────────────────────────────────
# (card_index, start_s, end_s, top_line, main_line, sub_line, main_color)
POSTCARDS = [
    (0,  0.5,  7.0,
     "She used to say...",
     "I was broke.",
     "Two jobs. Sending money home. Nothing left for me.",
     "#ffffff"),

    (1,  8.0, 14.5,
     "Then a friend whispered...",
     "Try BootHop.",
     "Carry a package on your next trip. Get paid. Simple.",
     "#facc15"),

    (2, 15.5, 22.0,
     "From Japa...",
     "to Japada.",
     "Now she travels. Every trip earns. She runs her own thing.",
     "#10b981"),

    (3, 23.0, 29.5,
     "You could be next.",
     "Earn while you travel.",
     "Thousands of verified BootHop travellers already do.",
     "#fb923c"),
]

# ── Beautiful African women clip queries ──────────────────────────────────────
# 4 groups — one per card, each targeted to the card mood
CARD_QUERIES = [
    # Card 1 — contemplative, beautiful, quiet strength
    [
        "african woman beautiful portrait thinking",
        "black woman sad thoughtful beautiful",
        "african woman window light portrait",
        "nigerian woman beautiful serious portrait",
    ],
    # Card 2 — curious, hopeful, phone/discovery moment
    [
        "african woman phone smiling excited",
        "black woman happy discovery smiling portrait",
        "african woman looking up hopeful beautiful",
        "nigerian woman excited happy phone",
    ],
    # Card 3 — confident, successful, travel, boss energy
    [
        "african woman confident successful boss",
        "black woman travel airport stylish",
        "african woman luxury lifestyle glamorous",
        "nigerian woman entrepreneur confident portrait",
    ],
    # Card 4 — joyful, dancing, celebrating, call to action
    [
        "african woman dancing joyful celebration",
        "black woman excited happy arms raised",
        "african woman stylish fashion celebrating",
        "nigerian woman glamorous happy portrait",
    ],
]

# Extra fallback queries (broad, high-yield)
FALLBACK_QUERIES = [
    "african woman beautiful confident portrait",
    "black woman glamorous fashion editorial",
    "african woman stylish elegant portrait",
    "black woman model beautiful portrait",
    "african woman luxury lifestyle fashion",
    "nigerian woman beautiful smiling outdoor",
    "black woman sexy confident fashion portrait",
    "african woman success entrepreneur smiling",
]


# ── 1. Music ───────────────────────────────────────────────────────────────────

def get_music() -> Path | None:
    cached = TEST / f"japa_audio_{_week}_{ARTIST_NAME.replace(' ', '_')}.mp3"
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
        return _fallback_music()

    raw_template = str(TEST / f"japa_raw_{_week}")
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
        c = TEST / f"japa_raw_{_week}.{ext}"
        if c.exists() and c.stat().st_size > 200_000:
            raw_file = c
            break

    if not raw_file:
        return _fallback_music()

    print(f"  [Music] Downloaded: {raw_file.name}")
    subprocess.run(
        ["ffmpeg", "-y", "-ss", "60", "-t", str(TOTAL_DUR),
         "-i", str(raw_file), "-c:a", "libmp3lame", "-q:a", "2", str(cached)],
        capture_output=True,
    )

    if cached.exists() and cached.stat().st_size > 30_000:
        import shutil; shutil.copy(cached, AUDIO_FILE)
        print(f"  [Music] Ready: {ARTIST_NAME}")
        return AUDIO_FILE

    return _fallback_music()


def _fallback_music() -> Path | None:
    for folder in [BASE / "music" / "daily", BASE / "music" / "archive"]:
        if folder.exists():
            tracks = list(folder.glob("*.mp3")) + list(folder.glob("*.m4a"))
            if tracks:
                t = random.choice(tracks)
                print(f"  [Music] Fallback: {t.name}")
                return t
    return None


# ── 2. Download one clip per card ─────────────────────────────────────────────

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
        return dest.stat().st_size > 50_000
    except Exception as e:
        print(f"    Download error: {e}")
        dest.unlink(missing_ok=True)
        return False


def _try_pexels(query: str, api_key: str, label: str,
                tried: set, _blocked: set, card_idx: int) -> Path | None:
    print(f"  [{label}] {query}")
    try:
        resp = requests.get(
            "https://api.pexels.com/videos/search",
            headers={"Authorization": api_key},
            params={"query": query, "per_page": 8, "orientation": "portrait"},
            timeout=15,
        )
        videos = resp.json().get("videos", [])
    except Exception as e:
        print(f"    {e}"); return None

    for vid in videos:
        vid_id = vid["id"]
        if vid_id in tried or int(vid_id) in _blocked:
            continue
        tried.add(vid_id)
        url = _best_portrait_url(vid)
        if not url:
            continue
        dest = TEST / f"japa_c{card_idx}_{vid_id}.mp4"
        if dest.exists() and dest.stat().st_size > 50_000:
            print(f"    Cached -> {dest.name}")
            return dest
        if _download_clip(url, dest):
            print(f"    Got    -> {dest.name}  ({dest.stat().st_size // 1024} KB)")
            return dest
    return None


def _try_pixabay(query: str, tried: set, _blocked: set, card_idx: int) -> Path | None:
    print(f"  [Pixabay] {query}")
    try:
        resp = requests.get(
            "https://pixabay.com/api/videos/",
            params={"key": PIXABAY_API_KEY, "q": query,
                    "per_page": 6, "video_type": "film", "orientation": "vertical"},
            timeout=15,
        )
        hits = resp.json().get("hits", [])
    except Exception as e:
        print(f"    {e}"); return None

    for hit in hits:
        vid_id = hit["id"]
        if vid_id in tried or int(vid_id) in _blocked:
            continue
        tried.add(vid_id)
        videos_map = hit.get("videos", {})
        url = None
        for q in ("large", "medium", "small", "tiny"):
            if videos_map.get(q, {}).get("url"):
                url = videos_map[q]["url"]; break
        if not url:
            continue
        dest = TEST / f"japa_c{card_idx}_pb_{vid_id}.mp4"
        if dest.exists() and dest.stat().st_size > 50_000:
            print(f"    Cached -> {dest.name}")
            return dest
        if _download_clip(url, dest):
            print(f"    Got    -> {dest.name}  ({dest.stat().st_size // 1024} KB)")
            return dest
    return None


def download_card_clips() -> list[Path | None]:
    """Download one beautiful clip per card. Returns list of 4 paths (or None if failed)."""
    _blocked = blocked_video_ids()
    clips = []

    for card_idx, queries in enumerate(CARD_QUERIES):
        print(f"\n  [Card {card_idx + 1}] Finding clip...")
        tried: set = set()
        clip = None

        # Try Pexels key 1
        for q in queries:
            clip = _try_pexels(q, PEXELS_API_KEY, "Pexels-1", tried, _blocked, card_idx)
            if clip:
                break

        # Pexels key 2
        if not clip:
            for q in queries:
                clip = _try_pexels(q, PEXELS_API_KEY2, "Pexels-2", tried, _blocked, card_idx)
                if clip:
                    break

        # Fallback queries (broad)
        if not clip:
            for q in FALLBACK_QUERIES:
                clip = _try_pexels(q, PEXELS_API_KEY, "Pexels-F", tried, _blocked, card_idx)
                if clip:
                    break

        # Pixabay
        if not clip:
            for q in queries + FALLBACK_QUERIES[:3]:
                clip = _try_pixabay(q, tried, _blocked, card_idx)
                if clip:
                    break

        if clip:
            print(f"  [Card {card_idx + 1}] OK: {clip.name}")
        else:
            print(f"  [Card {card_idx + 1}] WARNING: no clip found")
        clips.append(clip)

    return clips


# ── 3. Render ──────────────────────────────────────────────────────────────────

def render(clips: list[Path | None], audio: Path | None) -> bool:
    # Fill missing clips with any available clip
    available = [c for c in clips if c and c.exists()]
    if not available:
        print("  [Render] No clips at all — aborting")
        return False

    card_clips = [c if (c and c.exists()) else random.choice(available)
                  for c in clips]

    inputs: list[str] = []

    # 4 card clips
    for clip in card_clips:
        inputs += ["-i", str(clip)]

    audio_idx = None
    if audio and audio.exists():
        audio_idx = 4
        inputs += ["-i", str(audio)]

    logo_s_idx = logo_b_idx = None
    if LOGO.exists():
        _b = 4 + (1 if audio_idx is not None else 0)
        logo_s_idx, logo_b_idx = _b, _b + 1
        inputs += ["-loop", "1", "-i", str(LOGO)]
        inputs += ["-loop", "1", "-i", str(LOGO)]

    parts: list[str] = []

    # Cinematic slow clip per card — slight Ken Burns zoom
    for i in range(4):
        dur = CARD_DUR
        parts.append(
            f"[{i}:v]trim=duration={dur:.1f},setpts=PTS-STARTPTS,"
            f"scale=1180:2100:force_original_aspect_ratio=increase,"
            f"crop=1080:1920,setsar=1,fps=30,"
            f"eq=saturation=1.25:brightness=0.02:contrast=1.08,"
            f"zoompan=z='min(zoom+0.0004,1.06)':d={int(dur*30)}:s=1080x1920[seg{i}]"
        )

    # Concat all 4 cards (30s) then closing card = closing card reuses card 3 clip
    concat_in = "".join(f"[seg{i}]" for i in range(4))
    parts.append(f"{concat_in}concat=n=4:v=1:a=0[story]")

    # Closing card: darken card 3 clip for extra 5s
    parts.append(
        f"[3:v]trim=duration=5,setpts=PTS-STARTPTS,"
        f"scale=1180:2100:force_original_aspect_ratio=increase,"
        f"crop=1080:1920,setsar=1,fps=30,"
        f"eq=saturation=1.1:brightness=-0.05:contrast=1.05[closing_clip]"
    )
    parts.append("[story][closing_clip]concat=n=2:v=1:a=0[base]")
    parts.append("[base]vignette=PI/5:eval=frame[vign]")
    base = "[vign]"

    # Logo — small during story, large on closing card
    if logo_s_idx is not None:
        parts.append(
            f"[{logo_s_idx}:v]scale=240:-1,format=rgba,colorchannelmixer=aa=0.90[logo_s]"
        )
        parts.append(
            f"[{logo_b_idx}:v]scale=440:-1,format=rgba,colorchannelmixer=aa=0.97[logo_b]"
        )
        parts.append(
            f"{base}[logo_s]overlay=(W-w)/2:70:enable='lt(t,30)'[_s1]"
        )
        parts.append(
            f"[_s1][logo_b]overlay=(W-w)/2:55:enable='gte(t,30)'[with_logo]"
        )
        base = "[with_logo]"

    draw: list[str] = []

    # Artist credit
    artist_safe = ARTIST_NAME.replace("'", "").replace("\\", "")
    draw.append(
        f"drawtext=fontfile='{FONT_BODY}':text='Music  {artist_safe}'"
        f":fontsize=24:fontcolor=white@0.55"
        f":borderw=1:bordercolor=black@0.5"
        f":x=w-text_w-18:y=h-40"
        f":enable='lt(t,30)'"
    )

    # Postcard number indicator — small pill top right per card
    card_labels = ["01", "02", "03", "04"]
    for i, label in enumerate(card_labels):
        t0 = i * CARD_DUR
        t1 = t0 + CARD_DUR
        draw.append(
            f"drawtext=fontfile='{FONT_BOLD}':text='{label} / 04'"
            f":fontsize=28:fontcolor=white@0.70"
            f":borderw=2:bordercolor=black@0.6"
            f":x=w-text_w-30:y=120"
            f":enable='between(t,{t0:.1f},{t1:.1f})'"
        )

    # Each postcard — dark gradient bar at bottom, then 3 lines of text
    for (card_idx, t0, t1, top_line, main_line, sub_line, main_color) in POSTCARDS:
        # Dark bar bottom half — "postcard" feel
        draw.append(
            f"drawbox=x=0:y=ih*0.52:w=iw:h=ih*0.48"
            f":color=black@0.72:t=fill"
            f":enable='between(t,{t0:.1f},{t1:.1f})'"
        )
        # Top italic line
        safe_top = top_line.replace("'", "").replace("\\", "")
        draw.append(
            f"drawtext=fontfile='{FONT_BODY}':text='{safe_top}'"
            f":fontsize=32:fontcolor=white@0.75"
            f":borderw=2:bordercolor=black@0.70"
            f":x=(w-text_w)/2:y=h*0.57"
            f":enable='between(t,{t0:.1f},{t1:.1f})'"
        )
        # Big main line
        safe_main = main_line.replace("'", "").replace("\\", "")
        draw.append(
            f"drawtext=fontfile='{FONT_BOLD}':text='{safe_main}'"
            f":fontsize=88:fontcolor={main_color}"
            f":borderw=5:bordercolor=black@0.92"
            f":x=(w-text_w)/2:y=h*0.63"
            f":enable='between(t,{t0:.1f},{t1:.1f})'"
        )
        # Sub line
        safe_sub = sub_line.replace("'", "").replace("\\", "")
        draw.append(
            f"drawtext=fontfile='{FONT_BODY}':text='{safe_sub}'"
            f":fontsize=30:fontcolor=white@0.85"
            f":borderw=2:bordercolor=black@0.70"
            f":x=(w-text_w)/2:y=h*0.80"
            f":enable='between(t,{t0:.1f},{t1:.1f})'"
        )

    # Glass closing card (30-35s)
    draw.append(
        "drawbox=x=0:y=0:w=iw:h=ih"
        ":color=black@0.70:t=fill"
        ":enable='gte(t,30)'"
    )
    draw.append(
        f"drawtext=fontfile='{FONT_BOLD}':text='Join the Movement'"
        f":fontsize=80:fontcolor=white"
        f":borderw=5:bordercolor=black@0.95"
        f":x=(w-text_w)/2:y=430"
        f":enable='gte(t,30.5)'"
    )
    draw.append(
        f"drawtext=fontfile='{FONT_BOLD}':text='Join BootHop'"
        f":fontsize=96:fontcolor=#10b981"
        f":borderw=5:bordercolor=black@0.95"
        f":x=(w-text_w)/2:y=540"
        f":enable='gte(t,31)'"
    )
    draw.append(
        f"drawtext=fontfile='{FONT_BODY}':text='Same day delivery. Trusted travellers.'"
        f":fontsize=30:fontcolor=#d1d5db"
        f":borderw=2:bordercolor=black@0.70"
        f":x=(w-text_w)/2:y=670"
        f":enable='gte(t,31.5)'"
    )
    draw.append(
        f"drawtext=fontfile='{FONT_BOLD}':text='>> Earn money while you travel!'"
        f":fontsize=48:fontcolor=#facc15"
        f":borderw=4:bordercolor=black@0.90"
        f":box=1:boxcolor=black@0.50:boxborderw=14"
        f":x=(w-text_w)/2:y=790"
        f":enable='gte(t,32)'"
    )
    draw.append(
        f"drawtext=fontfile='{FONT_BOLD}':text='boothop.com'"
        f":fontsize=60:fontcolor=#10b981"
        f":borderw=4:bordercolor=black@0.88"
        f":box=1:boxcolor=black@0.55:boxborderw=14"
        f":x=(w-text_w)/2:y=h-290"
        f":enable='gte(t,32.5)'"
    )
    draw.append(
        f"drawtext=fontfile='{FONT_BODY}':text='info@boothop.com  |  +44 115 661 2825'"
        f":fontsize=28:fontcolor=white@0.88"
        f":borderw=2:bordercolor=black@0.80"
        f":x=(w-text_w)/2:y=h-180"
        f":enable='gte(t,32.5)'"
    )
    draw.append(
        f"drawtext=fontfile='{FONT_BODY}':text='#JapaToJapada  #BootHop  #EarnWhileYouTravel  #NaijaWomen'"
        f":fontsize=22:fontcolor=white@0.60"
        f":borderw=1:bordercolor=black@0.5"
        f":x=(w-text_w)/2:y=h-38"
        f":enable='gte(t,33)'"
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
                    f"afade=t=out:st={TOTAL_DUR - 2.5}:d=2.5"),
        ]
    cmd += [
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-t", str(TOTAL_DUR),
        "-movflags", "+faststart",
        str(OUT_MP4),
    ]

    print("  [Render] Running ffmpeg...")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

    if result.returncode == 0 and OUT_MP4.exists() and OUT_MP4.stat().st_size > 10_000:
        mb = OUT_MP4.stat().st_size / 1_048_576
        print(f"  [Render] Done  ->  {OUT_MP4.name}  ({mb:.1f} MB)")
        return True

    print(f"  [Render] ffmpeg failed (exit {result.returncode}):")
    print(result.stderr[-2000:])
    return False


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    week_num = datetime.now().isocalendar()[1]
    print("\n" + "=" * 60)
    print(f"  BootHop  JAPA TO JAPADA  -  Week {week_num}  -  {ARTIST_NAME}")
    print("=" * 60 + "\n")

    print("[1] R&B music...")
    audio = get_music()

    print("\n[2] Finding 4 beautiful African lady clips (one per card)...")
    clips = download_card_clips()

    print("\n[3] Rendering postcard story...")
    ok = render(clips, audio)

    if ok:
        print(f"\nDone!  ->  {OUT_MP4}")
    else:
        print("\nRender failed.")


if __name__ == "__main__":
    main()
