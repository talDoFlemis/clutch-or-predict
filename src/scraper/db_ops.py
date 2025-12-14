"""
Database operations for scraper tasks.
"""

from typing import List
from psycopg import AsyncConnection

from scraper.models import Event, MatchResult, Vetos, MapStat, PlayerMapStat


async def insert_event(conn: AsyncConnection, event: Event) -> None:
    await conn.execute(
        """
INSERT INTO EVENTS (event_id,
                    name,
                    start_date,
                    end_date,
                    location,
                    invite_date,
                    vrs_date,
                    vrs_weight,
                    teams,
                    total_prize_pool,
                    player_share,
                    event_type,
                    has_top_50_teams)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (event_id) DO
UPDATE
SET name = EXCLUDED.name,
    start_date = EXCLUDED.start_date,
    end_date = EXCLUDED.end_date,
    location = EXCLUDED.location,
               invite_date = EXCLUDED.invite_date,
               vrs_date = EXCLUDED.vrs_date,
               vrs_weight = EXCLUDED.vrs_weight,
               teams = EXCLUDED.teams,
               total_prize_pool = EXCLUDED.total_prize_pool,
               player_share = EXCLUDED.player_share,
               event_type = EXCLUDED.event_type,
               has_top_50_teams = EXCLUDED.has_top_50_teams
        """,
        (
            event.event_id,
            event.name,
            event.start_date,
            event.end_date,
            event.location,
            event.invite_date,
            event.vrs_date,
            event.vrs_weight,
            event.teams,
            event.total_prize_pool,
            event.player_share,
            event.event_type,
            event.has_top_50_teams,
        ),
    )
    pass


async def insert_match_result(conn: AsyncConnection, result: MatchResult) -> None:
    """Insert match result into the database."""
    await conn.execute(
        """INSERT INTO events 
            (event_id, name)
            VALUES (%s, %s)
            ON CONFLICT (event_id) DO NOTHING
        """,
        (
            result.event_id,
            result.event_name,
        ),
    )
    await conn.execute(
        """INSERT INTO teams 
            (team_id, name)
            VALUES (%s, %s), (%s, %s)
            ON CONFLICT (team_id) DO NOTHING
        """,
        (
            result.team_1_id,
            result.team_1_name,
            result.team_2_id,
            result.team_2_name,
        ),
    )
    await conn.execute(
        """INSERT INTO matches 
            (match_id, event_id, match_date, team_1_id, team_2_id, team_1_map_score, team_2_map_score, team_winner_id) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (match_id) DO NOTHING
        """,
        (
            result.match_id,
            result.event_id,
            result.date,
            result.team_1_id,
            result.team_2_id,
            result.team_1_map_score,
            result.team_2_map_score,
            result.team_winner,
        ),
    )


async def insert_vetos(conn: AsyncConnection, vetos: Vetos) -> None:
    """Insert vetos into the database."""
    await conn.execute(
        """INSERT INTO vetos 
            (match_id, best_of, t1_removed_1, t2_removed_1, t1_picked_1, t2_picked_1, 
             t1_removed_2, t2_removed_2, t1_picked_2, t2_picked_2, t1_removed_3, t2_removed_3, left_over_map) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (match_id) DO NOTHING
        """,
        (
            vetos.match_id,
            vetos.best_of,
            vetos.t1_removed_1,
            vetos.t2_removed_1,
            vetos.t1_picked_1,
            vetos.t2_picked_1,
            vetos.t1_removed_2,
            vetos.t2_removed_2,
            vetos.t1_picked_2,
            vetos.t2_picked_2,
            vetos.t1_removed_3,
            vetos.t2_removed_3,
            vetos.left_over_map,
        ),
    )


async def insert_map_stats(conn: AsyncConnection, map_stats: List[MapStat]) -> None:
    """Insert map stats into the database."""
    for map_stat in map_stats:
        await conn.execute(
            """INSERT INTO map_stats 
                (map_stat_id, match_id, map_name, team_1_score, team_2_score, 
                 team_1_ct_score, team_1_tr_score, team_2_ct_score, team_2_tr_score, 
                 picked_by, starting_ct, team_1_overtime_score, team_2_overtime_score
                 ) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (map_stat_id) DO NOTHING
            """,
            (
                map_stat.map_stat_id,
                map_stat.match_id,
                map_stat.map_name,
                map_stat.team_1_score,
                map_stat.team_2_score,
                map_stat.team_1_ct_score,
                map_stat.team_1_tr_score,
                map_stat.team_2_ct_score,
                map_stat.team_2_tr_score,
                map_stat.picked_by,
                map_stat.starting_ct,
                map_stat.team_1_overtime_score,
                map_stat.team_2_overtime_score,
            ),
        )


async def insert_player_stats(
    conn: AsyncConnection, player_stats: List[PlayerMapStat]
) -> None:
    """Insert player map stats into the database."""
    for player_stat in player_stats:
        await conn.execute(
            """INSERT INTO players 
                (player_id, name) 
                VALUES (%s, %s)
                ON CONFLICT (player_id) DO NOTHING
            """,
            (
                player_stat.player_id,
                player_stat.player_name,
            ),
        )
        await conn.execute(
            """INSERT INTO player_map_stats 
                (map_stat_id, player_id, 
                 opening_kills_ct, opening_deaths_ct, multikills_ct, kast_ct, clutches_ct, 
                 kills_ct, headshot_kills_ct, assists_ct, flash_assists_ct, deaths_ct, 
                 traded_deaths_ct, adr_ct, swing_ct, rating_3_dot_0_ct, 
                 opening_kills_tr, opening_deaths_tr, multikills_tr, kast_tr, clutches_tr, 
                 kills_tr, headshot_kills_tr, assists_tr, flash_assists_tr, deaths_tr, 
                 traded_deaths_tr, adr_tr, swing_tr, rating_3_dot_0_tr) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (map_stat_id, player_id) DO NOTHING
            """,
            (
                player_stat.map_stat_id,
                player_stat.player_id,
                player_stat.opening_kills_ct,
                player_stat.opening_deaths_ct,
                player_stat.multikills_ct,
                player_stat.kast_ct,
                player_stat.clutches_ct,
                player_stat.kills_ct,
                player_stat.headshot_kills_ct,
                player_stat.assists_ct,
                player_stat.flash_assists_ct,
                player_stat.deaths_ct,
                player_stat.traded_deaths_ct,
                player_stat.adr_ct,
                player_stat.swing_ct,
                player_stat.rating_3_dot_0_ct,
                player_stat.opening_kills_tr,
                player_stat.opening_deaths_tr,
                player_stat.multikills_tr,
                player_stat.kast_tr,
                player_stat.clutches_tr,
                player_stat.kills_tr,
                player_stat.headshot_kills_tr,
                player_stat.assists_tr,
                player_stat.flash_assists_tr,
                player_stat.deaths_tr,
                player_stat.traded_deaths_tr,
                player_stat.adr_tr,
                player_stat.swing_tr,
                player_stat.rating_3_dot_0_tr,
            ),
        )
