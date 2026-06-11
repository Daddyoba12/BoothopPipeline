"""
linkedin_b2b_daily.py
Runs daily (recommended: 10am) via Windows Task Scheduler.

Flow:
  1. Claude Haiku generates B2B LinkedIn content + card copy
  2. Pillow renders a branded 1200x628 image card with the BootHop logo
  3. Sends preview to Telegram for approval
  4. Waits up to 90 min — explicit approval required (no auto-post)
  5. Posts card image + caption to LinkedIn
  6. Saves HTML to blog/pending/ for Blogger auto-post
"""

import json, sys, time, re, io, textwrap
from datetime import datetime
from pathlib import Path

BASE    = Path(__file__).resolve().parent.parent
BLOG    = BASE / "blog" / "pending"
ASSETS  = BASE / "assets"
FONTS   = ASSETS / "fonts"
BLOG.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(BASE))
from config import (
    ANTHROPIC_API_KEY, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID,
)

import requests

# ── Logo — use mainlogo.png (transparent, RGBA) ────────────────────────────────
LOGO_PATH = ASSETS / "mainlogo.png"

# ── WhatsApp .env ──────────────────────────────────────────────────────────────
_WA_TOKEN    = ""
_WA_PHONE_ID = ""
_WA_RECIPIENT = "447405746302"
_env = BASE / ".env"
if _env.exists():
    for _line in _env.read_text(encoding="utf-8").splitlines():
        if "=" in _line and not _line.startswith("#"):
            k, v = _line.split("=", 1)
            k, v = k.strip(), v.strip()
            if k == "WHATSAPP_ACCESS_TOKEN":    _WA_TOKEN    = v
            if k == "WHATSAPP_PHONE_NUMBER_ID": _WA_PHONE_ID = v


def _load_linkedin():
    p = BASE / "scripts" / "social_credentials.json"
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        li = d.get("linkedin", {})
        return li.get("access_token", ""), li.get("person_urn", "")
    except Exception:
        return "", ""


# ── B2B topic rotation ─────────────────────────────────────────────────────────
B2B_TOPICS = [
    {"angle": "cross_border_delay",    "hook": "Cross-border parcel delays are costing UK SMEs thousands monthly"},
    {"angle": "diaspora_logistics",    "hook": "Why the UK diaspora corridor is the most underserved logistics route in Europe"},
    {"angle": "last_mile_problem",     "hook": "Last-mile delivery is broken — and it's not getting cheaper"},
    {"angle": "courier_alternatives",  "hook": "Traditional couriers charge 3x what peer-to-peer delivery costs"},
    {"angle": "supply_chain_trust",    "hook": "Trust is the missing layer in modern supply chain — here's how to fix it"},
    {"angle": "urgent_business_items", "hook": "AOG, spare parts, critical documents — when speed matters more than price"},
    {"angle": "traveller_economy",     "hook": "The traveller economy: turning empty luggage space into business value"},
    {"angle": "sme_logistics_cost",    "hook": "SMEs spend disproportionately on logistics — there's a smarter model"},
    {"angle": "nigeria_uk_trade",      "hook": "UK-Nigeria trade is growing — but logistics infrastructure hasn't kept up"},
    {"angle": "peer_to_peer_delivery", "hook": "Peer-to-peer delivery isn't new — it's just finally being done properly"},
    {"angle": "verified_travellers",   "hook": "Why verified human carriers outperform automated couriers on trust"},
    {"angle": "boothop_model",         "hook": "How BootHop turns existing journeys into same-day delivery capacity"},
    {"angle": "startup_logistics",     "hook": "Logistics startups are eating the courier industry from the bottom up"},
    {"angle": "carbon_footprint",      "hook": "Using journeys already happening reduces the carbon cost of delivery"},
]


def _log(msg):
    print(f"[{datetime.utcnow().strftime('%H:%M:%S')}] [LI-B2B] {msg}")


