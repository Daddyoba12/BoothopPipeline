"""
BootHop Walkthrough v3
- Reuses v2 cached Pexels images
- All URLs fixed to boothop.com
- Music from daily/archive tracks (low background)
- Crossfade transitions between slides
- Better VO sync: 0.3s lead-in silence per slide
"""
import sys, os, asyncio, subprocess, shutil, requests, random, wave, struct
from pathlib import Path
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE     = Path(r"C:\Users\babso\Desktop\BootHopPipeline")
SITE_IMG = Path(r"C:\Users\babso\Desktop\boothop\boothop\public\images")
ASSETS   = Path(r"C:\Users\babso\Desktop\BootHopPipeline\assets")
CACHE_V2 = BASE / "temp" / "walkthrough_v2"   # reuse v2 images
CACHE_V1 = BASE / "temp" / "walkthrough"       # reuse v1 images
OUT_DIR  = BASE / "output"
TEMP_DIR = BASE / "temp" / "walkthrough_v3"
LOGO     = str(ASSETS / "mainlogo.png")
TS       = datetime.now().strftime("%Y%m%d_%H%M%S")
OUT_FILE = OUT_DIR / f"boothop_walkthrough_v3_{TS}.mp4"
VO_DIR   = TEMP_DIR / "vo"

TEMP_DIR.mkdir(parents=True, exist_ok=True)
VO_DIR.mkdir(exist_ok=True)
OUT_DIR.mkdir(exist_ok=True)

W, H = 1280, 720
FPS  = 25
XFADE_DUR = 0.4   # crossfade duration between slides

NAVY  = (7,  20, 44)
BLUE  = (11, 78, 166)
GOLD  = (255, 184, 0)
WHITE = (255, 255, 255)
GREEN = (0,  176, 80)
LGREY = (180, 200, 220)

# ── Pick best available music ─────────────────────────────────────────────────
def pick_music():
    # Prefer daily tracks (Afrobeat) — more vibrant
    for candidate in [
        BASE / "music" / "daily" / "track_1.mp3",
        BASE / "music" / "archive" / "Rora.mp3",
        BASE / "music" / "archive" / "track_01.mp3",
        BASE / "music" / "archive" / "track_02.mp3",
        BASE / "music" / "archive" / "track_03.mp3",
    ]:
        if candidate.exists() and candidate.stat().st_size > 50000:
            return str(candidate)
    # Any archive track
    tracks = list((BASE / "music" / "archive").glob("*.mp3"))
    return str(random.choice(tracks)) if tracks else None

# ── Cached image lookup: try v2, then v1, then None ──────────────────────────
def cached(index):
    for d in [CACHE_V2, CACHE_V1]:
        p = d / f"pexels_{index:02d}.jpg"
        if p.exists() and p.stat().st_size > 10000:
            return str(p)
    return None

