"""
weekly_analysis.py
BootHop Weekly Virality Analysis — compares our last 7 days to viral competitor content.

Outputs:
  analysis/reports/YYYY-WW_summary.md  — full Markdown report
  analysis/reports/YYYY-WW_hooks.csv   — hook comparison table
  Telegram: concise summary + action items
"""

import json, csv, re, sys, subprocess, datetime, os
from pathlib import Path
from collections import Counter

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE     = Path(__file__).resolve().parent.parent
DATA     = BASE / "data"
SCRIPTS  = BASE / "scripts"
ANALYSIS = BASE / "analysis"
REPORTS  = ANALYSIS / "reports"
CONFIG   = ANALYSIS / "config.json"
REPORTS.mkdir(exist_ok=True)

sys.path.insert(0, str(BASE))

# ── Config ────────────────────────────────────────────────────────────────────
DEFAULT_CONFIG = {
    "competitor_hashtags": [
        "#uknigeriadelivery",
        "#diasporadelivery",
        "#naijauk",
        "#uktolagos",
        "#lagosdelivery",
        "#sendbox",
        "#africandiaspora",
        "#nigeriansinuk",
    ],
    "competitor_accounts": [],
    "top_n_videos": 15,
    "look_back_days": 7,
    "ig_followers": 5000,
}

def load_config():
    if CONFIG.exists():
        try:
            saved = json.loads(CONFIG.read_text(encoding="utf-8"))
            merged = {**DEFAULT_CONFIG, **saved}
            return merged
        except Exception:
            pass
    CONFIG.write_text(json.dumps(DEFAULT_CONFIG, indent=2, ensure_ascii=False), encoding="utf-8")
    return DEFAULT_CONFIG


# ── Credentials ───────────────────────────────────────────────────────────────
def _load_creds():
    creds_path = SCRIPTS / "social_credentials.json"
    if creds_path.exists():
        return json.loads(creds_path.read_text(encoding="utf-8"))
    return {}


# ── Telegram ──────────────────────────────────────────────────────────────────
def send_telegram(text):
    try:
        import requests
        creds = _load_creds()
        token   = creds.get("telegram", {}).get("bot_token", "")
        chat_id = creds.get("telegram", {}).get("chat_id", "")
        if not token or not chat_id:
            return
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text[:4096], "parse_mode": "Markdown"},
            timeout=20,
        )
    except Exception as e:
        print(f"  [Telegram] {e}")


def send_telegram_apply_keyboard(summary_text, gap_words, best_hook):
    """Send report summary with Apply / Ignore buttons."""
    import requests
    creds   = _load_creds()
    token   = creds.get("telegram", {}).get("bot_token", "")
    chat_id = creds.get("telegram", {}).get("chat_id", "")
    if not token or not chat_id:
        return None
    markup = json.dumps({"inline_keyboard": [[
        {"text": "Apply Recommendations", "callback_data": "analysis_apply"},
        {"text": "Ignore",                "callback_data": "analysis_ignore"},
    ]]})
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id":      chat_id,
                "text":         summary_text[:4096],
                "parse_mode":   "Markdown",
                "reply_markup": markup,
            },
            timeout=20,
        )
        data = r.json()
        return data.get("result", {}).get("message_id")
    except Exception as e:
        print(f"  [Telegram keyboard] {e}")
        return None


