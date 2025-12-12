from typing import List
import re

from scraper.models import MapStat
from scraper.match import get_team_names_from_selector, get_match_id
import logging
from patchright.async_api import Page
from parsel import Selector

logger = logging.getLogger(__name__)


def get_mapstatsid_from_url(url: str) -> str:
    match = re.search(r"/mapstatsid/(\w+)", url)
    if match is None:
        logger.error(f"Map Stat ID not found in URL: {url}")
        raise ValueError("Map Stat ID not found")

    return match.group(1)


def get_map_stat(
    match_id: str, map_selector: Selector, team_1_name: str, team_2_name: str
) -> MapStat | None:
    data_map = {}

    data_map["match_id"] = match_id
    map_name = map_selector.css(".mapname::text").get()
    if not map_name:
        raise ValueError("Could not find map name")
    data_map["map_name"] = map_name
    logger.debug(f"Processing map '{data_map['map_name']}'")

    # Check if map was played
    map_link = map_selector.css("a::attr(href)").get()
    if not map_link:
        logger.debug(f"Map '{data_map['map_name']}' was not played, skipping")
        return None

    data_map["map_stat_id"] = get_mapstatsid_from_url(map_link)
    logger.debug(f"Map Stat ID: {data_map['map_stat_id']}")

    # Get won/lost information
    won_class = map_selector.css(".won::attr(class)").get() or ""
    won_on_left_side = "results-left" in won_class

    won_image_alt = map_selector.css(".won img::attr(alt)").get()
    if won_image_alt is None:
        raise ValueError("Could not determine which team won the map")

    won_prefix = ""
    lost_prefix = ""

    if won_image_alt == team_1_name:
        logger.debug(f"Team 1 '{team_1_name}' won map '{data_map['map_name']}'")
        won_prefix = "team_1"
        lost_prefix = "team_2"
    elif won_image_alt == team_2_name:
        logger.debug(f"Team 2 '{team_2_name}' won map '{data_map['map_name']}'")
        won_prefix = "team_2"
        lost_prefix = "team_1"
    else:
        raise ValueError("Won team name does not match either team")

    # Get scores
    won_score = map_selector.css(".won .results-team-score::text").get()
    lost_score = map_selector.css(".lost .results-team-score::text").get()

    if not won_score or not lost_score:
        raise ValueError("Could not find team scores")

    data_map[f"{won_prefix}_score"] = won_score
    data_map[f"{lost_prefix}_score"] = lost_score

    # Get pick information
    pick_class = map_selector.css(".pick::attr(class)").get()
    picked_by = "leftover"

    if pick_class and "won" in pick_class:
        picked_by = won_prefix
    elif pick_class and "lost" in pick_class:
        picked_by = lost_prefix

    data_map["picked_by"] = picked_by

    # Get CT/T scores
    results_center_spans = map_selector.css(
        ".results-center .results-center-half-score > span"
    )
    logger.debug(f"Found {len(results_center_spans)} score spans in results center")

    if len(results_center_spans) != 10 and len(results_center_spans) != 15:
        raise ValueError("Unexpected number of score spans found")

    is_overtime = False
    if len(results_center_spans) == 15:
        is_overtime = True
        logger.debug("Overtime detected, extracting regular time scores only")

    # Get class and text for each span
    first_half_left_class = results_center_spans[1].xpath("@class").get() or ""
    first_half_left_score = results_center_spans[1].xpath("text()").get()
    first_half_right_score = results_center_spans[3].xpath("text()").get()
    second_half_left_score = results_center_spans[5].xpath("text()").get()
    second_half_right_score = results_center_spans[7].xpath("text()").get()

    if not all(
        [
            first_half_left_score,
            first_half_right_score,
            second_half_left_score,
            second_half_right_score,
        ]
    ):
        raise ValueError("Could not extract all half scores")

    # Type narrowing - we know these are strings now
    assert first_half_left_score is not None
    assert first_half_right_score is not None
    assert second_half_left_score is not None
    assert second_half_right_score is not None

    if "ct" in first_half_left_class and won_on_left_side:
        data_map["starting_ct"] = won_prefix
        data_map[f"{won_prefix}_ct_score"] = int(first_half_left_score)
        data_map[f"{won_prefix}_tr_score"] = int(second_half_left_score)
        data_map[f"{lost_prefix}_ct_score"] = int(first_half_right_score)
        data_map[f"{lost_prefix}_tr_score"] = int(second_half_right_score)
    else:
        data_map["starting_ct"] = lost_prefix
        data_map[f"{lost_prefix}_ct_score"] = int(first_half_left_score)
        data_map[f"{lost_prefix}_tr_score"] = int(second_half_left_score)
        data_map[f"{won_prefix}_ct_score"] = int(first_half_right_score)
        data_map[f"{won_prefix}_tr_score"] = int(second_half_right_score)

    return MapStat(**data_map)


async def get_maps_stats(
    page: Page,
    url: str,
) -> List[MapStat]:
    await page.goto(url, wait_until="domcontentloaded")

    match_id = await get_match_id(url)

    # Get HTML content and create parsel selector
    html = await page.content()
    selector = Selector(html)

    team_1_name, team_2_name = get_team_names_from_selector(selector)

    # Get all map divs
    maps = selector.css(".maps .flexbox-column > div")
    logger.debug(f"Found {len(maps)} maps")

    stats = []
    for map_selector in maps:
        stat = get_map_stat(match_id, map_selector, team_1_name, team_2_name)
        if stat is not None:
            stats.append(stat)

    return stats
