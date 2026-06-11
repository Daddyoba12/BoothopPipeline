"""
BootHop 20-Second Investor Demo Video Generator
Downloads free Pexels footage, generates VO via edge_tts,
overlays animated text with ffmpeg, outputs investor-ready MP4.
"""
import os, sys, json, subprocess, asyncio, requests, tempfile
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path
from datetime import datetime

BASE     = Path(r"C:\Users\babso\Desktop\BootHopPipeline")
OUT_DIR  = BASE / "output"
TEMP_DIR = BASE / "temp"
ASSETS   = BASE / "assets"
MUSIC    = BASE / "music" / "archive" / "track_01.mp3"

OUT_DIR.mkdir(exist_ok=True)
TEMP_DIR.mkdir(exist_ok=True)

PEXELS_KEY = "NY3tWysBJseeky8V1JEp2YjevIq6MTYcOCfuKNBU7iypjC7Qc5T1DTp5"
FONT       = r"C\:/Windows/Fonts/arialbd.ttf"
LOGO       = str(ASSETS / "mainlogo.png")

TS = datetime.now().strftime("%Y%m%d_%H%M%S")
VIDEO_OUT  = OUT_DIR / f"boothop_investor_20s_{TS}.mp4"
VOICE_FILE = TEMP_DIR / "investor_vo.mp3"

# ── Voiceover script ─────────────────────────────────────────────────────────
VO_SCRIPT = (
    "BootHop. Same-day and cross-border logistics, reimagined. "
    "Every day, businesses lose time and money because urgent parts, documents, and shipments get delayed at borders. "
    "Informal diaspora networks have no verification, no compliance, and no accountability. "
    "BootHop changes that. "
    "We turn existing passenger and commercial movement into a compliance-first logistics layer. "
    "Verified movement partners. AI-powered customs screening. Open manifests. Stripe escrow on every transaction. "
    "Same-day. Auditable. Trusted. "
    "From London to Lagos. Manchester to Abuja. Serving businesses and diaspora communities across Africa and Europe. "
    "The platform is live. The AI compliance engine is in production. "
    "Join us at boothop dot com."
)

# ── Frames: (duration_sec, pexels_query, headline, sub_text) ─────────────────
FRAMES = [
    (4.0,  "cargo aircraft airport",          "BootHop",                          "Same-Day Cross-Border Logistics"),
    (4.0,  "frustrated engineer delay",        "The Problem",                      "Expensive. Slow. Unverified."),
    (5.0,  "logistics compliance technology",  "Our Solution",                     "Verified Partners · AI Customs · Escrow"),
    (4.0,  "Africa Europe business people",    "Africa to Europe",                 "Trusted · Auditable · Same-Day"),
    (4.0,  "airport cargo terminal busy",      "Live Platform",                    "AI Compliance Engine in Production"),
    (4.0,  "startup technology success team",  "boothop.com",                      "Join the Movement"),
]
TOTAL_DUR = sum(f[0] for f in FRAMES)  # ~25s

def get_pexels_video(query, outpath):
    headers = {"Authorization": PEXELS_KEY}
    url = f"https://api.pexels.com/videos/search?query={requests.utils.quote(query)}&per_page=10&orientation=landscape&size=medium"
    try:
        res = requests.get(url, headers=headers, timeout=20)
        if res.ok:
            vids = res.json().get("videos", [])
            if vids:
                import random
                vid = random.choice(vids)
                files = [f for f in vid["video_files"] if f["file_type"] == "video/mp4"]
                files.sort(key=lambda x: x.get("width", 0), reverse=True)
                if files:
                    r = requests.get(files[0]["link"], timeout=60)
                    with open(outpath, "wb") as f:
                        f.write(r.content)
                    print(f"  Downloaded [{query}] → {Path(outpath).name}")
                    return True
    except Exception as e:
        print(f"  Pexels error: {e}")
    return False

async def generate_vo():
    import edge_tts
    communicate = edge_tts.Communicate(VO_SCRIPT, voice="en-GB-RyanNeural")
    await communicate.save(str(VOICE_FILE))
    print("  Voiceover generated")