def wait_for_apply_decision(timeout_seconds=86400):
    """
    Poll Telegram for Apply / Ignore callback.
    Default: 24-hour window (user can reply any time after Monday run).
    Returns True = apply, False = ignore/timeout.
    """
    import requests
    creds   = _load_creds()
    token   = creds.get("telegram", {}).get("bot_token", "")
    if not token:
        return False

    # Drain existing updates
    try:
        drain = requests.get(
            f"https://api.telegram.org/bot{token}/getUpdates",
            params={"timeout": 0, "allowed_updates": json.dumps(["callback_query"])},
            timeout=10,
        ).json()
        updates = drain.get("result", [])
        offset  = (updates[-1]["update_id"] + 1) if updates else 0
    except Exception:
        offset = 0

    deadline = datetime.datetime.now().timestamp() + timeout_seconds
    print(f"  [Analysis] Waiting up to {timeout_seconds//3600}h for Apply/Ignore...")

    while datetime.datetime.now().timestamp() < deadline:
        remaining = deadline - datetime.datetime.now().timestamp()
        wait      = int(min(60, remaining))
        if wait <= 0:
            break
        try:
            resp = requests.get(
                f"https://api.telegram.org/bot{token}/getUpdates",
                params={"offset": offset, "timeout": wait,
                        "allowed_updates": json.dumps(["callback_query"])},
                timeout=wait + 15,
            ).json()
        except Exception:
            continue
        for upd in resp.get("result", []):
            offset  = upd["update_id"] + 1
            cb      = upd.get("callback_query", {})
            cb_data = cb.get("data", "")
            if cb_data == "analysis_apply":
                try:
                    requests.post(
                        f"https://api.telegram.org/bot{token}/answerCallbackQuery",
                        json={"callback_query_id": cb["id"],
                              "text": "Applying recommendations to pipeline!"},
                        timeout=10,
                    )
                except Exception:
                    pass
                return True
            elif cb_data == "analysis_ignore":
                try:
                    requests.post(
                        f"https://api.telegram.org/bot{token}/answerCallbackQuery",
                        json={"callback_query_id": cb["id"],
                              "text": "Recommendations ignored."},
                        timeout=10,
                    )
                except Exception:
                    pass
                return False
    print("  [Analysis] Timeout — recommendations not applied")
    return False


