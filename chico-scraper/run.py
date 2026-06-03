"""
run.py
Orchestrator: scrape council → build dashboard → legislation agent → rebuild → notify.
Called by GitHub Actions on a twice-daily cron schedule.
"""

import sys
import os
import traceback


def main():
    print("=" * 55)
    print("STEP 1: Scraping Granicus RSS feeds")
    print("=" * 55)
    try:
        from scraper import scrape
        scrape()
    except Exception:
        print("FATAL: scraper failed")
        traceback.print_exc()
        sys.exit(1)

    print()
    print("=" * 55)
    print("STEP 2: Building dashboard (pass 1)")
    print("=" * 55)
    try:
        from build_dashboard import main as build
        build()
    except Exception:
        print("ERROR: dashboard build failed (non-fatal)")
        traceback.print_exc()

    print()
    print("=" * 55)
    print("STEP 3: Legislation agent (Open States + Gemini)")
    print("=" * 55)
    try:
        print(f"DEBUG key present: {bool(os.environ.get('OPENSTATES_API_KEY'))}")
        print(f"DEBUG key length: {len(os.environ.get('OPENSTATES_API_KEY', ''))}")
        from legislation_agent import run_agent
        run_agent()
    except Exception:
        print("ERROR: legislation agent failed (non-fatal)")
        traceback.print_exc()

    print()
    print("=" * 55)
    print("STEP 4: Rebuilding dashboard with legislation data")
    print("=" * 55)
    try:
        from build_dashboard import main as build
        build()
    except Exception:
        print("ERROR: dashboard rebuild failed (non-fatal)")
        traceback.print_exc()

    print()
    print("=" * 55)
    print("STEP 5: Sending notifications")
    print("=" * 55)
    try:
        from notify import notify
        notify()
    except Exception:
        print("ERROR: notification failed (non-fatal)")
        traceback.print_exc()

    print()
    print("All steps complete.")


if __name__ == "__main__":
    main()
