"""
generate_carousel_content.py
Generates daily Instagram/TikTok carousel content for BootHop using Claude AI.

Ported from: boothop/src/lib/services/boothop-content.ts
Status: MOVED — not yet wired into pipeline.py or telegram_commander.py
"""

import json
import os
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).parent.parent

# ── Themes — rotates daily so content stays fresh ─────────────────────────────
THEMES = [
    {"theme": "passport_emergency",  "route": "London to Manchester",   "urgency": "flight at 6am"},
    {"theme": "wedding_outfit",      "route": "UK to Lagos Nigeria",     "urgency": "wedding in 24 hours"},
    {"theme": "business_critical",   "route": "London to Dubai",         "urgency": "board meeting tomorrow"},
    {"theme": "family_sending_home", "route": "UK to Accra Ghana",       "urgency": "mothers birthday"},
    {"theme": "medical_supplies",    "route": "Birmingham to Nairobi",   "urgency": "urgent prescription needed"},
    {"theme": "missing_charger",     "route": "Leeds to London",         "urgency": "presentation in 3 hours"},
    {"theme": "birthday_gift",       "route": "Manchester to Lagos",     "urgency": "birthday party tonight"},
    {"theme": "forgotten_documents", "route": "Edinburgh to Heathrow",   "urgency": "visa interview tomorrow"},
    {"theme": "baby_items",          "route": "UK to Kumasi Ghana",      "urgency": "new baby arrived"},
    {"theme": "aog_parts",           "route": "London to Abu Dhabi",     "urgency": "aircraft on ground"},
    {"theme": "exam_materials",      "route": "Nottingham to London",    "urgency": "exam at 9am"},
    {"theme": "anniversary_gift",    "route": "UK to Enugu Nigeria",     "urgency": "30th anniversary tomorrow"},
    {"theme": "job_contract",        "route": "Bristol to Lagos",        "urgency": "contract signing deadline"},
    {"theme": "medication",          "route": "London to Abuja",         "urgency": "ran out of medication"},
]

HASHTAGS = (
    "#boothop #peertopeerdelivery #internationalshipping #sendingparcelabroad "
    "#uknigeria #diasporadelivery #verifiedtraveller #luggagespace "
    "#earningwhiletravelling #affordableshipping #uklogistics #travelhack "
    "#parcelsending #communitydelivery"
)


def _load_anthropic_key() -> str:
    # Try config.py first, then env
    try:
        import sys
        sys.path.insert(0, str(BASE))
        from config import ANTHROPIC_API_KEY
        return ANTHROPIC_API_KEY
    except (ImportError, AttributeError):
        return os.environ.get("ANTHROPIC_API_KEY", "")


def generate_daily_content() -> dict:
    """
    Returns a dict with keys:
      theme, scenario, hook, slides (list of {text, pexels_query}), caption, hashtags
    """
    import anthropic

    api_key = _load_anthropic_key()
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not configured")

    client = anthropic.Anthropic(api_key=api_key)

    day_of_year = datetime.utcnow().timetuple().tm_yday
    t = THEMES[day_of_year % len(THEMES)]
    theme, route, urgency = t["theme"], t["route"], t["urgency"]

    prompt = f"""You write punchy Instagram carousel content for BootHop — a platform where verified travellers carry parcels on their existing journeys. Senders pay far less than a courier. Travellers earn from spare luggage space.

The golden rule: people stop scrolling for PROBLEMS, not platforms. Never open with a logo or a product name.

Today's scenario:
- Theme: {theme}
- Route: {route}
- Urgency: {urgency}

Return ONLY valid JSON — no markdown, no explanation:
{{
  "scenario": "one vivid sentence describing the real-world problem",
  "hook": "10 words max — states the problem sharply, no brand name",
  "slides": [
    {{"text": "slide 1 — the problem (max 12 words)", "pexels_query": "relevant stock photo search"}},
    {{"text": "slide 2 — tension/consequences (max 12 words)", "pexels_query": "relevant stock photo search"}},
    {{"text": "slide 3 — the twist (someone is already travelling that route)", "pexels_query": "person travelling luggage"}},
    {{"text": "slide 4 — the outcome (problem solved)", "pexels_query": "relief happy travel success"}},
    {{"text": "BootHop. Link in bio.", "pexels_query": "airport departure gate morning"}}
  ],
  "caption": "3-4 sentence Instagram caption. Human, conversational, ends with a question to drive comments. No hashtags here.",
  "hashtags": "{HASHTAGS} #{theme.replace('_', '')}"
}}

Rules:
- Slide 1 must be the RAW PROBLEM — no solution, no brand
- Slide 3 MUST mention someone already travelling that route
- Caption: write like a real person, not a brand. Use "you" not "our customers"
- Keep hooks under 10 words"""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text
    import re
    match = re.search(r"\{[\s\S]*\}", raw)
    if not match:
        raise ValueError("Claude returned no JSON")

    parsed = json.loads(match.group(0))
    parsed["theme"] = theme
    return parsed


if __name__ == "__main__":
    content = generate_daily_content()
    print(json.dumps(content, indent=2))