# ── Slides: (bg, step, headline, sub1, sub2, accent, voice) ──────────────────
SLIDES = [
    (
        str(ASSETS / "site_screenshot.png"), "", "BootHop",
        "The smarter way to send and carry", "www.boothop.com", GOLD,
        "Welcome to BootHop. The smarter way to send — and carry."
    ),
    (
        cached(1) or "woman using laptop coffee shop", "1", "Sarah wants to send",
        "Birthday gift — London to Lagos", "www.boothop.com", GOLD,
        "Sarah needs to send a birthday gift from London to Lagos. "
        "She visits BootHop and clicks: I Want to Send."
    ),
    (
        str(SITE_IMG / "register_a.jpg"), "2", "Post a send request",
        "Route  ·  Weight  ·  Price  ·  Email", "No account needed yet", GOLD,
        "She enters her route, the item weight, her price, and her email. "
        "No account needed. BootHop saves her request instantly."
    ),
    (
        cached(3) or "man backpack airport departure", "3", "James is already travelling",
        "London to Lagos — next week", "Click: I'm Travelling", BLUE,
        "At the same time, James is flying London to Lagos next week. "
        "He visits boothop dot com and clicks: I am Travelling."
    ),
    (
        str(SITE_IMG / "Traveling.jpg"), "4", "Post a travel listing",
        "Route  ·  Date  ·  Space  ·  Price", "System saves his trip", BLUE,
        "He enters his route, travel date, how much spare space he has, and his asking price. "
        "BootHop stores his listing."
    ),
    (
        cached(5) or "computer server network technology", "5", "Auto-match engine",
        "Same route.  Compatible prices.", "Runs automatically every 6 hours", GOLD,
        "BootHop's matching engine runs every six hours. "
        "It finds Sarah and James. Same route. Close dates. Compatible prices. "
        "A match."
    ),
    (
        cached(6) or "person reading email phone smile", "6", "Both receive an email",
        "We found a match for you.", "One click to accept — no login yet", GREEN,
        "Both receive an email: we found a match. "
        "One click to accept. No login required at this stage."
    ),
    (
        cached(7) or "two professionals agreement signing", "7", "Price agreed. Terms signed.",
        "Both accept the price.", "Digital agreement — one click", GREEN,
        "They agree on a final price. "
        "Both sign BootHop's terms and conditions with one click."
    ),
    (
        cached(8) or "passport identity phone selfie", "8", "Identity verification",
        "Government ID  +  selfie", "Powered by Stripe Identity", GOLD,
        "Now identity verification. "
        "Each person photographs their ID and takes a selfie. "
        "Stripe Identity verifies both automatically. Takes about two minutes."
    ),
    (
        cached(9) or "secure payment banking online", "9", "Payment held in escrow",
        "Sarah pays through BootHop.", "Stripe holds the funds securely", GREEN,
        "Sarah pays the agreed fee through BootHop. "
        "The money is held in escrow by Stripe. "
        "James receives nothing until delivery is confirmed."
    ),
    (
        cached(10) or "phone unlock contact reveal", "10", "Contact details released",
        "Only after: verified + paid", "They arrange the handover", GOLD,
        "Only now does BootHop release their contact details to each other. "
        "They arrange the handover — where, when, and how."
    ),
    (
        str(SITE_IMG / "Handover.jpg"), "11", "James picks up the gift",
        "Agreed pickup location.", "Carries it on his flight", BLUE,
        "James picks up the birthday gift at the agreed location "
        "and carries it on his flight to Lagos."
    ),
    (
        str(SITE_IMG / "Customs1.jpg"), "12", "AI customs screening",
        "Every item checked before departure.", "No surprises at the border", GREEN,
        "BootHop's AI compliance engine screened the item before departure. "
        "Customs requirements are flagged upfront. No surprises at the border."
    ),
    (
        cached(13) or "happy woman receiving parcel", "13", "Delivery confirmed",
        "James confirms.   Sarah confirms.", "Both confirm — escrow unlocks", GREEN,
        "James confirms delivery. Sarah confirms she received it. "
        "Both confirmations unlock the escrow immediately."
    ),
    (
        cached(14) or "payment success celebration banking", "14", "James is paid",
        "Stripe releases the escrow.", "Transaction complete", GOLD,
        "Stripe releases the payment to James. "
        "Both leave a star rating. The transaction is complete."
    ),
    (
        str(ASSETS / "site_screenshot.png"), "", "BootHop",
        "Verified.  Compliant.  Same-Day.", "www.boothop.com", GOLD,
        "Sarah saved over sixty percent compared to a traditional courier. "
        "James earned money from a trip he was already making. "
        "This is BootHop. Verified. Compliant. Same-day. "
        "Visit www dot boothop dot com to get started today."
    ),
]

# ── Helpers ───────────────────────────────────────────────────────────────────
def ffmpeg(*args):
    r = subprocess.run(["ffmpeg", "-y"] + list(args), capture_output=True)
    if r.returncode != 0:
        print(f"    ffmpeg: {r.stderr[-150:].decode(errors='replace')}")
    return r.returncode == 0

def probe_dur(path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True)
    try: return float(r.stdout.strip())
    except: return Path(path).stat().st_size / 16000

def load_font(size):
    for fp in [r"C:\Windows\Fonts\arialbd.ttf", r"C:\Windows\Fonts\calibrib.ttf"]:
        if Path(fp).exists():
            try: return ImageFont.truetype(fp, size)
            except: pass
    return ImageFont.load_default()

