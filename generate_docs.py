"""Generate BootHop Pipeline PDF documentation."""
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                 TableStyle, HRFlowable, PageBreak)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from pathlib import Path

OUT = Path(r"C:\Users\babso\Desktop\BootHopPipeline\BootHop_Pipeline_Documentation.pdf")

W, H = A4
NAVY  = colors.HexColor("#07111f")
GREEN = colors.HexColor("#10b981")
LGREY = colors.HexColor("#f3f4f6")
MGREY = colors.HexColor("#6b7280")
WHITE = colors.white
YELLOW= colors.HexColor("#fbbf24")

doc = SimpleDocTemplate(
    str(OUT), pagesize=A4,
    leftMargin=18*mm, rightMargin=18*mm,
    topMargin=14*mm, bottomMargin=14*mm,
)

styles = getSampleStyleSheet()

def S(name, **kw):
    return ParagraphStyle(name, parent=styles["Normal"], **kw)

TITLE  = S("Title",  fontSize=26, textColor=WHITE,  spaceAfter=4,  fontName="Helvetica-Bold", alignment=TA_CENTER)
STITLE = S("STitle", fontSize=13, textColor=WHITE,  spaceAfter=2,  fontName="Helvetica",      alignment=TA_CENTER)
H1     = S("H1",     fontSize=15, textColor=NAVY,   spaceAfter=5,  spaceBefore=12, fontName="Helvetica-Bold", borderPad=4)
H2     = S("H2",     fontSize=12, textColor=GREEN,  spaceAfter=3,  spaceBefore=8,  fontName="Helvetica-Bold")
BODY   = S("Body",   fontSize=9.5,textColor=colors.HexColor("#1f2937"), spaceAfter=4, leading=15, alignment=TA_JUSTIFY)
MONO   = S("Mono",   fontSize=8.5,textColor=NAVY,   spaceAfter=3,  fontName="Courier", backColor=LGREY, leading=13)
NOTE   = S("Note",   fontSize=8.5,textColor=MGREY,  spaceAfter=2,  fontName="Helvetica-Oblique")
BULLET = S("Bullet", fontSize=9.5,textColor=colors.HexColor("#1f2937"), spaceAfter=3, leading=15, leftIndent=12)

def hr(): return HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#e5e7eb"), spaceAfter=6, spaceBefore=6)
def sp(h=4): return Spacer(1, h*mm)

def table(data, col_widths, header_fill=NAVY):
    t = Table(data, colWidths=col_widths)
    style = [
        ("BACKGROUND", (0,0), (-1,0), header_fill),
        ("TEXTCOLOR",  (0,0), (-1,0), WHITE),
        ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",   (0,0), (-1,0), 9),
        ("FONTNAME",   (0,1), (-1,-1), "Helvetica"),
        ("FONTSIZE",   (0,1), (-1,-1), 8.5),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [WHITE, LGREY]),
        ("GRID",       (0,0), (-1,-1), 0.4, colors.HexColor("#d1d5db")),
        ("VALIGN",     (0,0), (-1,-1), "TOP"),
        ("TOPPADDING", (0,0), (-1,-1), 5),
        ("BOTTOMPADDING",(0,0),(-1,-1),5),
        ("LEFTPADDING",(0,0), (-1,-1), 7),
    ]
    t.setStyle(TableStyle(style))
    return t

def cover_block():
    cover = Table(
        [[Paragraph("BootHop Content Pipeline", TITLE)],
         [Paragraph("Full Technical Workflow & Schedule — v1.0 — May 2026", STITLE)],
         [Paragraph("Confidential — BootHop Internal", NOTE)]],
        colWidths=[W - 36*mm],
    )
    cover.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), NAVY),
        ("TOPPADDING",  (0,0), (-1,-1), 12),
        ("BOTTOMPADDING",(0,0),(-1,-1),12),
        ("LEFTPADDING", (0,0), (-1,-1), 12),
        ("RIGHTPADDING",(0,0), (-1,-1), 12),
        ("ROUNDEDCORNERS", [6]),
    ]))
    return cover

story = []

# ─── COVER ────────────────────────────────────────────────────────────────────
story.append(sp(8))
story.append(cover_block())
story.append(sp(10))

