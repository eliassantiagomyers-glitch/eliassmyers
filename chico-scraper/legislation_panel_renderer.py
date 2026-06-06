"""
legislation_panel_renderer.py

Drop-in replacement for render_legislation_cards() in build_dashboard.py.
Call render_legislation_panel(bills) and embed the result in the panel HTML.

Layout:
  - Left: grouped bill list (narrow cards, click to select)
  - Right: detail pane (updates on click)
  - Filter bar: keyword search + status filter + rep filter
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from legislation_priority import (
    group_and_sort,
    group_display_meta,
    TIER1_TOPICS,
    TIER2_TOPICS,
    DEAD_STATUSES,
)


STATUS_TAG = {
    "introduced": ("tag-blue",  "Introduced"),
    "committee":  ("tag-amber", "Committee"),
    "floor":      ("tag-green", "On Floor"),
    "active":     ("tag-blue",  "Active"),
    "passed":     ("tag-green", "Passed"),
    "failed":     ("tag-red",   "Failed"),
    "vetoed":     ("tag-red",   "Vetoed"),
}

VOTE_TAG = {
    "yes":        ("tag-green", "YES"),
    "no":         ("tag-red",   "NO"),
    "absent":     ("tag-dim",   "ABSENT"),
    "not_voting": ("tag-dim",   "NV"),
    "excused":    ("tag-dim",   "EXC"),
}

TIER_COLORS = {
    "rep":    ("var(--amber)",  "var(--amber2)"),
    "direct": ("var(--green)",  "var(--green2)"),
    "tier1":  ("var(--blue)",   "var(--blue2)"),
    "tier2":  ("var(--text2)",  "var(--bg4)"),
    "other":  ("var(--text3)",  "var(--bg3)"),
}


def _score_bar(score: int) -> str:
    """Render a tiny priority score bar."""
    pct = max(0, min(100, score))
    color = "var(--green)" if pct >= 60 else "var(--amber)" if pct >= 30 else "var(--text3)"
    return (
        f'<div class="score-bar-wrap" title="Priority score: {pct}/100">'
        f'<div class="score-bar-fill" style="width:{pct}%;background:{color}"></div>'
        f'</div>'
    )


def _status_tag(bill: dict) -> str:
    status = bill.get("status", "introduced")
    cls, label = STATUS_TAG.get(status, ("tag-dim", status.title()))
    return f'<span class="tag {cls}">{label}</span>'


def _rep_badge(bill: dict) -> str:
    if not bill.get("_is_rep_bill"):
        return ""
    sponsors = bill.get("sponsors", [])
    name = ""
    for s in sponsors:
        sl = s.lower()
        if "gallagher" in sl:
            name = "Gallagher"
            break
        if "dahle" in sl:
            name = "Dahle"
            break
    label = f"◈ {name}" if name else "◈ Rep"
    return f'<span class="tag tag-rep">{label}</span>'


def _direct_badge(bill: dict) -> str:
    if not bill.get("_is_butte_direct"):
        return ""
    return '<span class="tag tag-direct">📍 Butte</span>'


def _topic_chips(bill: dict) -> str:
    topics = bill.get("_topics_detected", [])
    chips = []
    for t in topics[:2]:
        short = t.split("/")[0].strip()[:14]
        chips.append(f'<span class="topic-chip">{short}</span>')
    return "".join(chips)


def render_bill_card_mini(bill: dict, idx: int) -> str:
    """Narrow left-column card for the list."""
    bnum = bill.get("bill_number", "")
    title = bill.get("title", "")
    score = bill.get("_priority_score", 0)
    status = bill.get("status", "introduced")
    is_dead = status in DEAD_STATUSES

    stcls, stlbl = STATUS_TAG.get(status, ("tag-dim", status.title()))
    dead_dim = ' style="opacity:0.55"' if is_dead else ""

    return f"""<div class="bill-row" id="bill-row-{idx}" onclick="selectBill({idx})" data-idx="{idx}"
     data-status="{status}"
     data-rep="{str(bill.get('_is_rep_bill', False)).lower()}"
     data-topics="{','.join(bill.get('_topics_detected', []))}"
     data-title="{title.lower().replace('"', '')}"
     data-number="{bnum.lower()}"{dead_dim}>
  <div class="bill-row-top">
    <span class="mono bill-num-sm">{bnum}</span>
    <span class="tag {stcls}" style="font-size:9px;padding:1px 5px">{stlbl}</span>
    {_rep_badge(bill)}
    {_direct_badge(bill)}
  </div>
  <div class="bill-row-title">{title[:90]}{"…" if len(title) > 90 else ""}</div>
  {_score_bar(score)}
  <div class="bill-row-topics">{_topic_chips(bill)}</div>