# ── Claude content generation ──────────────────────────────────────────────────
def generate_b2b_content(topic: dict) -> dict:
    prompt = f"""You write professional B2B LinkedIn content for BootHop — a peer-to-peer delivery platform where verified travellers carry parcels on their existing journeys.

Today's angle: {topic['hook']}

Write:
1. A LinkedIn post (180-220 words). Opens with a data point or industry observation. Explains the business pain. Shows how BootHop solves it. Ends with a subtle CTA to boothop.com. Professional, authoritative — NOT a sales pitch.

2. Card copy for a branded image card:
   - card_headline: one punchy line (<10 words) — the key stat or insight
   - card_points: exactly 3 bullet points (each <12 words) — the key takeaways
   - card_cta: one short action phrase (<6 words)

3. A blog version: 400-500 word HTML article on the same topic with <h2> subheadings, <p> paragraphs, SEO-friendly, ends with <a href="https://www.boothop.com">Learn more at BootHop</a>

Return ONLY valid JSON:
{{
  "linkedin_post": "the 180-220 word LinkedIn text",
  "card_headline": "short punchy stat or insight",
  "card_points": ["point one", "point two", "point three"],
  "card_cta": "short CTA phrase",
  "blog_title": "SEO title",
  "blog_labels": ["logistics", "b2b"],
  "blog_html": "full HTML body content"
}}"""

    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key":         ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type":      "application/json",
        },
        json={
            "model":      "claude-haiku-4-5-20251001",
            "max_tokens": 2500,
            "messages":   [{"role": "user", "content": prompt}],
        },
        timeout=60,
    )
    resp.raise_for_status()
    raw   = resp.json()["content"][0]["text"]
    match = re.search(r"\{[\s\S]*\}", raw)
    if not match:
        raise ValueError("Claude returned no JSON")
    return json.loads(match.group(0))


# ── Card image renderer ────────────────────────────────────────────────────────
def create_card_image(headline: str, points: list, cta: str) -> bytes:
    """
    Renders a 1200x628 LinkedIn card image.
    Returns PNG bytes.
    """
    from PIL import Image, ImageDraw, ImageFont

    W, H = 1200, 628
    BG       = (13,  17,  23)   # #0D1117 — pipeline dark
    PURPLE   = (124, 58, 237)   # #7C3AED
    WHITE    = (249, 250, 251)
    GREY     = (156, 163, 175)
    ACCENT   = (110, 231, 183)  # #6EE7B7 — green accent

    img  = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    # Left purple bar
    draw.rectangle([(0, 0), (8, H)], fill=PURPLE)

    # Bottom accent bar
    draw.rectangle([(0, H - 6), (W, H)], fill=PURPLE)

    # Subtle grid lines (texture)
    for x in range(0, W, 60):
        draw.line([(x, 0), (x, H)], fill=(255, 255, 255, 8), width=1)
    for y in range(0, H, 60):
        draw.line([(0, y), (W, y)], fill=(255, 255, 255, 8), width=1)

    # Load fonts
    try:
        font_big   = ImageFont.truetype(str(FONTS / "Oswald-Bold.ttf"),      52)
        font_body  = ImageFont.truetype(str(FONTS / "Montserrat-ExtraBold.ttf"), 22)
        font_small = ImageFont.truetype(str(FONTS / "Montserrat-ExtraBold.ttf"), 18)
        font_cta   = ImageFont.truetype(str(FONTS / "Oswald-Bold.ttf"),      28)
    except Exception:
        font_big   = ImageFont.load_default()
        font_body  = font_big
        font_small = font_big
        font_cta   = font_big

    # ── Headline ──
    head_x = 48
    head_y = 60
    wrapped = textwrap.wrap(headline.upper(), width=32)
    for line in wrapped[:2]:
        draw.text((head_x, head_y), line, font=font_big, fill=WHITE)
        head_y += 62

    # Divider under headline
    draw.rectangle([(head_x, head_y + 10), (head_x + 120, head_y + 14)], fill=PURPLE)
    head_y += 36

    # ── Bullet points ──
    for pt in points[:3]:
        dot_x, dot_y = head_x, head_y + 10
        draw.ellipse([(dot_x, dot_y), (dot_x + 10, dot_y + 10)], fill=ACCENT)
        # Wrap long points
        wrapped_pt = textwrap.wrap(pt, width=52)
        for i, wline in enumerate(wrapped_pt[:2]):
            draw.text((dot_x + 20, head_y + (i * 26)), wline, font=font_body, fill=WHITE if i == 0 else GREY)
        head_y += 60

    # ── CTA ──
    cta_y = H - 80
    draw.text((head_x, cta_y), f"→ {cta}  |  boothop.com", font=font_cta, fill=ACCENT)

    # ── Logo (top right) ──
    if LOGO_PATH.exists():
        try:
            logo = Image.open(LOGO_PATH).convert("RGBA")
            lw, lh = 260, int(260 * logo.size[1] / logo.size[0])
            logo   = logo.resize((lw, lh), Image.LANCZOS)
            lx = W - lw - 40
            ly = 30
            img.paste(logo, (lx, ly), logo)
        except Exception as e:
            _log(f"Logo paste failed: {e}")

    # ── "BootHop B2B" tag (bottom right) ──
    tag = "BootHop  |  B2B Logistics"
    draw.text((W - 340, H - 40), tag, font=font_small, fill=GREY)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