story.append(Paragraph("Overview", H1))
story.append(Paragraph(
    "The BootHop Content Pipeline is a fully automated system that runs on a Windows PC "
    "and produces two 30-second TikTok/Instagram Reels every day without manual intervention. "
    "It collects real-time intelligence (Nigeria Google Trends, YouTube, TikTok, Instagram), "
    "selects trending music, generates AI voiceover, assembles videos with branded overlays, "
    "sends them to Telegram for review and one-tap approval, then posts directly to TikTok, "
    "Instagram and YouTube. Every Monday at 3 am it analyses last week's performance and "
    "automatically adjusts next week's content bucket weights and music search profile.",
    BODY))
story.append(sp())

# ─── SCHEDULE ─────────────────────────────────────────────────────────────────
story.append(Paragraph("Daily & Weekly Schedule", H1))
story.append(table(
    [["Time", "Task Scheduler Job", "Script", "What Happens"],
     ["5:45 am\n(daily)", "BootHopMorning", "main.py",
      "Downloads trending music (Nigeria → UK Grind → US RnB → Archive).\n"
      "Fetches Nigeria Google Trends, YouTube trending NG, TikTok hashtags,\n"
      "own Instagram insights. Writes data/trending_hooks_today.json.\n"
      "Sends daily briefing email (Gmail) + Telegram summary."],
     ["6:00 am\n(daily)", "BootHopPipeline", "pipeline.py",
      "Reads today's bucket (day-of-week rotation or performance override).\n"
      "Picks 2 unique POV hooks + engagements (7-day no-repeat memory).\n"
      "Downloads 8 Pexels video clips per version (different scenes per V1/V2).\n"
      "Generates Edge TTS voiceover (Nigerian/Spanish/British voice).\n"
      "Renders 4 videos (V1 Library, V1 Trending, V2 Library, V2 Trending).\n"
      "Sends all videos + captions to Telegram.\n"
      "Sends approval keyboard — user picks V1, V2, or Auto.\n"
      "Posts chosen version to TikTok + Instagram. Uploads one to YouTube."],
     ["3:00 am\n(Monday)", "BootHopWeekly", "scripts/weekly_review.py",
      "Fetches Instagram last-7-days posts + engagement.\n"
      "Reads music_log.json + daily_log.json.\n"
      "Identifies top-performing hook patterns and best posting day.\n"
      "Analyses music profile of viral videos (vibe/energy/pitch/mood).\n"
      "Writes data/performance_weights.json — pipeline.py reads this at 6am.\n"
      "Sends weekly report to Telegram + Gmail email."]],
    [22*mm, 36*mm, 42*mm, None],
))

story.append(sp(6))

# ─── BUCKET ROTATION ─────────────────────────────────────────────────────────
story.append(Paragraph("Day-of-Week Content Bucket Rotation", H1))
story.append(Paragraph(
    "Pipeline.py selects a content bucket each day. If last Monday's weekly review found a "
    "bucket with a performance weight ≥ 1.6 that differs from today's scheduled bucket, "
    "the override activates automatically.",
    BODY))
story.append(sp())
story.append(table(
    [["Day", "Default Bucket", "Content Theme", "Hashtag Emphasis"],
     ["Monday",    "Business",   "B2B / SME / supply-chain urgency",    "#Logistics #SupplyChain #B2B"],
     ["Tuesday",   "Family",     "Emotional diaspora family deliveries", "#DiasporaMagic #LondonToLagos"],
     ["Wednesday", "Airport",    "Traveller stress / passport moments",  "#AirportLife #TravelHack"],
     ["Thursday",  "Smart",      "Intelligent / sustainable logistics",  "#SmartLogistics #Innovation"],
     ["Friday",    "Cinematic",  "Premium, aspirational movement",       "#PremiumDelivery #TrustedMovement"],
     ["Saturday",  "Community",  "Diaspora culture / Nigerian pidgin",   "#NaijaUK #DiasporaLife"],
     ["Sunday",    "Community",  "Diaspora culture / Nigerian pidgin",   "#BootHop #NigerianTikTok"]],
    [22*mm, 28*mm, None, 55*mm],
))

story.append(PageBreak())

