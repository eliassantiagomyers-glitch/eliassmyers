"""
legiscan_agent.py

Fetches active California bills from the LegiScan API, runs each one
through Google Gemini to determine relevance to Chico / Butte County,
and writes flagged bills into data/state.json for the dashboard.

Required environment variables:
  LEGISCAN_API_KEY   — from legiscan.com (pending approval)
  GEMINI_API_KEY     — from Google AI Studio (free tier)

Optional (already set from scraper.py):
  TELEGRAM_BOT_TOKEN
  TELEGRAM_CHAT_ID
"""

import json
import os
import time
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

# ── Constants ────────────────────────────────────────────────────────────────

LEGISCAN_BASE   = "https://api.legiscan.com/"
GEMINI_BASE     = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
STATE_FILE      = Path(__file__).parent / "data" / "state.json"
TELEGRAM_API    = "https://api.telegram.org/bot{token}/sendMessage"

# Topics most relevant to Chico and Butte County
# LegiScan search queries — we run one search per topic
SEARCH_QUERIES = [
    "wildfire fire prevention Butte County",
    "water rights drought California rural",
    "housing affordability homeless California",
    "agriculture farming rural California",
    "transportation infrastructure highway California",
    "environment air quality pollution California",
    "public safety emergency management California",
    "education school funding California rural",
    "cannabis marijuana California county",
    "mental health substance abuse California county",
]

# How many bills to pull per query (LegiScan returns max 50 per search)
RESULTS_PER_QUERY = 20

# Gemini rate limiting — free tier allows 15 requests/min
GEMINI_DELAY_SECONDS = 4.5

# Relevance threshold — Gemini returns a score 1-10; we flag bills >= this
RELEVANCE_THRESHOLD = 6

# ── LegiScan API ──────────────────────────────────────────────────────────────

