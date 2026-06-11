"""
BootHop Premium Investor Deck — ReportLab PDF
Elite glass-effect layout with logo watermark on every page.
Brand: dark navy #07142C, blue #0B4EA6, green #0B6E4F, gold #FFCC33
"""
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.lib.colors import HexColor, white, black, Color
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import Flowable
from reportlab.lib import colors
from pathlib import Path
import copy

# ── Paths ──────────────────────────────────────────────────────────────────
ASSETS   = Path(r"C:\Users\babso\Desktop\BootHopPipeline\assets")
WEB_IMG  = Path(r"C:\Users\babso\Desktop\boothop\boothop\public\images")
OUT_DIR  = Path(r"C:\Users\babso\Desktop\BootHopPipeline\output")
OUT_DIR.mkdir(exist_ok=True)

LOGO_PATH    = str(WEB_IMG / "logoMainBoothop.png")
LOGO_TRANSP  = str(WEB_IMG / "logoMainBoothop-transparent.png")
PUBLIC_LOGO  = "https://www.boothop.co.uk/images/logoMainBoothop.png"
OUT_PDF   = str(OUT_DIR / "BootHop_Investor_Deck_2026_PREMIUM.pdf")

# ── Brand colours ──────────────────────────────────────────────────────────
NAVY     = HexColor('#07142C')
BLUE     = HexColor('#0B4EA6')
GREEN    = HexColor('#0B6E4F')
GOLD     = HexColor('#FFCC33')
LGOLD    = HexColor('#FFF3B0')
WHITE    = HexColor('#FFFFFF')
OFFWHITE = HexColor('#F7F9FC')
LGREY    = HexColor('#E8EDF5')
MGREY    = HexColor('#8899BB')
GLASS_BG = HexColor('#EBF1FA')   # glass card background
GLASS_BD = HexColor('#C5D4EF')   # glass card border

W, H = A4  # 595 x 842 pts

# ── Watermark + background drawn on every page ────────────────────────────
def draw_page_background(canv, doc):
    canv.saveState()
    # Full-page subtle gradient effect (navy → dark blue)
    canv.setFillColor(HexColor('#071830'))
    canv.rect(0, 0, W, H, fill=1, stroke=0)

    # Subtle gradient overlay bands
    for i, (y, opacity, color) in enumerate([
        (H*0.7, 0.08, '#0B4EA6'),
        (H*0.3, 0.06, '#0B6E4F'),
    ]):
        canv.setFillColor(HexColor(color))
        canv.setFillAlpha(opacity)
        canv.rect(0, y, W, H*0.4, fill=1, stroke=0)

    canv.setFillAlpha(1.0)

    # Logo watermark — centred, transparent version
    try:
        canv.saveState()
        canv.setFillAlpha(0.07)
        logo_w = 380
        logo_h = logo_w * (1024/1536)
        lx = (W - logo_w) / 2
        ly = (H - logo_h) / 2
        wm = LOGO_TRANSP if __import__('pathlib').Path(LOGO_TRANSP).exists() else LOGO_PATH
        canv.drawImage(wm, lx, ly, width=logo_w, height=logo_h,
                       preserveAspectRatio=True, mask='auto')
        canv.restoreState()
    except Exception:
        pass

    # Top header bar
    canv.setFillColor(BLUE)
    canv.setFillAlpha(0.9)
    canv.rect(0, H - 22*mm, W, 22*mm, fill=1, stroke=0)
    canv.setFillAlpha(1.0)

    # Gold accent line under header
    canv.setFillColor(GOLD)
    canv.rect(0, H - 23*mm, W, 1*mm, fill=1, stroke=0)

    # Header text — logo small + title
    try:
        canv.drawImage(LOGO_PATH, 6*mm, H - 20*mm, width=38*mm, height=12*mm,
                       preserveAspectRatio=True, mask='auto')
    except Exception:
        pass
    canv.setFillColor(WHITE)
    canv.setFont('Helvetica-Bold', 11)
    canv.drawString(26*mm, H - 13*mm, 'BootHop')
    canv.setFont('Helvetica', 9)
    canv.setFillColor(HexColor('#AAC4F0'))
    canv.drawString(26*mm, H - 18*mm, 'Compliance-First Distributed Logistics Infrastructure')

    # Page number bottom right
    canv.setFillColor(MGREY)
    canv.setFont('Helvetica', 8)
    page_num = doc.page
    canv.drawRightString(W - 10*mm, 8*mm, f'boothop.com  ·  Confidential  ·  {page_num}')

    # Bottom gold line
    canv.setFillColor(GOLD)
    canv.rect(0, 4*mm, W, 0.8*mm, fill=1, stroke=0)

    canv.restoreState()

