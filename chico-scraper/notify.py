"""
notify.py
Compares new scrape results against previous state and sends
Telegram notifications for any meaningful changes.

Required env vars:
  TELEGRAM_BOT_TOKEN  — from BotFather
  TELEGRAM_CHAT_ID    — your personal chat ID (run @userinfobot to find it)
"""

import json
import os
import urllib.request
import urllib.parse
from datetime import datetime
from pathlib import Path

STATE_FILE = Path(__file__).parent / "data" / "state.json"

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


def send_telegram(token: str, chat_id: str, text: str):
    url  = TELEGRAM_API.format(token=token)
    data = urllib.parse.urlencode({
        "chat_id":    chat_id,
        "text":       text,
        "parse_mode": "HTML",
        "disable_web_page_preview": "true",
    }).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def fmt_date(d: str) -> str:
    try:
        return datetime.strptime(d, "%Y-%m-%d").strftime("%b %-d, %Y")
    except Exception:
        return d


def build_messages(state: dict) -> list[str]:
    """Return a list of Telegram message strings based on what changed."""
    msgs = []

    if not state.get("changed"):
        return msgs  # nothing new — send nothing

    meetings      = state.get("meetings", [])
    bills         = state.get("bills", [])
    prev_dates    = set(state.get("prev_meeting_dates", []))
    prev_bill_ids = set(state.get("prev_bill_ids", []))

    # New meetings
    new_meetings = [m for m in meetings if m["date"] not in prev_dates]
    if new_meetings:
        for m in new_meetings:
            date_str = fmt_date(m["date"])
            title    = m.get("title", f"Meeting {date_str}")
            link     = m.get("link", "")
            mtype    = "📋 Agenda" if m.get("type") == "agenda" else "📝 Minutes"
            items    = m.get("items") or m.get("agenda_items", [])
            item_preview = ""
            if items:
                top = items[:5]
                item_preview = "\n" + "\n".join(
                    f"  • {it.get('num','')+' ' if it.get('num') else ''}{it['title']}"
                    for it in top
                )
                if len(items) > 5:
                    item_preview += f"\n  …and {len(items)-5} more"

            msg = (
                f"🏛 <b>New Chico Council {mtype}</b>\n"
                f"<b>{title}</b> — {date_str}\n"
                f"{item_preview}\n"
                f'<a href="{link}">View on Granicus ↗</a>'
            )
            msgs.append(msg.strip())

    # New recurring bills detected
    new_bills = [b for b in bills if b["id"] not in prev_bill_ids]
    if new_bills:
        lines = [f"🔁 <b>New recurring agenda items detected ({len(new_bills)})</b>"]
        for b in new_bills[:5]:
            lines.append(
                f"  • <b>{b['canonical_title'][:80]}</b>\n"
                f"    Seen {b['meeting_count']}× — first {fmt_date(b['first_seen'])}"
            )
        if len(new_bills) > 5:
            lines.append(f"  …and {len(new_bills)-5} more")
        msgs.append("\n".join(lines))

    # Bills with status updates (meeting count grew)
    # We don't persist old meeting counts in state, so this is approximate:
    # if a bill is in prev_bill_ids and appears with a higher count, flag it.
    # For now we skip deep diffing — covered in future iterations.

    return msgs


def notify():
    token   = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")

    if not token or not chat_id:
        print("WARN: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set — skipping notifications.")
        return

    if not STATE_FILE.exists():
        print("ERROR: state.json not found.")
        return

    state = json.loads(STATE_FILE.read_text())
    msgs  = build_messages(state)

    if not msgs:
        print("No changes to notify about.")
        return

    for msg in msgs:
        print(f"Sending notification:\n{msg[:120]}…")
        try:
            resp = send_telegram(token, chat_id, msg)
            if resp.get("ok"):
                print("  ✓ Sent")
            else:
                print(f"  ✗ Telegram error: {resp}")
        except Exception as e:
            print(f"  ✗ Exception: {e}")


if __name__ == "__main__":
    notify()
