"""
build_dashboard.py
Reads data/state.json and generates index.html —
the Chico Policy Tracker newsroom dashboard.
"""

import json
from datetime import datetime
from pathlib import Path

STATE_FILE = Path(__file__).parent / "data" / "state.json"
OUTPUT     = Path(__file__).parent / "index.html"


def fmt_date(d: str) -> str:
    try:
        return datetime.strptime(d, "%Y-%m-%d").strftime("%b %-d, %Y")
    except Exception:
        return d


def fmt_iso(d: str) -> str:
    try:
        return datetime.fromisoformat(d).strftime("%b %-d, %Y · %H:%M UTC")
    except Exception:
        return d


def render_meeting_cards(meetings: list) -> str:
    if not meetings:
        return '<div class="empty">No meetings scraped yet.</div>'
    cards = []
    for i, m in enumerate(meetings):
        date     = fmt_date(m.get("date", ""))
        title    = m.get("title", f"Meeting {date}")
        link     = m.get("link", "#")
        has_min  = m.get("has_minutes") or m.get("type") == "minutes"
        items    = m.get("items") or m.get("agenda_items", [])
        status   = "MIN" if has_min else "AGN"
        scls     = "tag-green" if has_min else "tag-blue"

        item_rows = ""
        for it in items[:10]:
            num = f'<span class="row-num">{it["num"]}</span>' if it.get("num") else ""
            item_rows += f'<div class="item-row">{num}<span class="row-title">{it["title"]}</span></div>'
        if len(items) > 10:
            item_rows += f'<div class="item-more">+{len(items)-10} more items</div>'

        expand = ""
        if items:
            expand = f"""<button class="expand-btn" onclick="xpand('mc{i}',this)">
                <span class="xicon">▸</span> {len(items)} agenda items
            </button>
            <div class="xbody" id="mc{i}">{item_rows}</div>"""

        cards.append(f"""<div class="card" data-id="council-{m.get('date',i)}">
            <div class="card-top">
                <div class="card-meta">
                    <span class="mono date-chip">{date}</span>
                    <span class="tag {scls}">{status}</span>
                </div>
                <div class="card-actions">
                    <button class="pin-btn" onclick="pinItem(this)" data-title="{title}" data-date="{date}" data-link="{link}" title="Pin to board">⊕</button>
                </div>
            </div>
            <div class="card-title"><a href="{link}" target="_blank">{title}</a></div>
            {expand}
        </div>""")
    return "\n".join(cards)


def render_bill_cards(bills: list) -> str:
    if not bills:
        return '<div class="empty">No recurring items detected yet. More meetings needed.</div>'

    STATUS_TAG = {
        "active":    ("tag-red",   "ACTIVE"),
        "passed":    ("tag-green", "PASSED"),
        "tabled":    ("tag-amber", "TABLED"),
        "scheduled": ("tag-blue",  "SCHED"),
        "unknown":   ("tag-dim",   "ONGOING"),
    }
    cards = []
    for i, b in enumerate(bills):
        tcls, tlbl = STATUS_TAG.get(b.get("status","unknown"), ("tag-dim","ONGOING"))
        count      = b.get("meeting_count", 0)
        first      = fmt_date(b.get("first_seen",""))
        last       = fmt_date(b.get("last_seen",""))
        title      = b.get("canonical_title","")

        tl_html = ""
        for j, ap in enumerate(sorted(b.get("appearances",[]), key=lambda x: x["date"])):
            dot = "tl-now" if j == len(b.get("appearances",[])) - 1 else "tl-past"
            tl_html += f"""<div class="tl-row">
                <div class="tl-dot {dot}"></div>
                <div><div class="mono tl-date">{fmt_date(ap['date'])}</div>
                <div class="tl-evt">{ap.get('title_seen', title)}</div></div>
            </div>"""

        cards.append(f"""<div class="card" data-id="bill-{b.get('id',i)}">
            <div class="card-top">
                <div class="card-meta">
                    <span class="tag {tcls}">{tlbl}</span>
                    <span class="mono dim">{count} meetings</span>
                </div>
                <div class="card-actions">
                    <button class="pin-btn" onclick="pinItem(this)" data-title="{title}" data-date="{last}" data-link="" title="Pin to board">⊕</button>
                </div>
            </div>
            <div class="card-title">{title}</div>
            <div class="card-dates mono dim">First: {first} · Last: {last}</div>
            <button class="expand-btn" onclick="xpand('bc{i}',this)">
                <span class="xicon">▸</span> Timeline
            </button>
            <div class="xbody" id="bc{i}">
                <div class="timeline">{tl_html}</div>
            </div>
        </div>""")
    return "\n".join(cards)


