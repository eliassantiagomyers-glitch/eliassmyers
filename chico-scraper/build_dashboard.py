"""
build_dashboard.py
Reads data/state.json produced by scraper.py and generates index.html —
the Chico Policy Tracker dashboard.
"""

import json
from datetime import datetime
from pathlib import Path

STATE_FILE = Path(__file__).parent / "data" / "state.json"
OUTPUT     = Path(__file__).parent / "index.html"

STATUS_BADGE = {
    "active":    ("badge-red",   "Active"),
    "passed":    ("badge-green", "Passed"),
    "tabled":    ("badge-amber", "Tabled / Continued"),
    "scheduled": ("badge-info",  "Scheduled"),
    "unknown":   ("badge-gold",  "Ongoing"),
}


def fmt_date(d: str) -> str:
    try:
        return datetime.strptime(d, "%Y-%m-%d").strftime("%b %-d, %Y")
    except Exception:
        return d


def badge(cls: str, text: str) -> str:
    return f'<span class="badge {cls}">{text}</span>'


def render_bill_card(bill: dict, idx: int) -> str:
    color_cls, label = STATUS_BADGE.get(bill["status"], ("badge-gold", "Ongoing"))
    appearances = bill["appearances"]
    count = bill["meeting_count"]

    timeline_html = ""
    for i, ap in enumerate(sorted(appearances, key=lambda x: x["date"])):
        dot_cls = "now" if i == len(appearances) - 1 else "past"
        sub = f'<div class="tl-sub">{ap["meeting_title"]}</div>' if ap.get("meeting_title") else ""
        timeline_html += f"""
          <div class="tl-item">
            <div class="tl-dot {dot_cls}"></div>
            <div class="tl-date">{fmt_date(ap["date"])}</div>
            <div class="tl-event">{ap.get("title_seen", bill["canonical_title"])}</div>
            {sub}
          </div>"""

    expand_id = f"bill-{idx}"
    return f"""
    <div class="card">
      <div class="card-row">
        <span class="card-num">{count} mtgs</span>
        <span class="card-title">{bill["canonical_title"]}</span>
      </div>
      <div class="card-meta">
        {badge(color_cls, label)}
        {badge("badge-slate", f'First: {fmt_date(bill["first_seen"])}')}
        {badge("badge-slate", f'Last: {fmt_date(bill["last_seen"])}')}
      </div>
      <button class="expand-btn" onclick="toggleExpand('{expand_id}', this)">
        &#8964; Show timeline ({count} appearances)
      </button>
      <div class="expand-content" id="{expand_id}">
        <div class="tl">{timeline_html}</div>
      </div>
    </div>"""


def render_meeting_card(meeting: dict, idx: int) -> str:
    has_min  = meeting.get("has_minutes") or meeting.get("type") == "minutes"
    date_str = fmt_date(meeting["date"])
    title    = meeting.get("title", f"Meeting {date_str}")
    link     = meeting.get("link", "#")
    items    = meeting.get("items") or meeting.get("agenda_items", [])

    items_html = ""
    for item in items[:12]:
        num = f'<span class="card-num">{item["num"]}</span>' if item.get("num") else ""
        items_html += f'<div class="card-row" style="margin-bottom:4px">{num}<span class="card-title" style="font-size:13px;font-weight:400">{item["title"]}</span></div>'
    if len(items) > 12:
        items_html += f'<div class="card-desc">and {len(items) - 12} more items</div>'

    min_badge = badge("badge-green", "&#10003; Minutes available") if has_min else badge("badge-amber", "Agenda only")
    expand_id = f"mtg-{idx}"

    expand_section = ""
    if items:
        expand_section = f"""
      <button class="expand-btn" onclick="toggleExpand('{expand_id}', this)">
        &#8964; Show items ({len(items)})
      </button>
      <div class="expand-content" id="{expand_id}">{items_html}</div>"""

    source_link = f'<a class="source-link" href="{link}" target="_blank">&#8599; Granicus source</a>' if link and link != "#" else ""

    return f"""
    <div class="card">
      <div class="card-row">
        <span class="card-num">{date_str}</span>
        <span class="card-title">
          <a href="{link}" target="_blank" style="color:inherit;text-decoration:none">{title} &#8599;</a>
        </span>
      </div>
      <div class="card-meta">
        {min_badge}
        {source_link}
      </div>
      {expand_section}
    </div>"""


