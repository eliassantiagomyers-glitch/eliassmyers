# PATCH FOR build_dashboard.py — render_meeting_cards()
#
# FIND the existing render_meeting_cards function and REPLACE it entirely with this:

def render_meeting_cards(meetings: list) -> str:
    if not meetings:
        return '<div class="empty">No meetings scraped yet.</div>'

    cards = []
    for i, m in enumerate(meetings):
        date        = fmt_date(m.get("date", ""))
        title       = m.get("title", f"Meeting {date}")
        link        = m.get("link", "#")
        has_minutes = m.get("has_minutes", False)
        minutes_link = m.get("minutes_link") or m.get("minutes_doc_url")
        minutes_title = m.get("minutes_title", "Minutes")

        items = m.get("items") or m.get("agenda_items", [])

        # Status badge
        if has_minutes:
            status_html = f'<a href="{minutes_link}" target="_blank" class="tag tag-green" style="text-decoration:none">MIN</a>'
        else:
            status_html = '<span class="tag tag-blue">AGN</span>'

        # Agenda items expand
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

        # Minutes link row (if available)
        minutes_row = ""
        if has_minutes and minutes_link:
            minutes_row = f'<div class="card-minutes-row"><a href="{minutes_link}" target="_blank" class="minutes-link">📄 {minutes_title or "View Minutes"}</a></div>'

        cards.append(f"""<div class="card" data-id="council-{m.get('date', i)}">
<div class="card-top">
  <div class="card-meta">
    <span class="mono date-chip">{date}</span>
    {status_html}
  </div>
  <div class="card-actions">
    <button class="pin-btn" onclick="pinItem(this)" data-title="{title}" data-date="{date}" data-link="{link}" title="Pin to board">⊕</button>
  </div>
</div>
<div class="card-title"><a href="{link}" target="_blank">{title}</a></div>
{minutes_row}
{expand}
</div>""")

    return "\n".join(cards)


# ALSO ADD to the CSS block (find the .card-dates rule and add after it):
"""
.card-minutes-row {
  margin: 4px 0 6px;
}
.minutes-link {
  font-size: 11px;
  color: var(--green);
  font-family: 'IBM Plex Mono', monospace;
}
.minutes-link:hover {
  text-decoration: underline;
}
"""

# ALSO in build_dashboard.py's build() function:
# FIND:
#   bill_html = render_bill_cards(bills)
# REPLACE WITH:
#   bill_html = ""  # bill tracker removed
#
# AND remove the Bill Tracker panel from the HTML template entirely:
# FIND and DELETE the entire block:
#   <!-- Bill tracker panel -->
#   <div id="panel-bills" class="panel">
#     ...
#   </div>
#
# AND remove from the sidebar:
#   <div class="nav-item" onclick="showPanel('bills', this)">
#     <span class="nav-icon">↻</span>
#     <span class="nav-label">Bill Tracker</span>
#     <span class="nav-count">{n_bills}</span>
#   </div>
#
# AND in the header meta, change:
#   {n_meetings} meetings · {n_bills} tracked · {n_leg} bills
# TO:
#   {n_meetings} meetings · {n_leg} bills
