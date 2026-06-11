"""
BootHop Explainer Video Generator
===================================
Builds a professional ~60s video:
  Part 1 (0–30s): Live Pexels clips + narrative text overlays
  Part 2 (30–60s): Branded slideshow — 6 slides × 5s

Outputs:
  output/explainer/boothop_explainer_vertical.mp4    1080×1920  TikTok / Instagram Reel
  output/explainer/boothop_explainer_landscape.mp4   1920×1080  YouTube / Demo submission

Run:
  python scripts/make_explainer_video.py
"""

import os, sys, json, asyncio, subprocess, shutil, random, textwrap
from pathlib import Path
from datetime import datetime

import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE     = Path(r"C:\Users\babso\Desktop\BootHopPipeline")
ASSETS   = BASE / "assets"
FONTS    = ASSETS / "fonts"
TEMP     = BASE / "temp" / "explainer"
OUT_DIR  = BASE / "output" / "explainer"

LOGO_PATH  = ASSETS / "mainlogo.png"
SITE_PATH  = ASSETS / "site_hires.png"

FONT_TITLE = str(FONTS / "Oswald-Bold.ttf")
FONT_BODY  = str(FONTS / "Montserrat-ExtraBold.ttf")

PEXELS_KEY       = "NY3tWysBJseeky8V1JEp2YjevIq6MTYcOCfuKNBU7iypjC7Qc5T1DTp5"
TELEGRAM_TOKEN   = "8717698733:AAF7GI9Yw1DhdYVv_TK35fYQcwaGdk4caeA"
TELEGRAM_CHAT_ID = "8641867751"

# ── Brand colours ─────────────────────────────────────────────────────────────
YELLOW  = (255, 220, 0)
BLACK   = (0, 0, 0)
WHITE   = (255, 255, 255)
DARK    = (8, 8, 20)          # near-black navy
GREY    = (160, 160, 160)

# Force UTF-8
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── Voiceover script ──────────────────────────────────────────────────────────
VOICEOVER_SCRIPT = """
BootHop is changing the way urgent deliveries cross borders.

Traditional courier services cost hundreds of pounds and take days.
But every day, thousands of trusted people are already flying the exact routes your package needs.

BootHop connects you with verified travellers already making that journey.
Your item travels safely, legally — and arrives the same day.

Send medication to a parent in Lagos.
Get urgent business parts to Frankfurt.
Save a wedding with last-minute delivery from London.

Here is how it works.
Post your delivery need.
Match with a verified traveller heading your way.
Track and receive — same day.

BootHop. Verified travellers. Same-day delivery. Up to ninety percent cheaper.

Join the movement. Visit boothop dot com.
""".strip()

# ── Slide definitions ─────────────────────────────────────────────────────────
SLIDES = [
    {
        "title": "THE PROBLEM",
        "lines": [
            "Same-day courier across borders:",
            "£400+ and 3–5 days",
            "",
            "But someone trusted is already",
            "flying that route tonight.",
        ],
        "accent": True,
    },
    {
        "title": "THE SOLUTION",
        "lines": [
            "Peer-to-peer delivery powered",
            "by verified travellers",
            "",
            "Someone going your way",
            "carries your item — safe,",
            "legal, same-day.",
        ],
        "accent": False,
        "logo": True,
    },
    {
        "title": "HOW IT WORKS",
        "steps": [
            ("01", "Post your delivery need"),
            ("02", "Match with a verified traveller"),
            ("03", "Track & receive — same day"),
        ],
    },
    {
        "title": "WHY BOOTHOP",
        "bullets": [
            "Up to 90% cheaper than couriers",
            "Same-day UK  Nigeria  EU  Africa",
            "Stripe escrow protection",
            "AI-assisted customs compliance",
            "Verified travellers on every route",
        ],
    },
    {
        "title": "USE CASES",
        "cases": [
            ("FAMILY",   "Medication, gifts, documents"),
            ("BUSINESS", "Urgent parts, samples, contracts"),
            ("AIRPORT",  "Passport, papers, emergency items"),
        ],
    },
    {
        "title": "JOIN BOOTHOP",
        "tagline": "Trusted Movement.\nSmarter Logistics.",
        "url": "boothop.com",
        "logo": True,
        "final": True,
    },
]