def render_legislation_cards(bills: list) -> str:
    if not bills:
        return '<div class="empty">Awaiting LegiScan API key. Bills will appear here once the agent runs.</div>'
    cards = []
    for i, b in enumerate(bills):
        score   = b.get("score", 0)
        scls    = "tag-green" if score >= 8 else "tag-blue" if score >= 6 else "tag-dim"
        title   = b.get("title","")
        bnum    = b.get("bill_number","")
        url     = b.get("url","#")
        expl    = b.get("explanation","")
        action  = b.get("last_action","")
        adate   = b.get("last_action_date","")
        topics  = b.get("topics", [])
        topic_tags = " ".join(f'<span class="tag tag-dim">{t}</span>' for t in topics[:3])

        cards.append(f"""<div class="card" data-id="leg-{b.get('bill_id',i)}">
            <div class="card-top">
                <div class="card-meta">
                    <span class="mono bill-num">{bnum}</span>
                    <span class="tag {scls}">{score}/10</span>
                    {topic_tags}
                </div>
                <div class="card-actions">
                    <button class="pin-btn" onclick="pinItem(this)" data-title="{bnum}: {title}" data-date="{adate}" data-link="{url}" title="Pin to board">⊕</button>
                </div>
            </div>
            <div class="card-title"><a href="{url}" target="_blank">{title}</a></div>
            <div class="card-expl">{expl}</div>
            <div class="mono dim card-action-line">Last action {adate}: {action[:80]}{"…" if len(action)>80 else ""}</div>
        </div>""")
    return "\n".join(cards)


def build(state: dict) -> str:
    meetings    = state.get("meetings", [])
    bills       = state.get("bills", [])
    leg_bills   = state.get("state_legislation", [])
    updated     = state.get("last_updated", "")
    updated_fmt = fmt_iso(updated)

    n_meetings  = len(meetings)
    n_bills     = len(bills)
    n_leg       = len(leg_bills)
    recent_date = fmt_date(meetings[0]["date"]) if meetings else "—"

    council_html = render_meeting_cards(meetings)
    bill_html    = render_bill_cards(bills)
    leg_html     = render_legislation_cards(leg_bills)

    # Pre-serialize dashboard data for JS
    js_meetings = json.dumps([
        {
            "date":        m.get("date"),
            "title":       m.get("title"),
            "link":        m.get("link", ""),
            "description": m.get("description", ""),
            "has_minutes": m.get("has_minutes", False),
            "items": (m.get("items") or m.get("agenda_items", []))[:15]
        }
        for m in meetings[:10]
    ])
    js_bills = json.dumps([
        {"title": b.get("canonical_title"), "status": b.get("status"),
         "meeting_count": b.get("meeting_count"), "last_seen": b.get("last_seen")}
        for b in bills[:20]
    ])
    js_legislation = json.dumps([
        {"bill_number": b.get("bill_number"), "title": b.get("title"),
         "score": b.get("score"), "explanation": b.get("explanation")}
        for b in leg_bills[:20]
    ])

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Chico Scraper</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@300;400;500&display=swap" rel="stylesheet">
<style>
/* ── Reset & Base ──────────────────────────────────────────── */
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
:root {{
    --bg:       #0a0e13;
    --bg2:      #0f1520;
    --bg3:      #141c28;
    --bg4:      #1a2234;
    --border:   rgba(255,255,255,0.07);
    --border2:  rgba(255,255,255,0.12);
    --text:     #d4dce8;
    --text2:    #7a8a9e;
    --text3:    #4a5568;
    --green:    #00c896;
    --green2:   rgba(0,200,150,0.12);
    --blue:     #3b82f6;
    --blue2:    rgba(59,130,246,0.12);
    --red:      #ef4444;
    --red2:     rgba(239,68,68,0.12);
    --amber:    #f59e0b;
    --amber2:   rgba(245,158,11,0.12);
    --sidebar-w: 200px;
    --right-w:   300px;
    --header-h:  44px;
}}

html, body {{ height: 100%; overflow: hidden; }}
body {{
    font-family: 'IBM Plex Sans', sans-serif;
    background: var(--bg);
    color: var(--text);
    font-size: 13px;
    line-height: 1.6;
}}
a {{ color: var(--green); text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
.mono {{ font-family: 'IBM Plex Mono', monospace; }}
.dim {{ color: var(--text2); }}

/* ── Header ────────────────────────────────────────────────── */
.header {{
    position: fixed; top: 0; left: 0; right: 0;
    height: var(--header-h);
    background: var(--bg2);
    border-bottom: 1px solid var(--border);
    display: flex; align-items: center;
    padding: 0 16px;
    z-index: 100;
    gap: 16px;
}}
.header-logo {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 13px; font-weight: 500;
    color: var(--green);
    letter-spacing: 0.05em;
    white-space: nowrap;
}}
.header-logo span {{ color: var(--text3); }}
.header-spacer {{ flex: 1; }}
.header-meta {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px; color: var(--text3);
    display: flex; align-items: center; gap: 12px;
}}
.live-dot {{
    width: 6px; height: 6px; border-radius: 50%;
    background: var(--green);
    animation: pulse 2.5s ease-in-out infinite;
    flex-shrink: 0;
}}
@keyframes pulse {{ 0%,100%{{opacity:1;}} 50%{{opacity:0.2;}} }}

