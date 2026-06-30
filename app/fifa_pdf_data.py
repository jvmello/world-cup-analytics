from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import pandas as pd


DEFAULT_OUTPUT_DIR = Path("data/silver/fifa_pdf/world_cup/2026")
OUTPUT_DIR_CANDIDATES = (
    DEFAULT_OUTPUT_DIR,
    Path("data/silver/fifa_pdf"),
    Path("data/silver/fifa_pdf_2026"),
    Path("data/fifa_pdf/silver"),
)

DATASET_FILES = {
    "matches": "match_summary.csv",
    "team_metrics": "team_key_statistics.csv",
    "phases": "phases_of_play.csv",
    "attempts": "attempts_at_goal.csv",
    "player_metrics": "player_metrics.csv",
    "issues": "extraction_issues.csv",
}

COLUMN_ALIASES = {
    "team": "team_name",
    "team_display_name": "team_name",
    "player": "player_name",
    "player_display_name": "player_name",
    "metric_name": "metric",
    "statistic": "metric",
    "metric_value": "value",
    "stat_value": "value",
    "home_team_name": "home_team",
    "away_team_name": "away_team",
    "stage": "competition_stage",
}


def resolve_output_dir(output_dir: Path | str | None = None) -> Path:
    if output_dir is not None:
        return Path(output_dir)

    for candidate in OUTPUT_DIR_CANDIDATES:
        if candidate.exists():
            return candidate

    return DEFAULT_OUTPUT_DIR


def _dataset_path(output_dir: Path, filename: str) -> Path:
    direct_path = output_dir / filename
    if direct_path.exists():
        return direct_path

    matches = sorted(output_dir.glob(f"**/{filename}")) if output_dir.exists() else []
    return matches[0] if matches else direct_path


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()

    try:
        data = pd.read_csv(path)
    except (OSError, pd.errors.EmptyDataError, pd.errors.ParserError):
        return pd.DataFrame()

    rename = {
        column: COLUMN_ALIASES[column]
        for column in data.columns
        if column in COLUMN_ALIASES
        and COLUMN_ALIASES[column] not in data.columns
    }
    data = data.rename(columns=rename)

    if "edition_year" not in data.columns:
        data["edition_year"] = 2026

    return data


@dataclass
class FifaPdfData:
    output_dir: Path
    matches: pd.DataFrame = field(default_factory=pd.DataFrame)
    team_metrics: pd.DataFrame = field(default_factory=pd.DataFrame)
    phases: pd.DataFrame = field(default_factory=pd.DataFrame)
    attempts: pd.DataFrame = field(default_factory=pd.DataFrame)
    player_metrics: pd.DataFrame = field(default_factory=pd.DataFrame)
    issues: pd.DataFrame = field(default_factory=pd.DataFrame)

    @classmethod
    def load(cls, output_dir: Path | str | None = None) -> "FifaPdfData":
        resolved = resolve_output_dir(output_dir)
        frames = {
            name: _read_csv(_dataset_path(resolved, filename))
            for name, filename in DATASET_FILES.items()
        }
        return cls(output_dir=resolved, **frames)

    @property
    def available(self) -> bool:
        return any(
            not frame.empty
            for frame in (
                self.matches,
                self.team_metrics,
                self.phases,
                self.attempts,
                self.player_metrics,
            )
        )

    @property
    def availability_message(self) -> str:
        if self.available:
            return f"CSVs FIFA carregados de {self.output_dir}."
        return (
            f"Nenhum CSV FIFA processado foi encontrado em {self.output_dir}. "
            "Execute o pipeline de PDFs."
        )

    def dataset(self, name: str) -> pd.DataFrame:
        if name not in DATASET_FILES:
            raise KeyError(f"Unknown FIFA PDF dataset: {name}")
        return getattr(self, name)

    def available_datasets(self) -> list[str]:
        return [
            name
            for name in DATASET_FILES
            if name != "issues" and not self.dataset(name).empty
        ]

    def match_ids(self) -> list[str]:
        values: Iterable[object] = []
        for frame in (
            self.matches,
            self.team_metrics,
            self.phases,
            self.attempts,
            self.player_metrics,
        ):
            if "match_id" in frame.columns:
                values = [*values, *frame["match_id"].dropna().tolist()]
        return sorted({str(value) for value in values})

    def for_match(self, match_id: object) -> "FifaPdfData":
        selected = str(match_id)

        def filter_frame(frame: pd.DataFrame) -> pd.DataFrame:
            if frame.empty or "match_id" not in frame.columns:
                return frame.copy()
            return frame[frame["match_id"].astype(str).eq(selected)].copy()

        return FifaPdfData(
            output_dir=self.output_dir,
            matches=filter_frame(self.matches),
            team_metrics=filter_frame(self.team_metrics),
            phases=filter_frame(self.phases),
            attempts=filter_frame(self.attempts),
            player_metrics=filter_frame(self.player_metrics),
            issues=filter_frame(self.issues),
        )
