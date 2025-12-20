import asyncio
from typing import Dict, List, Any
from patchright.async_api import Page
from scraper.match import get_match_result_from_selector
from scraper.models import MatchResult, PlayerMapStat
from scraper.map import get_mapstatsid_from_url
import logging
import re
from parsel import Selector

from scraper.pool import PagePool


logger = logging.getLogger(__name__)


def get_player_id_from_href(player_href: str) -> str:
    match = re.search(r"/players/(\d+)", player_href)
    if match is None:
        raise ValueError("Player ID not found in href")
    return match.group(1)


def process_row(
    row_selector: Selector,
    map_stat_id: str,
    is_tr: bool,
) -> Dict[str, Any]:
    data_map: Dict[str, Any] = {"map_stat_id": map_stat_id}

    suffix = "_tr" if is_tr else "_ct"

    # Get player name and ID
    player_name = row_selector.css(".st-player a::text").get()
    player_href = row_selector.css(".st-player a::attr(href)").get()

    if not player_name or not player_href:
        raise ValueError("Player name or href not found")

    player_id = get_player_id_from_href(player_href)
    data_map["player_id"] = player_id
    data_map["player_name"] = player_name

    # Opening kills/deaths
    openings_kd = row_selector.css(".st-opkd.traditional-data::text").get()
    if not openings_kd:
        raise ValueError("Opening K/D not found")
    openings_kd = openings_kd.replace(" ", "")
    data_map[f"opening_kills{suffix}"] = int(openings_kd.split(":")[0])
    data_map[f"opening_deaths{suffix}"] = int(openings_kd.split(":")[1])

    # Multikills
    multikills = row_selector.css(".st-mks::text").get()
    if not multikills:
        raise ValueError("Multikills not found")
    data_map[f"multikills{suffix}"] = int(multikills)

    # KAST
    kast = row_selector.css(".st-kast.traditional-data::text").get()
    if not kast:
        raise ValueError("KAST not found")
    data_map[f"kast{suffix}"] = float(kast.replace("%", "").replace("-", "0"))

    # Clutches
    clutches = row_selector.css(".st-clutches::text").get()
    if not clutches:
        raise ValueError("Clutches not found")
    data_map[f"clutches{suffix}"] = int(clutches)

    # Kills and headshot kills
    # Use xpath to get full text content including nested elements
    kills_text = row_selector.xpath(
        ".//td[contains(@class, 'st-kills')]//text()"
    ).getall()
    kills_text = " ".join(kills_text).strip()
    if not kills_text:
        raise ValueError("Kills not found")
    kills_parts = kills_text.split()
    data_map[f"kills{suffix}"] = int(kills_parts[0])
    if len(kills_parts) > 1:
        data_map[f"headshot_kills{suffix}"] = int(
            kills_parts[1].replace("(", "").replace(")", "")
        )
    else:
        data_map[f"headshot_kills{suffix}"] = 0

    # Assists and flash assists
    assists_text = row_selector.xpath(
        ".//td[contains(@class, 'st-assists')]//text()"
    ).getall()
    assists_text = " ".join(assists_text).strip()
    if not assists_text:
        raise ValueError("Assists not found")
    assists_parts = assists_text.split()
    data_map[f"assists{suffix}"] = int(assists_parts[0])
    if len(assists_parts) > 1:
        data_map[f"flash_assists{suffix}"] = int(
            assists_parts[1].replace("(", "").replace(")", "")
        )
    else:
        data_map[f"flash_assists{suffix}"] = 0

    # Deaths and traded deaths
    deaths_text = row_selector.xpath(
        ".//td[contains(@class, 'st-deaths')]//text()"
    ).getall()
    deaths_text = " ".join(deaths_text).strip()
    if not deaths_text:
        raise ValueError("Deaths not found")
    deaths_parts = deaths_text.split()
    data_map[f"deaths{suffix}"] = int(deaths_parts[0])
    if len(deaths_parts) > 1:
        data_map[f"traded_deaths{suffix}"] = int(
            deaths_parts[1].replace("(", "").replace(")", "")
        )
    else:
        data_map[f"traded_deaths{suffix}"] = 0

    # ADR
    adr_text = row_selector.css(".st-adr.traditional-data::text").get()
    if not adr_text:
        raise ValueError("ADR not found")
    data_map[f"adr{suffix}"] = float(
        adr_text.replace("-", "0")  # Handle special case where ADR is 0
    )

    # Swing
    swing_text = row_selector.css(".st-roundSwing::text").get()
    if not swing_text:
        raise ValueError("Swing not found")
    data_map[f"swing{suffix}"] = float(swing_text.replace("+", "").replace("%", ""))

    # Rating
    rating_text = row_selector.css(".st-rating::text").get()
    if not rating_text:
        raise ValueError("Rating not found")
    data_map[f"rating_3_dot_0{suffix}"] = float(rating_text)

    return data_map