/* ── Layout ─────────────────────────────────────────────────── */
.layout {{
    display: grid;
    grid-template-columns: var(--sidebar-w) 1fr var(--right-w);
    grid-template-rows: 1fr;
    height: 100vh;
    padding-top: var(--header-h);
}}

/* ── Left Sidebar ───────────────────────────────────────────── */
.sidebar {{
    background: var(--bg2);
    border-right: 1px solid var(--border);
    overflow-y: auto;
    padding: 16px 0;
    display: flex;
    flex-direction: column;
    gap: 0;
}}
.sidebar-section {{
    padding: 0 12px;
    margin-bottom: 8px;
}}
.sidebar-label {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 9px; font-weight: 500;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--text3);
    padding: 8px 4px 6px;
}}
.nav-item {{
    display: flex; align-items: center; gap: 10px;
    padding: 8px 10px;
    border-radius: 6px;
    cursor: pointer;
    color: var(--text2);
    font-size: 13px;
    transition: all 0.15s;
    position: relative;
    border: 1px solid transparent;
    margin-bottom: 2px;
    user-select: none;
}}
.nav-item:hover {{
    background: var(--bg3);
    color: var(--text);
}}
.nav-item.active {{
    background: var(--bg3);
    color: var(--green);
    border-color: rgba(0,200,150,0.2);
}}
.nav-item.active::before {{
    content: '';
    position: absolute; left: -12px; top: 50%;
    transform: translateY(-50%);
    width: 3px; height: 20px;
    background: var(--green);
    border-radius: 0 2px 2px 0;
}}
.nav-icon {{ font-size: 14px; width: 18px; text-align: center; flex-shrink: 0; }}
.nav-label {{ flex: 1; }}
.nav-count {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 10px;
    background: var(--bg4);
    color: var(--text3);
    padding: 1px 6px;
    border-radius: 10px;
}}
.nav-soon {{
    font-size: 9px;
    color: var(--text3);
    letter-spacing: 0.06em;
    font-family: 'IBM Plex Mono', monospace;
}}
.sidebar-divider {{
    border: none;
    border-top: 1px solid var(--border);
    margin: 8px 12px;
}}

/* ── Center Panel ───────────────────────────────────────────── */
.main {{
    overflow-y: auto;
    background: var(--bg);
    display: flex;
    flex-direction: column;
}}
.main-header {{
    padding: 16px 20px 12px;
    border-bottom: 1px solid var(--border);
    background: var(--bg);
    position: sticky; top: 0; z-index: 10;
    display: flex; align-items: center; gap: 12px;
}}
.main-title {{
    font-size: 15px; font-weight: 500;
    color: var(--text);
    flex: 1;
}}
.main-subtitle {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px; color: var(--text3);
}}
.main-body {{ padding: 16px 20px; flex: 1; }}

.panel {{ display: none; }}
.panel.active {{ display: block; }}

/* ── Cards ──────────────────────────────────────────────────── */
.card {{
    background: var(--bg2);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 14px 16px;
    margin-bottom: 10px;
    transition: border-color 0.15s;
}}
.card:hover {{ border-color: var(--border2); }}
.card-top {{
    display: flex; justify-content: space-between;
    align-items: flex-start; margin-bottom: 8px;
}}
.card-meta {{ display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }}
.card-actions {{ display: flex; gap: 6px; flex-shrink: 0; }}
.card-title {{
    font-size: 14px; font-weight: 500;
    color: var(--text); line-height: 1.4;
    margin-bottom: 6px;
}}
.card-title a {{ color: var(--text); }}
.card-title a:hover {{ color: var(--green); text-decoration: none; }}
.card-dates {{ font-size: 11px; margin-bottom: 6px; }}
.card-expl {{
    font-size: 12px; color: var(--text2);
    line-height: 1.65; margin-bottom: 6px;
    padding: 8px 10px;
    background: var(--bg3);
    border-radius: 4px;
    border-left: 2px solid var(--blue);
}}
.card-action-line {{ font-size: 11px; margin-top: 6px; }}
.bill-num {{ color: var(--blue); font-size: 12px; }}
.date-chip {{ font-size: 11px; color: var(--text2); }}

