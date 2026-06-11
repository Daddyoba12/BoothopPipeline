"""
generate_pipeline_pdf.py
Generates BootHop Pipeline v1 — System Documentation (PDF artifact).

Usage:
    python scripts/generate_pipeline_pdf.py

Output:
    BootHop_Pipeline_v1_Documentation.pdf  (project root)
"""

from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, KeepTogether
)
from reportlab.platypus.flowables import Flowable
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, cm
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.graphics.shapes import Drawing, Rect, String, Line
from reportlab.graphics import renderPDF
from datetime import datetime
from pathlib import Path
import sys

BASE = Path(r"C:\Users\babso\Desktop\BootHopPipeline")
OUT  = BASE / "BootHop_Pipeline_v1_Documentation.pdf"

# ── Colour palette ────────────────────────────────────────────────────────────
C_NAVY      = colors.HexColor("#07111f")
C_GREEN     = colors.HexColor("#10b981")
C_TEAL      = colors.HexColor("#0d9488")
C_AMBER     = colors.HexColor("#f59e0b")
C_SLATE     = colors.HexColor("#334155")
C_LIGHTGRAY = colors.HexColor("#f1f5f9")
C_MIDGRAY   = colors.HexColor("#94a3b8")
C_WHITE     = colors.white
C_RED       = colors.HexColor("#ef4444")
C_BLUE      = colors.HexColor("#3b82f6")
C_PURPLE    = colors.HexColor("#8b5cf6")

W, H = A4  # 595 x 842 pt

# ── Styles ────────────────────────────────────────────────────────────────────
SS = getSampleStyleSheet()

def style(name, **kw):
    s = SS[name].clone(name + "_" + "_".join(f"{k}{v}" for k,v in kw.items())[:20])
    for k, v in kw.items():
        setattr(s, k, v)
    return s

S_H1   = style("Heading1", fontSize=18, textColor=C_GREEN,  spaceBefore=18, spaceAfter=8,  fontName="Helvetica-Bold")
S_H2   = style("Heading2", fontSize=13, textColor=C_NAVY,   spaceBefore=12, spaceAfter=6,  fontName="Helvetica-Bold")
S_H3   = style("Heading3", fontSize=11, textColor=C_TEAL,   spaceBefore=8,  spaceAfter=4,  fontName="Helvetica-Bold")
S_BODY = style("Normal",   fontSize=9,  textColor=C_NAVY,   spaceAfter=4,   fontName="Helvetica", leading=14)
S_SMALL= style("Normal",   fontSize=8,  textColor=C_SLATE,  spaceAfter=3,   fontName="Helvetica", leading=12)
S_CODE = style("Code",     fontSize=7.5,textColor=C_NAVY,   spaceAfter=2,   fontName="Courier",   leading=11, backColor=C_LIGHTGRAY, leftIndent=8, rightIndent=8)
S_CAP  = style("Normal",   fontSize=8,  textColor=C_MIDGRAY,spaceAfter=6,   fontName="Helvetica-Oblique", alignment=TA_CENTER)
S_TOC  = style("Normal",   fontSize=10, textColor=C_NAVY,   spaceAfter=5,   fontName="Helvetica", leftIndent=12)

# ── Helper Flowables ──────────────────────────────────────────────────────────

class ColorBox(Flowable):
    def __init__(self, text, bg=C_NAVY, fg=C_WHITE, width=None, height=24):
        super().__init__()
        self.text    = text
        self.bg      = bg
        self.fg      = fg
        self.bwidth  = width or (W - 3.6*cm)
        self.bheight = height

    def wrap(self, aw, ah):
        return self.bwidth, self.bheight + 6

    def draw(self):
        c = self.canv
        c.setFillColor(self.bg)
        c.roundRect(0, 0, self.bwidth, self.bheight, 4, fill=1, stroke=0)
        c.setFillColor(self.fg)
        c.setFont("Helvetica-Bold", 11)
        c.drawCentredString(self.bwidth / 2, self.bheight / 2 - 4, self.text)


class FlowArrow(Flowable):
    def __init__(self, steps, width=None):
        super().__init__()
        self.steps = steps
        self.w     = width or (W - 3.6*cm)
        self.bh    = 38
        self.gap   = 14
        self.total = len(steps) * (self.bh + self.gap) - self.gap

    def wrap(self, aw, ah):
        return self.w, self.total + 10

    def draw(self):
        c  = self.canv
        bw = self.w * 0.84
        bx = (self.w - bw) / 2
        y  = self.total

        for i, (label, col, sub) in enumerate(self.steps):
            by = y - self.bh
            c.setFillColor(col)
            c.roundRect(bx, by, bw, self.bh, 5, fill=1, stroke=0)
            c.setFillColor(C_WHITE)
            c.setFont("Helvetica-Bold", 9)
            c.drawCentredString(self.w / 2, by + self.bh / 2 + 3, label)
            if sub:
                c.setFont("Helvetica", 7)
                c.setFillColor(colors.HexColor("#d1fae5"))
                c.drawCentredString(self.w / 2, by + self.bh / 2 - 10, sub)
            if i < len(self.steps) - 1:
                ax = self.w / 2
                c.setStrokeColor(C_MIDGRAY)
                c.setLineWidth(1.5)
                c.line(ax, by, ax, by - self.gap + 5)
                c.setFillColor(C_MIDGRAY)
                c.setStrokeColor(C_MIDGRAY)
                ap = c.beginPath()
                ap.moveTo(ax,     by - self.gap)
                ap.lineTo(ax - 4, by - self.gap + 7)
                ap.lineTo(ax + 4, by - self.gap + 7)
                ap.close()
                c.drawPath(ap, fill=1, stroke=0)
            y = by - self.gap


def hr(color=C_GREEN, thickness=1.5):
    return HRFlowable(width="100%", thickness=thickness, color=color, spaceAfter=6, spaceBefore=4)

def sp(h=6):
    return Spacer(1, h)

def p(text, s=S_BODY):
    return Paragraph(text, s)

def h1(text): return Paragraph(text, S_H1)
def h2(text): return Paragraph(text, S_H2)
def h3(text): return Paragraph(text, S_H3)


# ── Page callbacks ────────────────────────────────────────────────────────────

def on_page(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(C_NAVY)
    canvas.rect(0, H - 22, W, 22, fill=1, stroke=0)
    canvas.setFillColor(C_GREEN)
    canvas.setFont("Helvetica-Bold", 8)
    canvas.drawString(1.8*cm, H - 14, "BootHop Pipeline")
    canvas.setFillColor(C_MIDGRAY)
    canvas.setFont("Helvetica", 7)
    canvas.drawRightString(W - 1.8*cm, H - 14, "Version 1  |  Confidential")
    canvas.setFillColor(C_LIGHTGRAY)
    canvas.rect(0, 0, W, 18, fill=1, stroke=0)
    canvas.setFillColor(C_MIDGRAY)
    canvas.setFont("Helvetica", 7)
    canvas.drawString(1.8*cm, 5, f"Generated {datetime.now().strftime('%d %B %Y')}")
    canvas.drawCentredString(W/2, 5, "BootHop Pipeline — Internal Documentation")
    canvas.drawRightString(W - 1.8*cm, 5, f"Page {doc.page}")
    canvas.restoreState()


def on_first_page(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(C_NAVY)
    canvas.rect(0, 0, W, H, fill=1, stroke=0)
    canvas.setFillColor(C_GREEN)
    canvas.rect(0, H * 0.38, W, 5, fill=1, stroke=0)
    canvas.rect(0, H * 0.38 - 8, W, 2, fill=1, stroke=0)
    canvas.setFillColor(C_GREEN)
    canvas.setFont("Helvetica-Bold", 48)
    canvas.drawCentredString(W/2, H*0.71, "BootHop")
    canvas.setFillColor(C_WHITE)
    canvas.setFont("Helvetica", 16)
    canvas.drawCentredString(W/2, H*0.65, "Verified Operators. Same Day.")
    canvas.setFillColor(C_WHITE)
    canvas.setFont("Helvetica-Bold", 30)
    canvas.drawCentredString(W/2, H*0.49, "Pipeline Documentation")
    canvas.setFillColor(C_GREEN)
    canvas.setFont("Helvetica-Bold", 15)
    canvas.drawCentredString(W/2, H*0.43, "VERSION 1")
    canvas.setFillColor(C_MIDGRAY)
    canvas.setFont("Helvetica", 10)
    canvas.drawCentredString(W/2, H*0.34, f"Generated: {datetime.now().strftime('%d %B %Y')}")
    canvas.drawCentredString(W/2, H*0.31, "Classification: Internal — Confidential")
    canvas.setFillColor(C_GREEN)
    canvas.rect(0, 0, W, 8, fill=1, stroke=0)
    canvas.restoreState()


# ── Table helper ─────────────────────────────────────────────────────────────

def make_table(data, col_widths):
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0),  C_NAVY),
        ("TEXTCOLOR",     (0,0), (-1,0),  C_WHITE),
        ("FONTNAME",      (0,0), (-1,0),  "Helvetica-Bold"),
        ("FONTSIZE",      (0,0), (-1,0),  8),
        ("FONTNAME",      (0,1), (-1,-1), "Helvetica"),
        ("FONTSIZE",      (0,1), (-1,-1), 8),
        ("ALIGN",         (0,0), (-1,-1), "LEFT"),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("GRID",          (0,0), (-1,-1), 0.4, C_MIDGRAY),
        ("TOPPADDING",    (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("LEFTPADDING",   (0,0), (-1,-1), 6),
        ("RIGHTPADDING",  (0,0), (-1,-1), 6),
        ("ROWBACKGROUND", (0,1), (-1,-1), [C_WHITE, C_LIGHTGRAY]),
    ]))
    return t


