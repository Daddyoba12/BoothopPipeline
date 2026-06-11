"""
BootHop Walkthrough Video — Pillow-based slide generation (reliable)
"""
import sys, os, asyncio, subprocess, shutil, requests, random, textwrap
from pathlib import Path
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageFilter

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE      = Path(r"C:\Users\babso\Desktop\BootHopPipeline")
SITE_IMG  = Path(r"C:\Users\babso\Desktop\boothop\boothop\public\images")
ASSETS    = Path(r"C:\Users\babso\Desktop\BootHopPipeline\assets")
OUT_DIR   = BASE / "output"
TEMP_DIR  = BASE / "temp" / "walkthrough"
LOGO_PATH = str(ASSETS / "mainlogo.png")
TS        = datetime.now().strftime("%Y%m%d_%H%M%S")
OUT_FILE  = OUT_DIR / f"boothop_walkthrough_{TS}.mp4"
VOICE_FILE= TEMP_DIR / "walkthrough_vo.mp3"

TEMP_DIR.mkdir(parents=True, exist_ok=True)
OUT_DIR.mkdir(exist_ok=True)

PEXELS_KEY = "NY3tWysBJseeky8V1JEp2YjevIq6MTYcOCfuKNBU7iypjC7Qc5T1DTp5"
W, H = 1280, 720

# Colours
NAVY   = (7,  20, 44)
BLUE   = (11, 78, 166)
GOLD   = (255, 184, 0)
WHITE  = (255, 255, 255)
GREEN  = (0,  176, 80)
LGREY  = (180, 200, 220)

# ── Voiceover ────────────────────────────────────────────────────────────────
VO = """
Welcome to BootHop. The smarter way to send and carry.
Let us show you exactly how it works.

Sarah needs to send a birthday gift from London to Lagos.
She visits boothop dot com and clicks I Want to Send.
She enters her route, the item weight, her price, and her email.
That is it. No account needed yet.

At the same time, James is flying London to Lagos next week.
He clicks I am Travelling, enters his route, date, space available, and his price.

BootHop's matching engine runs automatically every few hours.
It finds Sarah and James. Same route. Compatible prices.

Both receive an email. We found a match.
One click to accept. No login required yet.

They agree on a price. Both sign BootHop's terms with one click.

Now identity verification. Each takes a photo of their ID and a quick selfie.
Stripe Identity verifies both. Takes about two minutes.

Sarah pays through BootHop. The money is held in escrow by Stripe.
James receives nothing yet.

Only now are contact details released to both parties.
They arrange the handover directly.

James picks up the gift and carries it on his flight to Lagos.
Our AI customs engine already screened the item before departure.

James confirms delivery. Sarah confirms she received it.
BootHop releases the payment to James immediately.

Sarah saved over sixty percent versus a courier.
James earned money from a trip he was already taking.

This is BootHop. Verified. Compliant. Same-day.
Visit boothop dot com to get started.
"""

# ── Steps ────────────────────────────────────────────────────────────────────
STEPS = [
    # (secs, bg_source, step_num, headline, sub1, sub2, accent_color)
    (5, str(ASSETS/"site_screenshot.png"),       "",   "BootHop",                    "The smarter way to send and carry",  "boothop.co.uk",                    GOLD),
    (5, "woman using laptop at home",            "1",  "Sarah wants to send",        "Birthday gift — London to Lagos",    "Visit boothop.co.uk",              GOLD),
    (5, str(SITE_IMG/"register_a.jpg"),          "2",  "Post a send request",        "Route  .  Weight  .  Price  .  Email","No account needed yet",           GOLD),
    (5, "man with backpack airport departure",   "3",  "James is already travelling","London to Lagos — next week",        "Click: I'm Travelling",            BLUE),
    (5, str(SITE_IMG/"Traveling.jpg"),           "4",  "Post a travel listing",      "Route  .  Date  .  Space  .  Price", "System stores his trip",           BLUE),
    (5, "server room data centre technology",   "5",  "Auto-match engine runs",     "Same route. Compatible prices.",     "Runs automatically every 6 hours", GOLD),
    (5, "person reading email on phone",        "6",  "Both receive an email",      "We found a match for you.",          "One click to accept",              GREEN),
    (4, "two professionals shaking hands",      "7",  "Price agreed. Terms signed.","Both accept. One click.",            "Legally binding digital agreement",GREEN),
    (5, "passport identity document phone",     "8",  "Identity verification",      "Government ID + selfie.",            "Verified by Stripe Identity",      GOLD),
    (4, "secure payment online banking",        "9",  "Payment held in escrow",     "Sarah pays through BootHop.",        "Money secured by Stripe — safe",   GREEN),
    (4, "smartphone contact exchange",          "10", "Contact details released",   "Only after: verified + paid.",       "They arrange the handover",        GOLD),
    (5, str(SITE_IMG/"Handover.jpg"),           "11", "James picks up the gift",    "Agreed pickup location.",            "Carries it on his flight",         BLUE),
    (5, str(SITE_IMG/"Customs1.jpg"),           "12", "AI customs screening",       "Every item checked before dispatch.","No surprises at the border",       GREEN),
    (4, "happy person receiving package door",  "13", "Delivery confirmed",         "James: I delivered it.",             "Sarah: I received it.",            GREEN),
    (4, "bank transfer payment success",        "14", "Payment released to James",  "Stripe releases the escrow.",        "Transaction complete",             GOLD),
    (5, str(ASSETS/"site_screenshot.png"),      "",   "BootHop",                    "Verified.  Compliant.  Same-Day.",   "boothop.co.uk",                    GOLD),
]

