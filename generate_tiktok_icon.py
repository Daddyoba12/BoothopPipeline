"""
Generates boothop_tiktok_icon.png — 512x512 PNG matching the BootHop website logo.
Output saved to Desktop for easy upload to TikTok developer portal.
"""

import os, math
from PIL import Image, ImageDraw, ImageFont

W, H = 512, 512

# ── Background gradient (#0f172a → #1e3a8a, top to bottom) ─────────────────
img = Image.new('RGBA', (W, H), (15, 23, 42, 255))
draw = ImageDraw.Draw(img)

for y in range(H):
    t = y / H
    r = int(15  + (30  - 15)  * t)
    g = int(23  + (58  - 23)  * t)
    b = int(42  + (138 - 42)  * t)
    draw.line([(0, y), (W, y)], fill=(r, g, b, 255))

# ── Coordinate helpers (SVG viewBox 0 0 44 44 → 512×512 canvas) ────────────
# Figure occupies roughly x 1–31, y -1–32 in the original viewBox.
# We scale so the figure is ~55% of canvas width, centred slightly left
# to leave room for the backpack on the right.

SCALE    = (W * 0.58) / 31        # ≈ 9.6
OFFSET_X = W * 0.22               # push figure left to centre the whole logo
OFFSET_Y = H * 0.10               # top margin

def tx(x): return int(OFFSET_X + x * SCALE)
def ty(y): return int(OFFSET_Y + y * SCALE)

WHITE  = (255, 255, 255, 255)
BLUE   = (59,  130, 246, 255)   # blue-500
CYAN   = (6,   182, 212, 255)   # cyan-400
DIMW   = (255, 255, 255, 110)   # semi-transparent white

# ── Figure: head ────────────────────────────────────────────────────────────
hr = int(4.5 * SCALE)
draw.ellipse([tx(13)-hr, ty(6)-hr, tx(13)+hr, ty(6)+hr], fill=WHITE)

# ── Figure: torso ───────────────────────────────────────────────────────────
draw.polygon([
    (tx(10), ty(11)),
    (tx(8.5), ty(20)), (tx(12), ty(20)),
    (tx(13), ty(14.5)),
    (tx(14), ty(20)), (tx(17.5), ty(20)),
    (tx(16), ty(11)),
], fill=WHITE)

# ── Figure: forward arm ─────────────────────────────────────────────────────
draw.polygon([
    (tx(10), ty(12.5)), (tx(5.5), ty(18)),
    (tx(7.5), ty(19)),  (tx(12),  ty(13.5)),
], fill=WHITE)

# ── Figure: back arm (reaching to pack) ─────────────────────────────────────
draw.polygon([
    (tx(16), ty(12.5)), (tx(19.5), ty(15)),
    (tx(18), ty(16.5)), (tx(14.5), ty(14)),
], fill=WHITE)

# ── Figure: legs (mid stride) ───────────────────────────────────────────────
draw.polygon([
    (tx(10), ty(20)), (tx(7.5), ty(32)),
    (tx(11), ty(32)), (tx(13),  ty(22)),
], fill=WHITE)
draw.polygon([
    (tx(14), ty(20)),  (tx(16.5), ty(32)),
    (tx(20), ty(32)),  (tx(16.5), ty(22)),
], fill=WHITE)

# ── Backpack / package (rect x=19 y=9 w=12 h=12) ───────────────────────────
br = max(4, int(2.5 * SCALE))
draw.rounded_rectangle([tx(19), ty(9), tx(31), ty(21)], radius=br, fill=BLUE)
# Buckle stripes
draw.rectangle([tx(21), ty(11),   tx(29), ty(12.5)], fill=DIMW)
draw.rectangle([tx(21), ty(14.5), tx(29), ty(16)],   fill=DIMW)

# ── Straps ──────────────────────────────────────────────────────────────────
lw = max(3, int(1.8 * SCALE))
draw.line([(tx(19), ty(12)),  (tx(17.5), ty(13))],   fill=WHITE, width=lw)
draw.line([(tx(19), ty(17)),  (tx(17.5), ty(17.5))], fill=WHITE, width=lw)

# ── Motion speed lines ──────────────────────────────────────────────────────
mlw = max(2, int(1.5 * SCALE))
draw.line([(tx(3),   ty(16)),   (tx(1), ty(16))],   fill=(255,255,255,128), width=mlw)
draw.line([(tx(3.5), ty(19.5)), (tx(1), ty(19.5))], fill=(255,255,255,89),  width=mlw)
draw.line([(tx(4),   ty(23)),   (tx(2), ty(23))],   fill=(255,255,255,51),  width=mlw)

# ── Hop arc above head (approximate quadratic bezier) ───────────────────────
# Original: M8 3 Q13 -1 18 3  → draw arc using bounding ellipse
arc_cx, arc_cy = tx(13), ty(1)
arc_rx, arc_ry = int(5 * SCALE), int(4 * SCALE)
draw.arc(
    [arc_cx - arc_rx, arc_cy - arc_ry, arc_cx + arc_rx, arc_cy + arc_ry],
    start=200, end=340,
    fill=(255, 255, 255, 140),
    width=mlw,
)

# ── Wordmark "BootHop" ───────────────────────────────────────────────────────
text_y = ty(35) + int(SCALE * 2)
font_size = int(W * 0.145)   # ~74px

font_bold = None
for path in [
    'C:/Windows/Fonts/arialbd.ttf',
    'C:/Windows/Fonts/calibrib.ttf',
    'C:/Windows/Fonts/verdanab.ttf',
    'C:/Windows/Fonts/trebucbd.ttf',
]:
    if os.path.exists(path):
        font_bold = path
        break

try:
    font = ImageFont.truetype(font_bold, font_size) if font_bold else ImageFont.load_default()
except Exception:
    font = ImageFont.load_default()

boot_txt = "Boot"
hop_txt  = "Hop"

try:
    boot_w = int(draw.textlength(boot_txt, font=font))
    hop_w  = int(draw.textlength(hop_txt,  font=font))
except Exception:
    boot_w = int(len(boot_txt) * font_size * 0.58)
    hop_w  = int(len(hop_txt)  * font_size * 0.58)

total_w = boot_w + hop_w
text_x  = (W - total_w) // 2

draw.text((text_x,           text_y), boot_txt, font=font, fill=WHITE)
draw.text((text_x + boot_w,  text_y), hop_txt,  font=font, fill=CYAN)

# ── Save ────────────────────────────────────────────────────────────────────
out = os.path.join(os.path.expanduser('~'), 'Desktop', 'boothop_tiktok_icon.png')
img.convert('RGB').save(out, 'PNG', quality=95)
print(f"Icon saved → {out}")
print("Upload this file to TikTok as your app icon.")
