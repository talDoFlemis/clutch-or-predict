"""
Example script showing how to use the Celery task to scrape HLTV matches.

Usage:
    python examples/celery_example.py
"""

import time
from scraper.celery import full_match, event

bo1_match = "https://www.hltv.org/matches/2388622/wild-vs-sentinels-digital-warriors-fall-cup-2025"
bo3_match = "https://www.hltv.org/matches/2388119/g2-vs-the-mongolz-starladder-budapest-major-2025"
bo5_match = (
    "https://www.hltv.org/matches/2380134/mouz-vs-vitality-blast-open-lisbon-2025"
)

event_url = "https://www.hltv.org/events/8042/starladder-budapest-major-2025"


def main():
    print("Sending match scraping task to Celery...")

    # Send task to Celery
    start = time.time()

    matches = [bo1_match]

    results = []

    for match in matches:
        results.append(full_match.delay(match))  # type: ignore

    results.append(event.delay(event_url, True))  # type: ignore

    print("Waiting for result...")

    try:
        for result in results:
            data = result.get(timeout=60)
            print(data)

        end = time.time()
        print(f"\nTotal time taken: {end - start:.2f} seconds")

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
