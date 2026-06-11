"""
BootHop Walkthrough v4
- ffmpeg zoompan for Ken Burns (no Pillow frame loop — no stuck frames)
- Per-slide VO synced exactly to image duration
- Simple concat — no xfade chain that breaks sync
- Fade-to-black between slides via overlay
- Music at low volume, fades in/out
"""
import sys, os, asyncio, subprocess, shutil, requests, random
from pathlib import Path
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE     = Path(r"C:\Users\babso\Desktop\BootHopPipeline")
SITE_IMG = Path(r"C:\Users\babso\Desktop\boothop\boothop\public\images")
ASSETS   = Path(r"C:\Users\babso\Desktop\BootHopPipeline\assets")
CACHE    = BASE / "temp" / "walkthrough_v2"
OUT_DIR  = BASE / "output"
TEMP     = BASE / "temp" / "walkthrough_v4"
LOGO     = str(ASSETS / "mainlogo.png")
TS       = datetime.now().strftime("%Y%m%d_%H%M%S")
OUT_FILE = OUT_DIR / f"boothop_walkthrough_v8_{TS}.mp4"
VO_DIR   = TEMP / "vo"

TEMP.mkdir(parents=True, exist_ok=True)
VO_DIR.mkdir(exist_ok=True)
OUT_DIR.mkdir(exist_ok=True)

PEXELS_KEY = "NY3tWysBJseeky8V1JEp2YjevIq6MTYcOCfuKNBU7iypjC7Qc5T1DTp5"
W, H, FPS = 1280, 720, 25

NAVY  = (7,  20, 44)
NAVY2 = (12, 46, 106)
GOLD  = (255, 184, 0)
WHITE = (255, 255, 255)
GREEN = (0,  176, 80)
LGREY = (180, 200, 220)

def pick_music():
    for c in [BASE/"music"/"daily"/"track_1.mp3",
               BASE/"music"/"archive"/"Rora.mp3",
               BASE/"music"/"archive"/"track_02.mp3"]:
        if c.exists() and c.stat().st_size > 50000:
            return str(c)
    tracks = list((BASE/"music"/"archive").glob("*.mp3"))
    return str(random.choice(tracks)) if tracks else None

def cached(i):
    p = CACHE / f"pexels_{i:02d}.jpg"
    return str(p) if p.exists() and p.stat().st_size > 10000 else None

