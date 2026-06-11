"""
BootHop Walkthrough v2 — synced VO + Ken Burns effect + crossfades
Each slide has its own voice segment so speech matches image exactly.
"""
import sys, os, asyncio, subprocess, shutil, requests, random, struct
from pathlib import Path
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE      = Path(r"C:\Users\babso\Desktop\BootHopPipeline")
SITE_IMG  = Path(r"C:\Users\babso\Desktop\boothop\boothop\public\images")
ASSETS    = Path(r"C:\Users\babso\Desktop\BootHopPipeline\assets")
OUT_DIR   = BASE / "output"
TEMP_DIR  = BASE / "temp" / "walkthrough_v2"
LOGO_PATH = str(ASSETS / "mainlogo.png")
TS        = datetime.now().strftime("%Y%m%d_%H%M%S")
OUT_FILE  = OUT_DIR / f"boothop_walkthrough_v2_{TS}.mp4"
VOICE_DIR = TEMP_DIR / "vo_segments"

TEMP_DIR.mkdir(parents=True, exist_ok=True)
VOICE_DIR.mkdir(parents=True, exist_ok=True)
OUT_DIR.mkdir(exist_ok=True)

PEXELS_KEY = "NY3tWysBJseeky8V1JEp2YjevIq6MTYcOCfuKNBU7iypjC7Qc5T1DTp5"
W, H = 1280, 720

NAVY  = (7,  20, 44)
BLUE  = (11, 78, 166)
GOLD  = (255, 184, 0)
WHITE = (255, 255, 255)
GREEN = (0,  176, 80)
LGREY = (180, 200, 220)
DARK  = (0, 0, 0)

# ── Each slide: (bg_source, step_num, headline, sub1, sub2, accent, voice_text) ─
SLIDES = [
    (
        str(ASSETS/"site_screenshot.png"), "", "BootHop",
        "The smarter way to send and carry", "boothop.co.uk", GOLD,
        "Welcome to BootHop. The smarter way to send — and carry."
    ),
    (
        "woman using laptop coffee shop",  "1", "Sarah needs to send",
        "Birthday gift — London to Lagos", "boothop.co.uk", GOLD,
        "Sarah needs to send a birthday gift from London to Lagos. "
        "She visits BootHop and clicks I Want to Send."
    ),
    (
        str(SITE_IMG/"register_a.jpg"), "2", "Post a send request",
        "Route  ·  Weight  ·  Price  ·  Email", "No account needed yet", GOLD,
        "She enters her route, the item weight, her price, and her email. "
        "That is it. No account needed. BootHop stores her request."
    ),
    (
        "man backpack airport check in", "3", "James is already travelling",
        "London to Lagos — next week", "Click: I'm Travelling", BLUE,
        "At the same time, James is flying London to Lagos next week. "
        "He visits BootHop and clicks I am Travelling."
    ),
    (
        str(SITE_IMG/"Traveling.jpg"), "4", "Post a travel listing",
        "Route  ·  Date  ·  Space  ·  Price", "System stores his trip", BLUE,
        "He enters his route, travel date, how much spare space he has, and his price. "
        "BootHop stores his listing."
    ),
    (
        "computer algorithm matching network", "5", "Auto-match engine",
        "Same route. Compatible prices.", "Runs every 6 hours automatically", GOLD,
        "BootHop's matching engine runs automatically every six hours. "
        "It finds Sarah and James. Same route. Close dates. Compatible prices."
    ),
    (
        "person excited reading phone notification", "6", "Both receive an email",
        "We found a match for you.", "One click to accept — no login needed", GREEN,
        "Both receive an email. We found a match. "
        "One click to accept. No login required yet."
    ),
    (
        "two people agreement digital tablet", "7", "Price agreed. Terms signed.",
        "Both accept the midpoint price.", "Digital agreement — one click", GREEN,
        "They agree on a final price. "
        "Both sign BootHop's terms and conditions with a single click."
    ),
    (
        "passport selfie identity verification", "8", "Identity verification",
        "Government ID  +  selfie", "Verified by Stripe Identity in 2 minutes", GOLD,
        "Now identity verification. Each person takes a photo of their ID and a quick selfie. "
        "Stripe Identity verifies both automatically. Takes about two minutes."
    ),
    (
        "secure online payment escrow lock", "9", "Payment held in escrow",
        "Sarah pays through BootHop.", "Stripe holds funds — James gets nothing yet", GREEN,
        "Sarah pays the agreed fee through BootHop. "
        "The money is held securely in escrow by Stripe. "
        "James receives nothing until delivery is confirmed."
    ),
    (
        "phone contact details reveal unlock", "10", "Contact details released",
        "Only after: verified + paid", "They arrange the handover directly", GOLD,
        "Only now does BootHop release their contact details to each other. "
        "They arrange the handover — time, place, everything."
    ),
    (
        str(SITE_IMG/"Handover.jpg"), "11", "James picks up the gift",
        "Agreed pickup location.", "Carries it on his flight to Lagos", BLUE,
        "James picks up the birthday gift at the agreed location "
        "and carries it on his flight to Lagos."
    ),
    (
        str(SITE_IMG/"Customs1.jpg"), "12", "AI customs screening",
        "Every item checked before departure.", "No surprises at the border", GREEN,
        "BootHop's AI compliance engine already screened the item before departure. "
        "Customs requirements flagged upfront. No surprises at the border."
    ),
    (
        "happy woman receiving parcel door delivery", "13", "Delivery confirmed",
        "James confirms. Sarah confirms.", "Both confirm — escrow unlocks", GREEN,
        "James confirms he delivered it. Sarah confirms she received it. "
        "Both confirmations unlock the escrow."
    ),
    (
        "payment success bank transfer celebration", "14", "James is paid",
        "Stripe releases the escrow to James.", "Transaction complete", GOLD,
        "Stripe releases the payment to James immediately. "
        "Both leave a rating. The transaction is complete."
    ),
    (
        str(ASSETS/"site_screenshot.png"), "", "BootHop",
        "Verified.  Compliant.  Same-Day.", "boothop.co.uk", GOLD,
        "Sarah saved over sixty percent versus a traditional courier. "
        "James earned money from a trip he was already taking. "
        "This is BootHop. Verified. Compliant. Same day. "
        "Visit boothop dot com to get started."
    ),
]