/* Tags */
.tag {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 10px; font-weight: 500;
    padding: 2px 7px; border-radius: 3px;
    letter-spacing: 0.04em;
    white-space: nowrap;
}}
.tag-green  {{ background: var(--green2); color: var(--green); }}
.tag-blue   {{ background: var(--blue2);  color: var(--blue);  }}
.tag-red    {{ background: var(--red2);   color: var(--red);   }}
.tag-amber  {{ background: var(--amber2); color: var(--amber); }}
.tag-dim    {{ background: var(--bg4);    color: var(--text3); }}

/* Expand */
.expand-btn {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px; color: var(--text3);
    background: none; border: none; cursor: pointer;
    padding: 4px 0; margin-top: 4px;
    display: flex; align-items: center; gap: 5px;
    transition: color 0.15s;
}}
.expand-btn:hover {{ color: var(--text); }}
.expand-btn.open .xicon {{ transform: rotate(90deg); }}
.xicon {{ display: inline-block; transition: transform 0.2s; font-size: 10px; }}
.xbody {{ display: none; margin-top: 10px; padding-top: 10px; border-top: 1px solid var(--border); }}
.xbody.open {{ display: block; }}

/* Item rows */
.item-row {{
    display: flex; gap: 8px; padding: 4px 0;
    border-bottom: 1px solid var(--border);
    font-size: 12px;
}}
.item-row:last-child {{ border-bottom: none; }}
.row-num {{ color: var(--text3); font-family: 'IBM Plex Mono', monospace; font-size: 11px; min-width: 36px; }}
.row-title {{ color: var(--text2); }}
.item-more {{ font-size: 11px; color: var(--text3); padding: 4px 0; font-family: 'IBM Plex Mono', monospace; }}

/* Timeline */
.timeline {{ padding-left: 14px; }}
.tl-row {{ display: flex; gap: 12px; margin-bottom: 12px; position: relative; }}
.tl-row::before {{
    content: ''; position: absolute;
    left: -10px; top: 14px; bottom: -12px;
    width: 1px; background: var(--border2);
}}
.tl-row:last-child::before {{ display: none; }}
.tl-dot {{
    width: 8px; height: 8px; border-radius: 50%;
    margin-top: 5px; flex-shrink: 0;
    position: relative; left: -14px; margin-right: -8px;
}}
.tl-past {{ background: var(--text3); }}
.tl-now  {{ background: var(--green); box-shadow: 0 0 0 3px var(--green2); }}
.tl-date {{ font-size: 10px; color: var(--text3); margin-bottom: 2px; }}
.tl-evt  {{ font-size: 12px; color: var(--text2); }}

/* Pin button */
.pin-btn {{
    background: none; border: 1px solid var(--border);
    color: var(--text3); cursor: pointer;
    font-size: 14px; width: 26px; height: 26px;
    border-radius: 4px; display: flex; align-items: center;
    justify-content: center; transition: all 0.15s;
    line-height: 1;
}}
.pin-btn:hover {{ border-color: var(--green); color: var(--green); }}
.pin-btn.pinned {{ border-color: var(--green); color: var(--green); background: var(--green2); }}

.empty {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 12px; color: var(--text3);
    padding: 24px 16px;
    border: 1px dashed var(--border);
    border-radius: 8px; text-align: center;
}}

/* ── Right Column ───────────────────────────────────────────── */
.right-col {{
    display: flex; flex-direction: column;
    border-left: 1px solid var(--border);
    background: var(--bg2);
    overflow: hidden;
}}

/* Pinboard */
.pinboard {{
    flex: 1; overflow-y: auto;
    border-bottom: 1px solid var(--border);
    display: flex; flex-direction: column;
    min-height: 0;
}}
.panel-header {{
    padding: 10px 14px;
    border-bottom: 1px solid var(--border);
    display: flex; align-items: center; gap: 8px;
    background: var(--bg2);
    position: sticky; top: 0; z-index: 5;
    flex-shrink: 0;
}}
.panel-header-title {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px; font-weight: 500;
    color: var(--green); letter-spacing: 0.08em;
    text-transform: uppercase; flex: 1;
}}
.panel-header-count {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 10px; color: var(--text3);
}}
.pinboard-body {{ padding: 10px 12px; flex: 1; overflow-y: auto; }}
.pin-card {{
    background: var(--bg3);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 10px 12px;
    margin-bottom: 8px;
}}
.pin-card-title {{ font-size: 12px; font-weight: 500; color: var(--text); margin-bottom: 4px; line-height: 1.4; }}
.pin-card-date {{ font-family: 'IBM Plex Mono', monospace; font-size: 10px; color: var(--text3); margin-bottom: 6px; }}
.pin-note {{
    width: 100%; background: var(--bg4);
    border: 1px solid var(--border); color: var(--text2);
    font-family: 'IBM Plex Sans', sans-serif; font-size: 11px;
    padding: 5px 8px; border-radius: 4px; resize: none;
    margin-top: 4px; line-height: 1.5;
}}
.pin-note:focus {{ outline: none; border-color: var(--green); }}
.pin-card-actions {{ display: flex; justify-content: flex-end; margin-top: 6px; }}
.unpin-btn {{
    font-size: 10px; color: var(--text3);
    background: none; border: none; cursor: pointer;
    font-family: 'IBM Plex Mono', monospace;
    padding: 2px 6px; border-radius: 3px;
    transition: color 0.15s;
}}
.unpin-btn:hover {{ color: var(--red); }}
.pinboard-empty {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px; color: var(--text3);
    text-align: center; padding: 24px 12px;
    line-height: 1.8;
}}

