from pydantic import BaseModel
from datetime import datetime
from typing import Literal


class MatchResult(BaseModel):
    match_id: str
    team_1_name: str
    team_1_id: str
    team_1_map_score: int
    team_2_name: str
    team_2_map_score: int
    team_2_id: str
    team_winner: str
    event_name: str
    event_id: str
    date: datetime


class Vetos(BaseModel):
    match_id: str
    best_of: Literal[1, 3, 5]

    t1_removed_1: str | None = None
    t2_removed_1: str | None = None

    t1_picked_1: str | None = None
    t2_picked_1: str | None = None

    t1_removed_2: str | None = None
    t2_removed_2: str | None = None

    t1_picked_2: str | None = None
    t2_picked_2: str | None = None

    t1_removed_3: str | None = None
    t2_removed_3: str | None = None

    left_over_map: str | None = None


class MapStat(BaseModel):
    map_stat_id: str
    match_id: str
    map_name: str

    team_1_score: int
    team_1_ct_score: int
    team_1_tr_score: int

    team_2_score: int
    team_2_ct_score: int
    team_2_tr_score: int

    picked_by: Literal["team_1", "team_2", "leftover"]

    starting_ct: Literal["team_1", "team_2"]


class PlayerMapStat(BaseModel):
    map_stat_id: str

    player_id: str
    player_name: str

    # CT Side
    opening_kills_ct: int
    opening_deaths_ct: int
    multikills_ct: int
    kast_ct: float
    clutches_ct: int
    kills_ct: int
    headshot_kills_ct: int
    assists_ct: int
    flash_assists_ct: int
    deaths_ct: int
    traded_deaths_ct: int
    adr_ct: float
    swing_ct: float
    rating_3_dot_0_ct: float

    # TR Side
    opening_kills_tr: int
    opening_deaths_tr: int
    multikills_tr: int
    kast_tr: float
    clutches_tr: int
    kills_tr: int
    headshot_kills_tr: int
    assists_tr: int
    flash_assists_tr: int
    deaths_tr: int
    traded_deaths_tr: int
    adr_tr: float
    swing_tr: float
    rating_3_dot_0_tr: float