</div>"""


def render_bill_detail(bill: dict) -> str:
    """Right-column detail pane content for one bill."""
    bnum   = bill.get("bill_number", "")
    title  = bill.get("title", "")
    url    = bill.get("url", "#")
    expl   = bill.get("explanation", "")
    angle  = bill.get("local_angle", "")
    action = bill.get("last_action", "")
    adate  = bill.get("last_action_date", "")
    committee = bill.get("committee", "")
    sponsors  = bill.get("sponsors", [])
    rep_votes = bill.get("rep_votes", {})
    rep_notes = bill.get("rep_vote_notes", {})
    timeline  = bill.get("timeline", [])
    topics    = bill.get("_topics_detected", [])
    score     = bill.get("_priority_score", 0)
    status    = bill.get("status", "introduced")
    status_label = bill.get("status_label", status.title())

    stcls, _ = STATUS_TAG.get(status, ("tag-dim", ""))

    # Topic tags
    topic_tags = "".join(
        f'<span class="tag tag-dim" style="font-size:10px">{t.split("/")[0].strip()}</span>'
        for t in topics
    )

    # Rep vote block
    rep_html = ""
    for rep_name, vote in rep_votes.items():
        vcls, vlbl = VOTE_TAG.get(vote.lower(), ("tag-dim", vote.upper()))
        note = rep_notes.get(rep_name, "")
        role = "AD-3" if "Gallagher" in rep_name else "SD-1"
        rep_html += f"""<div class="rep-row-detail">
      <div class="rep-info">
        <span class="rep-name">{rep_name}</span>
        <span class="mono dim" style="font-size:10px">{role}</span>
      </div>
      <span class="tag {vcls}">{vlbl}</span>
      {"<div class='rep-note dim'>" + note + "</div>" if note else ""}
    </div>"""
    if not rep_html:
        rep_html = '<div class="dim" style="font-size:11px;font-family:\'IBM Plex Mono\',monospace">No recorded votes yet for Gallagher or Dahle.</div>'

    # Timeline
    tl_html = ""
    for j, ev in enumerate(timeline):
        dot = "tl-now" if j == len(timeline) - 1 else "tl-past"
        tl_html += f"""<div class="tl-row">
      <div class="tl-dot {dot}"></div>
      <div>
        <div class="mono tl-date">{ev.get('date','')}</div>
        <div class="tl-evt">{ev.get('description','')}</div>
      </div>
    </div>"""

    sponsor_str = f'<div class="detail-meta-row"><span class="detail-label">Sponsor</span><span>{", ".join(sponsors[:3])}</span></div>' if sponsors else ""
    committee_str = f'<div class="detail-meta-row"><span class="detail-label">Committee</span><span>{committee}</span></div>' if committee else ""
    action_str = f'<div class="detail-meta-row"><span class="detail-label">Last Action</span><span>{adate} — {action[:120]}</span></div>' if action else ""

    badges = _rep_badge(bill) + _direct_badge(bill)

    return f"""<div class="detail-bill-header">
  <div class="detail-bill-num-row">
    <span class="mono detail-bnum">{bnum}</span>
    <span class="tag {stcls}">{status_label}</span>
    {badges}
    <a href="{url}" target="_blank" class="detail-ext-link">Open States ↗</a>
  </div>
  <div class="detail-bill-title">{title}</div>
  <div class="detail-topics" style="margin-top:6px;display:flex;gap:4px;flex-wrap:wrap">{topic_tags}</div>
</div>

