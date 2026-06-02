"""
scraper.py
Fetches Chico City Council agenda + minutes RSS feeds from Granicus,
parses meeting items, and builds/updates data/state.json.

Bill tracking: agenda item titles are normalized and fuzzy-matched across
meetings. Items appearing in 2+ meetings are flagged as tracked bills.
"""

import json
import re
import hashlib
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

# ── Constants ────────────────────────────────────────────────────────────────

AGENDAS_RSS = "https://chico-ca.granicus.com/ViewPublisherRSS.php?view_id=2&mode=agendas"
MINUTES_RSS  = "https://chico-ca.granicus.com/ViewPublisherRSS.php?view_id=2&mode=minutes"
STATE_FILE   = Path(__file__).parent / "data" / "state.json"

# Stopwords to strip when normalizing item titles for matching
STOPWORDS = {
    "a","an","the","and","or","of","for","to","in","on","at","by","from",
    "with","this","that","is","are","was","were","be","been","being","it",
    "its","as","–","—","-","city","chico","council","item","staff","report",
    "recommendation","regarding","re","no","not","vs","v","discussion",
    "&","1st","2nd","3rd","reading","ordinance","resolution","approval",
    "approve","consideration","related","information","presentation","agenda",
}

# Badge/status labels surfaced in the dashboard
STATUS_LABELS = {
    "active":    "Active — in progress",
    "passed":    "Passed",
    "tabled":    "Tabled / continued",
    "scheduled": "Scheduled — first reading",
    "unknown":   "Ongoing",
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def fetch_rss(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "ChicoScraper/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", errors="replace")


def parse_rss(xml_text: str) -> list[dict]:
    """Parse Granicus RSS into a list of meeting dicts."""
    root = ET.fromstring(xml_text)
    ns = {"media": "http://search.yahoo.com/mrss/"}
    meetings = []
    for item in root.findall(".//item"):
        def t(tag): 
            el = item.find(tag)
            return el.text.strip() if el is not None and el.text else ""
        
        title = t("title")
        link  = t("link")
        pub   = t("pubDate")
        desc  = t("description")
        guid  = t("guid")

        # Parse date
        date_parsed = None
        for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z"):
            try:
                date_parsed = datetime.strptime(pub, fmt)
                break
            except ValueError:
                pass
        date_str = date_parsed.strftime("%Y-%m-%d") if date_parsed else pub[:10]

        # Extract agenda items and plain text from description
        items = extract_agenda_items(desc)
        plain_desc = extract_plain_text(desc)

        meetings.append({
            "title":      title,
            "link":       link,
            "date":       date_str,
            "guid":       guid or hashlib.md5(title.encode()).hexdigest(),
            "raw_desc":   desc,
            "description": plain_desc,  # plain text version for AI context
            "items":      items,
        })
    return meetings


def extract_agenda_items(html: str) -> list[dict]:
    """
    Pull agenda item titles out of Granicus description HTML.
    Granicus typically wraps items in <li> or separates them with newlines.
    """
    # Strip HTML tags, collapse whitespace
    clean = re.sub(r"<[^>]+>", "\n", html)
    clean = re.sub(r"&amp;", "&", clean)
    clean = re.sub(r"&nbsp;", " ", clean)
    clean = re.sub(r"&#\d+;", "", clean)
    clean = re.sub(r"&[a-z]+;", " ", clean)
    lines = [l.strip() for l in clean.splitlines() if l.strip()]

    items = []
    # Heuristic: lines that look like "A.1", "5.2", "Item 3", or just title text
    item_re = re.compile(r"^([A-Z]?\d+[\.\-]\d*|Item\s+\d+)[\s\.:\-]+(.+)$", re.I)
    for line in lines:
        if len(line) < 6 or len(line) > 300:
            continue
        m = item_re.match(line)
        if m:
            items.append({"num": m.group(1).strip(), "title": m.group(2).strip()})
        elif re.search(r"\w{4,}", line):  # bare title line
            items.append({"num": "", "title": line})
    return items


def extract_plain_text(html: str) -> str:
    """Strip HTML and return clean plain text from a description field."""
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&#\d+;", "", text)
    text = re.sub(r"&[a-z]+;", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_title(title: str) -> str:
    """Normalize a title for cross-meeting fuzzy matching."""
    t = title.lower()
    t = re.sub(r"[^\w\s]", " ", t)
    tokens = [w for w in t.split() if w not in STOPWORDS and len(w) > 2]
    return " ".join(sorted(tokens))  # sorted so word order doesn't matter


def token_overlap(a: str, b: str) -> float:
    """Jaccard similarity between two normalized title token sets."""
    sa = set(a.split())
    sb = set(b.split())
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def build_tracked_bills(meetings: list[dict]) -> list[dict]:
    """
    Cross-reference agenda items across all meetings to identify recurring items.
    Returns a list of bill-tracking dicts sorted by most-recent appearance.
    """
    # Collect all (meeting_idx, item) pairs with normalized title
    all_items = []
    for mi, meeting in enumerate(meetings):
        for item in meeting["items"]:
            norm = normalize_title(item["title"])
            if len(norm.split()) < 2:
                continue  # too short to match meaningfully
            all_items.append({
                "meeting_idx":  mi,
                "meeting_date": meeting["date"],
                "meeting_title": meeting["title"],
                "meeting_link":  meeting["link"],
                "num":   item["num"],
                "title": item["title"],
                "norm":  norm,
            })

    # Cluster by similarity (greedy, O(n²) — manageable for city council data)
    clusters = []
    used = set()
    for i, a in enumerate(all_items):
        if i in used:
            continue
        cluster = [a]
        used.add(i)
        for j, b in enumerate(all_items):
            if j in used or j == i:
                continue
            if b["meeting_idx"] == a["meeting_idx"]:
                continue  # same meeting — not a recurrence
            score = token_overlap(a["norm"], b["norm"])
            if score >= 0.50:
                cluster.append(b)
                used.add(j)
        if len(cluster) >= 2:
            clusters.append(cluster)

    # Build bill records
    bills = []
    for cluster in clusters:
        cluster.sort(key=lambda x: x["meeting_date"])
        first = cluster[0]
        last  = cluster[-1]
        dates = sorted({c["meeting_date"] for c in cluster})

        # Infer status
        if len(dates) >= 3:
            status = "active"
        elif len(dates) == 2:
            status = "active"
        else:
            status = "scheduled"

        appearances = [
            {
                "date":  c["meeting_date"],
                "title_seen": c["title"],
                "num":   c["num"],
                "meeting_title": c["meeting_title"],
                "link":  c["meeting_link"],
            }
            for c in cluster
        ]

        bills.append({
            "id":           hashlib.md5(first["norm"].encode()).hexdigest()[:10],
            "canonical_title": max(cluster, key=lambda x: len(x["title"]))["title"],
            "first_seen":   first["meeting_date"],
            "last_seen":    last["meeting_date"],
            "appearances":  appearances,
            "meeting_count": len(cluster),
            "status":       status,
        })

    bills.sort(key=lambda b: b["last_seen"], reverse=True)
    return bills


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"meetings": [], "bills": [], "last_updated": None, "last_items_hash": None}


def save_state(state: dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False))