/* AI Chat */
.ai-chat {{
    height: 45%;
    display: flex; flex-direction: column;
    flex-shrink: 0;
}}
.chat-messages {{
    flex: 1; overflow-y: auto;
    padding: 10px 12px;
}}
.chat-msg {{
    margin-bottom: 10px;
    font-size: 12px; line-height: 1.65;
}}
.chat-msg.user {{ color: var(--blue); }}
.chat-msg.assistant {{ color: var(--text2); }}
.chat-msg.assistant strong {{ color: var(--text); }}
.chat-msg-label {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 9px; color: var(--text3);
    margin-bottom: 3px; letter-spacing: 0.06em;
    text-transform: uppercase;
}}
.chat-msg-text {{
    background: var(--bg3);
    border-radius: 6px;
    padding: 8px 10px;
    border: 1px solid var(--border);
}}
.chat-msg.user .chat-msg-text {{ border-color: rgba(59,130,246,0.2); }}
.chat-msg.assistant .chat-msg-text {{ border-color: var(--border); }}
.chat-input-area {{
    padding: 10px 12px;
    border-top: 1px solid var(--border);
    flex-shrink: 0;
}}
.chat-key-row {{
    display: flex; gap: 6px; margin-bottom: 8px;
}}
.chat-key-input {{
    flex: 1; background: var(--bg3);
    border: 1px solid var(--border); color: var(--text2);
    font-family: 'IBM Plex Mono', monospace; font-size: 11px;
    padding: 5px 8px; border-radius: 4px;
}}
.chat-key-input:focus {{ outline: none; border-color: var(--blue); }}
.chat-key-btn {{
    font-family: 'IBM Plex Mono', monospace; font-size: 11px;
    background: var(--blue2); color: var(--blue);
    border: 1px solid rgba(59,130,246,0.3);
    padding: 5px 10px; border-radius: 4px; cursor: pointer;
    white-space: nowrap;
}}
.chat-input-row {{ display: flex; gap: 6px; }}
.chat-input {{
    flex: 1; background: var(--bg3);
    border: 1px solid var(--border); color: var(--text);
    font-family: 'IBM Plex Sans', sans-serif; font-size: 12px;
    padding: 7px 10px; border-radius: 4px;
    resize: none;
}}
.chat-input:focus {{ outline: none; border-color: var(--green); }}
.chat-send {{
    background: var(--green2); color: var(--green);
    border: 1px solid rgba(0,200,150,0.3);
    font-family: 'IBM Plex Mono', monospace; font-size: 11px;
    padding: 0 12px; border-radius: 4px; cursor: pointer;
    transition: all 0.15s; white-space: nowrap;
    align-self: flex-end; height: 34px;
}}
.chat-send:hover {{ background: rgba(0,200,150,0.2); }}
.chat-send:disabled {{ opacity: 0.4; cursor: not-allowed; }}
.chat-thinking {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px; color: var(--text3);
    padding: 4px 0; display: none;
}}
.chat-thinking.show {{ display: block; }}