def draw_frame(bg_path, step, headline, sub1, sub2, accent, zoom=1.0, px=0.5, py=0.5):
    if bg_path and Path(bg_path).exists():
        try:
            bg = Image.open(bg_path).convert("RGB")
            zw, zh = int(W * zoom), int(H * zoom)
            bg = bg.resize((zw, zh), Image.LANCZOS)
            ox = int((zw - W) * px)
            oy = int((zh - H) * py)
            bg = bg.crop((ox, oy, ox + W, oy + H))
            ov = Image.new("RGBA", (W, H), (0, 0, 0, 145))
            bg = Image.alpha_composite(bg.convert("RGBA"), ov).convert("RGB")
        except:
            bg = Image.new("RGB", (W, H), NAVY)
    else:
        bg = Image.new("RGB", (W, H), NAVY)

    d = ImageDraw.Draw(bg)

    if step:
        bf = load_font(20)
        d.rounded_rectangle([18, 18, 125, 47], radius=7, fill=(0,0,0,210))
        d.text((26, 23), f"STEP {step}", font=bf, fill=GOLD)

    hf = load_font(62)
    hb = d.textbbox((0,0), headline, font=hf)
    hx = (W - (hb[2]-hb[0])) // 2
    hy = H//2 - 82
    d.text((hx+3, hy+3), headline, font=hf, fill=(0,0,0))
    d.text((hx, hy), headline, font=hf, fill=WHITE)

    s1f = load_font(32)
    s1b = d.textbbox((0,0), sub1, font=s1f)
    s1x = (W - (s1b[2]-s1b[0])) // 2
    d.text((s1x+2, H//2+14+2), sub1, font=s1f, fill=(0,0,0))
    d.text((s1x, H//2+14), sub1, font=s1f, fill=accent)

    s2f = load_font(26)
    s2b = d.textbbox((0,0), sub2, font=s2f)
    s2x = (W - (s2b[2]-s2b[0])) // 2
    d.text((s2x, H//2+60), sub2, font=s2f, fill=LGREY)

    try:
        logo = Image.open(LOGO).convert("RGBA")
        lw = 155; lh = int(logo.height * lw / logo.width)
        logo = logo.resize((lw, lh), Image.LANCZOS)
        bg.paste(logo, (18, H-lh-16), logo)
    except: pass

    d.rectangle([0, H-26, W, H], fill=(0,0,0))
    baf = load_font(15)
    d.text((W//2, H-13), "www.boothop.com  |  Verified. Compliant. Same-Day.",
           font=baf, fill=(155, 190, 215), anchor="mm")

    return bg

async def gen_vo(text, out):
    import edge_tts
    await edge_tts.Communicate(text, voice="en-GB-SoniaNeural").save(str(out))

def make_clip(bg, step, headline, sub1, sub2, accent, duration, out):
    """Ken Burns clip: zoom 1.0->1.07 over duration."""
    n = int(duration * FPS)
    fd = TEMP_DIR / f"_frames_{Path(out).stem}"
    fd.mkdir(exist_ok=True)
    for fi in range(n):
        t   = fi / max(n-1, 1)
        zoom = 1.0 + 0.07 * t
        px   = 0.3 + 0.4 * t
        py   = 0.2 + 0.3 * t
        frame = draw_frame(bg, step, headline, sub1, sub2, accent, zoom, px, py)
        frame.save(str(fd / f"f{fi:05d}.png"))
    ffmpeg("-framerate", str(FPS), "-i", str(fd / "f%05d.png"),
           "-t", str(duration), "-r", str(FPS),
           "-c:v", "libx264", "-crf", "22", "-preset", "fast",
           "-pix_fmt", "yuv420p", "-an", out)
    shutil.rmtree(str(fd), ignore_errors=True)

def add_silence(mp3_in, mp3_out, lead=0.3, tail=0.2):
    """Add brief silence before and after VO for natural breathing."""
    ffmpeg("-f", "lavfi", "-i", f"anullsrc=r=24000:cl=mono",
           "-i", str(mp3_in),
           "-filter_complex",
           f"[0:a]atrim=0={lead}[sil_lead];"
           f"[1:a][sil_lead]concat=n=2:v=0:a=1[padded]",
           "-map", "[padded]", "-c:a", "mp3", str(mp3_out))
    return Path(mp3_out).exists()

def main():
    print("=" * 62)
    print("BootHop Walkthrough v3 — synced, crossfades, music")
    print("=" * 62)

    music = pick_music()
    print(f"\nMusic: {Path(music).name if music else 'none'}")

    # 1. VO per slide
    print(f"\nGenerating {len(SLIDES)} voice segments...")
    vo_info = []
    for i, slide in enumerate(SLIDES):
        raw  = VO_DIR / f"raw_{i:02d}.mp3"
        padded = VO_DIR / f"vo_{i:02d}.mp3"
        asyncio.run(gen_vo(slide[6], raw))
        raw_dur = probe_dur(raw)
        # Add 0.3s lead silence + 0.2s tail so voice doesn't cut on transition
        ok = add_silence(raw, padded, lead=0.3, tail=0.2)
        total_dur = probe_dur(padded) if ok else raw_dur + 0.5
        vo_info.append((padded if ok else raw, total_dur))
        print(f"  [{i+1}/{len(SLIDES)}] {total_dur:.1f}s — {slide[0][:30] if slide[0].startswith('C:') else slide[0][:30]!r}")

    # 2. Build Ken Burns clips
    print("\nBuilding slides with Ken Burns effect...")
    clip_paths = []
    cumulative = 0.0

    for i, (bg, step, headline, sub1, sub2, accent, _vo) in enumerate(SLIDES):
        vo_path, vo_dur = vo_info[i]
        clip_dur = round(vo_dur + 0.1, 2)
        clip_out = str(TEMP_DIR / f"clip_{i:02d}.mp4")

        print(f"  [{i+1}/{len(SLIDES)}] {clip_dur:.1f}s — {headline}")
        make_clip(bg, step, headline, sub1, sub2, accent, clip_dur, clip_out)

        if Path(clip_out).exists() and Path(clip_out).stat().st_size > 1000:
            # Mux VO into clip
            mux = str(TEMP_DIR / f"muxed_{i:02d}.mp4")
            ok = ffmpeg("-i", clip_out, "-i", str(vo_path),
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
                        "-t", str(clip_dur), "-shortest", mux)
            clip_paths.append((mux if ok else clip_out, clip_dur))
            cumulative += clip_dur
        else:
            print(f"    WARNING: slide {i} failed")

    total = cumulative
    print(f"\nTotal duration: {total:.0f}s across {len(clip_paths)} clips")

    # 3. Concat with xfade crossfades
    print("Assembling with crossfade transitions...")
    if len(clip_paths) == 1:
        shutil.copy(clip_paths[0][0], str(TEMP_DIR / "joined.mp4"))
    else:
        # Build xfade chain
        inputs = []
        for cp, _ in clip_paths:
            inputs += ["-i", cp]

        # Build filter_complex xfade chain
        n = len(clip_paths)
        durations = [d for _, d in clip_paths]
        fc_parts = []
        offsets = []
        running = 0.0
        for i in range(n - 1):
            running += durations[i] - XFADE_DUR
            offsets.append(running)

        # First xfade
        fc_parts.append(f"[0:v][1:v]xfade=transition=fade:duration={XFADE_DUR}:offset={offsets[0]:.3f}[x0]")
        fc_parts.append(f"[0:a][1:a]acrossfade=d={XFADE_DUR}[a0]")

        for i in range(1, n - 1):
            prev_v = f"[x{i-1}]"
            prev_a = f"[a{i-1}]"
            fc_parts.append(f"{prev_v}[{i+1}:v]xfade=transition=fade:duration={XFADE_DUR}:offset={offsets[i]:.3f}[x{i}]")
            fc_parts.append(f"{prev_a}[{i+1}:a]acrossfade=d={XFADE_DUR}[a{i}]")

        last_v = f"[x{n-2}]"
        last_a = f"[a{n-2}]"
        fc = ";".join(fc_parts)

        joined = str(TEMP_DIR / "joined.mp4")
        ok = ffmpeg(*inputs,
                    "-filter_complex", fc,
                    "-map", last_v, "-map", last_a,
                    "-c:v", "libx264", "-crf", "21", "-preset", "fast",
                    "-c:a", "aac", "-b:a", "128k",
                    "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart", joined)
        print(f"  Crossfade concat: {'OK' if ok else 'FAILED — falling back'}")

        if not ok or not Path(joined).exists():
            # Fallback: simple concat
            concat_f = str(TEMP_DIR / "concat.txt")
            with open(concat_f, "w") as f:
                for cp, _ in clip_paths:
                    f.write(f"file '{cp}'\n")
            ffmpeg("-f", "concat", "-safe", "0", "-i", concat_f,
                   "-c:v", "libx264", "-crf", "21", "-preset", "fast",
                   "-c:a", "aac", "-pix_fmt", "yuv420p", joined)

    joined = str(TEMP_DIR / "joined.mp4")

    # 4. Mix background music
    print("Mixing background music...")
    final = str(OUT_FILE)
    if music and Path(joined).exists():
        ok = ffmpeg("-i", joined, "-i", music,
                    "-filter_complex",
                    f"[1:a]volume=0.09,atrim=0:{total},"
                    f"afade=t=in:st=0:d=2,afade=t=out:st={total-3}:d=3[m];"
                    f"[0:a][m]amix=inputs=2:duration=first:normalize=0[out]",
                    "-map", "0:v", "-map", "[out]",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
                    "-t", str(total), "-movflags", "+faststart", final)
        print(f"  Music mix: {'OK' if ok else 'no music'}")
        if not ok:
            shutil.copy(joined, final)
    else:
        shutil.copy(joined, final)

    if Path(final).exists() and Path(final).stat().st_size > 10000:
        sz = Path(final).stat().st_size / 1_048_576
        print(f"\n{'='*62}")
        print(f"WALKTHROUGH v3 READY: {Path(final).name}")
        print(f"Duration: {total:.0f}s  |  Size: {sz:.1f} MB")
        print(f"{'='*62}")
    else:
        print("\nERROR: final file not created")

if __name__ == "__main__":
    main()