# ── Pexels clip queries for Part 1 ────────────────────────────────────────────
CLIP_QUERIES = [
    "airport departure gate international traveller",
    "stressed traveller passport airport urgent",
    "person packing suitcase gifts family",
    "airplane takeoff runway golden hour",
    "black traveller boarding gate phone",
    "airport arrivals family hugging emotional reunion",
]


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE IMAGE GENERATION
# ─────────────────────────────────────────────────────────────────────────────

def load_font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def draw_rounded_rect(draw, xy, radius, fill):
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=fill)


def make_slide(slide_def, width=1080, height=1920, index=0):
    """Render a single branded slide as a PIL Image."""
    img  = Image.new("RGB", (width, height), DARK)
    draw = ImageDraw.Draw(img)

    # ── Yellow accent bar (left edge) ─────────────────────────────────────────
    bar_w = 12
    draw.rectangle([0, 0, bar_w, height], fill=YELLOW)

    # ── Slide number (top right) ──────────────────────────────────────────────
    fn_small = load_font(FONT_BODY, 28)
    num_text = f"{index + 1:02d} / {len(SLIDES):02d}"
    draw.text((width - 80, 60), num_text, font=fn_small, fill=GREY)

    # ── BootHop wordmark (top left, small) ───────────────────────────────────
    fn_brand = load_font(FONT_TITLE, 36)
    draw.text((bar_w + 30, 55), "BOOTHOP", font=fn_brand, fill=YELLOW)

    y = 220

    # ── Title ─────────────────────────────────────────────────────────────────
    fn_title = load_font(FONT_TITLE, 88)
    title    = slide_def.get("title", "")
    # Yellow highlight pill behind title
    bbox     = draw.textbbox((0, 0), title, font=fn_title)
    tw       = bbox[2] - bbox[0]
    tx       = (width - tw) // 2
    pad      = 18
    draw_rounded_rect(draw, (tx - pad, y - pad, tx + tw + pad, y + (bbox[3] - bbox[1]) + pad), 12, YELLOW)
    draw.text((tx, y), title, font=fn_title, fill=BLACK)
    y += (bbox[3] - bbox[1]) + 60

    # ── Divider ────────────────────────────────────────────────────────────────
    draw.rectangle([bar_w + 30, y, width - 30, y + 3], fill=YELLOW)
    y += 40

    fn_body  = load_font(FONT_BODY, 54)
    fn_small = load_font(FONT_BODY, 42)
    fn_step  = load_font(FONT_TITLE, 110)
    fn_case  = load_font(FONT_TITLE, 48)

    # ── Variant: plain lines ───────────────────────────────────────────────────
    if "lines" in slide_def:
        for line in slide_def["lines"]:
            if not line:
                y += 20
                continue
            draw.text((bar_w + 40, y), line, font=fn_body, fill=WHITE)
            y += 70

    # ── Variant: numbered steps ────────────────────────────────────────────────
    elif "steps" in slide_def:
        for num, text in slide_def["steps"]:
            # Number (large yellow)
            draw.text((bar_w + 40, y - 20), num, font=fn_step, fill=YELLOW)
            # Step text (right of number)
            nbbox = draw.textbbox((0, 0), num, font=fn_step)
            nx    = bar_w + 40 + (nbbox[2] - nbbox[0]) + 24
            for line in textwrap.wrap(text, width=22):
                draw.text((nx, y + 12), line, font=fn_body, fill=WHITE)
                y += 58
            y += (nbbox[3] - nbbox[1]) - len(textwrap.wrap(text, 22)) * 58 + 20

    # ── Variant: bullet points ─────────────────────────────────────────────────
    elif "bullets" in slide_def:
        for bullet in slide_def["bullets"]:
            # Yellow tick
            draw.text((bar_w + 40, y), "✓", font=fn_body, fill=YELLOW)
            draw.text((bar_w + 100, y), bullet, font=fn_small, fill=WHITE)
            y += 75

    # ── Variant: use cases ─────────────────────────────────────────────────────
    elif "cases" in slide_def:
        for label, desc in slide_def["cases"]:
            # Label pill
            lb_bbox = draw.textbbox((0, 0), label, font=fn_case)
            lw      = lb_bbox[2] - lb_bbox[0]
            draw_rounded_rect(draw, (bar_w + 40, y, bar_w + 60 + lw, y + 52), 10, YELLOW)
            draw.text((bar_w + 50, y + 2), label, font=fn_case, fill=BLACK)
            # Description
            draw.text((bar_w + 40, y + 66), desc, font=fn_small, fill=WHITE)
            y += 140

    # ── Variant: final CTA ─────────────────────────────────────────────────────
    elif "final" in slide_def:
        fn_tag = load_font(FONT_TITLE, 72)
        fn_url = load_font(FONT_TITLE, 64)
        tag    = slide_def.get("tagline", "")
        for line in tag.split("\n"):
            draw.text((bar_w + 40, y), line, font=fn_tag, fill=WHITE)
            y += 88
        y += 40
        # URL on yellow pill
        url   = slide_def.get("url", "")
        ub    = draw.textbbox((0, 0), url, font=fn_url)
        uw    = ub[2] - ub[0]
        ux    = (width - uw) // 2
        draw_rounded_rect(draw, (ux - 28, y - 14, ux + uw + 28, y + (ub[3] - ub[1]) + 14), 14, YELLOW)
        draw.text((ux, y), url, font=fn_url, fill=BLACK)
        y += 100

    # ── Logo watermark (slides that request it) ───────────────────────────────
    if slide_def.get("logo") and LOGO_PATH.exists():
        logo    = Image.open(LOGO_PATH).convert("RGBA")
        max_w   = 420
        ratio   = max_w / logo.width
        logo    = logo.resize((max_w, int(logo.height * ratio)), Image.LANCZOS)
        lx      = (width - logo.width) // 2
        ly      = height - logo.height - 120
        img.paste(logo, (lx, ly), logo)

    # ── Bottom bar ────────────────────────────────────────────────────────────
    draw.rectangle([0, height - 6, width, height], fill=YELLOW)

    return img


