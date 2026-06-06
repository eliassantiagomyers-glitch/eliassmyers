"""
legislation_priority.py

Priority scoring and grouping system for Chico Policy Tracker legislation panel.

Groups (in display order):
  0. Rep Bills         — Gallagher or Dahle sponsored (always top)
  1. Butte Direct      — bill explicitly names Butte County / Chico / Oroville / Paradise
  2. Tier 1 topics     — Wildfire, Water, Agriculture, Emergency, Education
  3. Tier 2 topics     — Housing, Environment, Broadband
  4. Other             — passed keyword filter but no stronger signal

Within each group, bills are ranked 0–100 by priority_score().
Dead/failed/vetoed bills are hidden unless rep-sponsored.
"""

from datetime import datetime, timezone

# ── Geography signals ─────────────────────────────────────────────────────────

BUTTE_DIRECT_TERMS = [
    "butte county", "chico", "oroville", "paradise", "gridley",
    "biggs", "durham", "forest ranch", "magalia", "feather falls",
    "lake almanor", "camp fire", "north valley",
]

REP_NAMES = ["gallagher", "dahle"]

# ── Topic taxonomy ────────────────────────────────────────────────────────────

TIER1_TOPICS = {
    "Wildfire / Fire Safety": [
        "wildfire", "fire hazard", "fire prevention", "defensible space",
        "cal fire", "fire safe", "fire severity", "prescribed burn",
        "smoke", "evacuation", "camp fire", "paradise", "fire insurance",
        "structure fire", "fire suppression", "fire district",
    ],
    "Water / Oroville Dam": [
        "feather river", "oroville", "water rights", "water supply",
        "drought", "dam", "flood", "levee", "irrigation", "groundwater",
        "water district", "water board", "sacramento river",
    ],
    "Agriculture / Farming": [
        "agriculture", "farming", "almond", "rice", "olive", "orchard",
        "crop", "pesticide", "farmworker", "rural land", "farm bureau",
        "livestock", "dairy", "ranching", "agricultural water",
    ],
    "Emergency Management / Disaster": [
        "emergency", "disaster", "fema", "mutual aid", "caloes",
        "recovery", "resilience", "evacuation", "emergency declaration",
        "disaster relief", "emergency services",
    ],
    "Education / CSU Chico": [
        "chico state", "csu", "california state university",
        "higher education", "community college", "cal grant",
        "student housing", "university", "ferc", "k-12",
    ],
}

TIER2_TOPICS = {
    "Housing / Homelessness": [
        "housing", "homeless", "affordable housing", "shelter",
        "zoning", "density", "accessory dwelling", "adu", "encampment",
        "transitional housing", "low income housing", "rental",
    ],
    "Environment / Air Quality": [
        "air quality", "pollution", "emissions", "climate",
        "environmental", "ceqa", "conservation", "habitat",
        "clean air", "greenhouse gas", "carbon", "toxics",
    ],
    "Infrastructure / Broadband": [
        "highway", "rural road", "broadband", "infrastructure",
        "transportation", "bridge", "public transit", "internet",
        "fiber", "digital divide", "rural broadband",
    ],
}

# ── Status pipeline values ────────────────────────────────────────────────────

STATUS_SCORE = {
    "passed":      40,
    "floor":       35,
    "committee":   20,
    "active":      10,
    "introduced":   0,
    "failed":     -999,
    "vetoed":     -999,
}

DEAD_STATUSES = {"failed", "vetoed"}

# ── Core functions ────────────────────────────────────────────────────────────

def _text(bill: dict) -> str:
    return (
        (bill.get("title") or "") + " " +
        (bill.get("abstract") or "") + " " +
        (bill.get("explanation") or "")
    ).lower()


def is_butte_direct(bill: dict) -> bool:
    t = _text(bill)
    return any(term in t for term in BUTTE_DIRECT_TERMS)


def is_rep_bill(bill: dict) -> bool:
    sponsors = [s.lower() for s in bill.get("sponsors", [])]
    sponsor_str = " ".join(sponsors)
    rep_votes = {k.lower(): v for k, v in bill.get("rep_votes", {}).items()}
    # Primary sponsor check
    if any(rep in sponsor_str for rep in REP_NAMES):
        return True
    return False


