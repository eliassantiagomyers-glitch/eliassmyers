# Chico Policy Tracker

Automated intelligence tool for journalists covering Chico, CA and Butte County. Scrapes city council meetings, tracks California legislation, and surfaces what matters — scored, grouped, and prioritized by local relevance.

**Live dashboard:** [eliassmyers.wiki/chico-scraper](https://eliassmyers.wiki/chico-scraper)  
**Telegram alerts:** [@Chicoscraperbot](https://t.me/Chicoscraperbot)

---

## What it tracks

| Source | Data | Status |
|---|---|---|
| Chico City Council | Agendas, minutes, recurring agenda items | ✅ Live |
| California Legislature | Bills flagged for Butte County relevance, rep votes | ✅ Live |
| U.S. Congress | Federal legislation affecting Butte County | 🔜 Planned |
| Agency Policy | CalOES, EPA, CDFA regulatory changes | 🔜 Planned |
| Police Scanner | Local incident monitoring | 🔜 Planned |

Runs twice daily via GitHub Actions (7:00 AM + 7:00 PM UTC). Pushes to [eliassmyers.wiki/chico-scraper](https://eliassmyers.wiki/chico-scraper) on every run.

---

## How the pipeline works

```
scraper.py          →  Granicus RSS → city council agendas + minutes → data/state.json
legislation_agent.py → Open States API → CA bills → keyword filter → Gemini analysis → state.json
build_dashboard.py  →  state.json → index.html
notify.py           →  diffs against prior run → Telegram alerts for new items only
run.py              →  orchestrates all of the above
```

### City council

Fetches Chico City Council agenda and minutes RSS feeds from Granicus twice daily. Agenda items are normalized and compared across meetings using Jaccard token similarity — items with ≥50% token overlap across two or more meetings are clustered as recurring items and shown in the Bill Tracker tab with a full timeline.

### State legislation

Searches California's active bill list via the [Open States API](https://open.pluralpolicy.com) across 12 topic queries covering Butte County priorities. Bills pass through two filters:

**Pass 1 — Keyword filter:** A local keyword taxonomy covering 13 topic domains (wildfire, water, agriculture, housing, emergency management, CSU Chico, broadband, environment, public safety, mental health, cannabis, geologic hazards). Any match passes. Zero false negatives is the goal — over-inclusion is preferable to missing a relevant bill.

**Pass 2 — Gemini analysis:** Newly flagged bills are sent to Gemini 2.5 Flash for a structured local analysis: what the bill does, the Butte County angle, and what each rep's vote means for their constituents. Previously flagged bills skip this step — only status and vote records are updated on subsequent runs.

**Priority scoring:** Each bill receives a 0–100 priority score based on legislative momentum (floor/committee/introduced), Butte County geographic specificity (naming Chico, Oroville, Paradise, Butte County explicitly), rep sponsorship (Gallagher, Dahle), topic tier, and recency of action. Bills are grouped editorially — not filtered arbitrarily — into:

1. **Rep Bills** — Gallagher (AD-3) and Dahle (SD-1) sponsored bills, always surfaced at top
2. **Butte County Direct** — Bills explicitly naming local jurisdictions
3. **Tier 1 Topics** — Wildfire, Water/Oroville, Agriculture, Emergency Management, CSU Chico
4. **Tier 2 Topics** — Housing, Environment, Broadband
5. **Other** — Passed keyword filter but no stronger local signal

Failed and vetoed bills are hidden unless rep-sponsored.

### Notifications

Telegram alerts fire only for newly flagged bills and new council meetings. A bill scraped on a prior run will never re-trigger a notification, regardless of how many times the scraper runs.

---

## Representatives tracked

| Rep | Role | Party |
|---|---|---|
| James Gallagher | Assemblymember, AD-3 | Republican |
| Megan Dahle | Senator, SD-1 | Republican |

Vote records are pulled from Open States on every run and updated in place.

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/eliassantiagomyers-glitch/Chico-scraper.git
cd Chico-scraper
```

### 2. Add GitHub Secrets

Settings → Secrets and variables → Actions → New repository secret:

| Secret | Source | Required |
|---|---|---|
| `OPENSTATES_API_KEY` | [open.pluralpolicy.com](https://open.pluralpolicy.com) | Yes |
| `GEMINI_API_KEY` | [Google AI Studio](https://aistudio.google.com/) — free | Yes |
| `TELEGRAM_BOT_TOKEN` | [@BotFather](https://t.me/BotFather) | Yes |
| `TELEGRAM_CHAT_ID` | [@userinfobot](https://t.me/userinfobot) | Yes |
| `ELIASSMYERS_DEPLOY_TOKEN` | GitHub → Settings → Developer Settings → Personal Access Tokens (classic) → `repo` scope | Yes |

### 3. Enable GitHub Pages on the site repo

In `eliassantiagomyers-glitch/eliassmyers`: Settings → Pages → Source → Deploy from a branch → main → / (root)

### 4. Create the dashboard placeholder

In the `eliassmyers` repo, create `chico-scraper/.gitkeep` (blank file). The workflow replaces it with `index.html` on first run.

### 5. Trigger

Actions → Scrape & Deploy → Run workflow

---

## Running locally

```bash
pip install -r requirements.txt

export OPENSTATES_API_KEY=your_key
export GEMINI_API_KEY=your_key
export TELEGRAM_BOT_TOKEN=your_token
export TELEGRAM_CHAT_ID=your_chat_id

python run.py
# open index.html
```

Each agent fails gracefully if its API key is missing — the council scraper runs independently of the legislation agent.

---

## File structure

```
scraper.py                   City council Granicus scraper
legislation_agent.py         Open States + Gemini legislation pipeline
legislation_priority.py      Priority scoring and grouping logic
legislation_panel_renderer.py  Dashboard legislation panel renderer
build_dashboard.py           Reads state.json, generates index.html
notify.py                    Telegram notification diffing
run.py                       Pipeline orchestrator
data/state.json              Persistent state (meetings, bills, legislation)
.github/workflows/scrape.yml GitHub Actions cron
```

---

## Deployment

On each run, GitHub Actions:

1. Commits updated `data/state.json` and `index.html` to this repo
2. Pushes `index.html` to `eliassantiagomyers-glitch/eliassmyers` under `chico-scraper/` using a classic PAT (`ELIASSMYERS_DEPLOY_TOKEN`)
3. GitHub Pages serves it at `eliassmyers.wiki/chico-scraper`

The two-repo setup exists because the site repo (`eliassmyers`) hosts a personal site alongside the tracker. Don't change the PAT scope or the deploy target path without updating the workflow.

---

## Roadmap

- [ ] Federal legislation tracking via Congress.gov API
- [ ] Agency policy changes (CalOES, EPA, CDFA, FEMA)
- [ ] Full bill text analysis (currently title + summary only)
- [ ] Vote record parsing from council minutes PDFs
- [ ] Police scanner integration
- [ ] Email digest alongside Telegram
- [ ] Backfill Gemini analysis for bills with missing explanations