def ffmpeg(*args):
    r = subprocess.run(["ffmpeg", "-y"] + list(args), capture_output=True, text=True)
    if r.returncode != 0:
        print(f"    ffmpeg warn: {r.stderr[-200:]}")
    return r.returncode == 0

def get_pexels(query, out):
    if Path(out).exists() and Path(out).stat().st_size > 10000:
        return True
    try:
        url = f"https://api.pexels.com/v1/search?query={requests.utils.quote(query)}&per_page=10&orientation=landscape"
        r = requests.get(url, headers={"Authorization": PEXELS_KEY}, timeout=20)
        if r.ok:
            photos = r.json().get("photos", [])
            if photos:
                link = random.choice(photos)["src"].get("large2x", random.choice(photos)["src"]["large"])
                data = requests.get(link, timeout=30).content
                with open(out, "wb") as f: f.write(data)
                return True
    except Exception as e:
        print(f"    Pexels error: {e}")
    return False

def load_font(size):
    font_paths = [
        r"C:\Windows\Fonts\arialbd.ttf",
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\calibrib.ttf",
    ]
    for fp in font_paths:
        if Path(fp).exists():
            try: return ImageFont.truetype(fp, size)
            except: pass
    return ImageFont.load_default()

def draw_slide(bg_path, step_num, headline, sub1, sub2, accent):
    # Background
    if bg_path and Path(bg_path).exists():
        try:
            bg = Image.open(bg_path).convert("RGB")
            bg = bg.resize((W, H), Image.LANCZOS)
            # Dark overlay
            overlay = Image.new("RGBA", (W, H), (0, 0, 0, 155))
            bg = bg.convert("RGBA")
            bg = Image.alpha_composite(bg, overlay).convert("RGB")
        except:
            bg = Image.new("RGB", (W, H), NAVY)
    else:
        bg = Image.new("RGB", (W, H), NAVY)
        # Subtle gradient feel
        draw_bg = ImageDraw.Draw(bg)
        for y in range(H):
            t = y / H
            r = int(NAVY[0] + (BLUE[0]-NAVY[0]) * t * 0.4)
            g = int(NAVY[1] + (BLUE[1]-NAVY[1]) * t * 0.4)
            b = int(NAVY[2] + (BLUE[2]-NAVY[2]) * t * 0.4)
            draw_bg.line([(0,y),(W,y)], fill=(r,g,b))

    draw = ImageDraw.Draw(bg)

    # Step badge
    if step_num:
        badge_font = load_font(22)
        badge_text = f"STEP {step_num}"
        draw.rounded_rectangle([20, 20, 130, 52], radius=8, fill=(0,0,0,200))
        draw.text((28, 26), badge_text, font=badge_font, fill=accent)

    # Headline
    h_font = load_font(68)
    h_bbox = draw.textbbox((0,0), headline, font=h_font)
    hx = (W - (h_bbox[2]-h_bbox[0])) // 2
    hy = H//2 - 90
    # Shadow
    draw.text((hx+2, hy+2), headline, font=h_font, fill=(0,0,0))
    draw.text((hx, hy), headline, font=h_font, fill=WHITE)

    # Sub1
    s1_font = load_font(36)
    s1_bbox = draw.textbbox((0,0), sub1, font=s1_font)
    s1x = (W - (s1_bbox[2]-s1_bbox[0])) // 2
    draw.text((s1x+1, H//2+15+1), sub1, font=s1_font, fill=(0,0,0))
    draw.text((s1x, H//2+15), sub1, font=s1_font, fill=accent)

    # Sub2
    s2_font = load_font(28)
    s2_bbox = draw.textbbox((0,0), sub2, font=s2_font)
    s2x = (W - (s2_bbox[2]-s2_bbox[0])) // 2
    draw.text((s2x, H//2+65), sub2, font=s2_font, fill=LGREY)

    # Logo bottom left
    try:
        logo = Image.open(LOGO_PATH).convert("RGBA")
        lw = 180
        lh = int(logo.height * lw / logo.width)
        logo = logo.resize((lw, lh), Image.LANCZOS)
        bg.paste(logo, (20, H-lh-20), logo)
    except:
        pass

    # Bottom bar
    draw.rectangle([0, H-30, W, H], fill=(0,0,0,180))
    bar_font = load_font(18)
    draw.text((W//2, H-18), "boothop.co.uk  |  Verified. Compliant. Same-Day.",
              font=bar_font, fill=(180,200,220), anchor="mm")

    return bg

async def gen_vo():
    import edge_tts
    comm = edge_tts.Communicate(VO.strip(), voice="en-GB-SoniaNeural")
    await comm.save(str(VOICE_FILE))
    print("  Voiceover generated")

def main():
    print("=" * 60)
    print("BootHop Walkthrough Video")
    print("=" * 60)

    # 1. Voiceover
    print("\nGenerating voiceover...")
    asyncio.run(gen_vo())

    # 2. Slides
    print(f"\nBuilding {len(STEPS)} slides...")
    slide_paths = []
    total_dur = 0

    for i, (dur, source, step, headline, sub1, sub2, accent) in enumerate(STEPS):
        # Get background image
        if source.startswith("C:") or source.startswith("/"):
            bg_path = source
            print(f"  [{i+1}/{len(STEPS)}] Local: {Path(source).name}")
        else:
            bg_path = str(TEMP_DIR / f"pexels_{i:02d}.jpg")
            ok = get_pexels(source, bg_path)
            print(f"  [{i+1}/{len(STEPS)}] Pexels: {source[:35]!r} {'OK' if ok else 'fallback'}")
            if not ok:
                bg_path = None

        # Draw slide as PNG
        png_out = str(TEMP_DIR / f"slide_{i:02d}.png")
        mp4_out = str(TEMP_DIR / f"slide_{i:02d}.mp4")
        slide_img = draw_slide(bg_path, step, headline, sub1, sub2, accent)
        slide_img.save(png_out)

        # Convert PNG to video clip
        ffmpeg("-loop", "1", "-i", png_out,
               "-t", str(dur), "-r", "25",
               "-c:v", "libx264", "-crf", "23", "-preset", "fast",
               "-pix_fmt", "yuv420p", "-an", mp4_out)

        if Path(mp4_out).exists() and Path(mp4_out).stat().st_size > 1000:
            slide_paths.append(mp4_out)
            total_dur += dur
        else:
            print(f"    WARNING: slide {i} not created")

    print(f"\nCreated {len(slide_paths)}/{len(STEPS)} slides, total {total_dur}s")

    # 3. Concat
    print("Assembling slides...")
    concat_f = str(TEMP_DIR / "concat.txt")
    with open(concat_f, "w") as f:
        for sp in slide_paths:
            f.write(f"file '{sp}'\n")
    joined = str(TEMP_DIR / "joined.mp4")
    ok = ffmpeg("-f", "concat", "-safe", "0", "-i", concat_f,
                "-c:v", "libx264", "-crf", "22", "-preset", "fast",
                "-pix_fmt", "yuv420p", joined)
    print(f"  Concat: {'OK' if ok else 'FAILED'}")

    # 4. Mix audio
    print("Mixing audio...")
    music_files = list((BASE/"music"/"archive").glob("*.mp3"))
    music = str(random.choice(music_files)) if music_files else None
    mixed = str(TEMP_DIR / "audio.aac")

    if music:
        ok = ffmpeg("-i", str(VOICE_FILE), "-i", music,
               "-filter_complex",
               f"[1:a]volume=0.10,atrim=0:{total_dur}[m];[0:a][m]amix=inputs=2:duration=first:normalize=0[out]",
               "-map", "[out]", "-t", str(total_dur),
               "-c:a", "aac", "-b:a", "192k", mixed)
    else:
        ok = ffmpeg("-i", str(VOICE_FILE), "-t", str(total_dur),
                    "-c:a", "aac", "-b:a", "192k", mixed)
    print(f"  Audio: {'OK' if ok else 'FAILED'}")

    # 5. Final mux
    print("Final render...")
    if Path(mixed).exists() and Path(mixed).stat().st_size > 1000:
        ok = ffmpeg("-i", joined, "-i", mixed,
                    "-c:v", "copy", "-c:a", "copy",
                    "-t", str(total_dur), "-movflags", "+faststart",
                    str(OUT_FILE))
    else:
        ok = ffmpeg("-i", joined, "-an",
                    "-c:v", "copy", "-movflags", "+faststart", str(OUT_FILE))
    print(f"  Render: {'OK' if ok else 'FAILED'}")

    if OUT_FILE.exists() and OUT_FILE.stat().st_size > 10000:
        size_mb = OUT_FILE.stat().st_size / 1_048_576
        print(f"\n{'='*60}")
        print(f"WALKTHROUGH READY: {OUT_FILE.name}")
        print(f"Duration: {total_dur}s  |  Size: {size_mb:.1f} MB")
        print(f"{'='*60}")
    else:
        print("\nERROR: final file not created")

if __name__ == "__main__":
    main()
