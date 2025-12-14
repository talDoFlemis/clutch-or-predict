import logging
from patchright.async_api import Page
from parsel import Selector
from datetime import datetime
import re

from scraper.models import Event

logger = logging.getLogger(__name__)


def get_event_id_from_url(event_url: str) -> str:
    match = re.search(r"/events/(\d+)", event_url)
    if match:
        return match.group(1)
    return ""


def get_table_value(selector: Selector, header_text: str) -> str | None:
    row = selector.xpath(
        f'//table[@class="table eventMeta"]//tr[th[contains(text(), "{header_text}")]]/td'
    )
    if row:
        text = row.xpath("string()").get()
        return text.strip() if text else None
    return None


def get_unix_timestamp(selector: Selector, header_text: str) -> int | None:
    # Use descendant-or-self to handle nested spans (e.g., End date has extra span wrapper)
    row = selector.xpath(
        f'//table[@class="table eventMeta"]//tr[th[contains(text(), "{header_text}")]]/td//span/@data-unix'
    )
    if row:
        timestamp = row.get()
        return int(timestamp) if timestamp else None
    return None


async def get_event(page: Page, event_url: str) -> Event:
    await page.goto(event_url, wait_until="domcontentloaded")
    selector = Selector(await page.content())

    event_id = get_event_id_from_url(event_url)
    name = selector.css("h1.event-hub-title::text").get() or ""

    start_date_unix = get_unix_timestamp(selector, "Start date")
    end_date_unix = get_unix_timestamp(selector, "End date")
    invite_date_unix = get_unix_timestamp(selector, "Invite date")
    vrs_date_unix = get_unix_timestamp(selector, "VRS date")

    if start_date_unix is None:
        raise ValueError("Start date is missing for event ID: " + event_id)

    if end_date_unix is None:
        raise ValueError("End date is missing for event ID: " + event_id)

    start_date = datetime.fromtimestamp(start_date_unix / 1000)
    end_date = datetime.fromtimestamp(end_date_unix / 1000)
    invite_date = (
        datetime.fromtimestamp(invite_date_unix / 1000) if invite_date_unix else None
    )
    vrs_date = datetime.fromtimestamp(vrs_date_unix / 1000) if vrs_date_unix else None

    # Extract VRS weight - get only the direct text node, ignoring nested spans
    vrs_weight_node = selector.xpath(
        '//table[@class="table eventMeta"]//tr[th[contains(text(), "VRS weight")]]/td[@class="vrs-weight"]/text()'
    )
    vrs_weight = None
    if vrs_weight_node:
        vrs_weight_str = vrs_weight_node.get()
        if vrs_weight_str:
            vrs_weight_str = vrs_weight_str.strip()
            vrs_weight = int(vrs_weight_str.replace("$", "").replace(",", ""))

    teams_str = get_table_value(selector, "Teams")
    teams = int(teams_str.replace("+", "")) if teams_str else 0

    prize_pool_str = get_table_value(selector, "Total prize pool")
    total_prize_pool = 0
    if prize_pool_str:
        prize_pool_str = prize_pool_str.replace("$", "").replace(",", "")
        try:
            total_prize_pool = int(prize_pool_str)
        except ValueError:
            logger.warning(
                f"Could not parse total prize pool '{prize_pool_str}' for event ID: {event_id}"
            )

    player_share_str = get_table_value(selector, "Player share") or ""
    player_share = None
    if player_share_str:
        try:
            player_share = int(
                player_share_str.replace("$", "").replace(",", "")
            )
        except ValueError:
            logger.warning(
                f"Could not parse player share '{player_share_str}' for event ID: {event_id}"
            )
    

    location = get_table_value(selector, "Location") or ""
    event_type = get_table_value(selector, "Event type") or ""

    has_top_50_teams = False

    return Event(
        event_id=event_id,
        name=name,
        start_date=start_date,
        end_date=end_date,
        invite_date=invite_date,
        vrs_date=vrs_date,
        vrs_weight=vrs_weight,
        teams=teams,
        total_prize_pool=total_prize_pool,
        player_share=player_share,
        location=location,
        event_type=event_type,
        has_top_50_teams=has_top_50_teams,
    )