# ── Styles ──────────────────────────────────────────────────────────────────
def make_styles():
    s = {}

    def st(name, **kw):
        base = kw.pop('base', 'Normal')
        style = ParagraphStyle(name, **kw)
        s[name] = style
        return style

    st('slide_num',  fontSize=9,  textColor=GOLD,    fontName='Helvetica-Bold', spaceAfter=1*mm)
    st('slide_title',fontSize=22, textColor=WHITE,   fontName='Helvetica-Bold', spaceAfter=2*mm, leading=26)
    st('slide_sub',  fontSize=11, textColor=HexColor('#AAC4F0'), fontName='Helvetica', spaceAfter=6*mm, leading=15)
    st('body',       fontSize=10.5, textColor=HexColor('#D0DCEF'), fontName='Helvetica', spaceAfter=2*mm, leading=15)
    st('bullet',     fontSize=10.5, textColor=WHITE, fontName='Helvetica', spaceAfter=3*mm,
       leftIndent=12, bulletIndent=0, leading=14)
    st('bullet_bold',fontSize=10.5,textColor=GOLD,   fontName='Helvetica-Bold', spaceAfter=3*mm,
       leftIndent=12, leading=14)
    st('notes_label',fontSize=8,  textColor=GOLD,    fontName='Helvetica-Bold')
    st('notes_body', fontSize=8.5,textColor=MGREY,   fontName='Helvetica-Oblique', leading=12, spaceAfter=4*mm)
    st('cover_title',fontSize=44, textColor=WHITE,   fontName='Helvetica-Bold', alignment=TA_CENTER, leading=50)
    st('cover_sub',  fontSize=16, textColor=GOLD,    fontName='Helvetica-Bold', alignment=TA_CENTER, spaceAfter=4*mm, leading=20)
    st('cover_line', fontSize=11, textColor=HexColor('#AAC4F0'), fontName='Helvetica', alignment=TA_CENTER, leading=16, spaceAfter=2*mm)
    st('ep_text',    fontSize=11, textColor=HexColor('#D0DCEF'), fontName='Helvetica-Oblique', leading=16, spaceAfter=4*mm)
    st('section_hdr',fontSize=13, textColor=WHITE,   fontName='Helvetica-Bold', spaceAfter=2*mm, spaceBefore=3*mm)
    st('appendix',   fontSize=10, textColor=HexColor('#AAC4F0'), fontName='Helvetica', leading=14, spaceAfter=2*mm)
    return s

ST = make_styles()