def render_slides():
    """Generate all slide PNGs. Returns list of paths."""
    print("\n[SLIDES] Generating slide images...")
    paths = []
    for i, slide in enumerate(SLIDES):
        out = TEMP / f"slide_{i:02d}.png"
        img = make_slide(slide, index=i)
        img.save(str(out))
        print(f"  Slide {i+1}: {slide['title']}")
        paths.append(str(out))
    return paths


# ─────────────────────────────────────────────────────────────────────────────
# PEXELS CLIP DOWNLOAD (Part 1)
# ─────────────────────────────────────────────────────────────────────────────

def download_explainer_clips():
    print("\n[CLIPS] Downloading live clips from Pexels...")
    headers = {"Authorization": PEXELS_KEY}
    clips   = []
    for i, query in enumerate(CLIP_QUERIES):
        enc = requests.utils.quote(query)
        url = f"https://api.pexels.com/videos/search?query={enc}&per_page=10&orientation=portrait&size=medium"
        try:
            res  = requests.get(url, headers=headers, timeout=15).json()
            vids = res.get("videos", [])
            if not vids:
                print(f"  Clip {i+1}: no results for '{query}'")
                continue
            vid  = random.choice(vids)
            mp4s = [f for f in vid["video_files"] if f["file_type"] == "video/mp4"]
            mp4s.sort(key=lambda x: x["width"], reverse=True)
            dest = TEMP / f"raw_clip_{i:02d}.mp4"
            dest.write_bytes(requests.get(mp4s[0]["link"], timeout=60).content)
            clips.append(str(dest))
            print(f"  Clip {i+1}: {query[:50]}")
        except Exception as e:
            print(f"  Clip {i+1} failed: {e}")
    return clips


