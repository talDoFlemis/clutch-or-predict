from typing import Dict, List, Any
from patchright.async_api import Locator, Page
from scraper.models import PlayerMapStat
from scraper.map import get_mapstatsid_from_url
import logging
import asyncio
import re

from scraper.pool import PagePool


logger = logging.getLogger(__name__)


async def __process_row(
    row_locator: Locator, map_stat_id: str, is_tr: bool
) -> Dict[str, Any]:
    data_map: Dict[str, Any] = {"map_stat_id": map_stat_id}

    suffix = "_tr" if is_tr else "_ct"

    player_locator = row_locator.locator(".st-player").locator("a").first
    player_name = await player_locator.inner_text()

    player_href = await player_locator.get_attribute("href")
    if player_href is None:
        raise ValueError("Player href not found")

    match = re.search(r"/players/(\d+)", player_href)
    if match is None:
        raise ValueError("Player ID not found in href")

    data_map["player_id"] = match.group(1)
    data_map["player_name"] = player_name

    openings_kd = (
        await row_locator.locator(".st-opkd.traditional-data").inner_text()
    ).replace(" ", "")
    data_map[f"opening_kills{suffix}"] = int(openings_kd.split(":")[0])
    data_map[f"opening_deaths{suffix}"] = int(openings_kd.split(":")[1])

    data_map[f"multikills{suffix}"] = int(
        await row_locator.locator(".st-mks").inner_text()
    )

    data_map[f"kast{suffix}"] = (
        await row_locator.locator(".st-kast.traditional-data").first.inner_text()
    ).replace("%", "")

    data_map[f"clutches{suffix}"] = int(
        await row_locator.locator(".st-clutches").inner_text()
    )

    kills_text = await row_locator.locator(".st-kills.traditional-data").inner_text()
    data_map[f"kills{suffix}"] = int(kills_text.split(" ")[0])
    data_map[f"headshot_kills{suffix}"] = int(
        kills_text.split(" ")[1].replace("(", "").replace(")", "")
    )

    assists_text = await row_locator.locator(".st-assists").inner_text()
    data_map[f"assists{suffix}"] = int(assists_text.split(" ")[0])
    data_map[f"flash_assists{suffix}"] = int(
        assists_text.split(" ")[1].replace("(", "").replace(")", "")
    )

    deaths_text = await row_locator.locator(".st-deaths.traditional-data").inner_text()
    data_map[f"deaths{suffix}"] = int(deaths_text.split(" ")[0])
    data_map[f"traded_deaths{suffix}"] = int(
        deaths_text.split(" ")[1].replace("(", "").replace(")", "")
    )

    data_map[f"adr{suffix}"] = float(
        (await row_locator.locator(".st-adr.traditional-data").inner_text()).replace(
            # xertioN made 0 [ADR once](https://www.hltv.org/stats/matches/mapstatsid/196700/vitality-vs-mouz)
            "-",
            "0",
        )
    )

    data_map[f"swing{suffix}"] = float(
        (await row_locator.locator(".st-roundSwing").inner_text())
        .replace("+", "")
        .replace("%", "")
    )
    data_map[f"rating_3_dot_0{suffix}"] = float(
        await row_locator.locator(".st-rating").inner_text()
    )

    return data_map


async def __process_map(
    page: Page,
    map_stat_link: str,
) -> List[PlayerMapStat]:
    start = asyncio.get_event_loop().time()

    await page.goto(map_stat_link, wait_until="domcontentloaded")
    map_stat_id = get_mapstatsid_from_url(map_stat_link)
    logger.debug(f"Processing map stats for map_stat_id: {map_stat_id}")

    tasks = []

    player_map_stats: Dict[str, Dict[str, Any]] = {}

    all_tr_locators = await page.locator(".stats-table.tstats tbody > tr").all()
    tasks = [
        __process_row(row_locator, map_stat_id, is_tr=True)
        for row_locator in all_tr_locators
    ]
    tr_stats = await asyncio.gather(*tasks)

    for tr_stat in tr_stats:
        player_id = tr_stat["player_id"]
        player_map_stats[player_id] = tr_stat

    all_ct_locators = await page.locator(".stats-table.ctstats tbody > tr").all()
    tasks = [
        __process_row(row_locator, map_stat_id, is_tr=False)
        for row_locator in all_ct_locators
    ]
    ct_stats = await asyncio.gather(*tasks)

    for ct_stat in ct_stats:
        player_id = ct_stat["player_id"]
        if player_id not in player_map_stats:
            raise ValueError(f"CT stat for unknown player ID {player_id}")

        player_map_stats[player_id].update(ct_stat)

    stats = []

    for stat in player_map_stats.values():
        stats.append(PlayerMapStat(**stat))

    end = asyncio.get_event_loop().time()

    logger.info(f"Processed map_stat_id {map_stat_id} in {end - start:.2f} seconds")

    return stats


async def get_players_maps_stats(
    pool: PagePool,
    match_url: str,
) -> List[PlayerMapStat]:
    async with pool.get_page() as page:
        await page.goto(match_url, wait_until="domcontentloaded")
        await page.get_by_role("link", name="Detailed Stats").click()

        is_best_of_1 = (
            await page.locator(".stats-match-maps").get_by_role("link").count() == 0
        )

        logger.debug(f"Is best of 1: {is_best_of_1}")

        maps_to_process = []

        if is_best_of_1:
            maps_to_process.append(page.url)
        else:
            map_stats_links = await page.locator(
                ".col.stats-match-map.standard-box.a-reset"
            ).all()

            for link in map_stats_links:
                href = await link.get_attribute("href")
                if href is None:
                    raise ValueError("Map stats link href not found")

                maps_to_process.append(f"https://www.hltv.org{href}")

            # For non MD1 we ignore the link that don't contain mapstatsid in it as it is a summary link
            maps_to_process = [map for map in maps_to_process if "mapstatsid" in map]

        logger.debug(f"Found {len(maps_to_process)} map links")

    async def process_map_with_page(map_link: str) -> List[PlayerMapStat]:
        async with pool.get_page() as page:
            return await __process_map(page, map_link)

    results = await asyncio.gather(
        *[process_map_with_page(map_link) for map_link in maps_to_process]
    )

    stats = []
    for map_stats in results:
        stats.extend(map_stats)

    return stats