# ── Glass-effect card flowable ─────────────────────────────────────────────
class GlassCard(Flowable):
    def __init__(self, story, padding=10, bg=None, border=None, radius=8):
        super().__init__()
        self._story   = story
        self.padding  = padding
        self._bg      = bg or HexColor('#0D2A5C')
        self._border  = border or BLUE
        self.radius   = radius
        self._width   = 0
        self._height  = 0

    def wrap(self, availWidth, availHeight):
        self._width = availWidth
        inner_w = availWidth - 2 * self.padding
        h = self.padding
        for item in self._story:
            w2, h2 = item.wrap(inner_w, availHeight)
            h += h2 + getattr(item, 'spaceAfter', 0)
        h += self.padding
        self._height = h
        return availWidth, h

    def draw(self):
        c = self.canv
        c.saveState()
        # Glass background
        c.setFillColor(self._bg)
        c.setFillAlpha(0.55)
        c.roundRect(0, 0, self._width, self._height, self.radius, fill=1, stroke=0)
        # Border
        c.setStrokeColor(self._border)
        c.setStrokeAlpha(0.6)
        c.setLineWidth(0.8)
        c.roundRect(0, 0, self._width, self._height, self.radius, fill=0, stroke=1)
        c.setFillAlpha(1.0)
        c.setStrokeAlpha(1.0)
        # Draw inner content
        y = self._height - self.padding
        inner_w = self._width - 2 * self.padding
        for item in self._story:
            w2, h2 = item.wrap(inner_w, 9999)
            y -= h2
            item.drawOn(c, self.padding, y)
            y -= getattr(item, 'spaceAfter', 0)
        c.restoreState()

# ── Helper: bullet paragraph ────────────────────────────────────────────────
def B(text, bold_first=False):
    if text.startswith('**') and '**' in text[2:]:
        end = text.index('**', 2)
        bold_part = text[2:end]
        rest = text[end+2:]
        return Paragraph(
            f'<font color="#FFCC33"><b>• {bold_part}</b></font><font color="#D0DCEF">{rest}</font>',
            ST['bullet']
        )
    return Paragraph(f'<font color="#D0DCEF">• {text}</font>', ST['bullet'])

def spacer(h=4):
    return Spacer(1, h*mm)

def gold_rule():
    return HRFlowable(width='100%', thickness=0.8, color=GOLD, spaceAfter=4*mm, spaceBefore=2*mm)

def blue_rule():
    return HRFlowable(width='100%', thickness=0.5, color=BLUE, spaceAfter=3*mm, spaceBefore=2*mm)

# ── Slide header ─────────────────────────────────────────────────────────────
def slide_header_block(num, title, subtitle=None):
    items = [
        Paragraph(f'SLIDE {num}', ST['slide_num']),
        Paragraph(title, ST['slide_title']),
    ]
    if subtitle:
        items.append(Paragraph(subtitle, ST['slide_sub']))
    return GlassCard(items, padding=8, bg=HexColor('#0B3A8A'), border=GOLD, radius=6)

# ── Speaker note ─────────────────────────────────────────────────────────────
def speaker_note(text):
    return GlassCard([
        Paragraph('▶  SPEAKER NOTE', ST['notes_label']),
        Paragraph(text, ST['notes_body']),
    ], padding=7, bg=HexColor('#071428'), border=HexColor('#2A4A7A'), radius=5)

# ═══════════════════════════════════════════════════════════════════════════
# BUILD DOCUMENT
# ═══════════════════════════════════════════════════════════════════════════
doc = SimpleDocTemplate(
    OUT_PDF, pagesize=A4,
    topMargin=28*mm, bottomMargin=16*mm,
    leftMargin=16*mm, rightMargin=16*mm,
)

story = []

# ── COVER ────────────────────────────────────────────────────────────────────
story.append(spacer(28))
story.append(Paragraph('BootHop', ST['cover_title']))
story.append(spacer(4))
story.append(Paragraph('Compliance-First Distributed Logistics Infrastructure', ST['cover_sub']))
story.append(spacer(6))
story.append(GlassCard([
    Paragraph(
        'Same-day &amp; cross-border logistics powered by verified movement partners, '
        'production AI customs screening, and Stripe escrow.',
        ST['cover_line']
    ),
], padding=10, bg=HexColor('#0B3A8A'), border=GOLD, radius=8))
story.append(spacer(10))
story.append(Paragraph('Oluwatoyin (Titi) Olufeko  ·  Founder &amp; CEO', ST['cover_line']))
story.append(Paragraph('titi.olufeko@boothop.com  ·  boothop.com  ·  2026', ST['cover_line']))
story.append(PageBreak())