def ffmpeg(*args):
    result = subprocess.run(["ffmpeg", "-y"] + list(args),
                            capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ffmpeg warning: {result.stderr[-300:]}")
    return result.returncode == 0

def escape(text):
    return text.replace("'", "").replace(":", " ").replace(",", "")

def make_slide(clip_path, out_path, duration, headline, subtext, start_offset=0):
    headline = escape(headline)
    subtext  = escape(subtext)
    vf = (
        f"scale=1280:720:force_original_aspect_ratio=increase,"
        f"crop=1280:720,"
        f"fps=25,"
        f"drawbox=x=0:y=0:w=iw:h=ih:color=black@0.52:t=fill,"
        f"drawtext=fontfile='{FONT}':text='{headline}':"
        f"fontsize=72:fontcolor=white:box=1:boxcolor=black@0.55:boxborderw=14:"
        f"x=(w-text_w)/2:y=(h/2)-80,"
        f"drawtext=fontfile='{FONT}':text='{subtext}':"
        f"fontsize=30:fontcolor=#FFCC33:box=1:boxcolor=black@0.45:boxborderw=8:"
        f"x=(w-text_w)/2:y=(h/2)+20"
    )
    ffmpeg("-ss", str(start_offset), "-i", clip_path, "-t", str(duration),
           "-vf", vf, "-c:v", "libx264", "-crf", "23", "-preset", "fast",
           "-an", out_path)

def main():
    print("=" * 55)
    print("BootHop Investor Video — building now")
    print("=" * 55)

    # Step 1: Voiceover
    print("Generating voiceover...")
    asyncio.run(generate_vo())

    # Step 2: Download clips
    print("Downloading Pexels footage...")
    clip_paths = []
    slide_paths = []
    for i, (dur, query, headline, sub) in enumerate(FRAMES):
        clip_path  = str(TEMP_DIR / f"inv_clip_{i:02d}.mp4")
        slide_path = str(TEMP_DIR / f"inv_slide_{i:02d}.mp4")
        if get_pexels_video(query, clip_path):
            make_slide(clip_path, slide_path, dur, headline, sub)
            slide_paths.append(slide_path)
        else:
            # Fallback: black slide with text
            ffmpeg("-f", "lavfi", "-i", f"color=c=0x0B4EA6:s=1280x720:r=25",
                   "-t", str(dur),
                   "-vf",
                   f"drawtext=fontfile='{FONT}':text='{escape(headline)}':"
                   f"fontsize=72:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2",
                   "-c:v", "libx264", "-crf", "23", "-preset", "fast", "-an",
                   slide_path)
            slide_paths.append(slide_path)

    # Step 3: Concat slides
    print("Assembling slides...")
    concat_list = str(TEMP_DIR / "inv_list.txt")
    with open(concat_list, "w") as f:
        for sp in slide_paths:
            if Path(sp).exists():
                f.write(f"file '{sp}'\n")
    joined = str(TEMP_DIR / "inv_joined.mp4")
    ffmpeg("-f", "concat", "-safe", "0", "-i", concat_list,
           "-c:v", "libx264", "-crf", "23", "-preset", "fast", "-an", joined)

    # Step 4: Mix audio (VO + soft music)
    print("Mixing audio...")
    mixed_audio = str(TEMP_DIR / "inv_audio.aac")
    if MUSIC.exists():
        ffmpeg("-i", str(VOICE_FILE), "-i", str(MUSIC),
               "-filter_complex",
               f"[1:a]volume=0.12,atrim=0:{TOTAL_DUR}[m];[0:a][m]amix=inputs=2:duration=longest:normalize=0[out]",
               "-map", "[out]", "-t", str(TOTAL_DUR), "-c:a", "aac", "-b:a", "160k",
               mixed_audio)
    else:
        ffmpeg("-i", str(VOICE_FILE), "-t", str(TOTAL_DUR),
               "-c:a", "aac", "-b:a", "160k", mixed_audio)

    # Step 5: Final mux with logo overlay
    print("Rendering final video...")
    logo_filter = ""
    if Path(LOGO).exists():
        ffmpeg("-i", joined, "-loop", "1", "-i", LOGO, "-i", mixed_audio,
               "-filter_complex", "[1:v]scale=160:-1[logo];[0:v][logo]overlay=20:20[v]",
               "-map", "[v]", "-map", "2:a",
               "-c:v", "libx264", "-crf", "21", "-preset", "fast",
               "-c:a", "aac", "-b:a", "160k",
               "-t", str(TOTAL_DUR), "-movflags", "+faststart",
               str(VIDEO_OUT))
    else:
        ffmpeg("-i", joined, "-i", mixed_audio,
               "-c:v", "libx264", "-crf", "21", "-preset", "fast",
               "-c:a", "aac", "-b:a", "160k",
               "-t", str(TOTAL_DUR), "-movflags", "+faststart",
               str(VIDEO_OUT))

    if VIDEO_OUT.exists():
        size_mb = VIDEO_OUT.stat().st_size / 1_048_576
        print(f"\n{'='*55}")
        print(f"INVESTOR VIDEO READY: {VIDEO_OUT.name}")
        print(f"Size: {size_mb:.1f} MB  |  Duration: ~{TOTAL_DUR:.0f}s")
        print(f"{'='*55}")
    else:
        print("ERROR: video not created — check ffmpeg output above")

if __name__ == "__main__":
    main()
