"""
scraper.py

Fetches Chico City Council agenda + minutes RSS feeds from Granicus,
parses meeting items, and builds/updates data/state.json.

Minutes matching: Granicus agendas and minutes RSS feeds use the same
clip_id in their links (MediaPlayer.php?clip_id=XXXX). We match on
clip_id rather than date, since the minutes RSS pubDate reflects when
minutes were approved (typically 2 weeks after the meeting), not the
meeting date itself.

Bill tracker removed — the Jaccard cross-meeting clustering produced
too many false positives and is not reliable enough to surface.
"""

import json
import re
import hashlib
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

# ── Constants ─────────────────────────────────────────────────────────────────

AGENDAS_RSS = "https://chico-ca.granicus.com/ViewPublisherRSS.php?view_id=2&mode=agendas"
MINUTES_RSS  = "https://chico-ca.granicus.com/ViewPublisherRSS.php?view_id=2&mode=minutes"

STATE_FILE = Path(__file__).parent / "data" / "state.json"

# ── HTTP ──────────────────────────────────────────────────────────────────────

def fetch_rss(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "ChicoScraper/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", errors="replace")

# ── Parsing ───────────────────────────────────────────────────────────────────

def extract_clip_id(url: str) -> str | None:
    """Pull clip_id out of a Granicus MediaPlayer or document URL."""
    m = re.search(r'clip_id=(\d+)', url or "")
    return m.group(1) if m else None

def parse_date(pub: str) -> str:
    """Parse RSS pubDate string to YYYY-MM-DD."""
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z"):
        try:
            return datetime.strptime(pub, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return pub[:10]

def extract_plain_text(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&#\d+;", "", text)
    text = re.sub(r"&[a-z]+;", " ", text)
    return re.sub(r"\s+", " ", text).strip()

def extract_agenda_items(html: str) -> list[dict]:
    """Pull agenda item lines out of Granicus description HTML."""
    clean = re.sub(r"<[^>]+>", "\n", html)
    clean = re.sub(r"&amp;", "&", clean)
    clean = re.sub(r"&nbsp;", " ", clean)
    clean = re.sub(r"&#\d+;", "", clean)
    clean = re.sub(r"&[a-z]+;", " ", clean)
    lines = [l.strip() for l in clean.splitlines() if l.strip()]

    items = []
    item_re = re.compile(r"^([A-Z]?\d+[\.\-]\d*|Item\s+\d+)[\s\.:\-]+(.+)$", re.I)
    for line in lines:
        if len(line) < 6 or len(line) > 300:
            continue
        m = item_re.match(line)
        if m:
            items.append({"num": m.group(1).strip(), "title": m.group(2).strip()})
        elif re.search(r"\w{4,}", line):
            items.append({"num": "", "title": line})
    return items

def parse_rss(xml_text: str, feed_type: str) -> list[dict]:
    """
    Parse Granicus RSS into meeting dicts.
    feed_type: "agenda" or "minutes"
    """
    root = ET.fromstring(xml_text)
    meetings = []

    for item in root.findall(".//item"):
        def t(tag):
            el = item.find(tag)
            return el.text.strip() if el is not None and el.text else ""

        title    = t("title")
        link     = t("link")
        pub      = t("pubDate")
        desc     = t("description")
        guid     = t("guid")

        date_str = parse_date(pub)
        clip_id  = extract_clip_id(link) or extract_clip_id(guid)

        # Also look for document download links in description
        doc_links = re.findall(r'href="([^"]+)"', desc)
        doc_urls  = [l for l in doc_links if "granicus" in l.lower()]

        meetings.append({
            "title":       title,
            "link":        link,
            "date":        date_str,
            "clip_id":     clip_id,
            "guid":        guid or hashlib.md5(title.encode()).hexdigest(),
            "description": extract_plain_text(desc),
            "items":       extract_agenda_items(desc) if feed_type == "agenda" else [],
            "doc_urls":    doc_urls,
            "feed_type":   feed_type,
        })

    return meetings

# ── Merge agendas + minutes ───────────────────────────────────────────────────

def merge_meetings(agenda_mtgs: list[dict], minutes_mtgs: list[dict]) -> list[dict]:
    """
    Match agendas to minutes using clip_id (most reliable) with date as fallback.

    Granicus minutes RSS pubDate = date minutes were *approved*, not meeting date.
    The clip_id in the MediaPlayer URL is stable and ties both feeds to the same event.

    For each agenda meeting:
      - If a minutes entry shares the same clip_id → attach minutes link
      - Else if a minutes entry shares the same date → attach minutes link
      - Else mark has_minutes=False
    """
    # Index minutes by clip_id and by date
    minutes_by_clip: dict[str, dict] = {}
    minutes_by_date: dict[str, dict] = {}
    for m in minutes_mtgs:
        if m["clip_id"]:
            minutes_by_clip[m["clip_id"]] = m
        minutes_by_date[m["date"]] = m

    merged = []
    for agenda in agenda_mtgs:
        mtg = dict(agenda)  # copy

        # Find matching minutes
        min_entry = None
        if agenda["clip_id"] and agenda["clip_id"] in minutes_by_clip:
            min_entry = minutes_by_clip[agenda["clip_id"]]
        elif agenda["date"] in minutes_by_date:
            min_entry = minutes_by_date[agenda["date"]]

        if min_entry:
            mtg["has_minutes"]   = True
            mtg["minutes_link"]  = min_entry["link"]
            mtg["minutes_title"] = min_entry["title"]
            # If minutes have doc URLs, surface them
            if min_entry["doc_urls"]:
                mtg["minutes_doc_url"] = min_entry["doc_urls"][0]
        else:
            mtg["has_minutes"]   = False
            mtg["minutes_link"]  = None
            mtg["minutes_title"] = None

        merged.append(mtg)

    # Also include any minutes that have NO matching agenda (edge case: agenda RSS lags)
    agenda_clips = {m["clip_id"] for m in agenda_mtgs if m["clip_id"]}
    agenda_dates = {m["date"] for m in agenda_mtgs}
    for m in minutes_mtgs:
        no_clip_match = not m["clip_id"] or m["clip_id"] not in agenda_clips
        no_date_match = m["date"] not in agenda_dates
        if no_clip_match and no_date_match:
            mtg = dict(m)
            mtg["has_minutes"]   = True
            mtg["minutes_link"]  = m["link"]
            mtg["minutes_title"] = m["title"]
            merged.append(mtg)

    merged.sort(key=lambda x: x["date"], reverse=True)
    return merged

# ── State ─────────────────────────────────────────────────────────────────────

def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"meetings": [], "last_updated": None, "last_items_hash": None}

def save_state(state: dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False))