def apply_to_pipeline(gap_words, best_hooks, comp_pov_pct):
    """
    Write the weekly insights into data/weekly_insights.json so the
    main pipeline picks them up on the next run for hook generation.
    """
    insights_path = DATA / "weekly_insights.json"
    existing = {}
    if insights_path.exists():
        try:
            existing = json.loads(insights_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    existing.update({
        "applied_at":      datetime.datetime.now().isoformat(),
        "gap_keywords":    gap_words[:6],
        "top_viral_hooks": best_hooks[:3],
        "pov_pct_target":  max(comp_pov_pct, existing.get("pov_pct_target", 0)),
        "hint":            (
            "Incorporate these keywords naturally into hooks: "
            + ", ".join(gap_words[:5])
        ),
    })
    insights_path.write_text(
        json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"  [Analysis] Insights written to data/weekly_insights.json")
    send_telegram(
        "*Recommendations applied!*\n\n"
        f"Keywords added to pipeline: `{', '.join(gap_words[:5])}`\n"
        f"Pipeline will use these on next run."
    )


# ── Our performance — post_log ─────────────────────────────────────────────────
def load_our_posts(look_back_days=7):
    cutoff = (datetime.date.today() - datetime.timedelta(days=look_back_days)).isoformat()
    post_log = DATA / "post_log.json"
    if not post_log.exists():
        return []
    entries = json.loads(post_log.read_text(encoding="utf-8"))
    return [e for e in entries if e.get("date", "") >= cutoff]


# ── IG Insights — pull real engagement for our posts ─────────────────────────
def fetch_ig_insights(media_ids):
    """
    Pull likes, comments, reach, impressions for each IG media_id.
    Returns dict: media_id -> {likes, comments, reach, impressions, saved, video_views}
    """
    results = {}
    try:
        import requests
        creds    = _load_creds()
        token    = creds.get("instagram", {}).get("access_token", "")
        if not token:
            print("  [IG] No access token — skipping insights")
            return results
        for mid in media_ids:
            if not mid:
                continue
            try:
                r = requests.get(
                    f"https://graph.instagram.com/{mid}/insights",
                    params={
                        "metric": "impressions,reach,likes,comments,saved,video_views",
                        "access_token": token,
                    },
                    timeout=15,
                )
                data = r.json()
                if "data" in data:
                    row = {}
                    for item in data["data"]:
                        row[item["name"]] = item.get("values", [{}])[-1].get("value", 0)
                    results[mid] = row
                elif "error" in data:
                    # Insight endpoint needs business account; try basic field fetch
                    r2 = requests.get(
                        f"https://graph.instagram.com/{mid}",
                        params={"fields": "like_count,comments_count", "access_token": token},
                        timeout=10,
                    )
                    d2 = r2.json()
                    if "like_count" in d2 or "comments_count" in d2:
                        results[mid] = {
                            "likes":    d2.get("like_count", 0),
                            "comments": d2.get("comments_count", 0),
                        }
            except Exception as e:
                print(f"  [IG] {mid}: {e}")
    except Exception as e:
        print(f"  [IG insights] {e}")
    return results


def analyze_our_content(entries, ig_insights):
    """Compute stats and patterns from our own posts + IG data."""
    hooks      = [e.get("hook", "") for e in entries if e.get("hook")]
    platforms  = Counter(e.get("platform", "") for e in entries)
    buckets    = Counter(e.get("bucket", "") for e in entries)
    music      = Counter(e.get("music_track", "") for e in entries)
    slots      = Counter(e.get("slot", "") for e in entries)

    # Hook text analysis (ASCII only for pattern matching)
    clean_hooks = [re.sub(r'[^\x00-\x7F]+', '', h).strip() for h in hooks]
    pov_count = sum(1 for h in clean_hooks if h.upper().startswith("POV"))
    words = []
    for h in clean_hooks:
        words += re.findall(r'\b\w{4,}\b', h.lower())
    top_words = Counter(words).most_common(12)

    # IG engagement summary
    ig_stats = []
    for e in entries:
        mid = e.get("media_id", "")
        if mid and mid in ig_insights:
            ins = ig_insights[mid]
            ig_stats.append({
                "hook":        e.get("hook", ""),
                "bucket":      e.get("bucket", ""),
                "slot":        e.get("slot", ""),
                "likes":       ins.get("likes", 0),
                "comments":    ins.get("comments", 0),
                "reach":       ins.get("reach", 0),
                "impressions": ins.get("impressions", 0),
                "saved":       ins.get("saved", 0),
                "video_views": ins.get("video_views", 0),
            })

    ig_stats.sort(key=lambda x: x.get("reach", 0) + x.get("likes", 0) * 3, reverse=True)

    avg_reach = int(sum(s.get("reach", 0) for s in ig_stats) / max(1, len(ig_stats)))
    avg_likes = int(sum(s.get("likes", 0) for s in ig_stats) / max(1, len(ig_stats)))

    return {
        "total_posts":  len(entries),
        "pov_hooks":    pov_count,
        "top_words":    top_words,
        "platforms":    dict(platforms),
        "buckets":      dict(buckets),
        "music":        music.most_common(3),
        "slots":        dict(slots),
        "hooks":        hooks,
        "ig_stats":     ig_stats,
        "avg_reach":    avg_reach,
        "avg_likes":    avg_likes,
        "best_hook":    ig_stats[0]["hook"] if ig_stats else (hooks[0] if hooks else "—"),
        "worst_hook":   ig_stats[-1]["hook"] if len(ig_stats) > 1 else "—",
    }


# ── Competitor scraping via yt-dlp ────────────────────────────────────────────
def _parse_yt_dlp_output(stdout, source_tag):
    videos = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line or not line.startswith("{"):
            continue
        try:
            v = json.loads(line)
            videos.append({
                "id":            v.get("id", ""),
                "hook":          (v.get("description") or v.get("title") or "")[:300],
                "view_count":    int(v.get("view_count") or 0),
                "like_count":    int(v.get("like_count") or 0),
                "comment_count": int(v.get("comment_count") or 0),
                "uploader":      v.get("uploader", ""),
                "upload_date":   v.get("upload_date", ""),
                "source":        source_tag,
                "url":           v.get("webpage_url", ""),
            })
        except Exception:
            continue
    return videos


def scrape_tiktok_tag(tag, max_videos=15):
    """
    Pull video metadata from a TikTok hashtag or @account.
    Falls back to YouTube search when TikTok blocks the request.
    """
    tag_clean = tag.lstrip("#@")
    if tag.startswith("@"):
        tiktok_url = f"https://www.tiktok.com/@{tag_clean}"
    else:
        tiktok_url = f"https://www.tiktok.com/tag/{tag_clean}"

    # Try TikTok with browser cookies (user must be logged in to TikTok in Chrome/Edge)
    for browser in ("chrome", "edge", "firefox"):
        try:
            result = subprocess.run(
                ["yt-dlp", "--dump-json", "--flat-playlist",
                 f"--playlist-end={max_videos}", "--no-warnings", "--quiet",
                 f"--cookies-from-browser={browser}", tiktok_url],
                capture_output=True, text=True, timeout=60,
                encoding="utf-8", errors="replace",
            )
            videos = _parse_yt_dlp_output(result.stdout, tag)
            if videos:
                print(f"({browser} cookies) ", end="", flush=True)
                return videos
        except Exception:
            continue

    # TikTok blocked — fall back to YouTube search with matching terms
    search_term = tag_clean.replace("-", " ")
    yt_query = f"ytsearch{max_videos}:{search_term} diaspora delivery uk nigeria viral short"
    try:
        result = subprocess.run(
            ["yt-dlp", "--dump-json", "--flat-playlist",
             f"--playlist-end={max_videos}", "--no-warnings", "--quiet", yt_query],
            capture_output=True, text=True, timeout=90,
            encoding="utf-8", errors="replace",
        )
        videos = _parse_yt_dlp_output(result.stdout, tag + " [YT]")
        if videos:
            print("(YT fallback) ", end="", flush=True)
        return videos
    except Exception as e:
        print(f"  [yt-dlp] {tag}: {e}")
        return []


_STOPWORDS = {
    "with", "this", "that", "your", "have", "from", "they", "been",
    "more", "will", "also", "what", "when", "about", "like", "just",
    "than", "then", "into", "which", "their", "there", "after", "before",
    "very", "some", "here", "were", "each", "over", "back", "even",
    "most", "such", "much", "only", "well", "time", "make", "know",
    "take", "want", "look", "come", "find", "give", "good", "work",
    "call", "long", "down", "said", "does", "used", "where", "while",
    "video", "subscribe", "follow", "click", "link", "like", "share",
    "comment", "watch", "below", "check", "today", "enjoy", "thanks",
    "please", "above", "channel", "latest", "official",
}

def analyze_competitor_videos(videos):
    if not videos:
        return {"total": 0, "avg_views": 0, "top_avg_views": 0,
                "top_word_freq": [], "top_videos": []}

    sorted_v  = sorted(videos, key=lambda x: x.get("view_count", 0), reverse=True)
    top_n     = max(1, len(sorted_v) // 3)
    top_vids  = sorted_v[:top_n]

    # Word frequency in viral hooks — filter stopwords
    words = []
    for v in top_vids:
        clean = re.sub(r'[^\x00-\x7F]+', '', v.get("hook", ""))
        for w in re.findall(r'\b\w{4,}\b', clean.lower()):
            if w not in _STOPWORDS:
                words.append(w)
    top_word_freq = Counter(words).most_common(15)

    avg_views     = int(sum(v.get("view_count", 0) for v in videos) / len(videos))
    top_avg_views = int(sum(v.get("view_count", 0) for v in top_vids) / len(top_vids))

    return {
        "total":          len(videos),
        "avg_views":      avg_views,
        "top_avg_views":  top_avg_views,
        "top_word_freq":  top_word_freq,
        "top_videos":     top_vids[:5],
    }


# ── Gap analysis ──────────────────────────────────────────────────────────────
def compute_gaps(our_analysis, competitor_data):
    """Find keywords, patterns, themes that viral videos use but we don't."""
    our_words = {w for w, _ in our_analysis["top_words"]}

    all_comp_words = Counter()
    for data in competitor_data.values():
        for w, c in data["top_word_freq"]:
            all_comp_words[w] += c

    gap_words = [w for w, _ in all_comp_words.most_common(30) if w not in our_words][:8]

    # Find highest-view hooks from competitors
    all_top = []
    for data in competitor_data.values():
        all_top.extend(data.get("top_videos", []))
    all_top.sort(key=lambda x: x.get("view_count", 0), reverse=True)

    # POV ratio in competitors
    comp_hooks = []
    for data in competitor_data.values():
        for v in data.get("top_videos", []):
            comp_hooks.append(v.get("hook", ""))
    comp_pov = sum(1 for h in comp_hooks if "pov" in h.lower())
    comp_pov_pct = int(comp_pov / max(1, len(comp_hooks)) * 100)

    our_pov_pct = int(our_analysis["pov_hooks"] / max(1, our_analysis["total_posts"]) * 100)

    return {
        "gap_words":      gap_words,
        "top_comp_hooks": all_top[:5],
        "comp_pov_pct":   comp_pov_pct,
        "our_pov_pct":    our_pov_pct,
    }


# ── Report builder ────────────────────────────────────────────────────────────
def build_markdown_report(week_label, our, competitor_data, gaps, cfg):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        f"# BootHop Weekly Virality Analysis — {week_label}",
        f"_Generated {now}_",
        "",
        "---",
        "",
        "## Our Performance (last 7 days)",
        f"- **Total posts:** {our['total_posts']} across {list(our['platforms'].keys())}",
        f"- **POV hooks:** {our['pov_hooks']} / {our['total_posts']} ({int(our['pov_hooks']/max(1,our['total_posts'])*100)}%)",
        f"- **Buckets used:** {our['buckets']}",
        f"- **Most used music:** {', '.join(t for t,_ in our['music'])}",
        f"- **Avg IG reach:** {our['avg_reach']:,} | Avg likes: {our['avg_likes']:,}",
        "",
    ]

    if our["ig_stats"]:
        lines += [
            "### Best & Worst IG Posts (by reach)",
            f"- **Best hook:** `{our['best_hook'][:120]}`",
            f"- **Worst hook:** `{our['worst_hook'][:120]}`",
            "",
            "| Hook | Likes | Reach | Saved |",
            "|------|-------|-------|-------|",
        ]
        for s in our["ig_stats"][:5]:
            hook_short = re.sub(r'[^\x00-\x7F]+', '', s["hook"])[:70]
            lines.append(f"| {hook_short} | {s['likes']} | {s['reach']:,} | {s['saved']} |")
        lines.append("")

    lines += [
        "---",
        "",
        "## Competitor Landscape",
    ]
    for tag, data in competitor_data.items():
        if data["total"] == 0:
            lines.append(f"### {tag} — no data retrieved")
            continue
        lines += [
            f"### {tag}",
            f"- Videos analysed: {data['total']}",
            f"- Avg views: {data['avg_views']:,} | Viral tier avg: {data['top_avg_views']:,}",
            f"- Top words in viral hooks: `{', '.join(w for w,_ in data['top_word_freq'][:8])}`",
            "",
            "**Top videos:**",
        ]
        for v in data["top_videos"][:3]:
            hook_clean = re.sub(r'[^\x00-\x7F]+', '', v.get("hook",""))[:90]
            lines.append(
                f"- [{v.get('view_count',0):,} views] @{v.get('uploader','')} — {hook_clean}"
            )
        lines.append("")

    lines += [
        "---",
        "",
        "## Gap Analysis — What Viral Videos Do That We Don't",
        "",
        f"**Missing keywords** (viral content uses, we don't):",
        f"`{', '.join(gaps['gap_words']) or 'not enough data'}`",
        "",
        f"**POV hook usage** — Ours: {gaps['our_pov_pct']}% | Competitors: {gaps['comp_pov_pct']}%",
        "",
        "**Top viral hooks to study:**",
    ]
    for v in gaps["top_comp_hooks"][:4]:
        hook_clean = re.sub(r'[^\x00-\x7F]+', '', v.get("hook",""))[:100]
        lines.append(f"- [{v.get('view_count',0):,} views] {hook_clean}")

    lines += [
        "",
        "---",
        "",
        "## Action Items This Week",
        "",
        f"1. **Use gap keywords** — add `{', '.join(gaps['gap_words'][:3]) or 'n/a'}` to next hook batch",
        f"2. **Study best viral hook** — `{re.sub(chr(127489)+'-'+chr(128511),'',gaps['top_comp_hooks'][0].get('hook','—'))[:100] if gaps['top_comp_hooks'] else '—'}`",
        "3. **Music** — match trending audio from top competitor videos above",
        "4. **Caption length** — keep under 100 chars, front-load the hook before any hashtags",
        "5. **Posting cadence** — at least 2 posts/day; morning slot appears strongest",
        f"6. **POV ratio** — {'increase' if gaps['our_pov_pct'] < gaps['comp_pov_pct'] else 'maintain'} POV-style hooks",
        "",
    ]
    return "\n".join(lines)


# ── CSV export ────────────────────────────────────────────────────────────────
def export_csv(week_label, our, competitor_data):
    csv_path = REPORTS / f"{week_label}_hooks.csv"
    rows = []

    # Our posts
    for s in our.get("ig_stats", []):
        rows.append({
            "source":      "ours",
            "tag":         "",
            "uploader":    "boothop",
            "view_count":  s.get("video_views", 0),
            "like_count":  s.get("likes", 0),
            "reach":       s.get("reach", 0),
            "hook":        s.get("hook", "")[:200],
            "bucket":      s.get("bucket", ""),
            "slot":        s.get("slot", ""),
        })
    # Fallback if no IG insights
    if not our.get("ig_stats"):
        for h in our.get("hooks", []):
            rows.append({
                "source": "ours", "tag": "", "uploader": "boothop",
                "view_count": 0, "like_count": 0, "reach": 0,
                "hook": h[:200], "bucket": "", "slot": "",
            })

    # Competitor top videos
    for tag, data in competitor_data.items():
        for v in data.get("top_videos", []):
            rows.append({
                "source":     "competitor",
                "tag":        tag,
                "uploader":   v.get("uploader", ""),
                "view_count": v.get("view_count", 0),
                "like_count": v.get("like_count", 0),
                "reach":      0,
                "hook":       re.sub(r'[^\x00-\x7F]+', '', v.get("hook",""))[:200],
                "bucket":     "",
                "slot":       "",
            })

    if not rows:
        return None
    fields = ["source","tag","uploader","view_count","like_count","reach","hook","bucket","slot"]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    return csv_path


# ── Telegram summary ──────────────────────────────────────────────────────────
def build_telegram_summary(week_label, our, competitor_data, gaps):
    total_comp = sum(d["total"] for d in competitor_data.values())
    top_comp_line = ""
    all_tops = []
    for d in competitor_data.values():
        all_tops.extend(d.get("top_videos", []))
    all_tops.sort(key=lambda x: x.get("view_count", 0), reverse=True)
    if all_tops:
        v = all_tops[0]
        hook = re.sub(r'[^\x00-\x7F]+', '', v.get("hook",""))[:80]
        top_comp_line = f"\n*Top viral hook:* `{hook}` ({v.get('view_count',0):,} views)"

    gap_str = ', '.join(gaps["gap_words"][:5]) or "not enough data"

    return (
        f"*BootHop Weekly Analysis — {week_label}*\n\n"
        f"*Our posts (7 days):* {our['total_posts']} | Avg reach: {our['avg_reach']:,} | Avg likes: {our['avg_likes']:,}\n"
        f"*Competitor videos analysed:* {total_comp}\n"
        f"{top_comp_line}\n\n"
        f"*Keyword gaps (they use, we don't):*\n`{gap_str}`\n\n"
        f"*POV hooks — ours:* {gaps['our_pov_pct']}% | *competitors:* {gaps['comp_pov_pct']}%\n\n"
        f"*Our best hook this week:*\n_{re.sub(chr(0)+'-'+chr(127),'',our['best_hook'])[:100]}_\n\n"
        f"Full report saved to `analysis/reports/{week_label}_summary.md`"
    )


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    cfg        = load_config()
    today      = datetime.date.today()
    week_label = today.strftime("%Y-W%V")
    look_back  = cfg.get("look_back_days", 7)
    max_vids   = cfg.get("top_n_videos", 15)

    print(f"\n{'='*60}")
    print(f"  BootHop Weekly Analysis — {week_label}")
    print(f"{'='*60}\n")

    # 0. Refresh trending music before anything else
    print("[0/6] Refreshing trending music...")
    try:
        import importlib.util as _ilu
        _spec = _ilu.spec_from_file_location("refresh_music", BASE / "scripts" / "refresh_music.py")
        _rm   = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_rm)
        _rm.main()
    except Exception as _e:
        print(f"  [MusicRefresh] {_e}")

    # 1. Load our posts
    print("[1/6] Loading our recent posts...")
    entries = load_our_posts(look_back)
    print(f"  {len(entries)} posts found in last {look_back} days")

    # 2. Pull IG insights
    print("[2/6] Fetching IG engagement stats...")
    media_ids  = [e.get("media_id", "") for e in entries if e.get("media_id")]
    ig_insights = fetch_ig_insights(media_ids)
    print(f"  Got insights for {len(ig_insights)}/{len(media_ids)} IG posts")

    our = analyze_our_content(entries, ig_insights)

    # 3. Scrape competitors
    print("[3/6] Scraping competitor content...")
    competitor_data = {}
    tags = cfg.get("competitor_hashtags", []) + [f"@{a.lstrip('@')}" for a in cfg.get("competitor_accounts", [])]
    for tag in tags:
        print(f"  {tag}...", end=" ", flush=True)
        vids = scrape_tiktok_tag(tag, max_vids)
        competitor_data[tag] = analyze_competitor_videos(vids)
        if vids:
            print(f"{len(vids)} videos, avg {competitor_data[tag]['avg_views']:,} views")
        else:
            print("no data")

    # Also run direct YouTube searches from config
    for yt_q in cfg.get("yt_search_queries", []):
        label = yt_q.split(":", 1)[-1][:40]
        print(f"  YT: {label}...", end=" ", flush=True)
        try:
            result = subprocess.run(
                ["yt-dlp", "--dump-json", "--flat-playlist",
                 f"--playlist-end={max_vids}", "--no-warnings", "--quiet", yt_q],
                capture_output=True, text=True, timeout=90,
                encoding="utf-8", errors="replace",
            )
            vids = _parse_yt_dlp_output(result.stdout, f"yt:{label}")
            competitor_data[f"yt:{label}"] = analyze_competitor_videos(vids)
            if vids:
                print(f"{len(vids)} videos, avg {competitor_data[f'yt:{label}']['avg_views']:,} views")
            else:
                print("no data")
        except Exception as e:
            print(f"error: {e}")

    # 4. Gap analysis
    print("[4/6] Computing gap analysis...")
    gaps = compute_gaps(our, competitor_data)
    print(f"  Keyword gaps: {gaps['gap_words']}")
    print(f"  POV % — ours: {gaps['our_pov_pct']}%  competitors: {gaps['comp_pov_pct']}%")

    # 5. Reports
    print("[5/6] Writing reports...")
    md   = build_markdown_report(week_label, our, competitor_data, gaps, cfg)
    md_path  = REPORTS / f"{week_label}_summary.md"
    md_path.write_text(md, encoding="utf-8")
    print(f"  Report: {md_path}")

    csv_path = export_csv(week_label, our, competitor_data)
    if csv_path:
        print(f"  CSV:    {csv_path}")

    summary = build_telegram_summary(week_label, our, competitor_data, gaps)
    send_telegram_apply_keyboard(summary, gaps["gap_words"], gaps["top_comp_hooks"])
    print("  Telegram summary + Apply/Ignore buttons sent.")

    # Wait up to 24h for user to tap Apply or Ignore
    best_hooks = [
        re.sub(r'[^\x00-\x7F]+', '', v.get("hook", ""))[:120]
        for v in gaps["top_comp_hooks"][:3]
    ]
    decision = wait_for_apply_decision(timeout_seconds=5400)  # 90 min — fits within 2h task limit
    if decision:
        apply_to_pipeline(gaps["gap_words"], best_hooks, gaps["comp_pov_pct"])
    else:
        print("  [Analysis] No changes applied.")

    # 6. Trending music refresh report
    print("\n[6/6] Checking trending music freshness...")
    try:
        sys.path.insert(0, str(BASE))
        from pipeline import refresh_trending_music
        stale = refresh_trending_music()
        if stale:
            stale_list = "\n".join(f"  • {n}" for n in stale)
            from pipeline import send_telegram_text
            send_telegram_text(
                f"🎵 *Trending Music — Stale Files ({len(stale)})*\n"
                f"These tracks were used 3+ times this week. Replace with fresh audio:\n\n"
                f"{stale_list}"
            )
    except Exception as e:
        print(f"  [MusicRefresh] {e}")

    print(f"\n{'='*60}")
    print(f"  Done. Report: analysis/reports/{week_label}_summary.md")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