# ── Slides ────────────────────────────────────────────────────────────────────
SLIDES = [
    (str(ASSETS/"site_screenshot.png"),      "", "BootHop",
     "The smarter way to send and carry",   "www.boothop.com", GOLD,
     "Welcome to BootHop. The smarter way to send — and carry."),

    (cached(1) or "woman laptop coffee shop","1", "Sarah needs to send",
     "Birthday gift — London to Lagos",     "www.boothop.com", GOLD,
     "Sarah needs to send a birthday gift from London to Lagos. "
     "She visits BootHop and clicks I Want to Send."),

    (str(SITE_IMG/"register_a.jpg"),         "2", "Post a send request",
     "Route · Weight · Price · Email",      "No account needed yet", GOLD,
     "She enters her route, item weight, price, and email. "
     "No account needed. BootHop saves her request instantly."),

    (cached(3) or "man airport backpack",    "3", "James is already travelling",
     "London to Lagos — next week",         "Click: I'm Travelling", (11,78,166),
     "At the same time, James is flying London to Lagos next week. "
     "He visits boothop dot com and clicks I am Travelling."),

    (str(SITE_IMG/"Traveling.jpg"),          "4", "Post a travel listing",
     "Route · Date · Space · Price",        "System stores his trip", (11,78,166),
     "He enters his route, travel date, spare luggage space, and his price. "
     "BootHop stores his listing."),

    (cached(5) or "server network matching", "5", "Auto-match engine",
     "Same route.  Compatible prices.",     "Runs every 15 minutes", GOLD,
     "BootHop's matching engine runs every fifteen minutes. "
     "It finds Sarah and James. Same route. Close dates. Compatible prices."),

    (cached(6) or "person reading email",    "6", "Both receive an email",
     "We found a match for you.",           "One click to accept", GREEN,
     "Both receive an email — we found a match. "
     "One click to accept. No login required yet."),

    (cached(7) or "two people agreement",    "7", "Price agreed. Terms signed.",
     "Both accept the price.",              "Digital agreement — one click", GREEN,
     "They agree on a final price. "
     "Both sign BootHop's terms with one click."),

    (cached(8) or "passport identity phone", "8", "Identity verification",
     "Government ID  +  selfie",            "Verified by Stripe Identity", GOLD,
     "Now identity verification. Each photographs their ID and takes a selfie. "
     "Stripe Identity verifies both automatically in about two minutes."),

    (cached(9) or "secure payment banking",  "9", "Payment held in escrow",
     "Sarah pays through BootHop.",         "Stripe holds funds securely", GREEN,
     "Sarah pays through BootHop. The money is held in escrow by Stripe. "
     "James receives nothing until delivery is confirmed."),

    (cached(10) or "phone unlock contact",   "10","Contact details released",
     "Only after: verified + paid",         "They arrange the handover", GOLD,
     "Only now does BootHop release contact details to both parties. "
     "They arrange the handover directly."),

    (str(SITE_IMG/"Handover.jpg"),           "11","James picks up the gift",
     "Agreed pickup location.",             "Carries it on his flight", (11,78,166),
     "James picks up the birthday gift and carries it on his flight to Lagos."),

    (str(SITE_IMG/"Customs1.jpg"),           "12","Compliance & Inspection",
     "Declared. Screened. Verified.", "Open inspection at handover", GREEN,
     "When Sarah books, she declares exactly what she is sending. "
     "BootHop's AI screens the item against the destination country rules immediately. "
     "At the handover, the item must not be sealed. "
     "James inspects the contents by hand to confirm they match the declaration. "
     "Both parties have read and agreed to what is and is not permitted in the destination country. "
     "Accurate descriptions protect everyone."),

    (cached(13) or "woman receiving parcel", "13","Delivery confirmed",
     "James confirms.  Sarah confirms.",    "Escrow releases after 4 hours", GREEN,
     "James confirms delivery. Sarah confirms receipt. "
     "If no dispute is raised, the escrow releases to James four hours later."),

    (cached(14) or "payment success",        "14","James is paid",
     "Stripe releases the escrow.",         "Transaction complete", GOLD,
     "Stripe releases the payment to James. "
     "Both leave a star rating. Transaction complete."),

    (str(ASSETS/"site_screenshot.png"),      "", "BootHop",
     "Verified.  Compliant.  Same-Day.",    "www.boothop.com", GOLD,
     "Sarah saved over sixty percent versus a traditional courier. "
     "James earned from a trip he was already making. "
     "This is BootHop. Verified. Compliant. Same-day. "
     "Visit www dot boothop dot com to get started."),
]

END_CARD_DURATION = 15   # seconds of branded end card

def ffmpeg(*args):
    r = subprocess.run(["ffmpeg", "-y"] + list(args), capture_output=True)
    if r.returncode != 0:
        print(f"    ffmpeg: {r.stderr[-120:].decode(errors='replace')}")
    return r.returncode == 0