# ── ELEVATOR PITCH ────────────────────────────────────────────────────────────
story.append(Paragraph('ELEVATOR PITCH', ST['slide_num']))
story.append(gold_rule())
story.append(GlassCard([
    Paragraph(
        'BootHop turns existing passenger and commercial movement into a compliance-first '
        'distributed logistics layer for same-day, cross-border shipments. We combine verified '
        'movement partners, a production AI customs engine, manifest &amp; inspection workflows, '
        'airport coordination, and Stripe escrow to deliver auditable, enterprise-grade urgent '
        'logistics across Africa ↔ Europe.',
        ST['ep_text']
    )
], padding=12, bg=HexColor('#0A3060'), border=GOLD, radius=8))
story.append(PageBreak())

# ── SLIDES DATA ───────────────────────────────────────────────────────────────
slides = [
    {
        "n": "01", "title": "Cover",
        "subtitle": "Compliance-First Distributed Logistics Infrastructure · 2026",
        "bullets": [
            "**Title:** BootHop",
            "**One-liner:** Same-day & cross-border logistics — verified partners, AI customs screening, Stripe escrow",
            "**Contact:** Oluwatoyin (Titi) Olufeko · titi.olufeko@boothop.com · boothop.com",
        ],
        "note": "Quick hello, name, role. One-line framing: show problem, solution, traction, ask. 10 slides, ~10–12 minutes.",
    },
    {
        "n": "02", "title": "The Problem",
        "subtitle": "Urgent cross-border movement is broken",
        "bullets": [
            "Urgent shipments remain expensive, fragmented, and slow",
            "Informal diaspora networks lack verification, auditability, and compliance",
            "Businesses lose time & revenue when parts, docs, or medical items are delayed",
            "Existing carriers don't fill a trusted, same-day, customs-aware gap at scale",
        ],
        "note": "Give 1 short example — engineering firm missing a flight-critical part; law firm needing originals same-day. Stress trust and compliance gap.",
    },
    {
        "n": "03", "title": "Our Solution",
        "subtitle": "A compliance-first logistics layer over existing movement",
        "bullets": [
            "BootHop converts existing passenger & commercial movement into an auditable logistics layer",
            "**Key features:** verified movement partners, open-inspection manifests, production AI customs screening, identity & escrow",
            "**Use cases:** same-day hand-carry, airport-to-airport, urgent parts, legal documents, diaspora commerce",
            "Not a courier app — a compliance and trust layer enterprises can rely on",
        ],
        "note": "Emphasise 'not just a courier app' — it's an auditable logistics network built for enterprise compliance and urgent cross-border use.",
    },
    {
        "n": "04", "title": "Product & Technology",
        "subtitle": "Live platform · Production AI engine · Enterprise-ready stack",
        "bullets": [
            "**Production AI Compliance Engine:** country rules, restricted items, documentation checks, risk scoring",
            "**Matching & routing:** verified movement partners with airport-structured workflows",
            "**KYC, proof-of-contents, manifest generation, and Stripe escrow** on every movement",
            "**Core stack:** Next.js · Supabase · Google Maps · Stripe · Admin ops dashboard",
        ],
        "note": "Walk intake → open inspection → manifest → AI screening → verified assignment → tracked delivery → escrow release. Mention audit logs and dispute workflow.",
    },
    {
        "n": "05", "title": "Business Model",
        "subtitle": "Multiple revenue streams — consumer volume + enterprise margin",
        "bullets": [
            "**Transaction fees:** sender fee + platform commission on every movement",
            "**Enterprise premiums:** same-day, airport hand-carry, SLA packages",
            "**Recurring revenue:** priority business accounts and annual retainers (£10k–£15k/yr)",
            "**Upsell:** shipment insurance & protection, customs-tech licensing, embedded compliance APIs",
        ],
        "note": "Consumer volume feeds the pipeline; enterprise services and insurance yield higher margins and predictable retention.",
    },
    {
        "n": "06", "title": "Market Opportunity",
        "subtitle": "Africa to Europe corridor — diaspora + enterprise logistics",
        "bullets": [
            "Large informal diaspora flows + urgent enterprise logistics demand across Africa to Europe",
            "**Addressable segments:** SME exporters, healthcare, aerospace MRO, legal/corporate, events & production",
            "**Early focus:** UK to Nigeria/Ghana; scalable to EU and global hubs",
            "Billions in informal diaspora delivery flows each year — unstructured, unverified, uncompliant",
        ],
        "note": "Emphasise corridor product-market fit and explain why Africa-Europe is an efficient place to prove compliance controls and build enterprise relationships.",
    },
    {
        "n": "07", "title": "Go-to-Market & Corridor Strategy",
        "subtitle": "Pilot → Scale → Partnerships",
        "bullets": [
            "**Phase 1:** Build Africa to Europe gateway — control compliance & verify movement partners",
            "**B2B pilots:** 3-shipment pilot packages for engineering, healthcare, legal & e-commerce",
            "**Channels:** airport intake partners, diaspora community partnerships, enterprise procurement sales",
            "**Partnerships:** airports, insurers, customs advisors, verified courier networks",
        ],
        "note": "Describe pilot mechanics and benefits: short procurement cycle, measurable SLAs, and clear proof points for scaling enterprise and insurance relationships.",
    },
    {
        "n": "08", "title": "Traction & KPIs",
        "subtitle": "Live platform · AI engine in production · Active enterprise interest",
        "bullets": [
            "Live operational platform with AI compliance engine in production",
            "Early shipments coordinated; business logistics portal deployed",
            "Organic community traction; active enterprise enquiries and pilot pipeline forming",
            "**KPIs to track:** pilots onboarded · on-time SLA % · dispute resolution time · gross transaction volume (GTV)",
        ],
        "note": "Present 3–5 concrete metrics where available. If not public, share qualitative traction: live deployments, enterprise conversations, and platform activity.",
    },
    {
        "n": "09", "title": "Team & Advisors",
        "subtitle": "Founder-led · Operational depth · Domain expertise",
        "bullets": [
            "**Oluwatoyin (Titi) Olufeko — Founder & CEO:** logistics, aviation systems, enterprise infra, compliance workflows",
            "**Key hires planned:** engineering lead · compliance lead · Lagos operations head · enterprise BD",
            "**Advisors:** customs & airport operations experts, insurance partners",
            "Platform built entirely by the founder — zero external development cost to date",
        ],
        "note": "Emphasise founder operational background as a core asset; show hiring plan, timeline, and how this capital accelerates team building.",
    },
    {
        "n": "10", "title": "Ask & Use of Funds",
        "subtitle": "£350,000 pre-seed · SAFE / Convertible Note · SEIS/EIS eligible",
        "bullets": [
            "**Raise:** up to £350,000 (pre-seed)",
            "**Compliance & Legal £50k–£80k:** international legal, GDPR/NDPA, customs advisory, insurance frameworks",
            "**African Gateway Operations £40k–£70k:** Lagos intake, inspection workflows, airport coordination",
            "**Trust & Verification Systems £25k–£50k:** KYC expansion, fraud prevention, identity infrastructure",
            "**Enterprise Logistics Growth £50k–£100k:** B2B partnerships, airport relationships, business development",
            "**Brand & Community £15k–£40k:** diaspora partnerships, strategic digital growth, creator campaigns",
        ],
        "note": "State runway, milestones this raise enables, and strategic value from investors — airport introductions, insurance relationships, customs connections. Close: 30-minute follow-up to review pilot terms.",
    },
]