<div class="detail-score-row">
  <span class="detail-label">Priority</span>
  <div class="score-bar-wrap detail-score-bar" title="{score}/100">
    <div class="score-bar-fill" style="width:{score}%;background:{'var(--green)' if score >= 60 else 'var(--amber)' if score >= 30 else 'var(--text3)'}"></div>
  </div>
  <span class="mono dim" style="font-size:10px">{score}/100</span>
</div>

{"<div class='detail-section'><div class='detail-section-label'>Local Analysis</div><div class='detail-expl'>" + expl + "</div></div>" if expl and expl != "Analysis unavailable." else ""}
{"<div class='detail-angle'>📍 " + angle + "</div>" if angle else ""}

<div class="detail-section">
  <div class="detail-section-label">Bill Info</div>
  {sponsor_str}
  {committee_str}
  {action_str}
</div>

<div class="detail-section">
  <div class="detail-section-label">Rep Votes</div>
  <div class="rep-block-detail">{rep_html}</div>
</div>

{"<details class='detail-timeline'><summary class='detail-section-label' style='cursor:pointer;list-style:none'>▸ Full Timeline (" + str(len(timeline)) + " actions)</summary><div class='timeline' style='margin-top:10px'>" + tl_html + "</div></details>" if timeline else ""}"""


def render_legislation_panel(bills: list) -> str:
    """Full legislation panel HTML: filter bar + left list + right detail."""

    if not bills:
        return '<div class="empty">No bills flagged yet.</div>'

    grouped = group_and_sort(bills)

    # Build flat index of all bills in display order (for JS selection)
    all_bills_ordered = []
    for group_bills in grouped.values():
        all_bills_ordered.extend(group_bills)

    # Build JS data blob
    import json
    js_bills = json.dumps([{
        "bill_number": b.get("bill_number",""),
        "title": b.get("title",""),
        "url": b.get("url","#"),
        "status": b.get("status",""),
        "status_label": b.get("status_label",""),
        "explanation": b.get("explanation",""),
        "local_angle": b.get("local_angle",""),
        "last_action": b.get("last_action",""),
        "last_action_date": b.get("last_action_date",""),
        "committee": b.get("committee",""),
        "sponsors": b.get("sponsors",[]),
        "rep_votes": b.get("rep_votes",{}),
        "rep_vote_notes": b.get("rep_vote_notes",{}),
        "timeline": b.get("timeline",[]),
        "_topics_detected": b.get("_topics_detected",[]),
        "_priority_score": b.get("_priority_score",0),
        "_is_rep_bill": b.get("_is_rep_bill",False),
        "_is_butte_direct": b.get("_is_butte_direct",False),
    } for b in all_bills_ordered], ensure_ascii=False)

    # Build group sections
    group_sections_html = ""
    bill_rows_html = ""
    global_idx = 0

    for group_key, group_bills in grouped.items():
        meta = group_display_meta(group_key)
        tc, tbg = TIER_COLORS.get(meta["tier"], TIER_COLORS["other"])
        expanded = meta["expanded"]
        section_id = f"grp-{group_key.replace('::','--').replace('/','-').replace(' ','-')}"
        count = len(group_bills)

        row_html = ""
        first_in_group = True
        for bill in group_bills:
            row_html += render_bill_card_mini(bill, global_idx)
            if global_idx == 0 or first_in_group:
                first_in_group = False
            global_idx += 1

        group_sections_html += f"""<div class="leg-group" id="{section_id}">
  <div class="leg-group-header" onclick="toggleGroup('{section_id}')" style="--gc:{tc};--gbg:{tbg}">
    <span class="leg-group-toggle" id="{section_id}-arrow">{"▾" if expanded else "▸"}</span>
    <span class="leg-group-label">{meta["label"]}</span>
    <span class="leg-group-count mono">{count}</span>
  </div>
  <div class="leg-group-body" id="{section_id}-body" style="display:{'block' if expanded else 'none'}">
    {row_html}
  </div>
</div>"""

    # Pre-render all detail panes (hidden, shown by JS)
    detail_panes_html = ""
    global_idx = 0
    for bill in all_bills_ordered:
        detail_panes_html += f'<div class="detail-pane" id="detail-{global_idx}" style="display:none">{render_bill_detail(bill)}</div>'
        global_idx += 1

    # Empty detail placeholder
    placeholder_html = """<div class="detail-placeholder" id="detail-placeholder">
  <div class="detail-placeholder-inner">
    <div style="font-size:28px;margin-bottom:12px;opacity:0.3">◈</div>
    <div class="mono dim" style="font-size:12px">Select a bill to see details</div>
  </div>