def ffmpeg(*args):
    r = subprocess.run(["ffmpeg", "-y"] + list(args), capture_output=True)
    return r.returncode == 0

def get_mp3_duration(path):
    """Estimate MP3 duration from file size."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, text=True
        )
        return float(result.stdout.strip())
    except:
        size = Path(path).stat().st_size
        return size / 16000  # rough estimate for 128kbps

def get_pexels(query, out):
    if Path(out).exists() and Path(out).stat().st_size > 10000:
        return True
    try:
        url = f"https://api.pexels.com/v1/search?query={requests.utils.quote(query)}&per_page=10&orientation=landscape"
        r = requests.get(url, headers={"Authorization": PEXELS_KEY}, timeout=20)
        if r.ok:
            photos = r.json().get("photos", [])
            if photos:
                link = random.choice(photos)["src"].get("large2x") or random.choice(photos)["src"]["large"]
                data = requests.get(link, timeout=30).content
                with open(out, "wb") as f:
                    f.write(data)
                return True
    except:
        pass
    return False

def load_font(size):
    for fp in [r"C:\Windows\Fonts\arialbd.ttf", r"C:\Windows\Fonts\calibrib.ttf", r"C:\Windows\Fonts\arial.ttf"]:
        if Path(fp).exists():
            try:
                return ImageFont.truetype(fp, size)
            except:
                pass
    return ImageFont.load_default()

def draw_frame(bg_path, step_num, headline, sub1, sub2, accent, zoom=1.0, pan_x=0, pan_y=0):
    # Load and prep background
    if bg_path and Path(bg_path).exists():
        try:
            bg = Image.open(bg_path).convert("RGB")
            # Ken Burns: scale up and crop for zoom/pan effect
            zw = int(W * zoom)
            zh = int(H * zoom)
            bg = bg.resize((zw, zh), Image.LANCZOS)
            cx = int((zw - W) * pan_x)
            cy = int((zh - H) * pan_y)
            bg = bg.crop((cx, cy, cx + W, cy + H))
            # Dark overlay for readability
            overlay = Image.new("RGBA", (W, H), (0, 0, 0, 148))
            bg = Image.alpha_composite(bg.convert("RGBA"), overlay).convert("RGB")
        except:
            bg = Image.new("RGB", (W, H), NAVY)
    else:
        bg = Image.new("RGB", (W, H), NAVY)

    draw = ImageDraw.Draw(bg)

    # Step badge
    if step_num:
        bf = load_font(20)
        draw.rounded_rectangle([18, 18, 120, 46], radius=7, fill=(0, 0, 0, 200))
        draw.text((26, 23), f"STEP {step_num}", font=bf, fill=GOLD)

    # Headline with shadow
    hf = load_font(64)
    hb = draw.textbbox((0, 0), headline, font=hf)
    hx = (W - (hb[2] - hb[0])) // 2
    hy = H // 2 - 85
    draw.text((hx + 3, hy + 3), headline, font=hf, fill=(0, 0, 0))
    draw.text((hx, hy), headline, font=hf, fill=WHITE)

    # Sub1
    s1f = load_font(33)
    s1b = draw.textbbox((0, 0), sub1, font=s1f)
    s1x = (W - (s1b[2] - s1b[0])) // 2
    draw.text((s1x + 2, H // 2 + 16 + 2), sub1, font=s1f, fill=DARK)
    draw.text((s1x, H // 2 + 16), sub1, font=s1f, fill=accent)

    # Sub2
    s2f = load_font(26)
    s2b = draw.textbbox((0, 0), sub2, font=s2f)
    s2x = (W - (s2b[2] - s2b[0])) // 2
    draw.text((s2x, H // 2 + 64), sub2, font=s2f, fill=LGREY)

    # Logo
    try:
        logo = Image.open(LOGO_PATH).convert("RGBA")
        lw = 160
        lh = int(logo.height * lw / logo.width)
        logo = logo.resize((lw, lh), Image.LANCZOS)
        bg.paste(logo, (18, H - lh - 18), logo)
    except:
        pass

    # Bottom bar
    draw.rectangle([0, H - 28, W, H], fill=(0, 0, 0))
    bf2 = load_font(16)
    draw.text((W // 2, H - 14), "boothop.co.uk  |  Verified. Compliant. Same-Day.",
              font=bf2, fill=(160, 190, 220), anchor="mm")

    return bg

def make_ken_burns_clip(bg_path, step, headline, sub1, sub2, accent, duration, out_path):
    """Create a video clip with Ken Burns zoom effect — each frame slightly zoomed."""
    fps = 25
    n_frames = int(duration * fps)
    frames_dir = TEMP_DIR / f"frames_{Path(out_path).stem}"
    frames_dir.mkdir(exist_ok=True)

    for fi in range(n_frames):
        t = fi / max(n_frames - 1, 1)
        zoom  = 1.0 + 0.06 * t          # slow zoom in: 1.0x → 1.06x
        pan_x = 0.3 * t                  # gentle pan right
        pan_y = 0.2 * t                  # gentle pan down
        frame = draw_frame(bg_path, step, headline, sub1, sub2, accent, zoom, pan_x, pan_y)
        frame.save(str(frames_dir / f"f{fi:05d}.png"))

    # Convert frames to video
    ffmpeg("-framerate", "25",
           "-i", str(frames_dir / "f%05d.png"),
           "-t", str(duration),
           "-c:v", "libx264", "-crf", "23", "-preset", "fast",
           "-pix_fmt", "yuv420p", "-an", out_path)

    # Clean up frames to save disk
    shutil.rmtree(str(frames_dir), ignore_errors=True)

async def gen_segment(text, out_path, voice="en-GB-SoniaNeural"):
    import edge_tts
    comm = edge_tts.Communicate(text, voice=voice)
    await comm.save(str(out_path))

def main():
    print("=" * 62)
    print("BootHop Walkthrough v2 — synced VO + Ken Burns")
    print("=" * 62)

    music_files = list((BASE / "music" / "archive").glob("*.mp3"))
    music_path  = str(random.choice(music_files)) if music_files else None

    # ── 1. Generate per-slide VO ──────────────────────────────────────────────
    print(f"\nGenerating {len(SLIDES)} voice segments...")
    vo_paths = []
    for i, slide in enumerate(SLIDES):
        vo_text = slide[6]
        vo_out  = VOICE_DIR / f"vo_{i:02d}.mp3"
        asyncio.run(gen_segment(vo_text, vo_out))
        dur = get_mp3_duration(vo_out)
        vo_paths.append((vo_out, dur))
        print(f"  [{i+1}/{len(SLIDES)}] {dur:.1f}s — {vo_text[:50]!r}")

    # ── 2. Download Pexels images ─────────────────────────────────────────────
    print("\nFetching background images...")
    bg_paths = []
    for i, (source, *_rest) in enumerate(SLIDES):
        if source.startswith("C:") or source.startswith("/"):
            bg_paths.append(source)
            print(f"  [{i+1}] Local: {Path(source).name}")
        else:
            out = str(TEMP_DIR / f"pexels_{i:02d}.jpg")
            ok  = get_pexels(source, out)
            bg_paths.append(out if ok else None)
            print(f"  [{i+1}] Pexels: {source[:40]!r} {'OK' if ok else 'fallback'}")

    # ── 3. Build Ken Burns clips (duration = VO length + 0.5s pad) ────────────
    print("\nBuilding synced slides (Ken Burns effect)...")
    clip_paths = []
    total_dur  = 0

    for i, (source, step, headline, sub1, sub2, accent, vo_text) in enumerate(SLIDES):
        vo_path, vo_dur = vo_paths[i]
        clip_dur = round(vo_dur + 0.6, 2)   # VO + short pause

        clip_out = str(TEMP_DIR / f"clip_{i:02d}.mp4")
        print(f"  [{i+1}/{len(SLIDES)}] {clip_dur:.1f}s — {headline}")

        make_ken_burns_clip(bg_paths[i], step, headline, sub1, sub2, accent, clip_dur, clip_out)

        if Path(clip_out).exists() and Path(clip_out).stat().st_size > 1000:
            clip_paths.append((clip_out, str(vo_path), clip_dur))
            total_dur += clip_dur
        else:
            print(f"    WARNING: clip {i} failed")

    # ── 4. Mux each clip with its VO ─────────────────────────────────────────
    print("\nMuxing audio into clips...")
    muxed_paths = []
    for i, (vid, aud, dur) in enumerate(clip_paths):
        mux_out = str(TEMP_DIR / f"muxed_{i:02d}.mp4")
        ok = ffmpeg("-i", vid, "-i", aud,
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
                    "-t", str(dur), "-shortest", mux_out)
        if ok and Path(mux_out).exists():
            muxed_paths.append(mux_out)
        else:
            muxed_paths.append(vid)   # fallback: no audio

    # ── 5. Concat all muxed clips ─────────────────────────────────────────────
    print("Concatenating clips...")
    concat_f = str(TEMP_DIR / "concat.txt")
    with open(concat_f, "w") as f:
        for mp in muxed_paths:
            f.write(f"file '{mp}'\n")
    joined = str(TEMP_DIR / "joined.mp4")
    ffmpeg("-f", "concat", "-safe", "0", "-i", concat_f,
           "-c:v", "libx264", "-crf", "21", "-preset", "fast",
           "-c:a", "aac", "-b:a", "128k",
           "-pix_fmt", "yuv420p", joined)

    # ── 6. Add background music under VO ─────────────────────────────────────
    print("Adding background music...")
    final = str(OUT_FILE)
    if music_path and Path(joined).exists():
        ok = ffmpeg("-i", joined, "-i", music_path,
                    "-filter_complex",
                    f"[1:a]volume=0.08,atrim=0:{total_dur}[m];"
                    f"[0:a][m]amix=inputs=2:duration=first:normalize=0[out]",
                    "-map", "0:v", "-map", "[out]",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
                    "-t", str(total_dur), "-movflags", "+faststart", final)
    else:
        shutil.copy(joined, final)
        ok = True

    if Path(final).exists() and Path(final).stat().st_size > 10000:
        size_mb = Path(final).stat().st_size / 1_048_576
        print(f"\n{'='*62}")
        print(f"WALKTHROUGH v2 READY: {Path(final).name}")
        print(f"Duration: {total_dur:.0f}s  |  Size: {size_mb:.1f} MB")
        print(f"{'='*62}")
    else:
        print("\nERROR: final file not created")

if __name__ == "__main__":
    main()