async def process_map(
    page: Page,
    map_stat_link: str,
    match_result: MatchResult,
) -> List[PlayerMapStat]:
    await page.goto(map_stat_link, wait_until="domcontentloaded")
    map_stat_id = get_mapstatsid_from_url(map_stat_link)
    logger.debug(f"Processing map stats for map_stat_id: {map_stat_id}")

    # Get HTML content and create parsel selector
    html = await page.content()
    selector = Selector(html)

    player_map_stats: Dict[str, Dict[str, Any]] = {}

    # Process TR stats
    all_tr_rows = selector.css(".stats-table.tstats tbody > tr")
    for row_selector in all_tr_rows:
        tr_stat = process_row(row_selector, map_stat_id, is_tr=True)
        player_id = tr_stat["player_id"]
        player_map_stats[player_id] = tr_stat

    # Process CT stats
    all_ct_rows = selector.css(".stats-table.ctstats tbody > tr")
    for row_selector in all_ct_rows:
        ct_stat = process_row(row_selector, map_stat_id, is_tr=False)
        player_id = ct_stat["player_id"]

        if player_id not in player_map_stats:
            raise ValueError(f"CT stat for unknown player ID {player_id}")

        player_map_stats[player_id].update(ct_stat)

    # Get team id for each player
    for total_stats_selector in selector.css(".stats-table.totalstats"):
        team_name = total_stats_selector.css(
            "thead > tr > th > img.logo::attr(title)"
        ).get()
        team_id = (
            match_result.team_1_id
            if team_name and team_name == match_result.team_1_name
            else match_result.team_2_id
        )
        players = total_stats_selector.css(
            "tbody > tr .st-player a::attr(href)"
        ).getall()
        for player_href in players:
            player_id = get_player_id_from_href(player_href)

            if player_id in player_map_stats:
                player_map_stats[player_id]["team_id"] = team_id

    stats = []
    for stat in player_map_stats.values():
        stats.append(PlayerMapStat(**stat))

    logger.info(f"Processed map_stat_id {map_stat_id} with {len(stats)} players")

    return stats


async def get_players_maps_stats(
    pool: PagePool,
    match_url: str,
) -> List[PlayerMapStat]:
    async with pool.get_page() as page:
        await page.goto(match_url, wait_until="domcontentloaded")

        html = await page.content()
        selector = Selector(html)

        is_best_of_1 = (
            "best of 1"
            in selector.css(".standard-box.veto-box .padding.preformatted-text::text")
            .get("")
            .lower()
        )

        logger.debug(f"Is best of 1: {is_best_of_1}")

        maps_to_process = []

        # Get all map links
        map_links = selector.css(".results-stats::attr(href)").getall()

        for href in map_links:
            if href:
                maps_to_process.append(f"https://www.hltv.org{href}")

        match_result = await get_match_result_from_selector(selector, match_url)

        logger.debug(f"Found {len(maps_to_process)} map links")
        logger.debug(f"Map links: {maps_to_process}")

    async def process_map_with_page(map_link: str) -> List[PlayerMapStat]:
        async with pool.get_page() as page:
            return await process_map(page, map_link, match_result)

    results = await asyncio.gather(
        *[process_map_with_page(map_link) for map_link in maps_to_process]
    )

    stats = []
    for map_stats in results:
        stats.extend(map_stats)

    return stats
