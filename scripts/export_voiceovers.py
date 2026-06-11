"""
export_voiceovers.py
Exports all voiceover scripts from the pipeline to a readable text file.

Shows:
  - Every Story Template (problem + movement + solution) per bucket
  - Every Hero End Line per bucket
  - Full example voiceover scripts (assembled as they actually play in the video)

Usage:
    python scripts/export_voiceovers.py
    python scripts/export_voiceovers.py --pdf   (saves PDF too, requires fpdf2)

Output: output/voiceover_scripts.txt  (always)
        output/voiceover_scripts.pdf  (with --pdf flag)
"""

import sys, os
from pathlib import Path
from datetime import datetime

BASE = Path(r"C:\Users\babso\Desktop\BootHopPipeline")
sys.path.insert(0, str(BASE))

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# Pull the data directly from pipeline
from pipeline import (
    STORY_TEMPLATES, HERO_LINES, LANG_CTA, DAY_BUCKETS
)

BUCKETS = ["family", "business", "airport", "smart", "cinematic", "community"]

CTA_EN = LANG_CTA["EN"]
CTA_NG = LANG_CTA["NG"]

DIVIDER  = "=" * 70
DIVIDER2 = "-" * 70

lines = []

def ln(text=""):
    lines.append(text)

def heading(text):
    ln()
    ln(DIVIDER)
    ln(f"  {text}")
    ln(DIVIDER)

def subheading(text):
    ln()
    ln(f"  --- {text} ---")
    ln()

# ── Header ────────────────────────────────────────────────────────────────────
ln(DIVIDER)
ln("  BootHop Pipeline — All Voiceover Scripts")
ln(f"  Generated: {datetime.now().strftime('%A %d %B %Y  %H:%M')}")
ln(DIVIDER)
ln()
ln("  Every video voiceover follows this 5-part brand arc:")
ln("    1. Opening  — the hook / POV scenario (from the day's selected hook)")
ln("    2. Problem  — what goes wrong / the pain point")
ln("    3. Movement — someone trusted is already on their way")
ln("    4. Solution — how BootHop resolves it")
ln("    5. Hero     — cinematic end line (rotates)")
ln("    6. CTA      — 'boothop.com' call to action (language-matched)")
ln()
ln("  Day → Bucket rotation:")
for day_num, bucket in sorted(DAY_BUCKETS.items()):
    day_name = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"][day_num]
    ln(f"    {day_name:12s} → {bucket}")

# ── Full assembled examples per bucket ────────────────────────────────────────
heading("FULL VOICEOVER EXAMPLES  (as heard in the video)")
ln()
ln("  These are complete scripts assembled exactly as Edge TTS speaks them.")
ln("  Each video randomly picks one Story Template + one Hero Line.")
ln()

SAMPLE_HOOKS = {
    "family":    "the wedding cake made it from London to Lagos, still perfect",
    "business":  "Rolls-Royce brake part landed in Lagos before the mechanic closed",
    "airport":   "passport left at home — BootHop got it to the gate in time",
    "smart":     "someone was already flying that route with space in their bag",
    "cinematic": "diaspora magic — London luxury delivered same day in Lagos",
    "community": "the parcel wey you send don land before you sef reach",
}

for bucket in BUCKETS:
    templates  = STORY_TEMPLATES.get(bucket, [])
    hero_lines = HERO_LINES.get(bucket, [])
    hook       = SAMPLE_HOOKS[bucket]
    opening    = hook

    ln(DIVIDER2)
    ln(f"  BUCKET: {bucket.upper()}")
    ln(DIVIDER2)

    for i, tmpl in enumerate(templates, 1):
        for j, hero in enumerate(hero_lines, 1):
            script = (
                f"{opening}. "
                f"{tmpl['problem']} "
                f"{tmpl['movement']} "
                f"{tmpl['solution']} "
                f"{hero} "
                f"{CTA_EN}"
            )
            ln(f"  [{i}.{j}]  Story template {i}  ×  Hero line {j}")
            ln()
            ln(f"  \"{script}\"")
            ln()

# ── Story Templates reference ─────────────────────────────────────────────────
heading("STORY TEMPLATES  (Problem → Movement → Solution)")
ln()

for bucket in BUCKETS:
    templates = STORY_TEMPLATES.get(bucket, [])
    ln(DIVIDER2)
    ln(f"  {bucket.upper()}  ({len(templates)} template{'s' if len(templates) != 1 else ''})")
    ln(DIVIDER2)
    for i, tmpl in enumerate(templates, 1):
        ln(f"  Template {i}:")
        ln(f"    Problem  : {tmpl['problem']}")
        ln(f"    Movement : {tmpl['movement']}")
        ln(f"    Solution : {tmpl['solution']}")
        ln()

# ── Hero end lines ─────────────────────────────────────────────────────────────
heading("HERO END LINES  (cinematic close, bottom of screen at 27-30s)")
ln()

for bucket in BUCKETS:
    heroes = HERO_LINES.get(bucket, [])
    ln(f"  {bucket.upper()}:")
    for i, h in enumerate(heroes, 1):
        ln(f"    {i:2d}. {h}")
    ln()

# ── CTAs ──────────────────────────────────────────────────────────────────────
heading("CALL TO ACTION  (always last line)")
ln()
ln(f"  English / Nigerian English:")
ln(f"    \"{CTA_EN}\"")
ln()
ln(f"  Spanish:")
ln(f"    \"{LANG_CTA['ES']}\"")
ln()

# ── Stats ─────────────────────────────────────────────────────────────────────
heading("COVERAGE STATS")
ln()
total_scripts = sum(
    len(STORY_TEMPLATES.get(b, [])) * len(HERO_LINES.get(b, []))
    for b in BUCKETS
)
ln(f"  Buckets              : {len(BUCKETS)}")
ln(f"  Total story templates: {sum(len(STORY_TEMPLATES.get(b,[])) for b in BUCKETS)}")
ln(f"  Total hero lines     : {sum(len(HERO_LINES.get(b,[])) for b in BUCKETS)}")
ln(f"  Unique script combos : {total_scripts}  (templates × heroes per bucket)")
ln()

# ── Write text file ────────────────────────────────────────────────────────────
out_dir = BASE / "output"
out_dir.mkdir(exist_ok=True)
out_txt = out_dir / "voiceover_scripts.txt"
out_txt.write_text("\n".join(lines), encoding="utf-8")
print(f"Saved: {out_txt}")

# ── Optional PDF ──────────────────────────────────────────────────────────────
if "--pdf" in sys.argv:
    try:
        from fpdf import FPDF
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        pdf.set_font("Helvetica", size=10)
        for line in lines:
            safe = line.encode("latin-1", errors="replace").decode("latin-1")
            pdf.multi_cell(0, 5, safe)
        out_pdf = out_dir / "voiceover_scripts.pdf"
        pdf.output(str(out_pdf))
        print(f"Saved: {out_pdf}")
    except ImportError:
        print("fpdf2 not installed — skipping PDF. Install with: pip install fpdf2")

# Also print a short summary to console
print()
print(f"  {len(BUCKETS)} buckets  |  {total_scripts} unique voiceover combinations")
print(f"  File: {out_txt}")