def render_recent_item(it: dict) -> str:
    num_html = f'<span class="card-num">{it["num"]}</span>' if it.get("num") else ""
    return (
        f'<div class="card">'
        f'<div class="card-row">{num_html}'
        f'<span class="card-title">{it["title"]}</span>'
        f'</div></div>'
    )


def build(state: dict) -> str:
    meetings = state.get("meetings", [])
    bills    = state.get("bills", [])
    updated  = state.get("last_updated", "")

    try:
        updated_fmt = datetime.fromisoformat(updated).strftime("%b %-d, %Y at %-I:%M %p UTC")
    except Exception:
        updated_fmt = updated or "unknown"

    recent_meeting = meetings[0] if meetings else {}
    recent_date    = fmt_date(recent_meeting.get("date", "")) if recent_meeting else "—"
    recent_title   = recent_meeting.get("title", "—")
    recent_title_short = recent_title[:50] + ("…" if len(recent_title) > 50 else "")

    next_meeting  = next(
        (m for m in reversed(meetings) if m.get("date", "") > datetime.now().strftime("%Y-%m-%d")),
        None
    )
    next_date_fmt = fmt_date(next_meeting["date"]) if next_meeting else "TBD"
    tracked_active = sum(1 for b in bills if b["status"] == "active")

    meeting_cards_html = "\n".join(render_meeting_card(m, i) for i, m in enumerate(meetings))

    bill_cards_html = (
        "\n".join(render_bill_card(b, i) for i, b in enumerate(bills))
        if bills else
        '<div class="lead">No recurring agenda items detected yet. Bill tracking improves as more meetings are scraped.</div>'
    )

    recent_items = recent_meeting.get("items") or recent_meeting.get("agenda_items", [])
    recent_cards_html = (
        "\n".join(render_recent_item(it) for it in recent_items[:20])
        or '<div class="lead">No agenda items found for the most recent meeting.</div>'
    )

    has_min_recent = recent_meeting.get("has_minutes") or recent_meeting.get("type") == "minutes"
    minutes_note   = "Minutes are available." if has_min_recent else "Minutes not yet published."

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Chico Scraper</title>
<style>
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

:root {{
  --gold: #c9a84c;
  --gold-bg: rgba(201,168,76,0.12);
  --dark-header: #0f1923;
  --bg: #f4f1ec;
  --surface: #ffffff;
  --surface2: #eeebe4;
  --border: rgba(0,0,0,0.08);
  --border2: rgba(0,0,0,0.14);
  --text: #1a1814;
  --text2: #6b6660;
  --text3: #9c9691;
  --green: #2a5c3f;
  --green-bg: #e6f0ea;
  --red: #8b2020;
  --red-bg: #f5e8e8;
  --amber: #7a4f00;
  --amber-bg: #fdf3e0;
  --blue: #1a3d6b;
  --blue-bg: #e8eef7;
}}

body {{
  font-family: -apple-system, 'Helvetica Neue', Arial, sans-serif;
  background: var(--bg);
  color: var(--text);
  font-size: 15px;
  line-height: 1.65;
  min-height: 100vh;
}}