def probe(path):
    r = subprocess.run(
        ["ffprobe","-v","error","-show_entries","format=duration",
         "-of","default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True)
    try: return float(r.stdout.strip())
    except: return Path(path).stat().st_size / 16000

def get_pexels(query, out):
    if Path(out).exists() and Path(out).stat().st_size > 10000: return True
    try:
        url = f"https://api.pexels.com/v1/search?query={requests.utils.quote(query)}&per_page=10&orientation=landscape"
        r = requests.get(url, headers={"Authorization": PEXELS_KEY}, timeout=20)
        if r.ok:
            photos = r.json().get("photos", [])
            if photos:
                link = random.choice(photos)["src"].get("large2x") or random.choice(photos)["src"]["large"]
                data = requests.get(link, timeout=30).content
                with open(out, "wb") as f: f.write(data)
                return True
    except: pass
    return False

def load_font(size, bold=True):
    for p in ([r"C:\Windows\Fonts\arialbd.ttf"] if bold else []) + [r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\calibrib.ttf"]:
        if Path(p).exists():
            try: return ImageFont.truetype(p, size)
            except: pass
    return ImageFont.load_default()

def make_end_card_png(out_png):
    """Branded end card — dark navy, large logo, website, subscribe prompt."""
    card = Image.new("RGB", (W, H), NAVY)
    draw = ImageDraw.Draw(card)

    # Gradient feel
    for y in range(H):
        t = y / H
        r = int(NAVY[0] + (NAVY2[0]-NAVY[0]) * t)
        g = int(NAVY[1] + (NAVY2[1]-NAVY[1]) * t)
        b = int(NAVY[2] + (NAVY2[2]-NAVY[2]) * t)
        draw.line([(0,y),(W,y)], fill=(r,g,b))

    # Gold top and bottom accent bars
    draw.rectangle([0, 0, W, 8], fill=GOLD)
    draw.rectangle([0, H-8, W, H], fill=GOLD)

    # Large centred logo
    try:
        logo = Image.open(LOGO).convert("RGBA")
        lw = 420
        lh = int(logo.height * lw / logo.width)
        logo = logo.resize((lw, lh), Image.LANCZOS)
        lx = (W - lw) // 2
        ly = H // 2 - lh // 2 - 60
        card.paste(logo, (lx, ly), logo)
    except:
        hf = load_font(80)
        draw.text((W//2, H//2 - 80), "BootHop", font=hf, fill=WHITE, anchor="mm")

    # Website
    wf = load_font(42)
    draw.text((W//2, H//2 + 80), "www.boothop.com", font=wf, fill=GOLD, anchor="mm")

    # Tagline
    tf = load_font(28, bold=False)
    draw.text((W//2, H//2 + 130), "Verified.  Compliant.  Same-Day.", font=tf, fill=LGREY, anchor="mm")

    # Subscribe prompt box
    sub_f = load_font(30)
    sub_text = "Subscribe for more  ▶"
    sb = draw.textbbox((0,0), sub_text, font=sub_f)
    sw = sb[2]-sb[0] + 60
    sh = sb[3]-sb[1] + 24
    sx = (W - sw) // 2
    sy = H - 120
    draw.rounded_rectangle([sx, sy, sx+sw, sy+sh], radius=10, fill=GOLD)
    draw.text((sx + sw//2, sy + sh//2), sub_text, font=sub_f, fill=NAVY, anchor="mm")

    card.save(out_png)

def make_slide_png(bg_path, step, headline, sub1, sub2, accent, out_png):
    """Draw a single static PNG for this slide — ffmpeg zoompan handles the animation."""
    if bg_path and Path(bg_path).exists():
        try:
            bg = Image.open(bg_path).convert("RGB").resize((W, H), Image.LANCZOS)
            ov = Image.new("RGBA", (W,H), (0,0,0,148))
            bg = Image.alpha_composite(bg.convert("RGBA"), ov).convert("RGB")
        except:
            bg = Image.new("RGB", (W,H), NAVY)
    else:
        bg = Image.new("RGB", (W,H), NAVY)

    d = ImageDraw.Draw(bg)

    if step:
        bf = load_font(22)
        d.rounded_rectangle([18,18,128,50], radius=8, fill=(0,0,0,210))
        d.text((26,24), f"STEP {step}", font=bf, fill=GOLD)

    # Headline with shadow
    hf = load_font(65)
    hb = d.textbbox((0,0), headline, font=hf)
    hx = (W-(hb[2]-hb[0]))//2
    hy = H//2 - 88
    d.text((hx+3, hy+3), headline, font=hf, fill=(0,0,0))
    d.text((hx, hy), headline, font=hf, fill=WHITE)

    # Sub1
    s1f = load_font(34)
    s1b = d.textbbox((0,0), sub1, font=s1f)
    s1x = (W-(s1b[2]-s1b[0]))//2
    d.text((s1x+2, H//2+14+2), sub1, font=s1f, fill=(0,0,0))
    d.text((s1x, H//2+14), sub1, font=s1f, fill=accent)

    # Sub2
    s2f = load_font(27, bold=False)
    s2b = d.textbbox((0,0), sub2, font=s2f)
    s2x = (W-(s2b[2]-s2b[0]))//2
    d.text((s2x, H//2+62), sub2, font=s2f, fill=LGREY)

    # Logo
    try:
        logo = Image.open(LOGO).convert("RGBA")
        lw = 160; lh = int(logo.height*lw/logo.width)
        logo = logo.resize((lw,lh), Image.LANCZOS)
        bg.paste(logo, (18, H-lh-16), logo)
    except: pass

    # Bottom bar
    d.rectangle([0, H-26, W, H], fill=(0,0,0))
    bf2 = load_font(16, bold=False)
    d.text((W//2, H-13), "www.boothop.com  |  Verified. Compliant. Same-Day.",
           font=bf2, fill=(155,190,215), anchor="mm")

    bg.save(out_png)

def make_static_clip(png_path, duration, out_mp4):
    """Static clip with smooth fade-in and fade-out — no motion, epilepsy safe."""
    fade_dur = min(0.4, duration * 0.15)  # fade is 15% of clip or max 0.4s
    vf = (
        f"fade=t=in:st=0:d={fade_dur},"
        f"fade=t=out:st={duration - fade_dur}:d={fade_dur},"
        f"format=yuv420p"
    )
    return ffmpeg("-loop","1","-i", png_path,
                  "-vf", vf,
                  "-t", str(duration),
                  "-r", str(FPS),
                  "-c:v","libx264","-crf","22","-preset","fast",
                  "-an", out_mp4)

async def gen_vo(text, path):
    import edge_tts
    await edge_tts.Communicate(text, voice="en-GB-SoniaNeural").save(str(path))

def main():
    print("=" * 62)
    print("BootHop Walkthrough v4 — zoompan + synced VO + music")
    print("=" * 62)

    music = pick_music()
    print(f"\nMusic: {Path(music).name if music else 'none'}")

    # 1. Generate VO segments — skip if already cached
    print(f"\nGenerating {len(SLIDES)} voice segments...")
    vo_info = []
    for i, s in enumerate(SLIDES):
        vo = VO_DIR / f"vo_{i:02d}.mp3"
        if vo.exists() and vo.stat().st_size > 1000:
            print(f"  [{i+1}/{len(SLIDES)}] Using cached VO — {s[2]}")
        else:
            try:
                asyncio.run(gen_vo(s[6], vo))
                print(f"  [{i+1}/{len(SLIDES)}] Generated — {s[2]}")
            except Exception as e:
                print(f"  [{i+1}/{len(SLIDES)}] TTS error ({e.__class__.__name__}) — will retry or skip")
        if vo.exists() and vo.stat().st_size > 1000:
            dur = probe(vo)
            vo_info.append((str(vo), round(dur + 0.4, 2)))
        else:
            vo_info.append((None, 6.0))   # fallback 6s if TTS down

    # 2. Fetch any missing Pexels images
    print("\nChecking images...")
    bg_paths = []
    pexels_queries = {
        1: "woman laptop coffee shop",
        3: "man airport backpack departure",
        5: "server network matching data",
        6: "person reading email phone smile",
        7: "two people digital agreement signing",
        8: "passport selfie identity verification",
        9: "secure payment banking online",
        10:"phone unlock contact reveal",
        13:"happy woman receiving parcel",
        14:"payment success bank transfer",
    }
    for i, s in enumerate(SLIDES):
        src = s[0]
        if src and Path(src).exists():
            bg_paths.append(src)
        elif i in pexels_queries:
            out = str(TEMP / f"pexels_{i:02d}.jpg")
            get_pexels(pexels_queries[i], out)
            bg_paths.append(out if Path(out).exists() else None)
            print(f"  [{i+1}] fetched: {pexels_queries[i][:35]}")
        else:
            bg_paths.append(None)

    # 3. Build clips: PNG slide + zoompan video + mux with VO
    print("\nBuilding synced clips (zoompan)...")
    clip_paths = []
    total_dur  = 0.0

    for i, (s, bg) in enumerate(zip(SLIDES, bg_paths)):
        vo_path, clip_dur = vo_info[i]
        _, step, headline, sub1, sub2, accent, _ = s

        print(f"  [{i+1}/{len(SLIDES)}] {clip_dur:.1f}s — {headline}")

        png_out  = str(TEMP / f"slide_{i:02d}.png")
        vid_out  = str(TEMP / f"vid_{i:02d}.mp4")
        mux_out  = str(TEMP / f"mux_{i:02d}.mp4")

        make_slide_png(bg, step, headline, sub1, sub2, accent, png_out)
        make_static_clip(png_out, clip_dur, vid_out)

        if Path(vid_out).exists() and Path(vid_out).stat().st_size > 1000:
            if vo_path and Path(vo_path).exists():
                ok = ffmpeg("-i", vid_out, "-i", vo_path,
                            "-c:v","copy","-c:a","aac","-b:a","128k",
                            "-t", str(clip_dur), "-shortest", mux_out)
            else:
                ok = False
            clip_paths.append(mux_out if (ok and Path(mux_out).exists()) else vid_out)
            total_dur += clip_dur
        else:
            print(f"    WARNING: slide {i} failed")

    # 3b. Build branded end card (silent — music carries it)
    print("  Building end card...")
    end_png = str(TEMP / "end_card.png")
    end_mp4 = str(TEMP / "end_card.mp4")
    make_end_card_png(end_png)
    fade = min(0.6, END_CARD_DURATION * 0.15)
    vf = (f"fade=t=in:st=0:d={fade},"
          f"fade=t=out:st={END_CARD_DURATION - fade}:d={fade},"
          f"format=yuv420p")
    ffmpeg("-loop","1","-i", end_png,
           "-vf", vf, "-t", str(END_CARD_DURATION),
           "-r", str(FPS), "-c:v","libx264","-crf","22","-preset","fast",
           "-an", end_mp4)
    # Add 3s silence as audio for the end card
    end_mux = str(TEMP / "end_card_mux.mp4")
    ffmpeg("-i", end_mp4,
           "-f","lavfi","-i","anullsrc=r=44100:cl=mono",
           "-c:v","copy","-c:a","aac","-b:a","128k",
           "-t", str(END_CARD_DURATION), "-shortest", end_mux)
    clip_paths.append(end_mux if Path(end_mux).exists() else end_mp4)
    total_dur += END_CARD_DURATION

    # 4. Simple concat (no xfade — reliable sync)
    print(f"\nConcatenating {len(clip_paths)} clips ({total_dur:.0f}s total)...")
    concat_f = str(TEMP / "concat.txt")
    with open(concat_f, "w") as f:
        for cp in clip_paths:
            f.write(f"file '{cp}'\n")
    joined = str(TEMP / "joined.mp4")
    ffmpeg("-f","concat","-safe","0","-i", concat_f,
           "-c:v","libx264","-crf","21","-preset","fast",
           "-c:a","aac","-b:a","128k",
           "-pix_fmt","yuv420p", joined)

    # 5. Add music
    print("Mixing music...")
    final = str(OUT_FILE)
    if music and Path(joined).exists():
        ok = ffmpeg("-i", joined, "-i", music,
                    "-filter_complex",
                    f"[1:a]volume=0.08,"
                    f"afade=t=in:st=0:d=3,"
                    f"afade=t=out:st={total_dur-4}:d=4,"
                    f"atrim=0:{total_dur}[m];"
                    f"[0:a][m]amix=inputs=2:duration=first:normalize=0[out]",
                    "-map","0:v","-map","[out]",
                    "-c:v","copy","-c:a","aac","-b:a","160k",
                    "-t", str(total_dur), "-movflags","+faststart", final)
        if not ok: shutil.copy(joined, final)
    else:
        shutil.copy(joined, final)

    if Path(final).exists() and Path(final).stat().st_size > 10000:
        sz = Path(final).stat().st_size / 1_048_576
        print(f"\n{'='*62}")
        print(f"WALKTHROUGH v4 READY: {Path(final).name}")
        print(f"Duration: {total_dur:.0f}s  |  Size: {sz:.1f} MB")
        print(f"{'='*62}")
    else:
        print("\nERROR: output not created")

if __name__ == "__main__":
    main()
