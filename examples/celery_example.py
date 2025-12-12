"""
Example script showing how to use the Celery task to scrape HLTV matches.

Usage:
    python examples/celery_example.py
"""

import time
from scraper.celery import match_result, vetos, maps, player_stats

bo1_match = "https://www.hltv.org/matches/2388622/wild-vs-sentinels-digital-warriors-fall-cup-2025"
bo3_match = "https://www.hltv.org/matches/2388119/g2-vs-the-mongolz-starladder-budapest-major-2025"
bo5_match = (
    "https://www.hltv.org/matches/2380134/mouz-vs-vitality-blast-open-lisbon-2025"
)


def main():
    print("Sending match scraping task to Celery...")

    # Send task to Celery
    start = time.time()
    matches = [bo1_match, bo3_match, bo5_match]
    results = []

    for match in matches:
        results.append(match_result.delay(match))  # type: ignore
        results.append(vetos.delay(match))  # type: ignore
        results.append(maps.delay(match))  # type: ignore
        results.append(player_stats.delay(match))  # type: ignore

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
