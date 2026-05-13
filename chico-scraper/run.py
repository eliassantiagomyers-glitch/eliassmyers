"""
run.py
Orchestrator: scrape → build dashboard → send Telegram notifications.
Called by GitHub Actions on a twice-daily cron schedule.
"""

import sys
import traceback

def main():
    print("=" * 50)
    print("STEP 1: Scraping RSS feeds")
    print("=" * 50)
    try:
        from scraper import scrape
        state = scrape()
    except Exception:
        print("FATAL: scraper failed")
        traceback.print_exc()
        sys.exit(1)

    print()
    print("=" * 50)
    print("STEP 2: Building dashboard")
    print("=" * 50)
    try:
        from build_dashboard import main as build
        build()
    except Exception:
        print("ERROR: dashboard build failed (non-fatal)")
        traceback.print_exc()

    print()
    print("=" * 50)
    print("STEP 3: Sending notifications")
    print("=" * 50)
    try:
        from notify import notify
        notify()
    except Exception:
        print("ERROR: notification failed (non-fatal)")
        traceback.print_exc()

    print()
    print("Done.")


if __name__ == "__main__":
    main()
