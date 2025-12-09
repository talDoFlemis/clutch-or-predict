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
    map_name: str

    team_1_score: int
    team_1_ct_score: int
    team_1_tr_score: int

    team_2_score: int
    team_2_ct_score: int
    team_2_tr_score: int

    picked_by: Literal["t1", "t2", "leftover"]

    starting_ct: Literal[1, 2]