</div>"""

    # Topic filter chips
    all_topics = list(TIER1_TOPICS.keys()) + list(TIER2_TOPICS.keys())
    topic_chips_html = '<button class="filter-chip active" onclick="filterTopic(this,\'all\')">All Topics</button>'
    for t in all_topics:
        short = t.split("/")[0].strip()
        topic_chips_html += f'<button class="filter-chip" onclick="filterTopic(this,\'{t}\')" data-topic="{t}">{short}</button>'

    return f"""
<div class="leg-panel-wrap">

  <!-- Filter bar -->
  <div class="leg-filter-bar">
    <div class="leg-filter-row">
      <input class="leg-search" type="text" placeholder="Search bills…" oninput="filterSearch(this.value)">
      <select class="leg-select" onchange="filterStatus(this.value)">
        <option value="all">All Statuses</option>
        <option value="floor">On Floor</option>
        <option value="committee">In Committee</option>
        <option value="introduced">Introduced</option>
        <option value="passed">Passed</option>
      </select>
      <label class="leg-toggle-label">
        <input type="checkbox" id="rep-only-toggle" onchange="filterRepOnly(this.checked)">
        Rep bills only
      </label>
    </div>
    <div class="leg-topic-chips">{topic_chips_html}</div>
  </div>

  <!-- Two-pane layout -->
  <div class="leg-body">

    <!-- Left: grouped bill list -->
    <div class="leg-list" id="leg-list">
      {group_sections_html}
      <div class="empty" id="no-results" style="display:none">No bills match your filters.</div>
    </div>

    <!-- Right: detail pane -->
    <div class="leg-detail" id="leg-detail">
      {placeholder_html}
      {detail_panes_html}
    </div>

  </div>

</div>

<script>
// ── Bill data ──────────────────────────────────────────────────────────────
const LEG_BILLS = {js_bills};
let _activeBillIdx = null;
let _activeFilters = {{ topic: 'all', status: 'all', repOnly: false, search: '' }};

// ── Selection ──────────────────────────────────────────────────────────────
function selectBill(idx) {{
  // Deactivate old
  if (_activeBillIdx !== null) {{
    const old = document.getElementById('bill-row-' + _activeBillIdx);
    if (old) old.classList.remove('active');
    const oldPane = document.getElementById('detail-' + _activeBillIdx);
    if (oldPane) oldPane.style.display = 'none';
  }}
  // Activate new
  _activeBillIdx = idx;
  const row = document.getElementById('bill-row-' + idx);
  if (row) row.classList.add('active');
  document.getElementById('detail-placeholder').style.display = 'none';
  const pane = document.getElementById('detail-' + idx);
  if (pane) pane.style.display = 'block';
}}

// ── Group toggle ───────────────────────────────────────────────────────────
function toggleGroup(sectionId) {{
  const body = document.getElementById(sectionId + '-body');
  const arrow = document.getElementById(sectionId + '-arrow');
  if (!body) return;
  const open = body.style.display !== 'none';
  body.style.display = open ? 'none' : 'block';
  arrow.textContent = open ? '▸' : '▾';
}}

// ── Filtering ──────────────────────────────────────────────────────────────
function applyFilters() {{
  const rows = document.querySelectorAll('.bill-row');
  let anyVisible = false;

  rows.forEach(row => {{
    const status  = row.dataset.status || '';
    const rep     = row.dataset.rep === 'true';
    const topics  = (row.dataset.topics || '').split(',');
    const title   = row.dataset.title || '';
    const bnum    = row.dataset.number || '';

    let show = true;

    if (_activeFilters.status !== 'all' && status !== _activeFilters.status)
      show = false;
    if (_activeFilters.repOnly && !rep)
      show = false;
    if (_activeFilters.topic !== 'all' && !topics.includes(_activeFilters.topic))
      show = false;
    if (_activeFilters.search) {{
      const q = _activeFilters.search.toLowerCase();
      if (!title.includes(q) && !bnum.includes(q)) show = false;
    }}

    row.style.display = show ? 'block' : 'none';
    if (show) anyVisible = true;
  }});

  // Hide empty groups
  document.querySelectorAll('.leg-group').forEach(grp => {{
    const visibleRows = grp.querySelectorAll('.bill-row[style="display: block"], .bill-row:not([style*="display: none"])');
    const hasVisible = Array.from(grp.querySelectorAll('.bill-row')).some(r => r.style.display !== 'none');
    grp.style.display = hasVisible ? 'block' : 'none';
  }});

  document.getElementById('no-results').style.display = anyVisible ? 'none' : 'block';
}}