def items_hash(meetings: list[dict]) -> str:
    blob = json.dumps(
        [{"date": m["date"], "has_minutes": m.get("has_minutes")} for m in meetings],
        sort_keys=True
    )
    return hashlib.sha256(blob.encode()).hexdigest()[:16]

# ── Main ──────────────────────────────────────────────────────────────────────

def scrape() -> dict:
    print("Fetching RSS feeds…")

    try:
        agenda_xml  = fetch_rss(AGENDAS_RSS)
        agenda_mtgs = parse_rss(agenda_xml, "agenda")
        print(f"  Agendas: {len(agenda_mtgs)} meetings")
    except Exception as e:
        print(f"  ERROR fetching agendas: {e}")
        agenda_mtgs = []

    try:
        minutes_xml  = fetch_rss(MINUTES_RSS)
        minutes_mtgs = parse_rss(minutes_xml, "minutes")
        print(f"  Minutes: {len(minutes_mtgs)} meetings")
    except Exception as e:
        print(f"  ERROR fetching minutes: {e}")
        minutes_mtgs = []

    print("Merging agendas + minutes…")
    all_meetings = merge_meetings(agenda_mtgs, minutes_mtgs)

    meetings_with_minutes = sum(1 for m in all_meetings if m.get("has_minutes"))
    print(f"  Total: {len(all_meetings)} meetings, {meetings_with_minutes} with minutes")

    old_state  = load_state()
    new_hash   = items_hash(all_meetings)
    changed    = new_hash != old_state.get("last_items_hash")

    # Preserve legislation data written by legislation_agent.py
    new_state = {
        **old_state,
        "meetings":    all_meetings,
        "bills":       [],  # bill tracker removed
        "last_updated":      datetime.now(timezone.utc).isoformat(),
        "last_items_hash":   new_hash,
        "changed":           changed,
        "prev_meeting_dates": [m["date"] for m in old_state.get("meetings", [])],
    }

    save_state(new_state)
    print(f"  State saved → {STATE_FILE}")
    return new_state

if __name__ == "__main__":
    state = scrape()
    print(f"Done. Changed: {state['changed']}")
