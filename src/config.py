from dataclasses import dataclass


@dataclass(frozen=True)
class WorldCupSeason:
    edition_year: int
    competition_id: int
    season_id: int


WORLD_CUP_SEASONS = [
    WorldCupSeason(edition_year=2022, competition_id=43, season_id=106),
    WorldCupSeason(edition_year=2018, competition_id=43, season_id=3),
    WorldCupSeason(edition_year=1990, competition_id=43, season_id=55),
    WorldCupSeason(edition_year=1986, competition_id=43, season_id=54),
    WorldCupSeason(edition_year=1974, competition_id=43, season_id=51),
    WorldCupSeason(edition_year=1970, competition_id=43, season_id=272),
    WorldCupSeason(edition_year=1962, competition_id=43, season_id=270),
    WorldCupSeason(edition_year=1958, competition_id=43, season_id=269),
]