.site-header {{
  background: var(--dark-header);
  padding: 2.5rem 2rem 2rem;
  position: relative;
}}
.site-header::before {{
  content: '';
  position: absolute;
  left: 0; top: 0; bottom: 0;
  width: 3px;
  background: var(--gold);
}}
.header-inner {{ max-width: 920px; margin: 0 auto; }}
.header-eyebrow {{
  font-size: 11px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--gold);
  font-weight: 500;
  margin-bottom: 0.5rem;
}}
.header-title {{
  font-size: clamp(1.6rem, 4vw, 2.4rem);
  font-weight: 400;
  color: #f0ebe2;
  margin-bottom: 0.3rem;
  line-height: 1.15;
  letter-spacing: -0.01em;
}}
.header-desc {{
  font-size: 13px;
  color: #7a7570;
  margin-bottom: 1rem;
  max-width: 520px;
  line-height: 1.5;
}}
.update-pill {{
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: #7a7570;
  border: 0.5px solid #2a3540;
  border-radius: 20px;
  padding: 3px 11px;
}}
.live-dot {{
  width: 6px; height: 6px; border-radius: 50%;
  background: var(--gold);
  animation: blink 2s ease-in-out infinite;
}}
@keyframes blink {{ 0%,100%{{opacity:1;}} 50%{{opacity:0.3;}} }}

.container {{ max-width: 920px; margin: 0 auto; padding: 2rem 2rem 4rem; }}

.stats-row {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 10px;
  margin-bottom: 2rem;
}}
.stat {{
  background: var(--surface);
  border: 0.5px solid var(--border);
  border-radius: 10px;
  padding: 1rem 1.1rem;
}}
.stat-label {{ font-size: 10px; color: var(--text3); letter-spacing: 0.06em; text-transform: uppercase; margin-bottom: 4px; }}
.stat-val {{ font-size: 1.9rem; font-weight: 400; color: var(--text); line-height: 1; }}
.stat-val.sm {{ font-size: 1.3rem; padding-top: 4px; }}
.stat-sub {{ font-size: 11px; color: var(--text2); margin-top: 3px; }}

.tabs {{
  display: flex;
  flex-wrap: wrap;
  border-bottom: 0.5px solid var(--border);
  margin-bottom: 1.5rem;
}}
.tab-btn {{
  font-size: 13px;
  font-weight: 400;
  padding: 8px 15px;
  border: none;
  background: none;
  color: var(--text2);
  cursor: pointer;
  border-bottom: 2px solid transparent;
  margin-bottom: -0.5px;
  white-space: nowrap;
  font-family: inherit;
  transition: color 0.15s;
  display: flex;
  align-items: center;
  gap: 6px;
}}
.tab-btn:hover {{ color: var(--text); }}
.tab-btn.active {{ color: var(--text); border-bottom-color: var(--gold); font-weight: 500; }}
.tab-pill {{
  font-size: 10px;
  background: var(--surface2);
  color: var(--text3);
  border-radius: 20px;
  padding: 1px 7px;
}}
.tab-soon {{
  font-size: 10px;
  background: var(--gold-bg);
  color: var(--gold);
  border-radius: 20px;
  padding: 1px 7px;
}}
.panel {{ display: none; }}
.panel.active {{ display: block; }}

.card {{
  background: var(--surface);
  border: 0.5px solid var(--border);
  border-radius: 10px;
  padding: 1rem 1.2rem;
  margin-bottom: 0.75rem;
  transition: border-color 0.15s;
}}
.card:hover {{ border-color: var(--border2); }}
.card-row {{
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 6px;
}}
.card-num {{
  font-size: 11px;
  color: var(--text3);
  min-width: 44px;
  padding-top: 2px;
  font-weight: 500;
  white-space: nowrap;
}}
.card-title {{
  font-size: 14px;
  font-weight: 500;
  color: var(--text);
  flex: 1;
  line-height: 1.35;
}}
.card-desc {{
  font-size: 13px;
  color: var(--text2);
  line-height: 1.6;
  margin-top: 4px;
}}
.card-meta {{
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin-top: 6px;
  align-items: center;
}}
.source-link {{
  font-size: 12px;
  color: var(--blue);
  text-decoration: none;
}}
.source-link:hover {{ text-decoration: underline; }}

.badge {{
  font-size: 11px;
  font-weight: 500;
  padding: 2px 9px;
  border-radius: 20px;
  display: inline-flex;
  align-items: center;
  white-space: nowrap;
}}
.badge-green  {{ background: var(--green-bg);  color: var(--green);  }}
.badge-red    {{ background: var(--red-bg);    color: var(--red);    }}
.badge-amber  {{ background: var(--amber-bg);  color: var(--amber);  }}
.badge-info   {{ background: var(--blue-bg);   color: var(--blue);   }}
.badge-slate  {{ background: var(--surface2);  color: var(--text2);  }}
.badge-gold   {{ background: var(--gold-bg);   color: var(--gold);   }}