/* ── Mobile ─────────────────────────────────────────────────── */
@media (max-width: 768px) {{
    :root {{
        --sidebar-w: 100%;
        --right-w: 100%;
        --header-h: 48px;
    }}

    html, body {{ overflow: auto; height: auto; }}

    .layout {{
        display: flex;
        flex-direction: column;
        height: auto;
        min-height: 100vh;
        padding-top: var(--header-h);
    }}

    /* Sidebar becomes horizontal scrollable tab strip */
    .sidebar {{
        order: 3;
        position: fixed;
        bottom: 0; left: 0; right: 0;
        flex-direction: row;
        overflow-x: auto;
        overflow-y: hidden;
        padding: 0 8px;
        height: 52px;
        border-right: none;
        border-top: 1px solid var(--border);
        z-index: 100;
        background: var(--bg2);
        align-items: center;
        gap: 4px;
    }}
    .sidebar-section {{
        display: flex;
        flex-direction: row;
        gap: 4px;
        padding: 0;
        margin: 0;
        align-items: center;
    }}
    .sidebar-label, .sidebar-divider {{ display: none; }}
    .nav-item {{
        flex-direction: column;
        padding: 6px 10px;
        font-size: 10px;
        gap: 2px;
        border-radius: 6px;
        white-space: nowrap;
        min-width: 60px;
        text-align: center;
        margin: 0;
    }}
    .nav-item::before {{ display: none; }}
    .nav-item.active {{ border-color: rgba(0,200,150,0.3); }}
    .nav-icon {{ font-size: 16px; width: auto; }}
    .nav-count {{ display: none; }}
    .nav-soon {{ font-size: 8px; }}

    /* Main takes full width, add bottom padding for tab bar */
    .main {{
        order: 1;
        width: 100%;
        padding-bottom: 52px;
        min-height: 60vh;
    }}

    /* Right column stacks below main */
    .right-col {{
        order: 2;
        border-left: none;
        border-top: 1px solid var(--border);
        height: auto;
        flex-direction: column;
        margin-bottom: 52px;
    }}
    .pinboard {{
        max-height: 300px;
        min-height: 120px;
    }}
    .ai-chat {{
        height: 360px;
    }}

    /* Header compact */
    .header-meta {{ display: none; }}
    .header-logo {{ font-size: 12px; }}

    /* Cards full width */
    .card {{ margin-bottom: 8px; }}
}}
</style>
</head>
<body>

<!-- ═══ HEADER ═══════════════════════════════════════════════════════ -->
<header class="header">
    <div class="header-logo">CHICO<span> · </span>SCRAPER</div>
    <div class="header-spacer"></div>
    <div class="header-meta">
        <span class="live-dot"></span>
        <span>Updated {updated_fmt}</span>
        <span style="color:var(--border2)">|</span>
        <span>{n_meetings} meetings · {n_bills} tracked · {n_leg} bills</span>
    </div>
</header>

<!-- ═══ LAYOUT ════════════════════════════════════════════════════════ -->
<div class="layout">

    <!-- ── LEFT SIDEBAR ── -->
    <nav class="sidebar">
        <div class="sidebar-section">
            <div class="sidebar-label">Local</div>
            <div class="nav-item active" onclick="showPanel('council', this)">
                <span class="nav-icon">⬡</span>
                <span class="nav-label">City Council</span>
                <span class="nav-count">{n_meetings}</span>
            </div>
            <div class="nav-item" onclick="showPanel('bills', this)">
                <span class="nav-icon">↻</span>
                <span class="nav-label">Bill Tracker</span>
                <span class="nav-count">{n_bills}</span>
            </div>
        </div>

        <hr class="sidebar-divider">

        <div class="sidebar-section">
            <div class="sidebar-label">State</div>
            <div class="nav-item" onclick="showPanel('legislation', this)">
                <span class="nav-icon">◈</span>
                <span class="nav-label">CA Legislation</span>
                <span class="nav-count">{n_leg}</span>
            </div>
        </div>

        <hr class="sidebar-divider">

        <div class="sidebar-section">
            <div class="sidebar-label">Federal · Coming Soon</div>
            <div class="nav-item" style="opacity:0.4; cursor:default;">
                <span class="nav-icon">◇</span>
                <span class="nav-label">Congress</span>
                <span class="nav-soon">SOON</span>
            </div>
            <div class="nav-item" style="opacity:0.4; cursor:default;">
                <span class="nav-icon">◇</span>
                <span class="nav-label">Agency Policy</span>
                <span class="nav-soon">SOON</span>
            </div>
            <div class="nav-item" style="opacity:0.4; cursor:default;">
                <span class="nav-icon">◇</span>
                <span class="nav-label">Police Scanner</span>
                <span class="nav-soon">SOON</span>
            </div>
            <div class="nav-item" style="opacity:0.4; cursor:default;">
                <span class="nav-icon">◇</span>
                <span class="nav-label">Local Events</span>
                <span class="nav-soon">SOON</span>
            </div>
        </div>
    </nav>

    <!-- ── CENTER MAIN ── -->
    <main class="main">
        <!-- Council panel -->
        <div id="panel-council" class="panel active">
            <div class="main-header">
                <div>
                    <div class="main-title">City Council Meetings</div>
                    <div class="main-subtitle mono">Chico, CA · Granicus RSS · {n_meetings} meetings</div>
                </div>
            </div>
            <div class="main-body">{council_html}</div>
        </div>

        <!-- Bill tracker panel -->
        <div id="panel-bills" class="panel">
            <div class="main-header">
                <div>
                    <div class="main-title">Bill Tracker</div>
                    <div class="main-subtitle mono">Recurring agenda items across meetings · {n_bills} tracked</div>
                </div>
            </div>
            <div class="main-body">{bill_html}</div>
        </div>

        <!-- CA Legislation panel -->
        <div id="panel-legislation" class="panel">
            <div class="main-header">
                <div>
                    <div class="main-title">California Legislation</div>
                    <div class="main-subtitle mono">LegiScan · Gemini relevance filter · {n_leg} flagged for Butte County</div>
                </div>
            </div>
            <div class="main-body">{leg_html}</div>
        </div>
    </main>

    <!-- ── RIGHT COLUMN ── -->
    <div class="right-col">

        <!-- Pinboard -->
        <div class="pinboard">
            <div class="panel-header">
                <span class="panel-header-title">⊕ Pinboard</span>
                <span class="panel-header-count" id="pin-count">0 pins</span>
            </div>
            <div class="pinboard-body" id="pinboard-body">
                <div class="pinboard-empty" id="pinboard-empty">
                    No pins yet.<br>
                    Click ⊕ on any card<br>to pin it here.
                </div>
            </div>
        </div>

        <!-- AI Chat -->
        <div class="ai-chat">
            <div class="panel-header">
                <span class="panel-header-title">◈ AI Analysis</span>
                <span class="panel-header-count">Gemini</span>
            </div>
            <div class="chat-messages" id="chat-messages">
                <div class="chat-msg assistant">
                    <div class="chat-msg-label">System</div>
                    <div class="chat-msg-text">Ask me anything about the data on this dashboard. I can analyze council items, legislation, and help you find story angles.</div>
                </div>
            </div>
            <div class="chat-input-area">
                <div class="chat-key-row" id="key-row">
                    <input class="chat-key-input" id="gemini-key" type="password" placeholder="Enter Gemini API key…">
                    <button class="chat-key-btn" onclick="saveKey()">Save</button>
                </div>
                <div class="chat-input-row">
                    <textarea class="chat-input" id="chat-input" rows="2" placeholder="Ask about the data…" onkeydown="chatKeydown(event)"></textarea>
                    <button class="chat-send" id="chat-send" onclick="sendChat()" disabled>Send</button>
                </div>
                <div class="chat-thinking" id="chat-thinking">Gemini is thinking…</div>
            </div>
        </div>
    </div>