# ─── MUSIC ───────────────────────────────────────────────────────────────────
story.append(Paragraph("Music Selection — Priority Chain", H1))
story.append(Paragraph(
    "Every morning at 5:45 am, scripts/fetch_trending_music.py runs before the main pipeline "
    "and downloads one MP3 to music/daily/track_1.mp3. Pipeline.py uses this as the "
    '"Trending" music track. A second track is drawn from the local archive (music/archive/).',
    BODY))
story.append(sp())
story.append(table(
    [["Priority", "Source", "Method", "Filter"],
     ["0 — Profile\nmatch",
      "YouTube Search",
      "Reads preferred_music_profile from\nperformance_weights.json (written Monday 3am).\nSearches for SIMILAR vibe/energy/mood to\nlast week's viral video music. Never same track.",
      "Vibe → energy → mood → custom search queries.\nIf is_old_school=True: searches classics/nostalgic.\nElse: searches fresh trending tracks."],
     ["1 — Nigeria\nTrending",
      "YouTube Data API v3",
      "Videos chart, regionCode=NG,\nvideoCategoryId=10 (Music), max 10 results.",
      "No filter — top Nigerian music chart."],
     ["1b — Nigeria\nKeyword",
      "YouTube Search",
      '"Nigeria afrobeats trending 2025",\n"Naija music trending today"',
      "Used if trending chart returns 0 results."],
     ["2 — UK Grind\n/ Urban",
      "YouTube Data API v3",
      "Videos chart, regionCode=GB,\nvideoCategoryId=10, max 12 results.",
      "Title must contain: drill, grime, urban,\nafroswing, central cee, stormzy, dave, skepta…"],
     ["3 — US R&B",
      "YouTube Data API v3",
      "Videos chart, regionCode=US,\nvideoCategoryId=10, max 12 results.",
      "Title must contain: rnb, r&b, neo soul,\nusher, beyonce, sza, frank ocean, h.e.r…"],
     ["4 — Archive\nFallback",
      "Local files",
      "Rotates through music/archive/*.mp3\nby day-of-year, skipping tracks used in\nthe past 7 days.",
      "7-day no-repeat enforced.\nAll-used: just rotate."]],
    [22*mm, 28*mm, 60*mm, None],
))
story.append(sp())
story.append(Paragraph(
    "No-repeat rule: every downloaded track is logged to data/music_log.json (90-day rolling). "
    "Before downloading, the title is checked — if it was used in the past 7 days it is skipped "
    "and the pipeline tries the next candidate.",
    NOTE))

story.append(sp(6))

# ─── VIDEO PRODUCTION ────────────────────────────────────────────────────────
story.append(Paragraph("Video Production — What's Inside Each 30-Second Video", H1))
story.append(table(
    [["Timestamp", "Layer / Element", "Detail"],
     ["0–30s",     "Background clips",
      "8 × Pexels portrait video clips, each trimmed to 3.75s and concatenated.\n"
      "V1 uses hook-specific queries then bucket queries.\n"
      "V2 uses different queries (exclude_queries ensures no repeated scenes)."],
     ["0–8s",      "POV Hook text",
      "Top of frame. Yellow 'POV:' label (Oswald-Bold, 72pt) + 3 content lines (60pt).\n"
      "Black pill background for readability. Dark stinger for first 0.3s."],
     ["8–17s",     "Problem text",
      "Center frame. 2 white lines on dark pill. Describes the delivery problem."],
     ["17–27s",    "Solution text",
      "Center frame. 2 white lines on dark pill. Explains how BootHop helps.\n"
      "boothop.com ghost text fades in at 21s."],
     ["20–22s",    "Brand card overlay",
      "fig1Start.png or fig2start.png (randomly selected) centered over video."],
     ["27–30s",    "FIG4End end card",
      "Full-screen FIG4End.png trust/safety end card.\n"
      "Hero end line (2 lines, Oswald-Bold, shadow-only, bottom of frame)."],
     ["0–30s",     "BootHop logo",
      "mainlogo.png, scaled to 180px wide, top-right corner throughout."],
     ["0–30s",     "Voiceover audio",
      "Edge TTS 5-part brand arc: Hook → Problem → Movement → Solution → Hero CTA.\n"
      "Voice auto-detected: Nigerian (Ezinne) / Spanish (Dalia) / British (Sonia).\n"
      "Phonetic replacements applied for Naija/Pidgin/Yoruba words."],
     ["0–30s",     "Background music",
      "Ducked to 18% volume, mixed under voiceover.\n"
      "Library version: archive track. Trending version: music/daily/track_1.mp3."]],
    [22*mm, 38*mm, None],
))

