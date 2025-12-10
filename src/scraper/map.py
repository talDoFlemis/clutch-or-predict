from typing import List
import re

from scraper.models import MapStat
import logging
from patchright.async_api import Locator, Page
import asyncio

logger = logging.getLogger(__name__)


def get_mapstatsid_from_url(url: str) -> str:
    match = re.search(r"/mapstatsid/(\w+)", url)
    if match is None:
        logger.error(f"Map Stat ID not found in URL: {url}")
        raise ValueError("Map Stat ID not found")

    return match.group(1)


async def get_map_stat(
    map_locator: Locator,
    team_1_name: str,
    team_2_name: str,
) -> MapStat | None:
    data_map = {}

    data_map["map_name"] = await map_locator.locator(".mapname").inner_text()
    logger.debug(f"Processing map '{data_map['map_name']}'")

    map_was_played = await map_locator.get_by_role("link").count() > 0
    if not map_was_played:
        logger.debug(f"Map '{data_map['map_name']}' was not played, skipping")
        return None

    map_id_href = await map_locator.get_by_role("link").get_attribute("href")

    data_map["map_stat_id"] = get_mapstatsid_from_url(map_id_href or "")
    logger.debug(f"Map Stat ID: {data_map['map_stat_id']}")

    won_locator = map_locator.locator(".won")
    won_locator_class_attrs = (await won_locator.get_attribute("class")) or ""
    won_on_left_side = True if "results-left" in won_locator_class_attrs else False
    lost_locator = map_locator.locator(".lost")

    won_image_alt = await won_locator.get_by_role("img").get_attribute("alt")
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

    data_map[f"{won_prefix}_score"] = await won_locator.locator(
        ".results-team-score"
    ).inner_text()
    data_map[f"{lost_prefix}_score"] = await lost_locator.locator(
        ".results-team-score"
    ).inner_text()

    pick_locator = map_locator.locator(".pick")
    is_leftover_pick = await pick_locator.count() == 0
    pick_class_attrs = (
        await pick_locator.get_attribute("class") if not is_leftover_pick else None
    )
    picked_by = "leftover"

    if pick_class_attrs and "won" in pick_class_attrs:
        picked_by = won_prefix
    elif pick_class_attrs and "lost" in pick_class_attrs:
        picked_by = lost_prefix

    data_map["picked_by"] = picked_by

    results_center = map_locator.locator(".results-center .results-center-half-score")
    results_center_spans = await results_center.locator("> span").all()
    logger.debug(f"Found {len(results_center_spans)} score spans in results center")

    if len(results_center_spans) != 10:
        raise ValueError("Unexpected number of score spans found")

    first_half_left = results_center_spans[1]
    starting_left_side_text = await first_half_left.get_attribute("class")

    if starting_left_side_text is None:
        raise ValueError("Could not determine starting CT team")

    first_half_left_score = await first_half_left.inner_text()
    first_half_right_score = await results_center_spans[3].inner_text()
    second_half_left_score = await results_center_spans[5].inner_text()
    second_half_right_score = await results_center_spans[7].inner_text()

    if "ct" in starting_left_side_text and won_on_left_side:
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
    team_1_name: str,
    team_2_name: str,
) -> List[MapStat]:
    maps_column_locator = page.locator(".maps .flexbox-column")
    maps = await maps_column_locator.locator(
        "> div",
    ).all()
    logger.debug(f"Found {len(maps)} maps")

    tasks = [
        get_map_stat(map_locator, team_1_name, team_2_name) for map_locator in maps
    ]

    stats = await asyncio.gather(*tasks)

    return [stat for stat in stats if stat is not None]