# ── LinkedIn image upload + post ───────────────────────────────────────────────
def post_to_linkedin_image(caption: str, img_bytes: bytes) -> str | None:
    access_token, person_urn = _load_linkedin()
    if not access_token or not person_urn:
        _log("LinkedIn credentials missing — skipping")
        return None

    auth = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type":  "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
    }

    # 1. Register image upload
    try:
        reg = requests.post(
            "https://api.linkedin.com/v2/assets?action=registerUpload",
            headers=auth,
            json={"registerUploadRequest": {
                "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                "owner":   person_urn,
                "serviceRelationships": [
                    {"relationshipType": "OWNER", "identifier": "urn:li:userGeneratedContent"}
                ],
            }},
            timeout=30,
        )
        reg.raise_for_status()
        rd         = reg.json()
        upload_url = rd["value"]["uploadMechanism"][
            "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"
        ]["uploadUrl"]
        asset_urn  = rd["value"]["asset"]
    except Exception as e:
        _log(f"Register upload failed: {e}")
        return None

    # 2. Upload image bytes
    try:
        up = requests.put(
            upload_url,
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "image/png"},
            data=img_bytes,
            timeout=120,
        )
        up.raise_for_status()
        _log(f"Image uploaded — HTTP {up.status_code}")
    except Exception as e:
        _log(f"Image upload failed: {e}")
        return None

    # 3. Create UGC post with image
    try:
        post = requests.post(
            "https://api.linkedin.com/v2/ugcPosts",
            headers=auth,
            json={
                "author":          person_urn,
                "lifecycleState":  "PUBLISHED",
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary":    {"text": caption},
                        "shareMediaCategory": "IMAGE",
                        "media": [{
                            "status":      "READY",
                            "description": {"text": caption[:200]},
                            "media":       asset_urn,
                            "title":       {"text": caption[:100]},
                        }],
                    }
                },
                "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
            },
            timeout=30,
        )
        post.raise_for_status()
        urn = post.headers.get("x-restli-id", "") or post.json().get("id", "")
        _log(f"LinkedIn image post created — URN: {urn}")
        return urn or "ok"
    except Exception as e:
        _log(f"UGC post failed: {e}")
        return None