def legiscan_request(api_key: str, operation: str, params: dict) -> dict:
    """Make a request to the LegiScan API and return parsed JSON."""
    query = urllib.parse.urlencode({
        "key": api_key,
        "op":  operation,
        **params
    })
    url = f"{LEGISCAN_BASE}?{query}"
    req = urllib.request.Request(url, headers={"User-Agent": "ChicoPolicyTracker/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def fetch_bills_for_query(api_key: str, query: str) -> list[dict]:
    """Search LegiScan for California bills matching a query string."""
    try:
        resp = legiscan_request(api_key, "getSearch", {
            "state": "CA",
            "query": query,
            "year":  2,   # current + previous session
        })
        if resp.get("status") != "OK":
            print(f"  LegiScan error for '{query}': {resp.get('alert', {}).get('message', 'unknown')}")
            return []

        results = resp.get("searchresult", {})
        bills   = []
        for key, val in results.items():
            if key == "summary":
                continue
            if isinstance(val, dict) and val.get("state") == "CA":
                bills.append({
                    "bill_id":     val.get("bill_id"),
                    "bill_number": val.get("bill_number", ""),
                    "title":       val.get("title", ""),
                    "url":         val.get("url", ""),
                    "last_action": val.get("last_action", ""),
                    "last_action_date": val.get("last_action_date", ""),
                    "relevance":   val.get("relevance", 0),  # LegiScan's own relevance score
                })
        return bills[:RESULTS_PER_QUERY]

    except Exception as e:
        print(f"  ERROR fetching '{query}': {e}")
        return []


def fetch_bill_detail(api_key: str, bill_id: int) -> dict | None:
    """Fetch full bill detail including description/summary."""
    try:
        resp = legiscan_request(api_key, "getBill", {"id": bill_id})
        if resp.get("status") != "OK":
            return None
        return resp.get("bill", {})
    except Exception as e:
        print(f"  ERROR fetching bill {bill_id}: {e}")
        return None


# ── Gemini API ────────────────────────────────────────────────────────────────

def ask_gemini(api_key: str, bill_number: str, title: str, description: str) -> dict:
    """
    Ask Gemini whether a bill is relevant to Chico / Butte County.
    Returns a dict with keys: relevant (bool), score (1-10), explanation (str).
    """
    prompt = f"""You are an assistant helping a local journalist in Chico, California track state legislation that affects the City of Chico and Butte County.

Analyze this California bill and determine how relevant it is to Chico and Butte County residents:

Bill: {bill_number}
Title: {title}
Description: {description if description else "No description available."}

Respond with ONLY a JSON object in this exact format, nothing else:
{{
  "score": <integer 1-10 where 10 is extremely relevant to Chico/Butte County>,
  "relevant": <true if score >= 6, false otherwise>,
  "explanation": "<If relevant: 2-3 sentences explaining specifically how this bill affects Chico or Butte County residents. If not relevant: one sentence saying why not.>",
  "topics": ["<topic1>", "<topic2>"]
}}

Consider Chico/Butte County context: wildfire recovery (2018 Camp Fire), Paradise rebuilding, agriculture (almonds, rice, olives), Chico State University, homeless population, water from Feather River and Oroville Dam, rural/urban mix, air quality issues."""

    url  = f"{GEMINI_BASE}?key={api_key}"
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature":     0.1,
            "maxOutputTokens": 512,
        }
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            resp = json.loads(r.read().decode("utf-8"))

        # Extract the text from Gemini's response
        text = resp["candidates"][0]["content"]["parts"][0]["text"].strip()

        # Strip markdown fences if Gemini wrapped it
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        text = text.strip()

        result = json.loads(text)
        return result

    except json.JSONDecodeError as e:
        print(f"    Gemini JSON parse error: {e}")
        return {"score": 0, "relevant": False, "explanation": "Parse error", "topics": []}
    except Exception as e:
        print(f"    Gemini request error: {e}")
        return {"score": 0, "relevant": False, "explanation": str(e), "topics": []}


# ── Main pipeline ─────────────────────────────────────────────────────────────

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


def run_agent():
    legiscan_key = os.environ.get("LEGISCAN_API_KEY", "")
    gemini_key   = os.environ.get("GEMINI_API_KEY", "")
    tg_token     = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    tg_chat      = os.environ.get("TELEGRAM_CHAT_ID", "")

    if not legiscan_key:
        print("WARN: LEGISCAN_API_KEY not set — skipping legislation agent.")
        return
    if not gemini_key:
        print("WARN: GEMINI_API_KEY not set — skipping legislation agent.")
        return

    print("=" * 50)
    print("LegiScan Agent: fetching California bills")
    print("=" * 50)

    # ── Step 1: Collect bills from all search queries ──────────────────────
    seen_ids = set()
    all_bills = []

    for query in SEARCH_QUERIES:
        print(f"  Searching: '{query}'")
        bills = fetch_bills_for_query(legiscan_key, query)
        for b in bills:
            if b["bill_id"] and b["bill_id"] not in seen_ids:
                seen_ids.add(b["bill_id"])
                all_bills.append(b)
        time.sleep(0.5)  # be polite to LegiScan

    print(f"  Total unique bills to analyze: {len(all_bills)}")

    # ── Step 2: Load existing state to find previously flagged bill IDs ────
    state = load_state()
    existing_flagged = {
        b["bill_id"]: b
        for b in state.get("state_legislation", [])
    }
    prev_flagged_ids = set(existing_flagged.keys())

    # ── Step 3: Run each bill through Gemini ──────────────────────────────
    print("\nRunning bills through Gemini relevance check…")
    flagged_bills = []
    newly_flagged = []

    for i, bill in enumerate(all_bills):
        bill_id     = bill["bill_id"]
        bill_number = bill["bill_number"]
        title       = bill["title"]

        print(f"  [{i+1}/{len(all_bills)}] {bill_number}: {title[:60]}…")

        # If we've already flagged this bill before, keep it but skip re-analysis
        if bill_id in existing_flagged:
            prev = existing_flagged[bill_id]
            # Update last_action if it changed
            prev["last_action"]      = bill["last_action"]
            prev["last_action_date"] = bill["last_action_date"]
            flagged_bills.append(prev)
            print(f"    → Already flagged (score {prev.get('score','?')}), keeping.")
            continue

        # Fetch bill detail for a better description
        detail      = fetch_bill_detail(legiscan_key, bill_id)
        description = ""
        if detail:
            # LegiScan puts description in 'description' or we can use last_action
            description = detail.get("description", "") or detail.get("title", "")
            # Also grab the LegiScan URL if not already set
            if not bill["url"] and detail.get("url"):
                bill["url"] = detail["url"]

        # Ask Gemini
        time.sleep(GEMINI_DELAY_SECONDS)
        result = ask_gemini(gemini_key, bill_number, title, description)

        score    = result.get("score", 0)
        relevant = result.get("relevant", False) or score >= RELEVANCE_THRESHOLD

        print(f"    → Score: {score}/10 | Relevant: {relevant}")

        if relevant:
            flagged_bill = {
                "bill_id":          bill_id,
                "bill_number":      bill_number,
                "title":            title,
                "url":              bill["url"],
                "last_action":      bill["last_action"],
                "last_action_date": bill["last_action_date"],
                "score":            score,
                "explanation":      result.get("explanation", ""),
                "topics":           result.get("topics", []),
                "flagged_at":       datetime.now(timezone.utc).isoformat(),
                "status":           "active",
            }
            flagged_bills.append(flagged_bill)

            if bill_id not in prev_flagged_ids:
                newly_flagged.append(flagged_bill)
                print(f"    ★ NEW relevant bill flagged!")

    # ── Step 4: Save to state.json ─────────────────────────────────────────
    flagged_bills.sort(key=lambda x: x.get("score", 0), reverse=True)
    state["state_legislation"]          = flagged_bills
    state["legislation_last_updated"]   = datetime.now(timezone.utc).isoformat()
    state["legislation_flagged_count"]  = len(flagged_bills)
    save_state(state)

    print(f"\nDone. {len(flagged_bills)} relevant bills saved, {len(newly_flagged)} newly flagged.")

    # ── Step 5: Telegram notifications for new bills ───────────────────────
    if tg_token and tg_chat and newly_flagged:
        for bill in newly_flagged[:5]:  # max 5 notifications per run
            msg = (
                f"📋 <b>New CA Bill Flagged for Chico/Butte County</b>\n"
                f"<b>{bill['bill_number']}</b> — {bill['title']}\n\n"
                f"{bill['explanation']}\n\n"
                f"Relevance score: {bill['score']}/10\n"
                f'<a href="{bill["url"]}">View full bill ↗</a>'
            )
            send_telegram(tg_token, tg_chat, msg)
            print(f"  Telegram sent for {bill['bill_number']}")

        if len(newly_flagged) > 5:
            send_telegram(
                tg_token, tg_chat,
                f"📋 <b>+{len(newly_flagged)-5} more new CA bills flagged</b> — check the dashboard for the full list."
            )


if __name__ == "__main__":
    run_agent()