.expand-btn {{
  font-size: 12px;
  color: var(--text2);
  background: none;
  border: none;
  cursor: pointer;
  padding: 0;
  margin-top: 6px;
  font-family: inherit;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  transition: color 0.15s;
}}
.expand-btn:hover {{ color: var(--text); }}
.expand-content {{
  display: none;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 0.5px solid var(--border);
}}
.expand-content.open {{ display: block; }}

.lead {{
  font-size: 13px;
  color: var(--text2);
  line-height: 1.7;
  margin-bottom: 1.25rem;
  padding: 1rem 1.2rem;
  background: var(--surface);
  border: 0.5px solid var(--border);
  border-radius: 10px;
  border-left: 3px solid var(--gold);
}}
.lead strong {{ color: var(--text); font-weight: 500; }}

.tl {{ position: relative; padding-left: 20px; margin-top: 4px; }}
.tl::before {{
  content: '';
  position: absolute;
  left: 4px; top: 6px; bottom: 6px;
  width: 1px;
  background: var(--border2);
}}
.tl-item {{ position: relative; margin-bottom: 1rem; }}
.tl-dot {{
  position: absolute;
  left: -17px; top: 5px;
  width: 8px; height: 8px;
  border-radius: 50%;
  border: 1.5px solid var(--border2);
  background: var(--surface);
}}
.tl-dot.past {{ background: var(--text2); border-color: var(--text2); }}
.tl-dot.now  {{ background: var(--gold); border-color: var(--gold); box-shadow: 0 0 0 3px var(--gold-bg); }}
.tl-date  {{ font-size: 11px; color: var(--text3); margin-bottom: 1px; }}
.tl-event {{ font-size: 13px; color: var(--text); font-weight: 500; line-height: 1.4; }}
.tl-sub   {{ font-size: 12px; color: var(--text2); margin-top: 2px; }}

.section-label {{
  font-size: 10px;
  font-weight: 500;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--text3);
  margin-bottom: 0.875rem;
}}

.placeholder-card {{
  background: var(--surface2);
  border: 0.5px dashed var(--border2);
  border-radius: 10px;
  padding: 2rem 1.5rem;
  margin-bottom: 0.75rem;
  text-align: center;
  color: var(--text2);
}}
.placeholder-card p {{ font-size: 13px; line-height: 1.6; }}
.placeholder-card strong {{ color: var(--text); }}

.site-footer {{
  border-top: 0.5px solid var(--border);
  padding: 1.25rem 2rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 12px;
  color: var(--text3);
  max-width: 920px;
  margin: 0 auto;
}}
.site-footer a {{ color: var(--text2); text-decoration: none; }}
.site-footer a:hover {{ text-decoration: underline; }}

@media (max-width: 600px) {{
  .site-header {{ padding: 2rem 1.25rem 1.5rem; }}
  .container {{ padding: 1.25rem 1.25rem 3rem; }}
  .stats-row {{ grid-template-columns: repeat(2, 1fr); }}
  .tabs {{ overflow-x: auto; flex-wrap: nowrap; }}
}}
</style>
</head>
<body>

<header class="site-header">
  <div class="header-inner">
    <div class="header-eyebrow">Butte County &middot; California</div>
    <h1 class="header-title">Chico Scraper</h1>
    <p class="header-desc">City council activity, legislation, and policy decisions affecting Chico and Butte County &mdash; updated automatically.</p>
    <div class="update-pill">
      <span class="live-dot"></span>
      Last updated: {updated_fmt}
    </div>
  </div>
</header>