# ─────────────────────────────────────────────────────────────────────────────
# VOICEOVER
# ─────────────────────────────────────────────────────────────────────────────

async def _make_voice(text, path, voice="en-GB-SoniaNeural"):
    import edge_tts
    await edge_tts.Communicate(text, voice=voice).save(str(path))


def generate_voiceover():
    print("\n[VOICE] Generating voiceover...")
    vo_path = TEMP / "voiceover.mp3"
    asyncio.run(_make_voice(VOICEOVER_SCRIPT, vo_path))
    # Trim leading silence
    trimmed = TEMP / "voiceover_trim.mp3"
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(vo_path),
         "-af", "silenceremove=start_periods=1:start_silence=0.03:start_threshold=-50dB",
         str(trimmed)],
        capture_output=True
    )
    if trimmed.exists() and trimmed.stat().st_size > 1000:
        trimmed.replace(vo_path)
    print(f"  Voiceover saved ({vo_path.stat().st_size // 1024}KB)")
    return str(vo_path)


# ─────────────────────────────────────────────────────────────────────────────
# FFMPEG HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def run_ff(*args):
    cmd = ["ffmpeg", "-y"] + list(args)
    r   = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.decode(errors="replace")[-400:])


def process_clip(raw, out, width=1080, height=1920, duration=5.0):
    """Scale + crop clip to target resolution, trim to duration."""
    run_ff(
        "-i", raw, "-t", str(duration),
        "-vf", f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},fps=30",
        "-an", str(out)
    )


def slide_to_video(png_path, out, width=1080, height=1920, duration=5.0):
    """Convert a PNG slide to a 5-second video with subtle Ken Burns zoom."""
    run_ff(
        "-loop", "1", "-i", png_path,
        "-t", str(duration),
        "-vf", (
            f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},"
            f"zoompan=z='min(zoom+0.0008,1.05)':d={int(duration*30)}:s={width}x{height}:fps=30"
        ),
        "-c:v", "libx264", "-crf", "20", "-preset", "fast", "-an", str(out)
    )


def get_background_music():
    """Pick a library track for background."""
    archive = BASE / "music" / "archive"
    tracks  = sorted(archive.glob("*.mp3"))
    if tracks:
        day = datetime.now().timetuple().tm_yday
        return str(tracks[day % len(tracks)])
    return None


def add_text_overlay_to_clips(concat_mp4, out_mp4, width=1080, height=1920):
    """Burn narrative text into the Part 1 clip section."""
    font_t  = FONT_TITLE.replace("\\", "/").replace("C:/", "C\\:/")
    font_b  = FONT_BODY.replace("\\", "/").replace("C:/", "C\\:/")

    def dt(text, y, t0, t1, color="white", size=56, bold=False):
        ff = font_t if bold else font_b
        return (
            f"drawtext=fontfile='{ff}':text='{text}':fontsize={size}"
            f":fontcolor={color}:box=1:boxcolor=yellow@0.88:boxborderw=12"
            f":x=(w-text_w)/2:y={y}:enable='between(t,{t0},{t1})'"
        )

    filters = ",".join([f for f in [
        # 0–5s: Hook
        dt("POV\\:", 160, 0, 8, color="black", size=72, bold=True),
        dt("Someone already going", 250, 0, 8, color="black", size=58),
        dt("your way.", 320, 0, 8, color="black", size=58),
        # 8–15s
        dt("Traditional couriers\\:", 160, 8, 15, color="black", size=52),
        dt("£400+ and 3-5 days.", 230, 8, 15, color="black", size=58, bold=True),
        # 15–22s
        dt("BootHop connects you", 160, 15, 22, color="black", size=55),
        dt("with verified travellers", 230, 15, 22, color="black", size=55),
        dt("already making the journey.", 300, 15, 22, color="black", size=52),
        # 22–30s: CTA into slideshow
        dt("Here is how it works.", "h-280", 22, 30, color="black", size=60, bold=True),
    ] if f])

    run_ff(
        "-i", str(concat_mp4),
        "-vf", filters,
        "-c:v", "libx264", "-crf", "22", "-preset", "fast", "-an",
        str(out_mp4)
    )


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ASSEMBLY
# ─────────────────────────────────────────────────────────────────────────────