# ── Main build ────────────────────────────────────────────────────────────────

def build():
    doc = SimpleDocTemplate(
        str(OUT), pagesize=A4,
        leftMargin=1.8*cm, rightMargin=1.8*cm,
        topMargin=1.6*cm,  bottomMargin=1.6*cm,
        title="BootHop Pipeline v1 Documentation",
        author="BootHop Engineering",
    )
    story = []

    # ── COVER (blank page — all drawing in on_first_page callback) ───────
    story.append(Spacer(1, 1))
    story.append(PageBreak())

    # ── TABLE OF CONTENTS ──────────────────────────────────────────────────
    story.append(h1("Table of Contents"))
    story.append(hr())
    story.append(sp(4))
    toc = [
        ("1.","System Overview & Architecture","3"),
        ("2.","Complete Code File Tree","4"),
        ("3.","All 19 Scheduled Tasks — Time, Day & Purpose","6"),
        ("4.","Main Pipeline Flow — Step by Step (pipeline.py)","8"),
        ("5.","Morning Intelligence — Trends & Briefing (main.py)","12"),
        ("6.","Music Generation System","13"),
        ("7.","LinkedIn Content Pipeline","14"),
        ("8.","Instagram Stories Pipeline","15"),
        ("9.","Blog System","16"),
        ("10.","Weekly Analysis & Feedback Loop","17"),
        ("11.","Platform Posting — TikTok, Instagram, YouTube, LinkedIn","18"),
        ("12.","Data Files Reference","21"),
        ("13.","Telegram Approval & Commander","22"),
        ("14.","4-Week Theme Cycle & Day-of-Week Buckets","23"),
        ("15.","Error Handling & Manual Recovery","24"),
    ]
    for num, title, pg in toc:
        row = Table([[
            p(f"<b>{num}</b>", S_BODY),
            p(title, S_TOC),
            p(pg, style("Normal", fontSize=10, textColor=C_MIDGRAY, alignment=TA_RIGHT)),
        ]], colWidths=[24, 380, 50])
        row.setStyle(TableStyle([
            ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
            ("TOPPADDING",(0,0),(-1,-1),3),
            ("BOTTOMPADDING",(0,0),(-1,-1),3),
            ("LINEBELOW",(0,0),(-1,-1),0.3,C_LIGHTGRAY),
        ]))
        story.append(row)
    story.append(PageBreak())

    # ── 1. SYSTEM OVERVIEW ─────────────────────────────────────────────────
    story.append(ColorBox("1 — System Overview & Architecture"))
    story.append(sp(8))
    story.append(p(
        "<b>BootHop Pipeline</b> is a fully autonomous social-media content generation and distribution "
        "system. Every day it wakes before 6 AM, collects Nigeria trending data, writes POV hooks, "
        "downloads video clips, renders two 30-second branded videos, sends them to Telegram for human "
        "approval, then posts approved content to <b>TikTok, Instagram Reels, YouTube Shorts, LinkedIn, "
        "Instagram Stories</b> and publishes daily blog posts — all without manual intervention. "
        "A weekly feedback loop measures engagement against competitors and automatically adjusts "
        "next week's content strategy.", S_BODY))
    story.append(sp(8))
    story.append(h2("Daily Architecture — End-to-End Flow"))
    story.append(FlowArrow([
        ("05:00  Music Generation",       C_PURPLE, "BootHop-MusicGen: download 3 tracks (2× Nigeria Afrobeats + 1× UK) via yt-dlp → 30s hook extract"),
        ("05:45  Morning Intelligence",   C_BLUE,   "BootHopMorning: Google Trends + YouTube NG → write trending_hooks_today.json + email briefing"),
        ("06:00  Main Video Pipeline",    C_GREEN,  "BootHop-TikTok: pick hooks → 8 Pexels clips × 2 versions → render V1 + V2 → Telegram approval"),
        ("06:30  Platform Posting",       C_TEAL,   "TikTok / Instagram Reels / YouTube Shorts / LinkedIn — after Telegram approval (90-min window)"),
        ("07:00  LinkedIn Pipeline",      C_AMBER,  "BootHop-LinkedIn: even days = 33s operator video; odd days = news image + B2B write-up"),
        ("07:00  Morning History Brief",  C_SLATE,  "BootHop-Morning: on-this-day history card → Telegram"),
        ("08:00  Blog Generation",        C_BLUE,   "BootHop-DailyBlog: daily topic → HTML post → blog/pending/"),
        ("13:00  Instagram Story (PM)",   C_GREEN,  "BootHop-Stories-Afternoon: 15s story card + music → Telegram + Instagram"),
        ("20:30  Instagram Story (Eve)",  C_TEAL,   "BootHop-Stories-Evening: engagement question card + music → Telegram + Instagram"),
        ("Mon 06:00  Weekly Analysis",    C_PURPLE, "BootHop-WeeklyAnalysis: 7-day vs competitors → recommendations → performance_weights.json"),
    ]))
    story.append(sp(6))
    story.append(p("<i>Every step is a separate Windows Task Scheduler job. All tasks have DisallowStartIfOnBatteries=false, StopIfGoingOnBatteries=false, and StartWhenAvailable=true for resilience.</i>", S_CAP))
    story.append(PageBreak())

    # ── 2. FILE TREE ───────────────────────────────────────────────────────
    story.append(ColorBox("2 — Complete Code File Tree"))
    story.append(sp(8))
    tree = [
        ["Path / File", "Type", "Purpose"],
        ["config.py",                             "Python",     "Central credentials, API keys, all shared paths (single source of truth)"],
        ["main.py",                               "Python",     "Morning Intelligence — Google Trends + YouTube + hook generation + briefing email"],
        ["pipeline.py",                           "Python",     "Main video pipeline (3,180 lines) — clips, render, voiceover, post, log"],
        ["face_detector_zoom.py",                 "Python",     "Ken Burns zoom effect when face detected in Pexels clip"],
        ["RegisterTasks.ps1",                     "PowerShell", "Registers all 19 Windows scheduled tasks (run once as admin)"],
        ["fix_battery_tasks.ps1",                 "PowerShell", "Removes battery + execution restrictions from all tasks"],
        ["REGISTER_ALL_TASKS.bat",                "Batch",      "Double-click to register all tasks as Administrator"],
        ["", "", ""],
        ["analysis/weekly_analysis.py",           "Python",     "Monday: 7-day engagement vs competitors → recommendations → Telegram buttons"],
        ["analysis/engagement.py",                "Python",     "Engagement rate calculation, daily_log.json entries"],
        ["analysis/hashtags.py",                  "Python",     "Hashtag performance + platform-specific tag recommendations"],
        ["analysis/hooks.py",                     "Python",     "Hook extraction and trend pattern analysis"],
        ["analysis/reports/",                     "Folder",     "Generated Markdown reports + CSV hook exports (weekly)"],
        ["", "", ""],
        ["assets/mainlogo.png",                   "Image",      "BootHop logo — story cards + video corner bug"],
        ["assets/fig1Start.png / fig2start.png",  "Image",      "Brand card overlays appearing at 20s in V1 / V2 videos"],
        ["assets/FIG4End.png",                    "Image",      "Full-screen end card at 27-30s"],
        ["assets/logo5A.png / logo5B.png",        "Image",      "LinkedIn mid-video (3s) and outro (5s) brand overlays"],
        ["assets/video-qr-transparent.png",       "Image",      "QR code for YouTube Shorts end card"],
        ["assets/fonts/Oswald-Bold.ttf",          "Font",       "Condensed bold — headlines and POV hook text"],
        ["assets/fonts/Montserrat-ExtraBold.ttf", "Font",       "Clean body text — sub-lines, CTAs, labels"],
        ["", "", ""],
        ["blog/generate_daily_blog.py",           "Python",     "Daily HTML post from 30+ topic pool (7-day dedup) → blog/pending/"],
        ["blog/gmail_to_blog.py",                 "Python",     "Gmail drafts tagged #boothop-blog → Blogger API publish"],
        ["blog/pdf_drop_to_blog.py",              "Python",     "PDFs in drop/ folder → HTML → Blogger publish → posted/pdfs/"],
        ["blog/post_to_blogger.py",               "Python",     "Core Blogger OAuth poster (called by above scripts)"],
        ["blog/publish_weekly_blog.py",           "Python",     "Monday: aggregates 7 daily posts into weekly meta-post"],
        ["blog/pending/",                         "Folder",     "Posts awaiting manual review before publish"],
        ["blog/posted/",                          "Folder",     "Successfully published posts + PDF archive"],
        ["", "", ""],
        ["briefing_module/briefing.py",           "Python",     "Builds HTML email + Telegram summary from collected trends"],
        ["briefing_module/templates/daily.html",  "Template",   "Jinja2 HTML email layout for morning briefing"],
        ["", "", ""],
        ["collectors/google_trends.py",           "Python",     "Nigeria Google Trends scraper (top 8 topics, no key needed)"],
        ["collectors/tiktok_scraper.py",          "Python",     "TikTok hashtag trending tracker"],
        ["collectors/youtube.py",                 "Python",     "YouTube trending videos (Nigeria region, API key)"],
        ["collectors/instagram.py",               "Python",     "Instagram Insights for own account (Graph API, cached 24h)"],
        ["", "", ""],
        ["data/post_log.json",                    "JSON",       "All posted content — platform, hook, music, media_id, timestamp"],
        ["data/daily_log.json",                   "JSON",       "Daily run history + engagement rates (60-day rolling window)"],
        ["data/music_log.json",                   "JSON",       "Played tracks — 7-day no-repeat enforcement"],
        ["data/used_content.json",                "JSON",       "Used hooks + engagement lines — 7-day deduplication window"],
        ["data/used_visuals.json",                "JSON",       "Used Pexels video IDs — 14-day deduplication window"],
        ["data/trending_hooks_today.json",        "JSON",       "Today's hooks written by main.py at 05:45, read by pipeline.py at 06:00"],
        ["data/performance_weights.json",         "JSON",       "Bucket override weights from weekly analysis (applied by user tap)"],
        ["data/weekly_insights.json",             "JSON",       "Monday analysis results + competitor comparison + recommendations"],
        ["data/pipeline_crash.log",               "Log",        "Appended crash log — START / DONE / SKIP / CRASH + traceback"],
        ["data/pipeline_step.txt",                "Text",       "Current running step — cleared on completion, detects mid-run kills"],
        ["data/cache/",                           "Folder",     "24h cached API responses (Google Trends, YouTube, TikTok, Instagram)"],
        ["", "", ""],
        ["music/generate_daily_music.py",         "Python",     "Daily artist rotation → SoundCloud download → 30s hook extract (librosa)"],
        ["music/daily/",                          "Folder",     "Today's tracks: track_1.mp3 (6am) + track_2.mp3 (12pm) + track_3.mp3 (6pm)"],
        ["music/archive/",                        "Folder",     "18 curated fallback MP3s used when download fails"],
        ["music/mute_ranges.json",                "JSON",       "Timestamps of profanity to mute in music tracks"],
        ["", "", ""],
        ["output/YYYY-MM-DD/",                    "Folder",     "Daily rendered videos + metadata JSON per platform"],
        ["", "", ""],
        ["scripts/post_tiktok.py",                "Python",     "TikTok Content Posting API v2 — chunked upload (64MB chunks)"],
        ["scripts/post_instagram.py",             "Python",     "Instagram Graph API Reels — catbox.moe host + poll until FINISHED"],
        ["scripts/post_linkedin.py",              "Python",     "LinkedIn UGC Posts API v2 — register upload → PUT → create post"],
        ["scripts/post_stories.py",               "Python",     "Instagram Stories 1pm + 8:30pm — 15s MP4 with music or JPEG fallback"],
        ["scripts/linkedin-daily.ps1",            "PowerShell", "Router — even days: video pipeline, odd days: news image pipeline"],
        ["scripts/linkedin-supply-chain.ps1",     "PowerShell", "33s B2B operator video — ffmpeg render + Telegram approval + LinkedIn post"],
        ["scripts/linkedin-news-image.ps1",       "PowerShell", "News image card + boothop_angle() regional B2B write-up"],
        ["scripts/boothop-history.ps1",           "PowerShell", "Morning on-this-day history card → Telegram"],
        ["scripts/telegram_commander.py",         "Python",     "Polls Telegram every 5 min — /rerun /status /story + inline buttons"],
        ["scripts/pipeline_status.py",            "Python",     "Manual status check — reports pipeline health to Telegram"],
        ["scripts/token_monitor.py",              "Python",     "Checks LinkedIn/TikTok/IG token expiry — Telegram alert if <7 days"],
        ["scripts/daily_briefing.py",             "Python",     "Standalone briefing sender (also called by main.py)"],
        ["scripts/fetch_trending_music.py",       "Python",     "Downloads 3 daily slots from YouTube/SoundCloud"],
    ]
    story.append(make_table(tree, [200, 62, 193]))
    story.append(PageBreak())

    # ── 3. SCHEDULE ────────────────────────────────────────────────────────
    story.append(ColorBox("3 — All 19 Scheduled Tasks — Time, Day & Purpose"))
    story.append(sp(8))
    story.append(p(
        "All tasks are registered in Windows Task Scheduler via <b>RegisterTasks.ps1</b>. "
        "Battery settings managed by <b>fix_battery_tasks.ps1</b>: "
        "DisallowStartIfOnBatteries=false, StopIfGoingOnBatteries=false, StartWhenAvailable=true.", S_BODY))
    story.append(sp(6))

    SCHED = [
        ("05:00",      "BootHop-MusicGen",           C_PURPLE, "Daily",   "Download 3 tracks (Nigeria Afrobeats + UK) via yt-dlp + librosa 30s hook extract"),
        ("05:45",      "BootHopMorning",              C_BLUE,   "Daily",   "main.py — Google Trends + YouTube NG → trending_hooks_today.json + email briefing"),
        ("06:00",      "BootHop-TikTok",              C_GREEN,  "Daily",   "pipeline.py — V1+V2 videos, Telegram approval, post TikTok/Instagram/YouTube/LinkedIn"),
        ("07:00",      "BootHop-Morning",             C_TEAL,   "Daily",   "boothop-history.ps1 — on-this-day history card → Telegram"),
        ("07:00",      "BootHop-LinkedIn",            C_AMBER,  "Daily",   "linkedin-daily.ps1 → even: 33s operator video  |  odd: news image + B2B write-up"),
        ("08:00",      "BootHop-DailyBlog",           C_BLUE,   "Daily",   "generate_daily_blog.py — daily HTML post from 30+ topic pool → blog/pending/"),
        ("09:00",      "BootHop-GmailBlog",           C_SLATE,  "Daily",   "gmail_to_blog.py — Gmail drafts tagged #boothop-blog → Blogger API"),
        ("09:30",      "BootHop-BlogDrop",            C_SLATE,  "Daily",   "pdf_drop_to_blog.py — PDFs in drop/ → HTML → Blogger publish"),
        ("12:30",      "BootHop-Afternoon",           C_GREEN,  "Daily",   "boothop-premium.ps1 — afternoon video run using track_2.mp3 (Afrobeats #2)"),
        ("13:00",      "BootHop-Stories-Afternoon",   C_TEAL,   "Daily",   "post_stories.py --slot afternoon — 15s story card + music → Telegram + Instagram"),
        ("17:00",      "BootHop-TokenMonitor",        C_MIDGRAY,"Daily",   "token_monitor.py — check LinkedIn/TikTok/IG token expiry → alert if <7 days"),
        ("18:00",      "BootHop-Evening",             C_AMBER,  "Daily",   "boothop-premium.ps1 — evening video run using track_3.mp3 (UK chart hit)"),
        ("20:30",      "BootHop-Stories-Evening",     C_TEAL,   "Daily",   "post_stories.py --slot evening — engagement question card → Telegram + Instagram"),
        ("Every 5min", "BootHop-Commander",           C_GREEN,  "Daily",   "telegram_commander.py — polls Telegram for /rerun /status and approval buttons"),
        ("06:00 Mon",  "BootHopWeekly",               C_PURPLE, "Monday",  "publish_weekly_blog.py — 7-day post aggregation → Blogger meta-post"),
        ("06:00 Mon",  "BootHop-WeeklyAnalysis",      C_PURPLE, "Monday",  "weekly_analysis.py — engagement vs competitors → recommendations → Telegram"),
        ("07:00 Mon",  "BootHop-Cleanup",             C_SLATE,  "Monday",  "cleanup-monday.ps1 — prune output/ >14 days, clear temp/, rotate logs"),
        ("09:00 Mon",  "BootHop-Blog",                C_BLUE,   "Monday",  "publish_weekly_blog.py — Monday collection post with all week's links"),
        ("On demand",  "BootHop-PipelineStatus",      C_MIDGRAY,"Manual",  "pipeline_status.py — manual health check → Telegram status report"),
    ]

    sched_rows = [["Time", "Task Name", "Days", "What It Does"]]
    for ts, task, col, days, desc in SCHED:
        sched_rows.append([
            Paragraph(f"<b>{ts}</b>", style("Normal", fontSize=7.5, textColor=C_WHITE, fontName="Helvetica-Bold", alignment=TA_CENTER)),
            Paragraph(f"<b>{task}</b>", style("Normal", fontSize=7.5, textColor=C_NAVY, fontName="Helvetica-Bold")),
            Paragraph(days, S_SMALL),
            Paragraph(desc, S_SMALL),
        ])

    st = Table(sched_rows, colWidths=[64, 150, 44, 197], repeatRows=1)
    style_cmds = [
        ("BACKGROUND",    (0,0),(-1,0),  C_NAVY),
        ("TEXTCOLOR",     (0,0),(-1,0),  C_WHITE),
        ("FONTNAME",      (0,0),(-1,0),  "Helvetica-Bold"),
        ("FONTSIZE",      (0,0),(-1,0),  8),
        ("ALIGN",         (0,0),(-1,-1), "LEFT"),
        ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
        ("GRID",          (0,0),(-1,-1), 0.4, C_MIDGRAY),
        ("TOPPADDING",    (0,0),(-1,-1), 4),
        ("BOTTOMPADDING", (0,0),(-1,-1), 4),
        ("LEFTPADDING",   (0,0),(-1,-1), 5),
        ("RIGHTPADDING",  (0,0),(-1,-1), 5),
    ]
    for i, (_, _, col, _, _) in enumerate(SCHED):
        style_cmds.append(("BACKGROUND", (0, i+1), (0, i+1), col))
        style_cmds.append(("ROWBACKGROUND", (0, i+1), (-1, i+1), C_WHITE if i%2==0 else C_LIGHTGRAY))
    st.setStyle(TableStyle(style_cmds))
    story.append(st)
    story.append(sp(8))

    legend = Table([[
        p("<font color='#8b5cf6'>■</font> Purple = Weekly/Monday", S_SMALL),
        p("<font color='#10b981'>■</font> Green = Core video pipeline", S_SMALL),
        p("<font color='#f59e0b'>■</font> Amber = Secondary runs", S_SMALL),
        p("<font color='#3b82f6'>■</font> Blue = Blog/briefing", S_SMALL),
        p("<font color='#0d9488'>■</font> Teal = Stories/history", S_SMALL),
    ]], colWidths=[100]*5)
    legend.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"MIDDLE"),("TOPPADDING",(0,0),(-1,-1),2)]))
    story.append(legend)
    story.append(PageBreak())

    # ── 4. PIPELINE FLOW ───────────────────────────────────────────────────
    story.append(ColorBox("4 — Main Pipeline Flow (pipeline.py)"))
    story.append(sp(8))
    story.append(p(
        "The main pipeline runs at <b>06:00 daily</b> via <i>BootHop-TikTok</i>. "
        "It is 3,180 lines of Python and handles the complete lifecycle from content selection "
        "to multi-platform posting.", S_BODY))
    story.append(sp(6))

    story.append(h2("Step 1 — Guard & Initialisation"))
    story.append(p("<b>Skip Guard:</b> Flag <code>--skip-if-ran-today</code> checks if ≥2 MP4s exist in <code>output/YYYY-MM-DD/</code>. If yes, exits silently to prevent double-runs from Task Scheduler StartWhenAvailable catchup.", S_BODY))
    story.append(sp(4))
    story.append(make_table([
        ["Init Step", "Detail", "Output"],
        ["Bucket selection",  "Day-of-week → bucket (Mon=business, Tue=family, Wed=airport, Thu=smart, Fri=cinematic, Sat/Sun=community). Weekly analysis can override via performance_weights.json.", "bucket string"],
        ["Music load",        "Loads track_1.mp3 (V1) + track_2.mp3 (V2) from music/daily/. Falls back to archive/ pool if missing.", "music_v1, music_v2"],
        ["Theme selection",   "(ISO_week - 1) % 4 → theme index (0=Problem Awareness, 1=Solution, 2=Trust, 3=Vision). Affects hook pool, captions, CTA.", "theme_idx, theme_name"],
        ["Asset check",       "Verifies fig1Start.png, fig2start.png, FIG4End.png, mainlogo.png exist. Creates output/YYYY-MM-DD/ folder.", "assets confirmed"],
    ], [100, 295, 60]))
    story.append(sp(8))

    story.append(h2("Step 2 — Content Selection (× 2 versions)"))
    story.append(p("Runs twice. V2 excludes V1's hook and Pexels query set to ensure variety.", S_BODY))
    story.append(make_table([
        ["Sub-step", "Detail"],
        ["Hook pool",         "Reads data/trending_hooks_today.json (written by main.py). 6+ POV hooks from Nigeria Google Trends + music trends."],
        ["7-day dedup",       "Reads data/used_content.json. Removes hooks used in last 7 days. Picks first fresh hook matching today's bucket."],
        ["Engagement line",   "Engagement question from bucket pool. Also deduped on 7-day window. Appended below main video."],
        ["Caption build",     "hook + engagement + 8 hashtags (from analysis/hashtags.py) + boothop.com CTA. Max 2,200 chars."],
        ["Clip queries",      "8 phased Pexels queries from hook keywords + bucket. Phase 1=setup(0-8s), 2=journey(8-22s), 3=solution(22-27s), 4=brand(27-30s)."],
    ], [120, 335]))
    story.append(sp(8))

    story.append(h2("Step 3 — Clip Download (Pexels API)"))
    story.append(make_table([
        ["Item", "Detail"],
        ["API",           "Pexels API v1 — /v1/videos/search"],
        ["Clips per video","8 clips across 4 phases (2 per phase)"],
        ["Resolution",    "HD minimum (1280×720), portrait orientation (1080×1920) preferred"],
        ["14-day dedup",  "data/used_visuals.json — never repeat same Pexels video ID within 2 weeks"],
        ["Fallback",      "If primary query returns no unused clips, expands to secondary query pool"],
        ["Saved to",      "clips/ as clip_01.mp4 through clip_08.mp4"],
    ], [120, 335]))
    story.append(sp(8))

    story.append(h2("Step 4 — Voiceover (Microsoft Edge TTS)"))
    story.append(make_table([
        ["Part", "Script Content", "Duration", "Voice"],
        ["1 — Setup",    "POV hook context — sets the scene",                 "~2s", "en-US-GuyNeural"],
        ["2 — Problem",  "Pain point from hook (missed delivery, delay)",      "~4s", "en-US-GuyNeural"],
        ["3 — Movement", "Observation — traveller already going that route",   "~4s", "en-US-GuyNeural"],
        ["4 — Solution", "BootHop pitch — match, verify, same day delivery",  "~6s", "en-US-GuyNeural"],
        ["5 — Brand",    "BootHop URL + CTA",                                 "~4s", "en-US-GuyNeural"],
        ["Nigerian hook","Pidgin hooks use female Nigerian voice instead",     "varies","en-NG-EzinneNeural"],
    ], [75, 215, 65, 100]))
    story.append(sp(8))

    story.append(h2("Step 5 — Video Render (ffmpeg)"))
    story.append(p("Each version produces <b>up to 3 output files</b> from the same base clip sequence:", S_BODY))
    story.append(make_table([
        ["Output File", "Audio Track", "When"],
        ["v1_library_v1.mp4",  "Curated archive MP3 (always available)",        "Primary fallback — always produced"],
        ["v1_trending_v1.mp4", "Daily SoundCloud track (track_1.mp3)",           "Primary post — when download succeeded"],
        ["v1_english_v1.mp4",  "English translation voiceover",                  "Only if hook is non-English (Pidgin/Yoruba)"],
        ["v2_library_v2.mp4",  "Different archive MP3",                          "V2 fallback"],
        ["v2_trending_v2.mp4", "track_2.mp3 (Afrobeats #2)",                     "V2 primary post"],
    ], [155, 205, 95]))
    story.append(sp(6))

    story.append(h3("Text Overlays (ffmpeg drawtext — all Unicode stripped to ASCII)"))
    story.append(make_table([
        ["Timecode", "Overlay Element", "Style"],
        ["0 – 8s",   "POV hook (label / line1 / line2 / line3)",          "Yellow, Oswald-Bold 48px, top area with shadow"],
        ["8 – 22s",  "Engagement line",                                   "White, Montserrat 36px, semi-transparent box, bottom third"],
        ["20 – 22s", "Brand card (fig1Start.png or fig2start.png)",       "Full-width overlay image, top center"],
        ["27 – 30s", "FIG4End.png end card",                              "Full-screen end card, bottom"],
        ["0 – 30s",  "BootHop logo corner bug",                           "40×40px, top-right, 70% opacity"],
        ["0 – 30s",  "Progress bar",                                      "Thin green strip growing 0→100% at bottom edge"],
    ], [65, 235, 155]))
    story.append(sp(8))

    story.append(h2("Step 6 — Telegram Dispatch & 90-Minute Approval"))
    story.append(make_table([
        ["Action", "Detail"],
        ["Send previews",    "All rendered MP4s sent to TELEGRAM_CHAT_ID with caption (hook + bucket + timestamp)"],
        ["Approval keyboard","Inline buttons per platform: [V1] [V2] [Skip] for TikTok, Instagram, YouTube, LinkedIn. Plus [All V1] [All V2] [Ignore All]."],
        ["90-min window",    "wait_for_approval(timeout_seconds=5400). Polls getUpdates every 20-30 seconds."],
        ["Callback data",    "tt_v1, tt_v2, tt_skip, ig_v1, ig_v2, ig_skip, yt_v1, yt_v2, yt_skip, li_v1, li_v2, li_skip, all_v1, all_v2, ignore_all"],
        ["Auto-post rule",   "If no button tapped after 90 minutes → automatically posts V1 to all platforms"],
    ], [110, 345]))
    story.append(sp(8))

    story.append(h2("Step 7 — Platform Posting"))
    story.append(make_table([
        ["Platform",   "Script",                      "API Used"],
        ["TikTok",     "scripts/post_tiktok.py",      "Content Posting API v2 — chunked file upload (64MB chunks)"],
        ["Instagram",  "scripts/post_instagram.py",   "Graph API v21 — catbox.moe host → media container → publish Reel"],
        ["YouTube",    "upload_to_youtube.py",         "YouTube Data API v3 — OAuth2 → videos.insert → auto-Shorts"],
        ["LinkedIn",   "scripts/post_linkedin.py",    "UGC Posts API v2 — registerUpload → PUT video → create post"],
    ], [70, 155, 230]))
    story.append(sp(8))

    story.append(h2("Step 8 — Logging"))
    story.append(make_table([
        ["Log File", "What Is Written"],
        ["data/post_log.json",                "posted_at, platform, hook, bucket, music_track, media_id"],
        ["data/used_content.json",            "Appends hook + engagement used today"],
        ["data/used_visuals.json",            "Appends all Pexels video IDs used today"],
        ["data/music_log.json",               "Appends track used (artist, title, slot, region, timestamp)"],
        ["data/pipeline_crash.log",           "DONE — exit 0  (or CRASH + full traceback on exception)"],
        ["output/YYYY-MM-DD/metadata_*.json", "Full metadata: hook, bucket, music, platform, media_id, timestamp"],
    ], [185, 270]))
    story.append(PageBreak())

    # ── 5. MORNING INTELLIGENCE ────────────────────────────────────────────
    story.append(ColorBox("5 — Morning Intelligence (main.py)"))
    story.append(sp(8))
    story.append(p("<b>Task:</b> BootHopMorning at <b>05:45 daily</b>. Must complete before pipeline.py at 06:00.", S_BODY))
    story.append(sp(4))
    story.append(make_table([
        ["Step", "Data Source", "Output"],
        ["1. Fetch Nigeria Trends",  "Google Trends API (public, no auth required)",        "Top 8 trending topics in Nigeria"],
        ["2. Fetch YouTube Trending","YouTube Data API v3 (YOUTUBE_API_KEY)",                "Top 10 trending videos (NG region)"],
        ["3. Fetch TikTok Hashtags", "TikTok scraper (no official API)",                     "Trending hashtag names + approximate counts"],
        ["4. Fetch IG Insights",     "Instagram Graph API (IG_ACCESS_TOKEN, cached 24h)",   "Own account likes, comments, reach"],
        ["5. Generate hooks",        "POV templates + trend keywords",                       "6 hooks written to trending_hooks_today.json"],
        ["6. Generate blog idea",    "Trend + 30-topic pool (7-day dedup)",                  "Headline + sections + CTA → blog/pending/"],
        ["7. Send email brief",      "Gmail SMTP (daddyoba12@gmail.com)",                    "HTML email: trends, hooks, music, blog angle"],
        ["8. Send Telegram brief",   "TELEGRAM_TOKEN + TELEGRAM_CHAT_ID",                   "Summary message with all daily metrics"],
    ], [130, 160, 165]))
    story.append(sp(6))
    story.append(h3("trending_hooks_today.json — read by pipeline.py 15 minutes later"))
    story.append(p(
        'Structure: <code>{"trends": ["topic1", ...], "hooks": [{"hook": "POV: ...", "source": "google_trend"}, ...], '
        '"hashtags": {"family": "#BootHop ...", "business": "..."}}</code>', S_CODE))
    story.append(PageBreak())

    # ── 6. MUSIC ───────────────────────────────────────────────────────────
    story.append(ColorBox("6 — Music Generation System"))
    story.append(sp(8))
    story.append(p("<b>Task:</b> BootHop-MusicGen at <b>05:00 daily</b>. Downloads before pipeline needs the tracks.", S_BODY))
    story.append(sp(4))
    story.append(make_table([
        ["Slot", "Used At", "Artist Pool (20 each)", "Download Source"],
        ["Slot 1 — track_1.mp3", "06:00 pipeline V1",     "Nigeria: Burna Boy, Asake, Wizkid, Davido, Rema, CKay, Tems, Omah Lay, Fireboy DML, Olamide + 10 more", "SoundCloud via yt-dlp"],
        ["Slot 2 — track_2.mp3", "12:30 + LinkedIn",       "Nigeria: offset +7 from Slot 1 artist index (different artist each day)",                                "SoundCloud via yt-dlp"],
        ["Slot 3 — track_3.mp3", "18:00 evening run",      "UK: Central Cee, Stormzy, Dave, Headie One, Little Simz, Jorja Smith, AJ Tracey + 13 more",              "SoundCloud via yt-dlp"],
        ["Fallback",             "Any slot if fail",        "music/archive/ — 18 curated MP3s",                                                                        "Pre-downloaded (no network)"],
    ], [108, 78, 195, 74]))
    story.append(sp(6))
    story.append(h3("30-Second Hook Extraction (librosa)"))
    story.append(p("Full audio loaded → RMS energy calculated per frame → energy curve smoothed → peak found (chorus/drop) → 30s window extracted around peak → 500ms fade-in + 1200ms fade-out → saved as track_N.mp3.", S_BODY))
    story.append(h3("7-Day No-Repeat"))
    story.append(p("data/music_log.json tracks every track (artist, title, slot, timestamp). Before use, checks if same title was played in last 7 days. If yes, archive pool used instead (index = day×3+slot % archive_count).", S_BODY))
    story.append(PageBreak())

    # ── 7. LINKEDIN ────────────────────────────────────────────────────────
    story.append(ColorBox("7 — LinkedIn Content Pipeline"))
    story.append(sp(8))
    story.append(p("<b>Task:</b> BootHop-LinkedIn at <b>07:00 daily</b>. Alternates by day of year.", S_BODY))
    story.append(sp(4))
    story.append(make_table([
        ["Day Type", "Script", "Output"],
        ["Even days (day % 2 == 0)", "linkedin-supply-chain.ps1", "33-second operator video (MP4) posted to LinkedIn + YouTube"],
        ["Odd days  (day % 2 == 1)", "linkedin-news-image.ps1",   "Pexels supply chain image + B2B write-up posted to LinkedIn"],
    ], [130, 165, 160]))
    story.append(sp(8))

    story.append(h2("Video Path — linkedin-supply-chain.ps1 (33 seconds, 12 steps)"))
    story.append(make_table([
        ["Step", "What Happens"],
        ["1. Content gen",     "Python script: theme rotation (weekly) → fact pool → voice script (~120 words) → LinkedIn write-up → hook lines → engagement CTA"],
        ["2. Voiceover",       "Edge TTS en-US-GuyNeural → voice.mp3"],
        ["3. Download clips",  "Pexels API — 60-query rotating pool (warehouse, logistics, operators, B2B delivery). 5 clips selected."],
        ["4. Format clips",    "ffmpeg: each clip → 5 seconds, 1080×1920, 30fps → clip01-05.mp4"],
        ["5. Assemble",        "clip01(5s) + clip02(5s) + logo5A(3s) + clip03(5s) + clip04(5s) + clip05(5s) + logo5B(5s) = 33 seconds total"],
        ["6. Audio mix",       "voice.mp3 (100%) + track_2.mp3 (15%) + profanity mutes from mute_ranges.json → audio.aac"],
        ["7. Text overlays",   "0-4s: HOOK (3 lines, white, large). 0-10s: subtitle. 10-13s: brand moment. 13-28s: key message. 28-33s: ENGAGEMENT + URL + QR"],
        ["8. Thumbnail",       "ffmpeg: frame at 1s → telegram_thumb.jpg"],
        ["9. Telegram send",   "Video preview + thumbnail + full write-up + [Post to LinkedIn] [Skip] buttons"],
        ["10. Approval",       "30-minute window. Auto-posts if no response."],
        ["11. LinkedIn post",  "scripts/post_linkedin.py — registerUpload → PUT → UGC post"],
        ["12. YouTube upload", "upload_to_youtube.py — same video as YouTube Short (if token valid)"],
    ], [90, 365]))
    story.append(sp(6))
    story.append(h3("B2B Operator Messaging (June 2026)"))
    story.append(p("All content focuses on: <b>verified operators already running your route → businesses choose from multiple options → time-critical parcels get the best match</b>. boothop_angle() generates regional copy for 7 headline types: Nigeria, Dubai/Gulf, Diaspora, Africa, Europe/UK, Cost, and Urgent/Critical.", S_BODY))
    story.append(PageBreak())

    # ── 8. STORIES ─────────────────────────────────────────────────────────
    story.append(ColorBox("8 — Instagram Stories Pipeline (post_stories.py)"))
    story.append(sp(8))
    story.append(make_table([
        ["Slot", "Task", "Time", "Content"],
        ["Afternoon", "BootHop-Stories-Afternoon", "13:00 daily", "Stat / fact card (operator-focused, business-facing)"],
        ["Evening",   "BootHop-Stories-Evening",   "20:30 daily", "Engagement question (community, comment-driving)"],
    ], [60, 160, 75, 160]))
    story.append(sp(8))

    story.append(h2("4-Week Story Content Rotation (ISO week % 4)"))
    story.append(make_table([
        ["Week", "Theme", "Afternoon Stat Example", "Evening Question Example"],
        ["1", "Problem Awareness",  "Urgent parcels miss their window every single day.",   "Has an urgent delivery ever failed your business?"],
        ["2", "Solution & Product", "BootHop matches your parcel to a carrier in minutes.", "Would you trust a verified operator to carry your parcel?"],
        ["3", "Trust & Credibility","Every BootHop carrier is identity-verified.",          "What makes you trust a delivery service with something urgent?"],
        ["4", "Vision & CTA",       "London to Lagos. Same day. Verified operator.",        "Ready to ship? Verified operators are live on BootHop."],
    ], [25, 100, 195, 135]))
    story.append(sp(8))

    story.append(h2("Card Build & Output"))
    story.append(make_table([
        ["Step", "Detail"],
        ["1. Layout",      "1080×1920. BootHop name (y=140, green 72px) → tagline 'Verified Operators. Same Day.' (y=240) → headline (y=580, 52px white) → 2 sub-lines (y=800/855) → CTA (y=1650, green) → date label (y=1830)"],
        ["2. Music lookup","_find_music_file() — checks music/daily/ then music/archive/ for MP3/M4A/WAV"],
        ["3. ffmpeg render","If music: MP4 15s (libx264 25fps) + music (afade in 1s, out at 13s, atrim 15s). No music: JPEG fallback."],
        ["4. Telegram",    "MP4 → sendVideo API. JPEG → sendPhoto. Caption includes theme + headline text."],
        ["5. Instagram",   "Graph API POST /{ig_user_id}/media (media_type=STORY). Requires public URL for video."],
    ], [80, 375]))
    story.append(PageBreak())

    # ── 9. BLOG ────────────────────────────────────────────────────────────
    story.append(ColorBox("9 — Blog System"))
    story.append(sp(8))
    story.append(make_table([
        ["Script", "Time", "What It Does"],
        ["generate_daily_blog.py", "08:00 daily",  "Picks topic from 30+ pool (7-day dedup) → full HTML post → blog/pending/"],
        ["gmail_to_blog.py",       "09:00 daily",  "Scans Gmail drafts for #boothop-blog tag → Blogger API publish → blog_log.txt"],
        ["pdf_drop_to_blog.py",    "09:30 daily",  "Watches blog/drop/ → PDF→HTML → Blogger publish → blog/posted/pdfs/"],
        ["post_to_blogger.py",     "On call",       "Core Blogger OAuth poster (used by above scripts)"],
        ["publish_weekly_blog.py", "06:00 Mon",    "Aggregates all 7 daily posts → weekly meta-post → Blogger"],
    ], [145, 78, 232]))
    story.append(sp(6))
    story.append(h3("Blog Topic Categories (30+ topics, 7-day dedup via blog_gen_used.json)"))
    story.append(p(
        "<b>UK-Nigeria Corridor:</b> London-Lagos cost savings, diaspora suitcase problem, earn on your flight. "
        "<b>Business & B2B:</b> supply chain innovation, same-day critical delivery, SME logistics cost. "
        "<b>Culture & Lifestyle:</b> family reunion stories, diaspora community, event-driven logistics.", S_BODY))
    story.append(PageBreak())

    # ── 10. WEEKLY ANALYSIS ────────────────────────────────────────────────
    story.append(ColorBox("10 — Weekly Analysis & Feedback Loop"))
    story.append(sp(8))
    story.append(p("<b>Task:</b> BootHop-WeeklyAnalysis at <b>Monday 06:00</b>. 90-minute execution limit.", S_BODY))
    story.append(sp(4))
    story.append(make_table([
        ["Phase", "Detail"],
        ["1. Collect own data",  "Reads data/post_log.json (last 7 days). engagement_rate = (likes+comments)/followers×100"],
        ["2. Competitor scan",   "Checks hashtags: #uknigeriadelivery #diasporadelivery #naijauk #uktolagos #lagosdelivery #sendbox"],
        ["3. Gap analysis",      "Identifies which buckets outperform competitors. Flags under-explored content angles."],
        ["4. Recommendations",   "2-4 action items (e.g. 'increase family bucket +34%', 'shift to Vision & CTA theme')"],
        ["5. Telegram report",   "Full Markdown summary + [Apply Recommendations] [Ignore] inline buttons"],
        ["6. Apply (if tapped)", "Updates data/performance_weights.json. get_adjusted_bucket() reads weights to override day defaults."],
        ["7. Exports",           "analysis/reports/YYYY-WW_summary.md + analysis/reports/YYYY-WW_hooks.csv"],
    ], [130, 325]))
    story.append(PageBreak())

    # ── 11. PLATFORM POSTING ───────────────────────────────────────────────
    story.append(ColorBox("11 — Platform Posting — All Channels"))
    story.append(sp(8))

    for title, col, rows in [
        ("TikTok — post_tiktok.py", C_PURPLE, [
            ["Item", "Detail"],
            ["API",      "TikTok Content Posting API v2"],
            ["Auth",     "OAuth 2.0 access_token from social_credentials.json ['tiktok']['access_token']"],
            ["Upload",   "POST /v2/post/publish/video/init/ → upload URL. PUT 64MB chunks. Auto-publishes on complete."],
            ["Returns",  "publish_id (logged as media_id in post_log.json)"],
            ["Status",   "Sandbox mode pending Content Posting API approval from TikTok."],
            ["Caption",  "150 chars max (pipeline truncates at 148 + '…')"],
        ]),
        ("Instagram — post_instagram.py", C_GREEN, [
            ["Item", "Detail"],
            ["API",     "Meta Instagram Graph API v21.0"],
            ["Auth",    "IG_ACCESS_TOKEN + IG_USER_ID from social_credentials.json"],
            ["Step 1",  "Upload to catbox.moe (POST /user/api.php) → returns public https:// URL"],
            ["Step 2",  "Create container: POST /v21.0/{ig_user_id}/media (media_type=REELS, video_url, caption)"],
            ["Step 3",  "Poll: GET /v21.0/{media_id} until status=FINISHED (max 5 min, 10s intervals)"],
            ["Step 4",  "Publish: POST /v21.0/{media_id}/publish → returns published media_id"],
            ["Caption", "Max 2,200 chars. Hook + engagement + hashtags + boothop.com"],
        ]),
        ("YouTube — upload_to_youtube.py", C_RED, [
            ["Item", "Detail"],
            ["API",      "Google YouTube Data API v3 — videos.insert"],
            ["Auth",     "OAuth 2.0 stored in scripts/youtube_token.json. Auto-refreshes. One-time setup via setup_youtube.py."],
            ["Upload",   "Resumable (5MB chunks). Progress logged to console."],
            ["Metadata", "Title max 100 chars. Category 22 (People & Blogs). Privacy: public. 15 keyword tags."],
            ["Shorts",   "Videos ≤60s in portrait (1080×1920) automatically qualify as YouTube Shorts."],
            ["Dual post","Non-English hooks: uploads primary (local language) + English translation version."],
        ]),
        ("LinkedIn — post_linkedin.py", C_BLUE, [
            ["Item", "Detail"],
            ["API",          "LinkedIn UGC Posts API v2"],
            ["Auth",         "OAuth 2.0. access_token + person_urn + refresh_token (60-day expiry) in social_credentials.json."],
            ["Token refresh","Auto-refresh if (expiry - now) < 7 days via POST /oauth/v2/accessToken with refresh_token."],
            ["Step 1",       "Register upload: POST /v2/assets?action=registerUpload → returns uploadUrl + signedHeaders"],
            ["Step 2",       "Upload: PUT to uploadUrl with signed headers + video binary"],
            ["Step 3",       "Create post: POST /v2/ugcPosts with author (person URN), commentary, video asset reference"],
            ["Caption",      "Full B2B write-up (~300 words). Operator marketplace messaging."],
        ]),
        ("Telegram — Notification & Approval", C_TEAL, [
            ["Usage", "Detail"],
            ["Video previews",   "All rendered MP4s sent via sendVideo before any platform posting"],
            ["Approval buttons", "Inline keyboards: per-platform V1/V2/Skip + batch All-V1/All-V2/Ignore-All"],
            ["Commander",        "telegram_commander.py polls every 5 min for /rerun /status /story commands"],
            ["Daily briefing",   "Morning summary: 6 trends + 3 hooks + music + engagement rate + blog angle"],
            ["Status alerts",    "Token expiry warnings, crash alerts, post confirmations"],
            ["Credentials",      "TELEGRAM_TOKEN + TELEGRAM_CHAT_ID from config.py"],
        ]),
    ]:
        story.append(ColorBox(title, col, height=20))
        story.append(sp(4))
        story.append(make_table(rows, [90, 365]))
        story.append(sp(10))

    story.append(PageBreak())

    # ── 12. DATA FILES ─────────────────────────────────────────────────────
    story.append(ColorBox("12 — Data Files Reference"))
    story.append(sp(8))
    story.append(make_table([
        ["File", "Purpose", "Updated By", "Retention"],
        ["post_log.json",             "All posted content history",                "pipeline.py after each post",     "All time"],
        ["daily_log.json",            "Daily run history + engagement rates",       "engagement.py",                   "60 days"],
        ["music_log.json",            "Played tracks (7-day no-repeat)",            "pipeline.py after music use",     "90 days"],
        ["used_content.json",         "Used hooks + engagement lines",              "pipeline.py pick_content()",      "7 days"],
        ["used_visuals.json",         "Used Pexels video IDs",                      "pipeline.py download_clips()",    "14 days"],
        ["trending_hooks_today.json", "Today's hooks from Nigeria trends",          "main.py at 05:45 (overwritten)",  "Daily"],
        ["performance_weights.json",  "Bucket override weights",                    "weekly_analysis.py (if applied)", "Until next analysis"],
        ["weekly_insights.json",      "Monday analysis + recommendations",          "weekly_analysis.py",              "1 week"],
        ["youtube_sequence.json",     "YouTube upload tracking",                    "upload_to_youtube.py",            "All time"],
        ["pipeline_crash.log",        "Step + exception log (appended)",            "pipeline.py always",              "All time"],
        ["pipeline_step.txt",         "Current step — cleared on completion",       "pipeline.py _set_step()",         "Cleared after run"],
        ["tg_commander_offset.json",  "Last processed Telegram update_id",          "telegram_commander.py",           "Always current"],
        ["cache/google_trends.json",  "Cached Google Trends response",              "collectors/google_trends.py",     "24 hours"],
        ["cache/youtube.json",        "Cached YouTube trending (NG)",               "collectors/youtube.py",           "24 hours"],
        ["cache/tiktok.json",         "Cached TikTok hashtag data",                 "collectors/tiktok_scraper.py",    "24 hours"],
        ["cache/instagram.json",      "Cached IG insights (own account)",           "collectors/instagram.py",         "24 hours"],
    ], [145, 145, 120, 45]))
    story.append(PageBreak())

    # ── 13. TELEGRAM ───────────────────────────────────────────────────────
    story.append(ColorBox("13 — Telegram Approval & Commander System"))
    story.append(sp(8))
    story.append(p("Telegram is the primary human-computer interface — handles both notification (outbound) and control (inbound).", S_BODY))
    story.append(sp(4))
    story.append(make_table([
        ["Command / Button", "Type", "Action"],
        ["/menu",               "Text",    "Posts control panel with inline keyboard (Re-run / Status / Story PM / Story Eve)"],
        ["/rerun",              "Text",    "Clears today's output MP4s + starts python pipeline.py (no skip flag)"],
        ["/status",             "Text",    "Reports video count today, last log entry, current step"],
        ["/story pm",           "Text",    "Runs post_stories.py --slot afternoon immediately"],
        ["/story eve",          "Text",    "Runs post_stories.py --slot evening immediately"],
        ["🔄 Re-run Pipeline",  "Button",  "Same as /rerun — clears old videos, starts fresh pipeline"],
        ["📊 Status",           "Button",  "Same as /status"],
        ["📱 Story (1pm)",      "Button",  "Same as /story pm"],
        ["📱 Story (8:30pm)",   "Button",  "Same as /story eve"],
        ["[V1] [V2] [Skip]",    "Approval","Sets platform choice in pipeline.py wait_for_approval() poll loop"],
        ["[All V1] [All V2]",   "Approval","Sets all 4 platforms to V1 or V2 at once"],
        ["[Ignore All]",        "Approval","Skips all platforms — no posts today"],
        ["[Post to LinkedIn]",  "LinkedIn","Triggers post_linkedin.py for the 33s operator video"],
    ], [130, 70, 255]))
    story.append(sp(6))
    story.append(p("<b>Polling cycle:</b> telegram_commander.py runs every 5 minutes via BootHop-Commander task. Reads last processed update_id from data/tg_commander_offset.json to avoid re-processing.", S_BODY))
    story.append(PageBreak())

    # ── 14. THEME CYCLE ────────────────────────────────────────────────────
    story.append(ColorBox("14 — 4-Week Theme Cycle & Day-of-Week Buckets"))
    story.append(sp(8))
    story.append(p("All components (videos, stories, LinkedIn, captions) share the same theme rotation: <code>(ISO_week - 1) % 4</code>.", S_BODY))
    story.append(sp(4))
    story.append(make_table([
        ["Week", "Theme", "Hook Focus", "Caption Tone", "CTA"],
        ["1", "Problem\nAwareness",   "Broken couriers, missed windows, 2-3 day delays, urgent fail",          "Pain-point led. Empathetic. Problem-first.",    "There's a smarter way. boothop.com"],
        ["2", "Solution &\nProduct",  "How BootHop works, verified operators, route-matching, minutes not days","Solution-led. Clear mechanism. Benefit-first.", "Book your first delivery at boothop.com"],
        ["3", "Trust &\nCredibility", "Identity-verified carriers, Stripe escrow, community trust",             "Trust-led. Evidence-based. Social proof.",      "Trusted operators. Real people. boothop.com"],
        ["4", "Vision &\nCTA",        "London-Lagos, global movement, join the platform",                       "Vision-led. Bold. Invitation-to-join.",          "Join BootHop — boothop.com"],
    ], [25, 75, 155, 120, 80]))
    story.append(sp(10))

    story.append(h2("Day-of-Week Bucket Rotation"))
    story.append(p("Independent of the 4-week theme. Determines visual style, Pexels queries, and hook pool for each video. Can be overridden by performance_weights.json from weekly analysis.", S_BODY))
    story.append(sp(4))
    story.append(make_table([
        ["Day", "Bucket", "Visual Style", "Pexels Query Focus"],
        ["Monday",    "business",  "Professional, office, B2B",          "business meeting, professional courier, logistics office, executive"],
        ["Tuesday",   "family",    "Warm, diaspora, personal",            "family reunion, grandmother gift, airport arrival, loved ones"],
        ["Wednesday", "airport",   "Travel, transit, movement",           "airport departure, flight boarding, traveller luggage, departure gate"],
        ["Thursday",  "smart",     "Tech-forward, modern, innovation",    "smartphone app, modern warehouse, drone delivery, logistics tech"],
        ["Friday",    "cinematic", "High-energy, night, dynamic",         "cinematic city night, neon lights, fast delivery, courier run"],
        ["Saturday",  "community", "Culture, lifestyle, celebration",     "Lagos market, community gathering, street food festival, celebration"],
        ["Sunday",    "community", "Culture, reflection, diaspora",       "diaspora community, Sunday family, church gathering, home culture"],
    ], [65, 72, 130, 188]))
    story.append(PageBreak())

    # ── 15. ERROR HANDLING ─────────────────────────────────────────────────
    story.append(ColorBox("15 — Error Handling & Manual Recovery"))
    story.append(sp(8))
    story.append(make_table([
        ["Failure Type", "Detection Method", "Recovery"],
        ["Pipeline killed mid-run",   "pipeline_step.txt not cleared at startup",                   "Logs [LEFTOVER STEP] warning. atexit clears on normal exit."],
        ["Battery stops task",        "fix_battery_tasks.ps1 settings",                             "Task resumes on next trigger. StartWhenAvailable catches missed runs."],
        ["Clip download fails",       "Pexels returns no unused clips",                              "Falls back to secondary query pool. Skips phase if still empty."],
        ["Music download fails",      "yt-dlp error or empty file",                                  "use_archive(): picks from 18 curated archive MP3s by (day×3+slot) % count."],
        ["Voiceover fails (TTS)",     "subprocess non-zero or empty .mp3",                          "Retries TTS call. Continues without audio if all attempts fail."],
        ["LinkedIn token expired",    "token_monitor.py at 17:00 checks (expiry - now) < 7 days", "Telegram alert. refresh_token auto-used. Manual re-auth if refresh fails."],
        ["Instagram upload fails",    "Graph API error on media container",                          "Telegram alert. Skips Instagram. Still posts to other platforms."],
        ["YouTube token expires",     "google.auth.exceptions.RefreshError",                        "Auto-refresh via googleapiclient. Telegram alert if refresh fails."],
        ["weekly_analysis timeout",   "Task killed at 90-min execution limit",                       "wait_for_apply_decision uses 90-min timeout to match task limit."],
        ["main.py crash",             "try/except in __main__ block",                               "Full traceback to pipeline_crash.log. Telegram alert (first 300 chars)."],
        ["pipeline.py crash",         "try/except in __main__ block",                               "CRASH entry + traceback in pipeline_crash.log. Telegram crash alert."],
        ["Double-run same day",       "--skip-if-ran-today flag",                                   "Pipeline exits if ≥2 MP4s in output/YYYY-MM-DD/. Logs SKIP."],
        ["Telegram poll error",       "requests.exceptions in wait_for_approval()",                 "Logs error, continues looping until 90-min deadline. Never crashes."],
    ], [140, 130, 185]))
    story.append(sp(8))

    story.append(h2("Manual Recovery Procedures"))
    story.append(make_table([
        ["Scenario", "Steps"],
        ["No videos today",        "Telegram → /menu → tap 🔄 Re-run Pipeline. Removes old outputs, runs fresh pipeline."],
        ["Stories not sent",       "Telegram → /menu → tap 📱 Story (1pm) or 📱 Story (8:30pm)."],
        ["LinkedIn not posted",    "Approve via Telegram button. Or re-run: powershell scripts\\linkedin-supply-chain.ps1"],
        ["Battery settings reset", "Run fix_battery_tasks.ps1 as Administrator."],
        ["Token expired",          "Run scripts/linkedin_oauth_now.py (LinkedIn) or setup_youtube.py (YouTube)."],
        ["Crash investigation",    "Read data/pipeline_crash.log — find last CRASH entry for full traceback."],
        ["Force re-run pipeline",  "Delete output/YYYY-MM-DD/*.mp4 then run: python pipeline.py (no skip flag)."],
    ], [150, 305]))

    story.append(sp(12))
    story.append(hr(C_GREEN, 2))
    story.append(sp(6))
    story.append(p(
        f"<b>BootHop Pipeline — Version 1 Documentation</b>  |  "
        f"Generated {datetime.now().strftime('%d %B %Y at %H:%M')}  |  Internal — Confidential",
        style("Normal", fontSize=8, textColor=C_MIDGRAY, alignment=TA_CENTER)
    ))

    # ── Build ─────────────────────────────────────────────────────────────
    doc.build(story, onFirstPage=on_first_page, onLaterPages=on_page)
    print(f"\n[PDF] Built:  {OUT}")
    print(f"[PDF] Size:   {OUT.stat().st_size // 1024} KB")
    print(f"[PDF] Pages:  (open the file to check page count)")


if __name__ == "__main__":
    build()
