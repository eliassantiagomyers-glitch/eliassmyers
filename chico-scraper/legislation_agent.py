"""
legislation_agent.py

Fetches active California bills from the Open States API (Plural/SAI360),
runs each through Gemini in two passes:
  1. Relevance filter — is this bill relevant to Chico / Butte County?
  2. Full analysis — how is it relevant, what's the local angle, how did reps vote?

Tracks bill lifecycle (introduced → committee → floor → passed/failed/vetoed)
and voting records for Butte County's two state reps:
  - James Gallagher, Assembly District 3
  - Megan Dahle, Senate District 1

Writes results into data/state.json under key: state_legislation

Required env vars:
  OPENSTATES_API_KEY   — from open.pluralpolicy.com
  GEMINI_API_KEY       — from Google AI Studio (free tier)

Optional:
  TELEGRAM_BOT_TOKEN
  TELEGRAM_CHAT_ID
"""

import json
import os
import time
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

# ── Constants ─────────────────────────────────────────────────────────────────

OPENSTATES_BASE = "https://v3.openstates.org"
GEMINI_BASE     = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
STATE_FILE      = Path(__file__).parent / "data" / "state.json"
TELEGRAM_API    = "https://api.telegram.org/bot{token}/sendMessage"

# Butte County representatives — Open States person IDs
# Gallagher: Assembly District 3 | Dahle: Senate District 1
BUTTE_REPS = {
    "James Gallagher": {
        "chamber":  "lower",
        "district": "3",
        "party":    "Republican",
        "role":     "Assemblymember, AD-3",
        "slug":     "james-gallagher",
    },
    "Megan Dahle": {
        "chamber":  "upper",
        "district": "1",
        "party":    "Republican",
        "role":     "Senator, SD-1",
        "slug":     "megan-dahle-dhKhkAAkBDu5BE6xcltWY",
    },
}

# Search queries across all priority topic areas
SEARCH_QUERIES = [
    "wildfire fire prevention defensible space CAL FIRE",
    "Camp Fire Paradise recovery Butte County",
    "water rights Feather River Oroville Dam drought",
    "housing affordability rural homelessness northern California",
    "agriculture farming almond rice olive rural",
    "public safety law enforcement rural county",
    "Chico State University CSU education funding",
    "environment air quality pollution rural",
    "infrastructure highway road rural transportation",
    "emergency management disaster relief county",
    "mental health substance abuse rural county",
    "cannabis marijuana county rural",
]

RESULTS_PER_QUERY = 20
GEMINI_DELAY      = 7.0   # seconds between Gemini calls (free tier: 10 req/min)
RELEVANCE_MIN     = 6     # minimum score to flag a bill


# ── HTTP helpers ──────────────────────────────────────────────────────────────

def http_get(url: str, headers: dict = None, timeout: int = 20) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "ChicoScraper/1.0",
            **(headers or {}),
        }
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def http_post(url: str, body: dict, headers: dict = None, timeout: int = 30) -> dict:
    data = json.dumps(body).encode("utf-8")
    req  = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "User-Agent":   "ChicoScraper/1.0",
            **(headers or {}),
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


# ── Open States API ───────────────────────────────────────────────────────────

def openstates_get(path: str, api_key: str, params: dict = None) -> dict:
    """Make a GET request to the Open States v3 API."""
    qs  = urllib.parse.urlencode(params or {})
    url = f"{OPENSTATES_BASE}{path}{'?' + qs if qs else ''}"
    return http_get(url, headers={"X-API-KEY": api_key})


def search_bills(api_key: str, query: str) -> list[dict]:
    """Search CA bills by keyword. Returns list of bill summary dicts."""
    try:
        resp = openstates_get("/bills", api_key, {
            "jurisdiction": "ca",
            "q":            query,
            "session":      "20252026",
            "per_page":     RESULTS_PER_QUERY,
            "include":      "sponsorships",
        })
        return resp.get("results", [])
    except Exception as e:
        print(f"    Open States search error for '{query}': {e}")
        return []


def get_bill_detail(api_key: str, bill_id: str) -> dict | None:
    """Fetch full bill detail including actions and votes."""
    try:
        return openstates_get(
            f"/bills/{bill_id}",
            api_key,
            {"include": "actions,votes,sponsorships"},
        )
    except Exception as e:
        print(f"    Error fetching bill {bill_id}: {e}")
        return None