def assemble_video(clip_videos, slide_videos, voiceover, width, height, out_path, label):
    print(f"\n[ASSEMBLE] Building {label} ({width}×{height})...")

    # ── Part 1: process live clips ─────────────────────────────────────────────
    proc_clips = []
    for i, raw in enumerate(clip_videos[:6]):
        dest = TEMP / f"proc_clip_{i:02d}_{label}.mp4"
        try:
            process_clip(raw, dest, width, height, duration=5.0)
            proc_clips.append(str(dest))
        except Exception as e:
            print(f"  Clip {i+1} processing failed: {e}")

    # Pad to 6 clips
    while len(proc_clips) < 6 and proc_clips:
        proc_clips.append(proc_clips[-1])

    # ── Concat Part 1 clips → 30s ──────────────────────────────────────────────
    list1 = TEMP / f"list_clips_{label}.txt"
    list1.write_text("\n".join(f"file '{p}'" for p in proc_clips))
    clips_raw = TEMP / f"clips_raw_{label}.mp4"
    run_ff("-f", "concat", "-safe", "0", "-i", str(list1),
           "-c:v", "libx264", "-crf", "22", "-preset", "fast", "-an", str(clips_raw))

    # ── Burn text overlays onto clips ──────────────────────────────────────────
    clips_text = TEMP / f"clips_text_{label}.mp4"
    try:
        add_text_overlay_to_clips(clips_raw, clips_text, width, height)
    except Exception as e:
        print(f"  Text overlay failed: {e} — using plain clips")
        clips_text = clips_raw

    # ── Part 2: render slides → 30s ───────────────────────────────────────────
    slide_vids = []
    for i, png in enumerate(slide_videos):
        dest = TEMP / f"slide_vid_{i:02d}_{label}.mp4"
        try:
            slide_to_video(png, dest, width, height, duration=5.0)
            slide_vids.append(str(dest))
        except Exception as e:
            print(f"  Slide {i+1} video failed: {e}")

    list2 = TEMP / f"list_slides_{label}.txt"
    list2.write_text("\n".join(f"file '{p}'" for p in slide_vids))
    slides_concat = TEMP / f"slides_concat_{label}.mp4"
    run_ff("-f", "concat", "-safe", "0", "-i", str(list2),
           "-c:v", "libx264", "-crf", "20", "-preset", "fast", "-an", str(slides_concat))

    # ── Concat Part 1 + Part 2 → 60s ──────────────────────────────────────────
    list_all = TEMP / f"list_all_{label}.txt"
    list_all.write_text(
        f"file '{clips_text}'\n"
        f"file '{slides_concat}'\n"
    )
    video_only = TEMP / f"video_only_{label}.mp4"
    run_ff("-f", "concat", "-safe", "0", "-i", str(list_all),
           "-c:v", "libx264", "-crf", "22", "-preset", "fast", "-an", str(video_only))

    # ── Mix voiceover + background music ──────────────────────────────────────
    music = get_background_music()
    audio_out = TEMP / f"audio_{label}.aac"
    if music:
        run_ff(
            "-i", voiceover,
            "-i", music,
            "-filter_complex",
            "[1:a]volume=0.15[m];[0:a][m]amix=inputs=2:duration=first:normalize=0[out]",
            "-map", "[out]", "-t", "60", "-c:a", "aac", "-b:a", "192k", str(audio_out)
        )
    else:
        run_ff("-i", voiceover, "-t", "60", "-c:a", "aac", "-b:a", "192k", str(audio_out))

    # ── Mux video + audio ─────────────────────────────────────────────────────
    run_ff(
        "-i", str(video_only),
        "-i", str(audio_out),
        "-c:v", "copy", "-c:a", "copy", "-t", "60",
        "-shortest",
        str(out_path)
    )
    size_mb = Path(out_path).stat().st_size // (1024 * 1024)
    print(f"  {label}: {out_path.name} ({size_mb}MB)")