<div class="container">

  <div class="stats-row">
    <div class="stat">
      <div class="stat-label">Meetings tracked</div>
      <div class="stat-val">{len(meetings)}</div>
      <div class="stat-sub">agendas + minutes</div>
    </div>
    <div class="stat">
      <div class="stat-label">Recurring items</div>
      <div class="stat-val">{len(bills)}</div>
      <div class="stat-sub">{tracked_active} currently active</div>
    </div>
    <div class="stat">
      <div class="stat-label">Most recent</div>
      <div class="stat-val sm">{recent_date}</div>
      <div class="stat-sub">{recent_title_short}</div>
    </div>
    <div class="stat">
      <div class="stat-label">Next meeting</div>
      <div class="stat-val sm">{next_date_fmt}</div>
      <div class="stat-sub">per published agenda</div>
    </div>
  </div>

  <div class="tabs" role="tablist">
    <button class="tab-btn active" onclick="showTab('council', this)">
      Council <span class="tab-pill">{len(meetings)}</span>
    </button>
    <button class="tab-btn" onclick="showTab('bills', this)">
      Bill tracker <span class="tab-pill">{len(bills)}</span>
    </button>
    <button class="tab-btn" onclick="showTab('state', this)">
      State leg. <span class="tab-soon">Soon</span>
    </button>
    <button class="tab-btn" onclick="showTab('federal', this)">
      Federal <span class="tab-soon">Soon</span>
    </button>
    <button class="tab-btn" onclick="showTab('agency', this)">
      Agency policy <span class="tab-soon">Soon</span>
    </button>
  </div>

  <div id="panel-council" class="panel active">
    <div class="lead">
      <strong>{recent_title}</strong><br>
      Most recently published meeting &mdash; {recent_date}. {minutes_note}
    </div>
    <div class="section-label">Latest agenda items</div>
    {recent_cards_html}
    <div class="section-label" style="margin-top:2rem">All meetings</div>
    {meeting_cards_html}
  </div>

  <div id="panel-bills" class="panel">
    <div class="lead">
      Items appearing on <strong>multiple meeting agendas</strong> are tracked here as recurring bills.
      Detected by comparing agenda item titles across meetings.
      <strong>{len(bills)} recurring items</strong> found so far.
    </div>
    <div class="section-label">Tracked items &mdash; most recent first</div>
    {bill_cards_html}
  </div>

  <div id="panel-state" class="panel">
    <div class="section-label">California state legislation</div>
    <div class="placeholder-card">
      <p><strong>Coming soon.</strong> California bills and agency rules with relevance to Chico and Butte County, filtered via the LegiScan and CA Legislative APIs.</p>
    </div>
  </div>

  <div id="panel-federal" class="panel">
    <div class="section-label">Federal legislation</div>
    <div class="placeholder-card">
      <p><strong>Coming soon.</strong> Federal bills affecting housing, water, infrastructure, and agriculture in Butte County &mdash; via Congress.gov API.</p>
    </div>
  </div>

  <div id="panel-agency" class="panel">
    <div class="section-label">Agency policy changes</div>
    <div class="placeholder-card">
      <p><strong>Coming soon.</strong> Regulatory and policy changes from CalOES, EPA, CDFA, FEMA, and other agencies relevant to Butte County.</p>
    </div>
  </div>

</div>

<footer class="site-footer">
  <span>Source: <a href="https://chico-ca.granicus.com/ViewPublisher.php?view_id=2" target="_blank">Chico Granicus</a> &middot; Updated twice daily via GitHub Actions</span>
  <a href="https://github.com/eliassantiagomyers-glitch/Chico-scraper" target="_blank">GitHub &rarr;</a>
</footer>

<script>
function showTab(id, btn) {{
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(t => t.classList.remove('active'));
  document.getElementById('panel-' + id).classList.add('active');
  btn.classList.add('active');
}}
function toggleExpand(id, btn) {{
  const el = document.getElementById(id);
  el.classList.toggle('open');
}}
</script>
</body>
</html>"""


def main():
    if not STATE_FILE.exists():
        print(f"ERROR: {STATE_FILE} not found. Run scraper.py first.")
        return
    state = json.loads(STATE_FILE.read_text())
    html  = build(state)
    OUTPUT.write_text(html, encoding="utf-8")
    print(f"Dashboard written -> {OUTPUT}")


if __name__ == "__main__":
    main()
