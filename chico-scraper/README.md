# Chico City Council Scraper

Automated tracker for Chico, CA City Council meetings. Scrapes agenda and minutes RSS feeds from Granicus twice daily, detects recurring agenda items across meetings (bill tracking), publishes a live dashboard to GitHub Pages, and sends Telegram notifications on new content.

---

## What it does

| Step | File | Description |
|------|------|-------------|
| 1 | `scraper.py` | Fetches agendas + minutes RSS, parses items, detects recurring bills, writes `data/state.json` |
| 2 | `build_dashboard.py` | Reads `state.json`, generates `index.html` |
| 3 | `notify.py` | Diffs against prior run, sends Telegram alerts |
| — | `run.py` | Orchestrates steps 1–3 |
| — | `.github/workflows/scrape.yml` | GitHub Actions cron (7:00 AM + 7:00 PM UTC daily) |

---

## Setup

### 1. Fork or clone this repo

```bash
git clone https://github.com/YOUR_USERNAME/Chico-scraper.git
cd Chico-scraper
```

### 2. Enable GitHub Pages

Go to **Settings → Pages** → Source: **GitHub Actions**.

### 3. Create a Telegram bot

1. Message [@BotFather](https://t.me/BotFather) on Telegram → `/newbot`
2. Copy the **bot token** it gives you
3. Message [@userinfobot](https://t.me/userinfobot) to get your **chat ID**

### 4. Add GitHub Secrets

Go to **Settings → Secrets and variables → Actions → New repository secret**:

| Secret name | Value |
|-------------|-------|
| `TELEGRAM_BOT_TOKEN` | Your bot token from BotFather |
| `TELEGRAM_CHAT_ID` | Your personal chat ID |

### 5. Trigger the first run

Go to **Actions → Scrape & Deploy → Run workflow**.

The action will:
- Scrape the Granicus RSS feeds
- Write `data/state.json` and `index.html`
- Commit them to the repo
- Deploy to GitHub Pages

Your dashboard will be live at:
`https://YOUR_USERNAME.github.io/Chico-scraper/`

---

## Bill tracking

The scraper normalizes agenda item titles (strips stopwords, punctuation, case) and computes Jaccard token overlap across meetings. Items with ≥50% token overlap appearing in **2 or more different meetings** are clustered as a recurring bill and shown in the Bill Tracker tab with a timeline.

This catches things like:
- Sewer rate items appearing across March, April, and May meetings
- Warren Settlement discussions recurring monthly
- Annual fee schedule items

---

## Running locally

```bash
pip install -r requirements.txt
python run.py
# Then open index.html in your browser
```

---

## RSS feed URLs

- Agendas: `https://chico-ca.granicus.com/ViewPublisherRSS.php?view_id=2&mode=agendas`
- Minutes: `https://chico-ca.granicus.com/ViewPublisherRSS.php?view_id=2&mode=minutes`

---

## Roadmap

- [ ] Phase 2: State/federal/agency legislation bot (LegiScan, Congress.gov, CA Legislative API) with Butte County relevance filtering via Claude API
- [ ] PDF text extraction from linked agenda documents
- [ ] Vote record parsing from minutes
- [ ] Search across all agenda items