story.append(PageBreak())

# ─── OUTPUT FILES ─────────────────────────────────────────────────────────────
story.append(Paragraph("Output Files Generated Each Day", H1))
story.append(table(
    [["File / Folder", "Description"],
     ["output/YYYY-MM-DD/\nv1_library_v1.mp4",    "V1 with archive music track"],
     ["output/YYYY-MM-DD/\nv1_trending_v1.mp4",   "V1 with today's trending music"],
     ["output/YYYY-MM-DD/\nv2_library_v2.mp4",    "V2 (different hook + scenes) with archive music"],
     ["output/YYYY-MM-DD/\nv2_trending_v2.mp4",   "V2 with today's trending music"],
     ["output/YYYY-MM-DD/\nv1_english_v1.mp4",    "English voiceover version (when hook is Pidgin/Spanish)"],
     ["output/YYYY-MM-DD/\nmetadata_*.json",       "Run metadata: hook, bucket, music paths, timestamp"],
     ["data/trending_hooks_today.json",             "Intelligence output from main.py: trends, generated hooks, hashtag sets"],
     ["data/music_log.json",                        "90-day rolling log of every music track used (7-day no-repeat)"],
     ["data/daily_log.json",                        "60-day rolling pipeline run history"],
     ["data/used_content.json",                     "7-day hook/engagement memory (prevents re-use within a week)"],
     ["data/weekly_insights.json",                  "Human-readable weekly review summary (written Monday 3am)"],
     ["data/performance_weights.json",              "Machine-readable weights: bucket boosts + music profile (written Monday 3am, read 6am daily)"],
     ["music/daily/track_1.mp3",                    "Today's trending music download (overwritten each morning)"],
     ["music/daily/daily_info.json",                "Track metadata: title, artist, source flag"]],
    [65*mm, None],
))

story.append(sp(6))

# ─── SOCIAL POSTING FLOW ─────────────────────────────────────────────────────
story.append(Paragraph("Social Posting — Telegram Approval Flow", H1))
story.append(Paragraph(
    "After rendering, all 4 videos are sent to the BootHop Telegram chat. "
    "A keyboard appears with three options:",
    BODY))
story.append(sp())
story.append(table(
    [["Button", "What Happens"],
     ["✅ Post V1",                   "V1 Library video posted immediately to TikTok + Instagram. V2 not posted."],
     ["✅ Post V2",                   "V2 Library video posted immediately to TikTok + Instagram. V1 not posted."],
     ["⏭ Auto (V1 now, V2 in 1hr)", "V1 posted immediately. V2 launched as a detached background process (time.sleep(3600) then posts)."],
     ["No reply in 15 min",          "Same as Auto — V1 posts now, V2 deferred to 1 hour later."]],
    [55*mm, None],
))
story.append(sp())
story.append(Paragraph(
    "YouTube upload also runs automatically: alternates between V1 and V2 each day (odd/even day-of-year). "
    "Non-English hooks generate a separate English voiceover version uploaded with version letter 'a' "
    "(e.g. BootHop-FD0001A primary, BootHop-FD0001a English translation).",
    BODY))

story.append(PageBreak())

# ─── WEEKLY REVIEW ───────────────────────────────────────────────────────────
story.append(Paragraph("Weekly Review — Monday 3:00 am", H1))
story.append(Paragraph(
    "scripts/weekly_review.py runs every Monday and produces the performance_weights.json "
    "that pipeline.py reads at 6am to dynamically adjust content and music for the coming week.",
    BODY))