def get_rep_ids(api_key: str) -> dict[str, str]:
    """
    Look up Open States person IDs for Butte County reps.
    Returns dict of name -> openstates_id.
    """
    rep_ids = {}
    for name, info in BUTTE_REPS.items():
        try:
            resp = openstates_get("/people", api_key, {
                "jurisdiction": "ca",
                "name":         name,
                "org_classification": info["chamber"],
            })
            results = resp.get("results", [])
            if results:
                rep_ids[name] = results[0]["id"]
                print(f"  Rep ID found: {name} → {results[0]['id']}")
            else:
                print(f"  WARN: No Open States ID found for {name}")
        except Exception as e:
            print(f"  Error looking up {name}: {e}")
    return rep_ids


def extract_rep_votes(bill_detail: dict, rep_ids: dict[str, str]) -> dict[str, str]:
    """
    Scan vote records for Gallagher and Dahle.
    Returns dict: rep_name -> "yes" | "no" | "absent" | "not_voting" | None
    """
    votes_out = {}
    if not bill_detail:
        return votes_out

    for vote_event in bill_detail.get("votes", []):
        for vote in vote_event.get("votes", []):
            voter_id   = vote.get("voter", {}).get("id", "")
            voter_name = vote.get("voter", {}).get("name", "")
            option     = vote.get("option", "").lower()

            for rep_name, rep_id in rep_ids.items():
                if voter_id == rep_id or rep_name.lower() in voter_name.lower():
                    votes_out[rep_name] = option
    return votes_out


def parse_bill_status(actions: list[dict]) -> dict:
    """
    Derive human-readable status, last action, and committee from action history.
    Returns dict with: status, status_label, last_action, last_action_date, committee.
    """
    if not actions:
        return {
            "status": "introduced",
            "status_label": "Introduced",
            "last_action": "",
            "last_action_date": "",
            "committee": "",
        }

    # Sort by date descending
    sorted_actions = sorted(actions, key=lambda a: a.get("date", ""), reverse=True)
    latest = sorted_actions[0]
    last_action      = latest.get("description", "")
    last_action_date = latest.get("date", "")

    # Derive committee from action text
    committee = ""
    for a in sorted_actions:
        desc = a.get("description", "").lower()
        if "committee on" in desc:
            # Extract committee name
            idx = desc.find("committee on")
            committee = a["description"][idx:idx+60].strip()
            break
        if "committee" in desc:
            committee = a.get("description", "")[:60]
            break

    # Derive status from action keywords
    desc_lower = last_action.lower()
    all_desc   = " ".join(a.get("description", "").lower() for a in sorted_actions)

    if any(w in desc_lower for w in ["chaptered", "signed by governor", "enacted"]):
        status, label = "passed", "Signed into Law"
    elif any(w in desc_lower for w in ["vetoed"]):
        status, label = "vetoed", "Vetoed"
    elif any(w in desc_lower for w in ["failed", "died", "held in committee"]):
        status, label = "failed", "Failed"
    elif any(w in desc_lower for w in ["floor", "third reading", "second reading"]):
        status, label = "floor", "On Floor"
    elif any(w in desc_lower for w in ["committee", "hearing"]):
        status, label = "committee", "In Committee"
    elif any(w in all_desc for w in ["introduced", "filed"]):
        status, label = "introduced", "Introduced"
    else:
        status, label = "active", "Active"

    return {
        "status":           status,
        "status_label":     label,
        "last_action":      last_action,
        "last_action_date": last_action_date,
        "committee":        committee,
    }


# ── Gemini API ────────────────────────────────────────────────────────────────

