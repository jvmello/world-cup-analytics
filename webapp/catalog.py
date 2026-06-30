from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_EDITION = 2026

COMMON_MENUS = (
    ("overview", "Início"),
    ("competition", "Competição"),
    ("matches", "Partidas"),
    ("players", "Jogadores"),
    ("teams", "Países"),
)


def _read_years(path: Path, column: str) -> set[int]:
    if not path.exists():
        return set()
    try:
        frame = (
            pd.read_csv(path, usecols=[column])
            if path.suffix == ".csv"
            else pd.read_parquet(path, columns=[column])
        )
    except (OSError, ValueError, KeyError, pd.errors.ParserError):
        return set()
    return {
        int(value)
        for value in frame[column].dropna().tolist()
        if str(value).strip()
    }


def discover_editions(data_root: Path) -> list[int]:
    years: set[int] = set()
    years |= _read_years(
        data_root
        / "gold/world_cup/gold_match_summary/gold_match_summary.parquet",
        "edition_year",
    )
    years |= _read_years(
        data_root
        / "silver/world_cup/metadata/world_cup_data_availability.parquet",
        "edition_year",
    )
    years |= _read_years(
        data_root
        / "gold/world_cup/gold_tournament_groups/gold_tournament_groups.parquet",
        "edition_year",
    )
    fifa_root = data_root / "silver/fifa_pdf/world_cup"
    if fifa_root.exists():
        years |= {
            int(path.name)
            for path in fifa_root.iterdir()
            if path.is_dir() and path.name.isdigit() and any(path.glob("*.csv"))
        }
    thestatsapi_root = data_root / "bronze/thestatsapi/world_cup"
    if thestatsapi_root.exists():
        years |= {
            int(path.name)
            for path in thestatsapi_root.iterdir()
            if path.is_dir() and path.name.isdigit()
        }
    return sorted(years, reverse=True)


def edition_catalog(data_root: Path) -> dict[str, Any]:
    editions = []
    fifa_root = data_root / "silver/fifa_pdf/world_cup"
    thestatsapi_root = data_root / "bronze/thestatsapi/world_cup"
    for year in discover_editions(data_root):
        fifa_files = list((fifa_root / str(year)).glob("*.csv"))
        is_fifa = bool(fifa_files)
        has_thestatsapi = any(
            (thestatsapi_root / str(year) / "fixtures").glob(
                "page=*/response.json"
            )
        )
        capabilities = {
            "overview": True,
            "competition": True,
            "teams": True,
            "players": True,
            "matches": True,
            "shots": (not is_fifa) or has_thestatsapi,
            "xg": (not is_fifa) or has_thestatsapi,
            "events": has_thestatsapi,
            "lineups": has_thestatsapi,
            "player_stats": has_thestatsapi,
            "thestatsapi_match": has_thestatsapi,
            "official_metrics": is_fifa and not has_thestatsapi,
            "phases_of_play": is_fifa and not has_thestatsapi,
            "physical_metrics": is_fifa and not has_thestatsapi,
        }
        if has_thestatsapi:
            menus = [
                {"id": "overview", "label": "Início"},
                {"id": "competition", "label": "Competição"},
                {"id": "matches", "label": "Partidas"},
                {"id": "players", "label": "Jogadores"},
                {"id": "teams", "label": "Países"},
            ]
        else:
            menus = [{"id": key, "label": label} for key, label in COMMON_MENUS]
            if capabilities["shots"]:
                menus.append({"id": "shots", "label": "Finalizações e xG"})
            if capabilities["official_metrics"]:
                menus.append(
                    {"id": "official_metrics", "label": "Métricas oficiais"}
                )
        editions.append(
            {
                "year": year,
                "is_default": year == DEFAULT_EDITION,
                "source": (
                    "TheStatsAPI"
                    if has_thestatsapi
                    else "FIFA PDF"
                    if is_fifa
                    else "StatsBomb"
                ),
                "coverage_level": (
                    "match_sample"
                    if has_thestatsapi
                    else "official_aggregate"
                    if is_fifa
                    else "event"
                ),
                "capabilities": capabilities,
                "menus": menus,
            }
        )
    return {"default_year": DEFAULT_EDITION, "editions": editions}