story.append(sp())
story.append(table(
    [["Step", "What It Does"],
     ["1. Load Instagram\nlast 7 days",
      "Calls Graph API /media endpoint, filters posts with timestamp > 7 days ago.\n"
      "Extracts: like_count, comments_count, caption, timestamp, media_type."],
     ["2. Load logs",
      "Reads music_log.json (tracks used this week) and daily_log.json (pipeline runs)."],
     ["3. Analyse\nengagement",
      "Ranks posts by likes + comments. Finds best day of week.\n"
      "Identifies top patterns in top-post captions (pov_hook, urgency_message,\n"
      "family_bucket, diaspora_angle, business_bucket, airport_bucket)."],
     ["4. Music profile\nanalysis",
      "Crosses top post timestamps with music_log.json dates.\n"
      "Identifies the vibe (Afrobeats / Amapiano / Afropop / Highlife / Afro-fusion),\n"
      "energy (high/medium/low), pitch, mood, and is_old_school flag.\n"
      "Generates custom YouTube search queries for SIMILAR tracks next week.\n"
      "Important: this never re-posts old content — only finds new music with same feel."],
     ["5. Write\nperformance_weights.json",
      "Bucket boosts: top pattern's bucket → 1.8×, 2nd → 1.4×, 3rd → 1.2×.\n"
      "Music weights: if trending source won → trending 1.5×; if archive won → library 1.3×.\n"
      "preferred_music_profile: full vibe/energy/mood/pitch + custom search queries.\n"
      "top_hooks: always empty — old captions are never re-used."],
     ["6. Send reports",
      "Telegram: full weekly report with stats, patterns, music profile, recommendations.\n"
      "Gmail (daddyoba12@gmail.com): branded HTML email with top posts table,\n"
      "winning patterns, boosted buckets, music this week summary."]],
    [38*mm, None],
))

story.append(sp(6))

# ─── INTELLIGENCE LAYER ──────────────────────────────────────────────────────
story.append(Paragraph("Morning Intelligence Layer — main.py (5:45 am)", H1))
story.append(table(
    [["Collector / Module", "Source", "Output"],
     ["collectors/google_trends.py",  "pytrends — Nigeria (geo=NG)",          "Top 20 rising keywords in Nigeria"],
     ["collectors/youtube.py",        "YouTube Data API v3 — regionCode=NG",  "Top 10 trending video titles/channels"],
     ["collectors/tiktok_scraper.py", "TikTokApi (unofficial) or fallback",   "Trending hashtag counts or empty list"],
     ["collectors/instagram.py",      "Instagram Graph API v21.0",            "Own account recent posts + insights"],
     ["analysis/hooks.py",            "YouTube titles + Nigeria trends",       "Viral trigger phrases + BootHop POV hook ideas"],
     ["analysis/hashtags.py",         "Platform hashtag sets",                "Recommended hashtag string (TikTok/IG/LinkedIn/YT)"],
     ["analysis/engagement.py",       "Instagram posts",                       "Engagement rate %, daily log entry, weekly summary"],
     ["scripts/fetch_trending_music.py","YouTube API + yt-dlp",               "music/daily/track_1.mp3 + daily_info.json"]],
    [55*mm, 45*mm, None],
))

story.append(sp(6))

# ─── DATA FILES MAP ───────────────────────────────────────────────────────────
story.append(Paragraph("Key Data Files Reference", H1))
story.append(table(
    [["File", "Written By", "Read By", "Purpose"],
     ["data/music_log.json",         "fetch_trending_music.py\n(5:45am daily)", "fetch_trending_music.py",       "90-day track history, 7-day no-repeat"],
     ["data/daily_log.json",         "analysis/engagement.py\n(5:45am daily)",  "weekly_review.py (3am Mon)",    "Pipeline run history for weekly analysis"],
     ["data/used_content.json",      "pipeline.py (6am)",                        "pipeline.py (6am)",             "7-day hook/engagement no-repeat memory"],
     ["data/trending_hooks_today.json","main.py (5:45am)",                       "pipeline.py (optional)",        "Generated hooks from Nigeria trends"],
     ["data/weekly_insights.json",   "weekly_review.py (3am Mon)",              "Briefing / human review",        "Human-readable weekly performance summary"],
     ["data/performance_weights.json","weekly_review.py (3am Mon)",             "pipeline.py (6am daily)",        "Bucket boosts + music profile for next week"],
     ["data/youtube_sequence.json",  "pipeline.py (6am)",                        "pipeline.py (6am)",             "Sequential YouTube video ID counter"]],
    [52*mm, 40*mm, 40*mm, None],
))

story.append(PageBreak())