def items_hash(meetings: list[dict]) -> str:
    blob = json.dumps(
        [{"date": m["date"], "items": m["items"]} for m in meetings],
        sort_keys=True
    )
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


# ── Main ──────────────────────────────────────────────────────────────────────

def scrape() -> dict:
    """Fetch, parse, diff, and return updated state + whether anything changed."""
    print("Fetching RSS feeds…")

    try:
        agenda_xml  = fetch_rss(AGENDAS_RSS)
        agenda_mtgs = parse_rss(agenda_xml)
        print(f"  Agendas: {len(agenda_mtgs)} meetings")
    except Exception as e:
        print(f"  ERROR fetching agendas: {e}")
        agenda_mtgs = []

    try:
        minutes_xml  = fetch_rss(MINUTES_RSS)
        minutes_mtgs = parse_rss(minutes_xml)
        print(f"  Minutes: {len(minutes_mtgs)} meetings")
    except Exception as e:
        print(f"  ERROR fetching minutes: {e}")
        minutes_mtgs = []

    # Merge: annotate agenda meetings with whether minutes exist
    minutes_dates = {m["date"] for m in minutes_mtgs}
    for m in agenda_mtgs:
        m["has_minutes"] = m["date"] in minutes_dates
        m["type"] = "agenda"
    for m in minutes_mtgs:
        m["type"] = "minutes"

    # De-duplicate by date, prefer minutes over agenda-only
    by_date: dict[str, dict] = {}
    for m in minutes_mtgs:
        by_date[m["date"]] = m
    for m in agenda_mtgs:
        if m["date"] not in by_date:
            by_date[m["date"]] = m
        else:
            by_date[m["date"]]["agenda_link"] = m["link"]
            by_date[m["date"]]["agenda_items"] = m["items"]

    all_meetings = sorted(by_date.values(), key=lambda x: x["date"], reverse=True)

    # Build bill tracking across all meetings
    print("Detecting recurring agenda items…")
    bills = build_tracked_bills(all_meetings)
    print(f"  Tracked items: {len(bills)}")

    old_state = load_state()
    new_hash  = items_hash(all_meetings)
    changed   = new_hash != old_state.get("last_items_hash")

    new_state = {
        "meetings":         all_meetings,
        "bills":            bills,
        "last_updated":     datetime.now(timezone.utc).isoformat(),
        "last_items_hash":  new_hash,
        "changed":          changed,
        # For notification diffing
        "prev_bill_ids":    [b["id"] for b in old_state.get("bills", [])],
        "prev_meeting_dates": [m["date"] for m in old_state.get("meetings", [])],
    }

    save_state(new_state)
    print(f"  State saved → {STATE_FILE}")
    return new_state


if __name__ == "__main__":
    state = scrape()
    print(f"Done. Changed: {state['changed']}")