</div>

<script>
// ── Dashboard data available to Gemini ───────────────────────────────
const DASHBOARD_DATA = {{
    meetings: {js_meetings},
    bills: {js_bills},
    legislation: {js_legislation},
    updated: "{updated_fmt}",
    location: "Chico, CA / Butte County"
}};

// ── Panel switching ───────────────────────────────────────────────────
function showPanel(id, navEl) {{
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    document.getElementById('panel-' + id).classList.add('active');
    navEl.classList.add('active');
}}

// ── Expand/collapse ───────────────────────────────────────────────────
function xpand(id, btn) {{
    const el = document.getElementById(id);
    const open = el.classList.toggle('open');
    btn.classList.toggle('open', open);
}}

// ── Pinboard ──────────────────────────────────────────────────────────
function makeId(str) {{
    // Safe hash — works with any Unicode string unlike btoa()
    let hash = 0;
    for (let i = 0; i < str.length; i++) {{
        hash = ((hash << 5) - hash) + str.charCodeAt(i);
        hash |= 0;
    }}
    return Math.abs(hash).toString(36).slice(0, 12);
}}

let pins = JSON.parse(localStorage.getItem('cpt_pins') || '[]');

function savePins() {{
    localStorage.setItem('cpt_pins', JSON.stringify(pins));
    renderPins();
}}

function pinItem(btn) {{
    const title = btn.dataset.title;
    const date  = btn.dataset.date;
    const link  = btn.dataset.link;
    const id    = makeId(title);

    if (pins.find(p => p.id === id)) {{
        pins = pins.filter(p => p.id !== id);
        btn.classList.remove('pinned');
        savePins();
        return;
    }}

    pins.unshift({{ id, title, date, link, note: '', pinned_at: new Date().toISOString() }});
    btn.classList.add('pinned');
    savePins();
}}

function unpin(id) {{
    pins = pins.filter(p => p.id !== id);
    savePins();
}}

function updateNote(id, val) {{
    const pin = pins.find(p => p.id === id);
    if (pin) {{ pin.note = val; savePins(); }}
}}