# ─── API KEYS & CREDENTIALS ───────────────────────────────────────────────────
story.append(Paragraph("API Keys & Credentials (config.py)", H1))
story.append(table(
    [["Service", "Config Key", "Used For"],
     ["Telegram Bot",      "TELEGRAM_TOKEN\nTELEGRAM_CHAT_ID",  "Send videos, captions, approval keyboards,\nweekly reports, briefings"],
     ["YouTube Data API",  "YOUTUBE_API_KEY",                   "Trending music charts (NG/GB/US),\nkeyword search for music, YouTube upload"],
     ["Pexels Video API",  "PEXELS_KEY (pipeline.py)",          "Download portrait video clips for each video version"],
     ["Instagram Graph API","IG_ACCESS_TOKEN\nIG_USER_ID",      "Post Reels, fetch own post insights for weekly review"],
     ["Gmail SMTP",        "EMAIL_SENDER\nEMAIL_PASSWORD",      "Daily briefing email + weekly review email\n(daddyoba12@gmail.com, port 587 STARTTLS)"],
     ["TikTok",            "scripts/social_credentials.json",   "Post videos via TikTok Content Posting API"]],
    [35*mm, 45*mm, None],
))

story.append(sp(6))

# ─── FILE STRUCTURE ───────────────────────────────────────────────────────────
story.append(Paragraph("Folder Structure", H1))
story.append(Paragraph("""
<font face="Courier" size="8.5">
BootHopPipeline/<br/>
├── main.py                     ← 5:45am intelligence runner<br/>
├── pipeline.py                 ← 6:00am video production<br/>
├── config.py                   ← All credentials + shared paths<br/>
├── assets/                     ← Brand overlays, logos, fonts<br/>
│   ├── mainlogo.png<br/>
│   └── fonts/ (Oswald-Bold.ttf, Montserrat-ExtraBold.ttf)<br/>
├── collectors/<br/>
│   ├── google_trends.py        ← pytrends Nigeria<br/>
│   ├── youtube.py              ← YT trending NG<br/>
│   ├── instagram.py            ← Graph API own media<br/>
│   └── tiktok_scraper.py       ← TikTokApi / fallback<br/>
├── analysis/<br/>
│   ├── hooks.py                ← Viral triggers + hook ideas<br/>
│   ├── hashtags.py             ← Platform hashtag sets<br/>
│   └── engagement.py           ← Engagement calc + log<br/>
├── briefing_module/<br/>
│   ├── briefing.py             ← Gmail SMTP email + Telegram briefing<br/>
│   └── templates/daily.html   ← Jinja2 HTML email template<br/>
├── scripts/<br/>
│   ├── fetch_trending_music.py ← Music priority chain + yt-dlp<br/>
│   ├── weekly_review.py        ← Monday 3am performance analysis<br/>
│   ├── post_tiktok.py          ← TikTok Content Posting API<br/>
│   ├── post_instagram.py       ← Instagram Graph API Reel post<br/>
│   ├── post_linkedin.py        ← LinkedIn post (optional)<br/>
│   ├── upload_to_youtube.py    ← YouTube Data API upload<br/>
│   └── boothop-history.ps1    ← Historical logistics video generator<br/>
├── music/<br/>
│   ├── daily/track_1.mp3       ← Today's trending download<br/>
│   └── archive/                ← Permanent library of approved tracks<br/>
├── data/<br/>
│   ├── hooks.txt               ← POV hook library (~200+ hooks)<br/>
│   ├── engagements.txt         ← Engagement CTA lines<br/>
│   ├── music_log.json          ← 90-day music usage log<br/>
│   ├── daily_log.json          ← Pipeline run history<br/>
│   ├── used_content.json       ← 7-day hook no-repeat memory<br/>
│   ├── weekly_insights.json    ← Human-readable weekly summary<br/>
│   └── performance_weights.json← Machine-readable weekly weights<br/>
├── output/YYYY-MM-DD/          ← Daily rendered videos (21-day retention)<br/>
└── temp/                       ← Scratch space (clips, overlays, audio)
</font>
""", BODY))

story.append(sp(6))