function filterTopic(btn, topic) {{
  document.querySelectorAll('.filter-chip').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  _activeFilters.topic = topic;
  applyFilters();
}}

function filterStatus(val) {{
  _activeFilters.status = val;
  applyFilters();
}}

function filterRepOnly(checked) {{
  _activeFilters.repOnly = checked;
  applyFilters();
}}

function filterSearch(val) {{
  _activeFilters.search = val.toLowerCase();
  applyFilters();
}}

// Auto-select first visible bill on load
window.addEventListener('DOMContentLoaded', () => {{
  const first = document.querySelector('.bill-row');
  if (first) selectBill(parseInt(first.dataset.idx));
}});
</script>
"""


# ── CSS to inject into build_dashboard.py's <style> block ─────────────────────
LEGISLATION_CSS = """
/* ── Legislation Panel ─────────────────────────────────────────────────── */
.leg-panel-wrap {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

/* Filter bar */
.leg-filter-bar {
  padding: 10px 16px;
  border-bottom: 1px solid var(--border);
  background: var(--bg2);
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.leg-filter-row {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}
.leg-search {
  flex: 1;
  min-width: 140px;
  background: var(--bg3);
  border: 1px solid var(--border);
  color: var(--text);
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 12px;
  padding: 5px 10px;
  border-radius: 4px;
}
.leg-search:focus { outline: none; border-color: var(--green); }
.leg-select {
  background: var(--bg3);
  border: 1px solid var(--border);
  color: var(--text2);
  font-family: 'IBM Plex Mono', monospace;
  font-size: 11px;
  padding: 5px 8px;
  border-radius: 4px;
  cursor: pointer;
}
.leg-select:focus { outline: none; }
.leg-toggle-label {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 11px;
  color: var(--text2);
  display: flex;
  align-items: center;
  gap: 5px;
  cursor: pointer;
  white-space: nowrap;
}
.leg-topic-chips {
  display: flex;
  gap: 5px;
  flex-wrap: wrap;
}
.filter-chip {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 10px;
  padding: 3px 9px;
  border-radius: 20px;
  border: 1px solid var(--border);
  background: var(--bg3);
  color: var(--text3);
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
}
.filter-chip:hover { border-color: var(--border2); color: var(--text2); }
.filter-chip.active {
  background: var(--green2);
  border-color: rgba(0,200,150,0.4);
  color: var(--green);
}

/* Two-pane body */
.leg-body {
  display: grid;
  grid-template-columns: 320px 1fr;
  flex: 1;
  overflow: hidden;
  min-height: 0;
}
.leg-list {
  overflow-y: auto;
  border-right: 1px solid var(--border);
  background: var(--bg);
}
.leg-detail {
  overflow-y: auto;
  background: var(--bg2);
  padding: 20px;
}

/* Group headers */
.leg-group { border-bottom: 1px solid var(--border); }
.leg-group-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  cursor: pointer;
  background: var(--bg2);
  border-bottom: 1px solid var(--border);
  user-select: none;
  position: sticky;
  top: 0;
  z-index: 5;
  border-left: 3px solid var(--gc, var(--text3));
}
.leg-group-header:hover { background: var(--bg3); }
.leg-group-toggle {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 10px;
  color: var(--gc, var(--text3));
  width: 12px;
  flex-shrink: 0;
}
.leg-group-label {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 11px;
  font-weight: 500;
  color: var(--gc, var(--text2));
  flex: 1;
  letter-spacing: 0.04em;
}
.leg-group-count {
  font-size: 10px;
  color: var(--text3);
  background: var(--bg4);
  padding: 1px 6px;
  border-radius: 10px;
}

/* Bill rows (left list) */
.bill-row {
  padding: 10px 12px;
  border-bottom: 1px solid var(--border);
  cursor: pointer;
  transition: background 0.1s;
  background: var(--bg);
}
.bill-row:hover { background: var(--bg3); }
.bill-row.active {
  background: var(--bg3);
  border-left: 3px solid var(--green);
  padding-left: 9px;
}
.bill-row-top {
  display: flex;
  align-items: center;
  gap: 5px;
  flex-wrap: wrap;
  margin-bottom: 4px;
}
.bill-num-sm {
  font-size: 11px;
  color: var(--blue);
  font-weight: 500;
}
.bill-row-title {
  font-size: 12px;
  color: var(--text2);
  line-height: 1.4;
  margin-bottom: 5px;
}
.bill-row.active .bill-row-title { color: var(--text); }
.bill-row-topics {
  display: flex;
  gap: 4px;
  margin-top: 4px;
  flex-wrap: wrap;
}
.topic-chip {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 9px;
  color: var(--text3);
  background: var(--bg4);
  padding: 1px 5px;
  border-radius: 3px;
}

/* Score bar */
.score-bar-wrap {
  height: 2px;
  background: var(--bg4);
  border-radius: 2px;
  overflow: hidden;
  margin: 4px 0 2px;
}
.score-bar-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.3s;
}

