"""
Example script showing how to use the Celery task to scrape HLTV matches.

Usage:
    python examples/celery_example.py
"""

import time
from scraper.tasks import scrape_match

bo1_match = "https://www.hltv.org/matches/2388622/wild-vs-sentinels-digital-warriors-fall-cup-2025"
bo3_match = "https://www.hltv.org/matches/2388119/g2-vs-the-mongolz-starladder-budapest-major-2025"
bo5_match = (
    "https://www.hltv.org/matches/2380134/mouz-vs-vitality-blast-open-lisbon-2025"
)


def main():
    print("Sending match scraping task to Celery...")

    # Send task to Celery
    result = scrape_match.delay(bo1_match)

    print(f"Task ID: {result.id}")
    print("Waiting for result...")

    # Wait for result (with timeout)
    try:
        data = result.get(timeout=60)

        print("\n=== Match Result ===")
        print(data["match_result"])

        print("\n=== Vetos ===")
        print(data["vetos"])

        print(f"\n=== Maps Stats ({len(data['maps_stats'])} maps) ===")
        for map_stat in data["maps_stats"]:
            print(f"  - {map_stat['map_name']}")

        print(f"\n=== Player Stats ({len(data['players_stats'])} players) ===")
        for player_stat in data["players_stats"]:
            print(f"  - {player_stat['player_name']}")

        print("\nTask completed successfully!")

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