def gemini_request(api_key: str, prompt: str, max_tokens: int = 400) -> str:
    """Send a prompt to Gemini and return the text response. Retries on 429."""
    url  = f"{GEMINI_BASE}?key={api_key}"
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature":     0.1,
            "maxOutputTokens": max_tokens,
        },
    }
    for attempt in range(3):
        try:
            resp = http_post(url, body)
            return resp["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception as e:
            msg = str(e)
            if "429" in msg and attempt < 2:
                wait = 30 * (attempt + 1)
                print(f"    Gemini 429 — waiting {wait}s before retry…")
                time.sleep(wait)
            else:
                print(f"    Gemini error: {e}")
                return ""
    return ""



SKIP_PATTERNS = [
    "budget act of 20", "budget acts of 20", "taxation: federal conformity",
    "maintenance of the codes", "omnibus budget trailer", "relative to transgender",
    "an act to amend sections", "education omnibus", "health omnibus", "public safety omnibus",
]

def is_obviously_irrelevant(title: str, abstract: str) -> bool:
    """Return True if bill is obviously statewide boilerplate with no local angle."""
    combined = (title + " " + (abstract or "")).lower()
    return any(pat in combined for pat in SKIP_PATTERNS)

def keyword_score(bills: list[dict]) -> dict[str, int]:
    """
    Pass 1: Keyword-based relevance filter replacing Gemini batch scoring.
    Casts a wide net — false negatives are worse than false positives.
    Any bill matching at least one keyword group passes with score >= RELEVANCE_MIN.
    Returns dict of bill_number -> score (0 = no match, 7 = match).
    bills: list of {"number": str, "title": str, "abstract": str}
    """
    KEYWORD_GROUPS = [
        # Wildfire / fire
        ["wildfire", "fire hazard", "fire prevention", "defensible space",
         "cal fire", "fire safe", "fire severity", "prescribed burn",
         "smoke", "evacuation", "camp fire", "paradise"],
        # Water / Oroville
        ["feather river", "oroville", "water rights", "water supply",
         "drought", "dam", "flood", "levee", "irrigation", "groundwater"],
        # Housing / homelessness
        ["housing", "homeless", "affordable housing", "shelter",
         "zoning", "density", "accessory dwelling", "adu", "encampment"],
        # Agriculture
        ["agriculture", "farming", "almond", "rice", "olive", "orchard",
         "crop", "pesticide", "farmworker", "rural land"],
        # Geography — direct references
        ["butte county", "chico", "paradise", "oroville", "gridley",
         "northern california", "rural county", "rural northern"],
        # CSU / education
        ["chico state", "csu", "california state university",
         "higher education", "community college"],
        # Infrastructure / transportation
        ["highway", "rural road", "broadband", "infrastructure",
         "transportation", "bridge", "public transit"],
        # Environment / air quality
        ["air quality", "pollution", "emissions", "climate",
         "environmental", "ceqa", "conservation", "habitat"],
        # Public safety / law enforcement
        ["law enforcement", "sheriff", "public safety", "crime",
         "jail", "corrections", "911", "dispatch"],
        # Mental health / substance abuse
        ["mental health", "substance abuse", "behavioral health",
         "addiction", "opioid", "treatment", "crisis"],
        # Emergency management
        ["emergency", "disaster", "fema", "mutual aid", "caloes",
         "recovery", "resilience"],
        # Cannabis
        ["cannabis", "marijuana", "dispensary", "cultivation"],
        # Geologic / seismic
        ["geologic", "earthquake", "landslide", "geological survey"],
    ]

    scores = {}
    for b in bills:
        combined = (b["title"] + " " + (b["abstract"] or "")).lower()
        matched = any(
            any(kw in combined for kw in group)
            for group in KEYWORD_GROUPS
        )
        scores[b["number"]] = 7 if matched else 0
    return scores


def gemini_full_analysis(
    api_key: str,
    bill_number: str,
    title: str,
    abstract: str,
    actions: list[dict],
    rep_votes: dict[str, str],
) -> dict:
    """
    Pass 2: Full analysis for bills that passed the relevance filter.
    Returns structured dict with explanation, local angle, and rep vote notes.
    """
    vote_str = ""
    for rep_name, vote in rep_votes.items():
        info = BUTTE_REPS.get(rep_name, {})
        vote_str += f"\n- {rep_name} ({info.get('role','')}): voted {vote.upper()}"
    if not vote_str:
        vote_str = "\nNeither Gallagher nor Dahle has a recorded vote yet."

    action_summary = ""
    if actions:
        recent = sorted(actions, key=lambda a: a.get("date", ""), reverse=True)[:5]
        action_summary = "\n".join(
            f"  {a.get('date','')}: {a.get('description','')}"
            for a in recent
        )

    prompt = f"""You are a research assistant for a journalist covering Chico, CA and Butte County.

Analyze this California bill and provide a structured response.

Bill: {bill_number}
Title: {title}
Abstract: {abstract or "None"}
Recent actions:
{action_summary}
Local rep votes:{vote_str}

Reply ONLY with valid JSON, no markdown:
{{
  "explanation": "<2-3 sentences: what this bill does and specifically how it affects Chico or Butte County residents>",
  "local_angle": "<1 sentence: the most newsworthy angle for a local journalist>",
  "topics": ["<topic1>", "<topic2>"],
  "rep_vote_notes": {{
    "James Gallagher": "<one sentence on what their vote means for AD-3 constituents, or 'No vote recorded' if absent>",
    "Megan Dahle": "<one sentence on what their vote means for SD-1 constituents, or 'No vote recorded' if absent>"
  }}
}}"""

    text = gemini_request(api_key, prompt, max_tokens=600)
    try:
        text = text.replace("```json", "").replace("```", "").strip()
        return json.loads(text)
    except Exception as e:
        print(f"    Full analysis parse error: {e}")
        return {
            "explanation":    "Analysis unavailable.",
            "local_angle":    "",
            "topics":         [],
            "rep_vote_notes": {},
        }


# ── State persistence ─────────────────────────────────────────────────────────

def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def save_state(state: dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False))