for i, slide in enumerate(slides):
    story.append(slide_header_block(slide["n"], slide["title"], slide.get("subtitle")))
    story.append(spacer(3))
    bullets = [B(b) for b in slide["bullets"]]
    story.append(GlassCard(bullets, padding=10, bg=HexColor('#0D2550'), border=BLUE, radius=7))
    story.append(spacer(3))
    story.append(speaker_note(slide["note"]))
    if i < len(slides) - 1:
        story.append(PageBreak())

# ── 20-SECOND DEMO SCRIPT ─────────────────────────────────────────────────────
story.append(PageBreak())
story.append(Paragraph('20-SECOND INVESTOR DEMO SCRIPT', ST['slide_num']))
story.append(gold_rule())

script_data = [
    ['Timing',    'Frame',           'Voiceover',                                                                   'Visual Direction'],
    ['0–3s',      'Logo reveal',     '"BootHop — same-day cross-border logistics."',                                'BH mark on brand gradient, scale-up reveal'],
    ['3–7s',      'The Problem',     '"Urgent parts and documents get delayed, costing businesses time and money."','Engineer + paused clock / plane on tarmac'],
    ['7–13s',     'The Solution',    '"BootHop turns existing movement into a compliance-first logistics layer — verified partners, AI customs screening, open manifests, and escrow."', 'Flow animation: Inspect→AI→Assign→Escrow'],
    ['13–17s',    'Benefit',         '"Faster, auditable, trusted same-day delivery across Africa and Europe."',    'Map with UK→Lagos route and delivery icon'],
    ['17–20s',    'CTA',             '"Visit boothop dot com."',                                                    'Large QR + boothop.com + BH logo pulse'],
]