# ─── DEPENDENCY LIST ──────────────────────────────────────────────────────────
story.append(Paragraph("Python Dependencies", H1))
story.append(table(
    [["Package", "Version", "Used For"],
     ["edge-tts",     "latest", "Microsoft Edge TTS neural voiceover (Nigerian, British, Spanish voices)"],
     ["yt-dlp",       "latest", "Download audio from YouTube as MP3 (trending music)"],
     ["requests",     "latest", "Telegram Bot API, Pexels API, YouTube API, Instagram Graph API"],
     ["pytrends",     "latest", "Google Trends Nigeria keyword collection"],
     ["jinja2",       "latest", "HTML email template rendering (daily briefing + weekly report)"],
     ["reportlab",    "latest", "PDF documentation generation"],
     ["ffmpeg",       "system", "Video processing: scale, trim, concat, drawtext, overlay, amix"],
     ["opencv-python","latest", "Face detection for first-frame zoom (optional)"],
     ["TikTokApi",    "latest", "Unofficial TikTok trend scraper (optional, fallback safe)"]],
    [35*mm, 22*mm, None],
))

story.append(sp(6))

# ─── WINDOWS TASK SCHEDULER ───────────────────────────────────────────────────
story.append(Paragraph("Windows Task Scheduler Commands", H1))
for label, cmd in [
    ("Daily 5:45am — Morning Intelligence",
     r"schtasks /create /tn BootHopMorning /tr "
     r'"python C:\Users\babso\Desktop\BootHopPipeline\main.py" '
     r"/sc daily /st 05:45"),
    ("Daily 6:00am — Video Pipeline",
     r"schtasks /create /tn BootHopPipeline /tr "
     r'"python C:\Users\babso\Desktop\BootHopPipeline\pipeline.py" '
     r"/sc daily /st 06:00"),
    ("Monday 3:00am — Weekly Review",
     r"schtasks /create /tn BootHopWeekly /tr "
     r'"python C:\Users\babso\Desktop\BootHopPipeline\scripts\weekly_review.py" '
     r"/sc weekly /d MON /st 03:00"),
]:
    story.append(Paragraph(f"<b>{label}</b>", H2))
    story.append(Paragraph(cmd, MONO))
    story.append(sp(2))

story.append(PageBreak())

# ─── FULL DATA FLOW DIAGRAM (text) ────────────────────────────────────────────
story.append(Paragraph("End-to-End Data Flow Summary", H1))
story.append(Paragraph(
    "The diagram below shows how data moves through the system from collection to posting.",
    BODY))
story.append(sp())

flow = [
    ["Stage", "Input", "Output", "Destination"],
    ["5:45am\nMUSIC",
     "YouTube API\n(NG/GB/US charts)",
     "music/daily/track_1.mp3\ndata/music_log.json",
     "pipeline.py at 6am\nreads the MP3"],
    ["5:45am\nINTELLIGENCE",
     "Google Trends, YouTube,\nTikTok, Instagram",
     "data/trending_hooks_today.json\nGmail email + Telegram",
     "Operator awareness.\nOptionally: pipeline.py hook enrichment"],
    ["6:00am\nCONTENT",
     "data/hooks.txt\ndata/performance_weights.json\nmusic/archive/ + daily/",
     "V1 Library, V1 Trending,\nV2 Library, V2 Trending (MP4)\nVoiceover + text overlays",
     "Telegram (preview)\nSocial approval flow"],
    ["6:00am\nAPPROVAL",
     "Telegram inline keyboard\n(15min window)",
     "Chosen version(s)\nposted to TikTok + Instagram",
     "Public audience"],
    ["6:00am\nYOUTUBE",
     "Alternating V1/V2\n(odd/even day-of-year)",
     "One video uploaded to YouTube\n(sequential ID: BootHop-FD0001A)",
     "YouTube channel"],
    ["Mon 3am\nWEEKLY",
     "Instagram last 7 days\nmusic_log.json\ndaily_log.json",
     "data/performance_weights.json\ndata/weekly_insights.json\nGmail + Telegram report",
     "pipeline.py reads weights\nat 6am next day → auto-adjusts\nbucket + music profile"],
]
story.append(table(flow, [22*mm, 45*mm, 55*mm, None]))

story.append(sp(8))
story.append(hr())
story.append(Paragraph(
    "BootHop Content Pipeline — Auto-generated documentation — May 2026 — Confidential",
    NOTE))

# ─── BUILD ────────────────────────────────────────────────────────────────────
doc.build(story)
print(f"PDF saved to: {OUT}")