def send_telegram(token: str, chat_id: str, text: str):
    url  = TELEGRAM_API.format(token=token)
    data = urllib.parse.urlencode({
        "chat_id":    chat_id,
        "text":       text,
        "parse_mode": "HTML",
        "disable_web_page_preview": "true",
    }).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"  Telegram error: {e}")


# ── Main pipeline ─────────────────────────────────────────────────────────────

def run_agent():
    openstates_key = os.environ.get("OPENSTATES_API_KEY", "")
    gemini_key     = os.environ.get("GEMINI_API_KEY", "")
    tg_token       = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    tg_chat        = os.environ.get("TELEGRAM_CHAT_ID", "")

    if not openstates_key:
        print("WARN: OPENSTATES_API_KEY not set — skipping legislation agent.")
        return
    if not gemini_key:
        print("WARN: GEMINI_API_KEY not set — skipping legislation agent.")
        return

    print("=" * 55)
    print("Legislation Agent: Open States + Gemini")
    print("=" * 55)

    # ── Step 1: Look up rep IDs ────────────────────────────────────────────
    print("\nLooking up Butte County rep IDs…")
    rep_ids = get_rep_ids(openstates_key)

    # ── Step 2: Search for CA bills across all topic areas ─────────────────
    print("\nSearching Open States for CA bills…")
    seen_ids   = set()
    all_bills  = []

    for query in SEARCH_QUERIES:
        print(f"  '{query}'")
        results = search_bills(openstates_key, query)
        for b in results:
            bid = b.get("id", "")
            if bid and bid not in seen_ids:
                seen_ids.add(bid)
                all_bills.append(b)
        time.sleep(0.3)

    print(f"\n  Total unique bills: {len(all_bills)}")

    # ── Step 3: Load existing state ────────────────────────────────────────
    state = load_state()
    existing = {b["bill_id"]: b for b in state.get("state_legislation", [])}
    prev_ids = set(existing.keys())

    # ── Step 4: Pass 1 — relevance filter (batched) ──────────────────────
    print("\nPass 1: Relevance filter…")
    relevant_bills = []
    to_score = []  # bills to send to Gemini in one batch

    for i, bill in enumerate(all_bills):
        bill_id     = bill.get("id", "")
        bill_number = bill.get("identifier", "")
        title       = bill.get("title", "")
        abstract    = bill.get("abstract", "") or ""

        print(f"  [{i+1}/{len(all_bills)}] {bill_number}: {title[:55]}…")

        # Already flagged — skip re-filter, keep and update later
        if bill_id in existing:
            relevant_bills.append(("existing", bill, existing[bill_id]))
            print(f"    → Already flagged, will update.")
            continue

        # Pre-filter obviously irrelevant bills without hitting Gemini
        if is_obviously_irrelevant(title, abstract):
            print(f"    → Skipped (boilerplate)")
            continue

        to_score.append({"number": bill_number, "title": title, "abstract": abstract, "_bill": bill})

    # Keyword filter pass — no API call, zero false negatives
    if to_score:
        print(f"\n  Keyword-filtering {len(to_score)} bills…")
        scores = keyword_score(to_score)
        for item in to_score:
            num   = item["number"]
            score = scores.get(num, 0)
            try:
                score = int(score)
            except (ValueError, TypeError):
                score = 0
            print(f"    {num}: {score}/10")
            if score >= RELEVANCE_MIN:
                relevant_bills.append(("new", item["_bill"], {"score": score}))

    print(f"\n  Relevant bills: {len(relevant_bills)}")

    # ── Step 5: Pass 2 — full analysis for new bills ───────────────────────
    print("\nPass 2: Full analysis + rep vote lookup…")
    flagged = []
    newly_flagged = []

    for kind, bill, prior in relevant_bills:
        bill_id     = bill.get("id", "")
        bill_number = bill.get("identifier", "")
        title       = bill.get("title", "")
        abstract    = bill.get("abstract", "") or ""

        # Fetch full detail (actions, votes)
        print(f"  {bill_number}: fetching detail…")
        detail   = get_bill_detail(openstates_key, bill_id)
        actions  = detail.get("actions", []) if detail else []
        status   = parse_bill_status(actions)
        rep_votes = extract_rep_votes(detail, rep_ids) if detail else {}

        # For existing bills — update status and votes, skip re-analysis
        # unless status changed
        if kind == "existing":
            prior["status"]           = status["status"]
            prior["status_label"]     = status["status_label"]
            prior["last_action"]      = status["last_action"]
            prior["last_action_date"] = status["last_action_date"]
            prior["committee"]        = status["committee"]
            prior["rep_votes"]        = rep_votes
            prior["updated_at"]       = datetime.now(timezone.utc).isoformat()
            flagged.append(prior)
            continue

        # New bill — run full analysis
        time.sleep(GEMINI_DELAY)
        analysis = gemini_full_analysis(
            gemini_key, bill_number, title, abstract, actions, rep_votes
        )

        # Build action timeline for display
        timeline = [
            {
                "date":        a.get("date", ""),
                "description": a.get("description", ""),
                "chamber":     a.get("organization", {}).get("name", ""),
            }
            for a in sorted(actions, key=lambda x: x.get("date", ""))
        ]

        # Sponsorships
        sponsors = [
            s.get("person", {}).get("name", "")
            for s in (detail.get("sponsorships", []) if detail else [])
            if s.get("primary")
        ]

        flagged_bill = {
            "bill_id":          bill_id,
            "bill_number":      bill_number,
            "title":            title,
            "abstract":         abstract,
            "url":              f"https://openstates.org/ca/bills/{bill.get('session','')}/{bill_number}/",
            "score":            prior.get("score", 6),
            "status":           status["status"],
            "status_label":     status["status_label"],
            "last_action":      status["last_action"],
            "last_action_date": status["last_action_date"],
            "committee":        status["committee"],
            "sponsors":         sponsors,
            "rep_votes":        rep_votes,
            "explanation":      analysis.get("explanation", ""),
            "local_angle":      analysis.get("local_angle", ""),
            "topics":           analysis.get("topics", []),
            "rep_vote_notes":   analysis.get("rep_vote_notes", {}),
            "timeline":         timeline,
            "flagged_at":       datetime.now(timezone.utc).isoformat(),
            "updated_at":       datetime.now(timezone.utc).isoformat(),
        }

        flagged.append(flagged_bill)
        newly_flagged.append(flagged_bill)
        print(f"    ★ Flagged: {bill_number} (score {prior.get('score',6)})")

    # ── Step 6: Sort and save ──────────────────────────────────────────────
    flagged.sort(key=lambda x: (
        {"passed": 0, "floor": 1, "committee": 2, "introduced": 3,
         "active": 4, "failed": 5, "vetoed": 6}.get(x.get("status", ""), 9),
        -(x.get("score", 0))
    ))

    state["state_legislation"]         = flagged
    state["legislation_last_updated"]  = datetime.now(timezone.utc).isoformat()
    state["legislation_flagged_count"] = len(flagged)
    save_state(state)

    print(f"\nDone. {len(flagged)} bills saved, {len(newly_flagged)} newly flagged.")

    # ── Step 7: Telegram notifications ────────────────────────────────────
    if tg_token and tg_chat and newly_flagged:
        for bill in newly_flagged[:5]:
            votes_str = ""
            for rep, vote in bill.get("rep_votes", {}).items():
                votes_str += f"\n{rep}: {vote.upper()}"

            msg = (
                f"📋 <b>CA Bill flagged for Butte County</b>\n"
                f"<b>{bill['bill_number']}</b> — {bill['title']}\n\n"
                f"{bill['explanation']}\n\n"
                f"<b>Status:</b> {bill['status_label']}"
                f"{(' · ' + bill['committee']) if bill['committee'] else ''}\n"
                f"{votes_str}\n\n"
                f'<a href="{bill["url"]}">View on Open States ↗</a>'
            )
            send_telegram(tg_token, tg_chat, msg.strip())

        if len(newly_flagged) > 5:
            send_telegram(
                tg_token, tg_chat,
                f"📋 <b>+{len(newly_flagged)-5} more CA bills flagged</b> — check the dashboard."
            )


if __name__ == "__main__":
    run_agent()