col_widths = [22*mm, 25*mm, 80*mm, 50*mm]
tbl = Table(script_data, colWidths=col_widths, repeatRows=1)
tbl.setStyle(TableStyle([
    ('BACKGROUND',  (0,0), (-1,0),  BLUE),
    ('TEXTCOLOR',   (0,0), (-1,0),  WHITE),
    ('FONTNAME',    (0,0), (-1,0),  'Helvetica-Bold'),
    ('FONTSIZE',    (0,0), (-1,-1), 8),
    ('FONTNAME',    (0,1), (-1,-1), 'Helvetica'),
    ('TEXTCOLOR',   (0,1), (-1,-1), HexColor('#D0DCEF')),
    ('BACKGROUND',  (0,1), (-1,-1), HexColor('#0D2550')),
    ('ROWBACKGROUNDS', (0,1), (-1,-1), [HexColor('#0D2550'), HexColor('#0B2040')]),
    ('GRID',        (0,0), (-1,-1), 0.4, HexColor('#2A4A7A')),
    ('VALIGN',      (0,0), (-1,-1), 'TOP'),
    ('TOPPADDING',  (0,0), (-1,-1), 4),
    ('BOTTOMPADDING',(0,0),(-1,-1), 4),
    ('LEFTPADDING', (0,0), (-1,-1), 5),
    ('RIGHTPADDING',(0,0),(-1,-1), 5),
]))
story.append(tbl)
story.append(spacer(6))

# Production specs
story.append(Paragraph('PRODUCTION SPECS', ST['slide_num']))
specs = [
    '1280×720 (720p)  ·  H.264 MP4  ·  Target ≤5 MB  ·  Bitrate 1.5–2.5 Mbps',
    'Audio: 44.1 kHz mono  ·  VO at −3 dB  ·  Burned-in captions for muted autoplay',
    'Brand: gradient #0B6E4F→#0B4EA6  ·  Accent #FFCC33  ·  Font: Inter / Calibri',
]
story.append(GlassCard(
    [Paragraph(f'• {s}', ST['appendix']) for s in specs],
    padding=8, bg=HexColor('#071428'), border=HexColor('#2A4A7A'), radius=5
))

# ── Build PDF ──────────────────────────────────────────────────────────────
doc.build(story, onFirstPage=draw_page_background, onLaterPages=draw_page_background)
print(f"Premium PDF saved: {OUT_PDF}")