# ── Comms ──────────────────────────────────────────────────────────────────────
def send_whatsapp(text: str):
    if not _WA_TOKEN or not _WA_PHONE_ID:
        return
    try:
        requests.post(
            f"https://graph.facebook.com/v18.0/{_WA_PHONE_ID}/messages",
            headers={"Authorization": f"Bearer {_WA_TOKEN}", "Content-Type": "application/json"},
            json={"messaging_product": "whatsapp", "to": _WA_RECIPIENT,
                  "type": "text", "text": {"body": text[:4096]}},
            timeout=20,
        )
    except Exception as e:
        _log(f"WhatsApp error: {e}")


def send_telegram(text: str, markup=None):
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text[:4096], "parse_mode": "Markdown"}
    if markup:
        payload["reply_markup"] = json.dumps(markup)
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json=payload, timeout=15,
        )
        return r.json().get("result", {}).get("message_id")
    except Exception as e:
        _log(f"Telegram error: {e}")
        return None


def send_telegram_photo(img_bytes: bytes, caption: str, markup=None):
    """Send the card image to Telegram as a photo."""
    files   = {"photo": ("card.png", img_bytes, "image/png")}
    payload = {"chat_id": TELEGRAM_CHAT_ID, "caption": caption[:1024], "parse_mode": "Markdown"}
    if markup:
        payload["reply_markup"] = json.dumps(markup)
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto",
            data=payload, files=files, timeout=30,
        )
        return r.json().get("result", {}).get("message_id")
    except Exception as e:
        _log(f"Telegram photo error: {e}")
        return None


# ── Approval polling ───────────────────────────────────────────────────────────
def wait_for_approval(approval_id: str) -> str:
    """
    Polls Telegram for explicit approval.
    LinkedIn NEVER auto-posts — requires tap on ✅ button.
    Returns: 'post' | 'skip' | 'timeout'
    """
    try:
        drain   = requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates",
            params={"timeout": 0, "allowed_updates": json.dumps(["callback_query"])},
            timeout=10,
        ).json()
        updates = drain.get("result", [])
        offset  = (updates[-1]["update_id"] + 1) if updates else 0
    except Exception:
        offset = 0

    deadline = time.time() + 5400   # 90-min window
    _log(f"Waiting for approval (id={approval_id}) — no auto-post...")

    while time.time() < deadline:
        remaining = deadline - time.time()
        wait      = int(min(30, remaining))
        if wait <= 0:
            break
        try:
            resp = requests.get(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates",
                params={"offset": offset, "timeout": wait,
                        "allowed_updates": json.dumps(["callback_query"])},
                timeout=wait + 15,
            ).json()
            for update in resp.get("result", []):
                offset = update["update_id"] + 1
                cb     = update.get("callback_query", {})
                data   = cb.get("data", "")
                if data == "li_post":
                    try:
                        requests.post(
                            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/answerCallbackQuery",
                            json={"callback_query_id": cb["id"], "text": "✅ Posting to LinkedIn + Blog!"},
                            timeout=10,
                        )
                    except Exception:
                        pass
                    _log("Approved via Telegram")
                    return "post"
                if data == "li_skip":
                    try:
                        requests.post(
                            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/answerCallbackQuery",
                            json={"callback_query_id": cb["id"], "text": "⏭ Skipped."},
                            timeout=10,
                        )
                    except Exception:
                        pass
                    _log("Skipped via Telegram")
                    return "skip"
        except Exception:
            time.sleep(10)

    _log("90-min window elapsed — LinkedIn NOT posted (requires explicit approval)")
    return "timeout"


# ── Blog save + publish ────────────────────────────────────────────────────────
def save_to_blog(title: str, labels: list, html: str) -> str:
    date_str = datetime.now().strftime("%Y-%m-%d")
    slug     = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60]
    filename = f"{date_str}_{slug}.html"
    content  = f"<!-- title: {title} -->\n<!-- labels: {', '.join(labels)} -->\n{html}"
    (BLOG / filename).write_text(content, encoding="utf-8")
    _log(f"Blog post saved → blog/pending/{filename}")
    return filename