function renderPins() {{
    const body  = document.getElementById('pinboard-body');
    const empty = document.getElementById('pinboard-empty');
    const count = document.getElementById('pin-count');
    count.textContent = pins.length + ' pin' + (pins.length !== 1 ? 's' : '');

    if (!pins.length) {{
        body.innerHTML = '';
        body.appendChild(empty || document.createElement('div'));
        if (empty) empty.style.display = 'block';
        return;
    }}
    if (empty) empty.style.display = 'none';

    body.innerHTML = pins.map(p => `
        <div class="pin-card" id="pin-${{p.id}}">
            <div class="pin-card-title">${{p.title}}</div>
            <div class="pin-card-date mono">${{p.date}}${{p.link ? ` · <a href="${{p.link}}" target="_blank">source ↗</a>` : ''}}</div>
            <textarea class="pin-note" rows="2" placeholder="Add notes…"
                onchange="updateNote('${{p.id}}', this.value)">${{p.note}}</textarea>
            <div class="pin-card-actions">
                <button class="unpin-btn" onclick="unpin('${{p.id}}')">unpin ×</button>
            </div>
        </div>
    `).join('');

    // Restore pinned button states
    document.querySelectorAll('.pin-btn').forEach(btn => {{
        const id = makeId(btn.dataset.title);
        if (pins.find(p => p.id === id)) btn.classList.add('pinned');
    }});
}}

// ── Gemini Chat ───────────────────────────────────────────────────────
let geminiKey = localStorage.getItem('cpt_gemini_key') || '';

function saveKey() {{
    geminiKey = document.getElementById('gemini-key').value.trim();
    if (geminiKey) {{
        localStorage.setItem('cpt_gemini_key', geminiKey);
        document.getElementById('key-row').style.display = 'none';
        document.getElementById('chat-send').disabled = false;
        addMsg('system', 'API key saved. Ready to analyze dashboard data.');
    }}
}}

function chatKeydown(e) {{
    if (e.key === 'Enter' && !e.shiftKey) {{
        e.preventDefault();
        sendChat();
    }}
}}

function addMsg(role, text) {{
    const wrap = document.getElementById('chat-messages');
    const label = role === 'user' ? 'You' : role === 'assistant' ? 'Gemini' : 'System';
    const div = document.createElement('div');
    div.className = 'chat-msg ' + (role === 'user' ? 'user' : 'assistant');
    div.innerHTML = `<div class="chat-msg-label">${{label}}</div><div class="chat-msg-text">${{text}}</div>`;
    wrap.appendChild(div);
    wrap.scrollTop = wrap.scrollHeight;
}}

async function sendChat() {{
    if (!geminiKey) {{ addMsg('system', 'Please enter your Gemini API key first.'); return; }}
    const input = document.getElementById('chat-input');
    const q = input.value.trim();
    if (!q) return;

    input.value = '';
    addMsg('user', q);

    const thinking = document.getElementById('chat-thinking');
    const sendBtn  = document.getElementById('chat-send');
    thinking.classList.add('show');
    sendBtn.disabled = true;

    const systemPrompt = `You are an AI assistant embedded in the Chico Scraper, a personal newsroom intelligence dashboard for a journalist covering Chico, CA and Butte County. You have access to the current dashboard data shown below, including meeting titles, dates, agenda items, descriptions, and source links. You also have Google Search available — use it to look up the actual content behind any links, find recent news about agenda items, or get more detail on anything in the data. Answer the journalist's questions concisely and helpfully. Focus on story angles, connections between items, and local impact.

Current dashboard data:
${{JSON.stringify(DASHBOARD_DATA, null, 2)}}`;

    try {{
        const resp = await fetch(
            'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=' + geminiKey,
            {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{
                    contents: [
                        {{ role: 'user', parts: [{{ text: systemPrompt + '\\n\\nJournalist question: ' + q }}] }}
                    ],
                    tools: [{{ googleSearch: {{}} }}],
                    generationConfig: {{ temperature: 0.7, maxOutputTokens: 800 }}
                }})
            }}
        );
        const data = await resp.json();
        if (data.error) {{
            addMsg('assistant', '⚠ Gemini error: ' + data.error.message);
        }} else {{
            const text = data?.candidates?.[0]?.content?.parts?.[0]?.text || 'No response received.';
            addMsg('assistant', text.replace(/\\n/g, '<br>'));
        }}
    }} catch(e) {{
        addMsg('assistant', '⚠ Request failed: ' + e.message + '. Check your API key and try again.');
    }}

    thinking.classList.remove('show');
    sendBtn.disabled = false;
}}

// ── Init ──────────────────────────────────────────────────────────────
(function init() {{
    if (geminiKey) {{
        document.getElementById('key-row').style.display = 'none';
        document.getElementById('chat-send').disabled = false;
        document.getElementById('gemini-key').value = geminiKey;
    }}
    renderPins();
}})();
</script>
</body>
</html>"""


def main():
    if not STATE_FILE.exists():
        print(f"No state.json found at {{STATE_FILE}} — generating empty dashboard.")
        state = {{"meetings": [], "bills": [], "state_legislation": [], "last_updated": ""}}
    else:
        state = json.loads(STATE_FILE.read_text())
    html = build(state)
    OUTPUT.write_text(html, encoding="utf-8")
    print(f"Dashboard written → {{OUTPUT}}")


if __name__ == "__main__":
    main()