def detect_topics(bill: dict) -> list[str]:
    """Return list of matching topic labels (can span tier1 and tier2)."""
    t = _text(bill)
    matched = []
    for label, keywords in {**TIER1_TOPICS, **TIER2_TOPICS}.items():
        if any(kw in t for kw in keywords):
            matched.append(label)
    return matched if matched else ["Other"]


def days_since_action(bill: dict) -> int:
    d = bill.get("last_action_date", "")
    if not d:
        return 999
    try:
        dt = datetime.strptime(d[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).days
    except Exception:
        return 999


def priority_score(bill: dict) -> int:
    """
    0–100 score. Higher = show first within group.

    Components:
      Status momentum:        0–40
      Butte County direct:   +30
      Rep sponsored:         +25
      Topic tier 1:          +15
      Topic tier 2:          +8
      Recent action (<30d):  +10
      Recent action (<7d):   +5 bonus
    """
    status = bill.get("status", "introduced")
    score = STATUS_SCORE.get(status, 0)

    if score <= -999:
        # Dead bill — only survives if rep-sponsored
        return score

    if is_butte_direct(bill):
        score += 30

    if is_rep_bill(bill):
        score += 25

    topics = detect_topics(bill)
    tier1_match = any(t in TIER1_TOPICS for t in topics)
    tier2_match = any(t in TIER2_TOPICS for t in topics)

    if tier1_match:
        score += 15
        # Floor + tier1 = multiplier bonus
        if status == "floor":
            score += 10
    elif tier2_match:
        score += 8
        if status == "floor":
            score += 5

    age = days_since_action(bill)
    if age <= 7:
        score += 15
    elif age <= 30:
        score += 10

    return min(score, 100)


def assign_group(bill: dict) -> str:
    """
    Returns the primary group key for this bill.
    Priority: rep_bills > butte_direct > tier1_topic > tier2_topic > other
    """
    if is_rep_bill(bill):
        return "rep_bills"
    if is_butte_direct(bill):
        return "butte_direct"
    topics = detect_topics(bill)
    for t in topics:
        if t in TIER1_TOPICS:
            return f"tier1::{t}"
    for t in topics:
        if t in TIER2_TOPICS:
            return f"tier2::{t}"
    return "other"


def group_and_sort(bills: list[dict]) -> dict:
    """
    Returns ordered dict of group_key -> list of bills, sorted by priority_score desc.
    Dead bills are dropped unless rep-sponsored.
    """
    groups: dict[str, list] = {}

    for bill in bills:
        status = bill.get("status", "introduced")
        is_dead = status in DEAD_STATUSES
        rep = is_rep_bill(bill)

        if is_dead and not rep:
            continue  # drop it

        score = priority_score(bill)
        bill["_priority_score"] = score
        bill["_topics_detected"] = detect_topics(bill)
        bill["_is_rep_bill"] = rep
        bill["_is_butte_direct"] = is_butte_direct(bill)

        group = assign_group(bill)
        if group not in groups:
            groups[group] = []
        groups[group].append(bill)

    # Sort bills within each group
    for key in groups:
        groups[key].sort(key=lambda b: b.get("_priority_score", 0), reverse=True)

    # Build ordered output
    ordered = {}

    # 1. Rep bills first
    if "rep_bills" in groups:
        ordered["rep_bills"] = groups["rep_bills"]

    # 2. Butte direct
    if "butte_direct" in groups:
        ordered["butte_direct"] = groups["butte_direct"]

    # 3. Tier 1 topics in defined order
    for label in TIER1_TOPICS:
        key = f"tier1::{label}"
        if key in groups:
            ordered[key] = groups[key]

    # 4. Tier 2 topics in defined order
    for label in TIER2_TOPICS:
        key = f"tier2::{label}"
        if key in groups:
            ordered[key] = groups[key]

    # 5. Other
    if "other" in groups:
        ordered["other"] = groups["other"]

    return ordered


def group_display_meta(group_key: str) -> dict:
    """Returns display label, tier, and default expanded state for a group."""
    if group_key == "rep_bills":
        return {"label": "Rep Bills — Gallagher & Dahle", "tier": "rep", "expanded": True}
    if group_key == "butte_direct":
        return {"label": "Butte County Direct", "tier": "direct", "expanded": True}
    if group_key == "other":
        return {"label": "Other Tracked Bills", "tier": "other", "expanded": False}
    topic = group_key.split("::", 1)[1] if "::" in group_key else group_key
    tier = "tier1" if group_key.startswith("tier1") else "tier2"
    return {"label": topic, "tier": tier, "expanded": False}
