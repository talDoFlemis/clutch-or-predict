import re
from scraper.models import Vetos
from scraper.match import get_match_id, get_team_names
import logging
from patchright.async_api import Page
from typing import Dict, Any, Literal
from parsel import Selector

logger = logging.getLogger(__name__)


async def get_vetos(page: Page, url: str) -> Vetos:
    await page.goto(url, wait_until="domcontentloaded")
    match_id = await get_match_id(url)

    # Get HTML content and create parsel selector
    html = await page.content()
    selector = Selector(html)

    t1_name, t2_name = await get_team_names(page)

    # Extract best of information
    bo_text = selector.css(".veto-box .padding::text").get()
    if not bo_text:
        raise ValueError("Could not find best of text")

    bo_match = re.search(r"Best of (\d)", bo_text)
    best_of = int(bo_match.group(1)) if bo_match else 3

    # Initialize Vetos data structure
    vetos_data: Dict[str, Any] = {"match_id": match_id, "best_of": best_of}

    logger.debug(f"Match ID: {match_id}, Best of: {best_of}")

    # Locate the map veto container (second .padding element within .veto-box)
    veto_boxes = selector.css(".veto-box .padding")
    if len(veto_boxes) < 2:
        raise ValueError("Could not find veto box container")

    # Get all direct child divs of the second .padding element
    # Use xpath for direct child selector since CSS "> div" doesn't work with parsel
    veto_lines = veto_boxes[1].xpath("./div")

    logger.debug(f"Found {len(veto_lines)} veto lines")

    removed_index = 0
    picked_index = 0

    for line in veto_lines:
        # Get all text content from the line
        line_text = " ".join(line.css("::text").getall()).strip()

        logger.debug(f"Processing veto line text: '{line_text}'")

        # Match for 'removed' action
        removed_match = re.search(r"removed (\w+)", line_text)
        # Match for 'picked' action
        picked_match = re.search(r"picked (\w+)", line_text)
        # Match for the leftover map (last map)
        leftover_match = re.search(r"(\w+) was left over", line_text)

        # Handle the leftover map immediately and finish
        if leftover_match:
            vetos_data["left_over_map"] = leftover_match.group(1)
            break

        # Determine which team made the action
        team_key_prefix: Literal["t1", "t2"] | None = None
        if t1_name in line_text:
            team_key_prefix = "t1"
        elif t2_name in line_text:
            team_key_prefix = "t2"

        if team_key_prefix is None:
            raise ValueError(f"Could not identify team in veto line: {line_text}")

        key = ""

        map_name = None
        if removed_match:
            map_name = removed_match.group(1)
            # The first two removals are index 1, the second two are index 2, etc.
            key = f"{team_key_prefix}_removed_{(removed_index // 2) + 1}"
            removed_index += 1
        elif picked_match:
            map_name = picked_match.group(1)
            key = f"{team_key_prefix}_picked_{(picked_index // 2) + 1}"
            picked_index += 1

        if not map_name:
            raise ValueError(f"Could not parse veto line: {line_text}")

        logger.debug(
            f"Processing veto line: '{line_text}' | Team: {team_key_prefix} | Map: {map_name} | Key: {key}"
        )

        vetos_data[key] = map_name

    return Vetos(**vetos_data)