def publish_blog():
    import subprocess
    try:
        r = subprocess.run(
            [sys.executable, str(BASE / "blog" / "post_to_blogger.py")],
            capture_output=True, text=True, timeout=60,
        )
        if r.returncode == 0:
            send_telegram("✅ Blog post published → boothop.blogspot.com")
            _log("Blog published.")
        else:
            _log(f"Blog publish failed: {r.stderr[:200]}")
            send_telegram("⚠️ Blog file saved but Blogger post failed.")
    except Exception as e:
        _log(f"Blog publish error: {e}")


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    _log("=== LinkedIn B2B Daily ===")

    topic = B2B_TOPICS[datetime.utcnow().timetuple().tm_yday % len(B2B_TOPICS)]
    _log(f"Topic: {topic['angle']} — {topic['hook']}")

    # Generate content
    _log("Generating content with Claude Haiku...")
    try:
        content = generate_b2b_content(topic)
    except Exception as e:
        _log(f"Content generation failed: {e}")
        send_telegram(f"❌ LinkedIn B2B: content generation failed — {e}")
        return

    li_text     = content["linkedin_post"]
    card_head   = content.get("card_headline", topic["hook"])
    card_points = content.get("card_points", [])
    card_cta    = content.get("card_cta", "Learn more")
    blog_title  = content["blog_title"]
    blog_html   = content["blog_html"]
    blog_labels = content.get("blog_labels", ["logistics", "b2b"])

    # Render card image
    _log("Rendering branded card image...")
    try:
        img_bytes = create_card_image(card_head, card_points, card_cta)
        _log(f"Card rendered — {len(img_bytes):,} bytes")
    except Exception as e:
        _log(f"Card render failed: {e}")
        img_bytes = None

    # WhatsApp preview
    preview = (
        f"📊 *BootHop LinkedIn B2B — Daily Post*\n\n"
        f"{li_text[:500]}{'…' if len(li_text) > 500 else ''}\n\n"
        f"Tap ✅ in Telegram to publish (no auto-post)."
    )
    send_whatsapp(preview)

    import random as _rand
    approval_id = str(_rand.randint(10000, 99999))

    markup = {"inline_keyboard": [[
        {"text": "✅ Post to LinkedIn + Blog", "callback_data": "li_post"},
        {"text": "⏭ Skip",                    "callback_data": "li_skip"},
    ]]}

    caption_tg = (
        f"*LinkedIn B2B Ready* (id: {approval_id})\n\n"
        f"_{topic['hook']}_\n\n"
        f"{li_text[:350]}…\n\n"
        f"⚠️ _Explicit approval required — will NOT auto-post._"
    )

    # Send card image as Telegram photo with approval buttons
    if img_bytes:
        send_telegram_photo(img_bytes, caption_tg, markup=markup)
    else:
        send_telegram(caption_tg, markup=markup)

    # Wait for explicit approval
    result = wait_for_approval(approval_id)

    if result in ("skip", "timeout"):
        msg = "LinkedIn B2B skipped." if result == "skip" else "LinkedIn B2B — no action taken."
        send_telegram(msg)
        _log(f"Result: {result}")
        return

    # Post to LinkedIn as image card
    _log("Posting card to LinkedIn...")
    if img_bytes:
        urn = post_to_linkedin_image(li_text, img_bytes)
    else:
        # Fallback to text-only if image render failed
        from post_linkedin import post_text
        urn = post_text(li_text)

    status = f"✅ LinkedIn posted — {urn}" if urn else "⚠️ LinkedIn post failed"
    send_telegram(status)

    # Save + publish blog
    _log("Saving blog post...")
    save_to_blog(blog_title, blog_labels, blog_html)
    publish_blog()

    _log("Done.")


if __name__ == "__main__":
    main()