/* Rep / direct badges */
.tag-rep {
  background: var(--amber2);
  color: var(--amber);
  font-family: 'IBM Plex Mono', monospace;
  font-size: 9px;
  padding: 1px 5px;
  border-radius: 3px;
}
.tag-direct {
  background: var(--green2);
  color: var(--green);
  font-family: 'IBM Plex Mono', monospace;
  font-size: 9px;
  padding: 1px 5px;
  border-radius: 3px;
}

/* Detail pane */
.detail-placeholder {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}
.detail-placeholder-inner { text-align: center; }
.detail-pane { animation: fadeIn 0.15s ease; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: translateY(0); } }

.detail-bill-header {
  margin-bottom: 16px;
  padding-bottom: 14px;
  border-bottom: 1px solid var(--border);
}
.detail-bill-num-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}
.detail-bnum {
  font-size: 14px;
  font-weight: 500;
  color: var(--blue);
}
.detail-ext-link {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 10px;
  color: var(--text3);
  margin-left: auto;
}
.detail-ext-link:hover { color: var(--green); text-decoration: none; }
.detail-bill-title {
  font-size: 16px;
  font-weight: 500;
  color: var(--text);
  line-height: 1.4;
}
.detail-score-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
}
.detail-score-bar { flex: 1; height: 4px; margin: 0; }
.detail-label {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 10px;
  color: var(--text3);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  white-space: nowrap;
}
.detail-section {
  margin-bottom: 16px;
  padding-bottom: 14px;
  border-bottom: 1px solid var(--border);
}
.detail-section-label {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 10px;
  color: var(--text3);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-bottom: 8px;
  display: block;
}
.detail-expl {
  font-size: 12px;
  color: var(--text2);
  line-height: 1.7;
  padding: 10px 12px;
  background: var(--bg3);
  border-radius: 4px;
  border-left: 2px solid var(--blue);
}
.detail-angle {
  font-size: 12px;
  color: var(--green);
  line-height: 1.5;
  margin-bottom: 16px;
  padding-bottom: 14px;
  border-bottom: 1px solid var(--border);
}
.detail-meta-row {
  display: flex;
  gap: 10px;
  font-size: 11px;
  color: var(--text2);
  margin-bottom: 5px;
  line-height: 1.5;
}
.detail-meta-row .detail-label { min-width: 80px; }
.rep-block-detail {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.rep-row-detail {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  gap: 8px;
}
.detail-timeline {
  margin-top: 4px;
}
.detail-timeline summary::-webkit-details-marker { display: none; }

/* Adjust main panel to not have internal padding when showing leg panel */
#panel-legislation .main-body {
  padding: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  height: 100%;
}
"""