def make_landscape_version(vertical_mp4, out_path):
    """Letterbox vertical video into 1920×1080 with blurred background fill."""
    print("\n[LANDSCAPE] Creating 1920×1080 demo version...")
    # Use split filter so one input feeds both the blurred bg and the foreground
    run_ff(
        "-i", str(vertical_mp4),
        "-filter_complex",
        "[0:v]split=2[bg][fg];"
        "[bg]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,boxblur=20:5[blurred];"
        "[fg]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2[padded];"
        "[blurred][padded]overlay=(W-w)/2:(H-h)/2[v]",
        "-map", "[v]",
        "-map", "0:a",
        "-c:v", "libx264", "-crf", "20", "-preset", "fast",
        "-c:a", "copy",
        str(out_path)
    )
    size_mb = Path(out_path).stat().st_size // (1024 * 1024)
    print(f"  Landscape: {out_path.name} ({size_mb}MB)")


def send_to_telegram(video_path, caption):
    try:
        with open(video_path, "rb") as f:
            r = requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendVideo",
                data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption[:900]},
                files={"video": f},
                timeout=300
            )
        if r.ok:
            print(f"  Telegram: sent {Path(video_path).name}")
        else:
            print(f"  Telegram: {r.text[:80]}")
    except Exception as e:
        print(f"  Telegram failed: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def main():
    TEMP.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 58)
    print("  BootHop Explainer Video Generator")
    print(f"  {datetime.now().strftime('%A %d %B %Y  %H:%M')}")
    print("=" * 58)

    # 1. Generate slide images
    slide_pngs = render_slides()

    # 2. Download Pexels clips
    raw_clips = download_explainer_clips()
    if len(raw_clips) < 3:
        print("  WARNING: fewer than 3 clips downloaded — video may have repeated footage")

    # 3. Generate voiceover
    voiceover = generate_voiceover()

    # 4. Assemble vertical (TikTok/IG)
    vert_out = OUT_DIR / "boothop_explainer_vertical.mp4"
    assemble_video(raw_clips, slide_pngs, voiceover, 1080, 1920, vert_out, "vertical")

    # 5. Make landscape version (Developer App demo / YouTube)
    land_out = OUT_DIR / "boothop_explainer_landscape.mp4"
    try:
        make_landscape_version(vert_out, land_out)
    except Exception as e:
        print(f"  Landscape version failed: {e}")

    # 6. Send to Telegram
    caption = (
        "BootHop Explainer Video\n\n"
        "Vertical (1080×1920) — TikTok / Instagram Reel\n"
        "Landscape (1920×1080) — YouTube / Developer App Demo\n\n"
        "BootHop — Someone is already going your way.\n"
        "boothop.com"
    )
    print("\n[TELEGRAM] Sending videos...")
    send_to_telegram(str(vert_out), "Vertical: " + caption)
    if land_out.exists():
        send_to_telegram(str(land_out), "Landscape demo: " + caption)

    print(f"\n{'=' * 58}")
    print("  Done!")
    print(f"  Vertical : {vert_out}")
    print(f"  Landscape: {land_out}")
    print(f"{'=' * 58}\n")


if __name__ == "__main__":
    main()
