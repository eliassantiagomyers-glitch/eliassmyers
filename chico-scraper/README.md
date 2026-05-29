# Chico Policy Tracker

Automated tracker for city council activity, legislation, and policy decisions affecting Chico and Butte County. Scrapes Chico City Council meeting data twice daily, runs California state bills through an AI relevance filter, and publishes everything to a live dashboard.

**Live dashboard:** [eliassmyers.wiki/chico-scraper](https://eliassmyers.wiki/chico-scraper)

---

## What it does

| Step | File | Description |
|------|------|-------------|
| 1 | `scraper.py` | Fetches Chico City Council agenda + minutes RSS feeds from Granicus, parses meeting items, detects recurring bills across meetings, writes `data/state.json` |
| 2 | `build_dashboard.py` | Reads `state.json`, generates `index.html` dashboard |
| 3 | `legiscan_agent.py` | Fetches active California bills from LegiScan, runs each through Gemini to determine relevance to Chico/Butte County, adds flagged bills to `state.json` |
| 4 | `build_dashboard.py` | Rebuilds dashboard a second time with legislation data included |
| 5 | `notify.py` | Diffs against prior run, sends Telegram alerts for new meetings and newly flagged bills |
| — | `run.py` | Orchestrates all steps in order |
| — | `.github/workflows/scrape.yml` | GitHub Actions cron (7:00 AM + 7:00 PM UTC daily) |

---

## Dashboard tabs

| Tab | Status | Description |
|-----|--------|-------------|
| Council | ✅ Live | Latest Chico City Council meeting agendas and minutes |
| Bill Tracker | ✅ Live | Agenda items that recur across multiple meetings, with timelines |
| State Legislation | ✅ Live | California bills flagged as relevant to Chico/Butte County by Gemini |
| Federal | 🔜 Planned | Federal legislation affecting Butte County |
| Agency Policy | 🔜 Planned | State and federal agency regulatory changes |

---

## Setup

### 1. Fork or clone this repo

```bash
git clone https://github.com/eliassantiagomyers-glitch/Chico-scraper.git
cd Chico-scraper
```

### 2. Add GitHub Secrets

Go to **Settings → Secrets and variables → Actions → New repository secret** and add:

| Secret | Where to get it | Required |
|--------|-----------------|----------|
| `TELEGRAM_BOT_TOKEN` | [@BotFather](https://t.me/BotFather) on Telegram | Yes |
| `TELEGRAM_CHAT_ID` | [@userinfobot](https://t.me/userinfobot) on Telegram | Yes |
| `GEMINI_API_KEY` | [Google AI Studio](https://aistudio.google.com/) — free | Yes |
| `LEGISCAN_API_KEY` | [legiscan.com](https://legiscan.com/legiscan) — free, requires approval | Yes |
| `ELIASSMYERS_DEPLOY_TOKEN` | GitHub → Settings → Developer Settings → Personal Access Tokens (classic) → `repo` scope | Yes |

### 3. Enable GitHub Pages on the eliassmyers repo

In the `eliassmyers` repo: **Settings → Pages → Source → Deploy from a branch → main → / (root)**

### 4. Create the dashboard folder in eliassmyers

In the `eliassmyers` repo, create a file at `chico-scraper/.gitkeep` (blank content). This placeholder gets replaced by `index.html` on the first workflow run.

### 5. Trigger the first run

**Actions → Scrape & Deploy → Run workflow**

The workflow will scrape, build, run the legislation agent, rebuild, and deploy to `eliassmyers.wiki/chico-scraper`.

---

## Running locally

```bash
pip install -r requirements.txt

# Set environment variables
export TELEGRAM_BOT_TOKEN=your_token
export TELEGRAM_CHAT_ID=your_chat_id
export GEMINI_API_KEY=your_gemini_key
export LEGISCAN_API_KEY=your_legiscan_key

python run.py

# Open index.html in your browser
```

The legislation agent skips itself gracefully if `LEGISCAN_API_KEY` or `GEMINI_API_KEY` are not set, so the council scraper will still run fine without them.

---

## How bill tracking works

### City council recurring items
Agenda item titles are normalized (stripped of stopwords, punctuation, case) and compared across meetings using Jaccard token similarity. Items with ≥50% token overlap appearing in two or more different meetings are clustered as a tracked bill and shown in the Bill Tracker tab with a timeline.

### State legislation relevance
The LegiScan agent searches California's active bill list across ten topic areas relevant to Butte County (wildfire, water, housing, agriculture, transportation, environment, public safety, education, cannabis, mental health). Each bill's title and description is sent to Gemini with a prompt asking it to score relevance to Chico/Butte County from 1–10, with specific context about the region (Camp Fire recovery, Oroville Dam, Chico State, Feather River, etc.). Bills scoring 6 or higher are flagged and added to the dashboard.

Previously flagged bills are preserved across runs and not re-analyzed, saving API calls. Only newly flagged bills trigger Telegram notifications.

---

## Data sources

| Source | Data | URL |
|--------|------|-----|
| Granicus (City of Chico) | City Council agendas + minutes | [chico-ca.granicus.com](https://chico-ca.granicus.com/ViewPublisher.php?view_id=2) |
| LegiScan | California state legislation | [legiscan.com](https://legiscan.com/CA) |
| Google Gemini | AI relevance analysis | [aistudio.google.com](https://aistudio.google.com/) |

---

## Deployment

The workflow runs on GitHub Actions twice daily. On each run:

1. New `data/state.json` and `index.html` are committed to this repo
2. `index.html` is pushed to `eliassantiagomyers-glitch/eliassmyers` under `chico-scraper/`
3. GitHub Pages serves it at `eliassmyers.wiki/chico-scraper`

---

## Roadmap

- [ ] Federal legislation tracking via Congress.gov API
- [ ] Agency policy changes (CalOES, EPA, CDFA, FEMA)
- [ ] Full bill text analysis (currently uses title + summary only)
- [ ] Vote record parsing from council minutes
- [ ] Search across all agenda items
- [ ] Email digest option alongside Telegram
