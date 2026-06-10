from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


GROUP_STAGES = {"Group Stage", "1st Group Stage", "2nd Group Stage"}
GROUP_LETTERS = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")

STAGE_ORDER = {
    "Group Stage": 10,
    "1st Group Stage": 10,
    "2nd Group Stage": 20,
    "Round of 32": 25,
    "Round of 16": 30,
    "Quarter-finals": 40,
    "Semi-finals": 50,
    "3rd Place Final": 60,
    "Final": 70,
}


@dataclass(frozen=True)
class MatchWinner:
    winner: str | None
    penalty_score: str | None
    source: str


def penalty_score_for_match(
    player_shots: pd.DataFrame,
    match_id: int,
) -> tuple[str | None, str | None]:
    if player_shots.empty or "period" not in player_shots.columns:
        return None, None

    penalties = player_shots[
        player_shots["match_id"].eq(match_id)
        & player_shots["period"].eq(5)
        & player_shots["shot_type"].eq("Penalty")
    ].copy()

    if penalties.empty:
        return None, None

    goals = (
        penalties.groupby("team_name", as_index=False)
        .agg(penalty_goals=("is_goal", "sum"))
        .sort_values("penalty_goals", ascending=False)
    )

    if len(goals) < 2 or goals["penalty_goals"].nunique() == 1:
        return None, None

    winner = str(goals.iloc[0]["team_name"])
    score = " - ".join(
        f"{row.team_name} {int(row.penalty_goals)}"
        for row in goals.itertuples(index=False)
    )

    return winner, score


def infer_match_winner(
    match: pd.Series,
    player_shots: pd.DataFrame | None = None,
) -> MatchWinner:
    home_score = int(match["home_score"])
    away_score = int(match["away_score"])

    if home_score > away_score:
        return MatchWinner(str(match["home_team"]), None, "score")

    if away_score > home_score:
        return MatchWinner(str(match["away_team"]), None, "score")

    if player_shots is not None:
        winner, penalty_score = penalty_score_for_match(
            player_shots,
            int(match["match_id"]),
        )
        if winner:
            return MatchWinner(winner, penalty_score, "penalties")

    return MatchWinner(None, None, "draw")


def prepare_matches(matches: pd.DataFrame) -> pd.DataFrame:
    data = matches.copy()

    data["match_date"] = pd.to_datetime(data["match_date"], errors="coerce")
    data["stage_order"] = data["competition_stage"].map(STAGE_ORDER).fillna(99)
    data["total_goals"] = data["home_score"] + data["away_score"]
    data["score"] = (
        data["home_score"].astype(str) + " x " + data["away_score"].astype(str)
    )
    data["match_label"] = (
        data["match_date"].dt.strftime("%Y-%m-%d").fillna("Sem data")
        + " | "
        + data["competition_stage"].astype(str)
        + " | "
        + data["home_team"].astype(str)
        + " "
        + data["score"]
        + " "
        + data["away_team"].astype(str)
    )

    return data


def build_champions(
    matches: pd.DataFrame,
    player_shots: pd.DataFrame | None = None,
) -> pd.DataFrame:
    finals = prepare_matches(matches)
    finals = finals[finals["competition_stage"].eq("Final")].copy()

    rows = []

    for final in finals.sort_values("edition_year").itertuples(index=False):
        match = pd.Series(final._asdict())
        winner = infer_match_winner(match, player_shots)
        champion = winner.winner

        runner_up = None
        if champion == final.home_team:
            runner_up = final.away_team
        elif champion == final.away_team:
            runner_up = final.home_team

        rows.append(
            {
                "edition_year": final.edition_year,
                "champion": champion,
                "runner_up": runner_up,
                "final": f"{final.home_team} {final.score} {final.away_team}",
                "final_date": final.match_date,
                "penalty_score": winner.penalty_score,
                "winner_source": winner.source,
            }
        )

    return pd.DataFrame(rows)


def build_top_scorers(
    player_summary: pd.DataFrame,
    edition_year: int | str | None = None,
    limit: int = 20,
) -> pd.DataFrame:
    data = player_summary.copy()

    if "player_display_name" not in data.columns:
        data["player_display_name"] = data["player_name"]

    if edition_year not in (None, "Todas"):
        data = data[data["edition_year"].eq(int(edition_year))]

    return (
        data[data["goals"].gt(0)]
        .sort_values(["goals", "xg", "shots"], ascending=False)
        .head(limit)
        .reset_index(drop=True)
    )


def build_assist_leaderboard(limit: int = 20) -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "edition_year",
            "team_name",
            "player_display_name",
            "assists",
        ]
    ).head(limit)


def build_group_table(matches: pd.DataFrame, edition_year: int) -> pd.DataFrame:
    data = prepare_matches(matches)
    data = data[
        data["edition_year"].eq(edition_year)
        & data["competition_stage"].isin(GROUP_STAGES)
    ].copy()

    rows = []

    for match in data.itertuples(index=False):
        outcomes = [
            (
                match.home_team,
                match.home_score,
                match.away_score,
            ),
            (
                match.away_team,
                match.away_score,
                match.home_score,
            ),
        ]

        for team, goals_for, goals_against in outcomes:
            rows.append(
                {
                    "stage": match.competition_stage,
                    "team_name": team,
                    "played": 1,
                    "wins": int(goals_for > goals_against),
                    "draws": int(goals_for == goals_against),
                    "losses": int(goals_for < goals_against),
                    "goals_for": goals_for,
                    "goals_against": goals_against,
                }
            )

    if not rows:
        return pd.DataFrame(
            columns=[
                "stage",
                "team_name",
                "played",
                "wins",
                "draws",
                "losses",
                "goals_for",
                "goals_against",
                "goal_difference",
                "points",
            ]
        )

    table = (
        pd.DataFrame(rows)
        .groupby(["stage", "team_name"], as_index=False)
        .sum(numeric_only=True)
    )

    table["goal_difference"] = table["goals_for"] - table["goals_against"]
    table["points"] = table["wins"] * 3 + table["draws"]

    return table.sort_values(
        ["stage", "points", "goal_difference", "goals_for", "team_name"],
        ascending=[True, False, False, False, True],
    ).reset_index(drop=True)


def infer_group_assignments(matches: pd.DataFrame, edition_year: int) -> pd.DataFrame:
    data = prepare_matches(matches)
    group_matches = data[
        data["edition_year"].eq(edition_year)
        & data["competition_stage"].isin(GROUP_STAGES)
    ].copy()

    if group_matches.empty:
        return pd.DataFrame(columns=["team_name", "group_name"])

    adjacency: dict[str, set[str]] = {}
    first_date: dict[str, pd.Timestamp] = {}

    for match in group_matches.itertuples(index=False):
        home_team = str(match.home_team)
        away_team = str(match.away_team)
        adjacency.setdefault(home_team, set()).add(away_team)
        adjacency.setdefault(away_team, set()).add(home_team)
        match_date = match.match_date
        for team in [home_team, away_team]:
            if team not in first_date or match_date < first_date[team]:
                first_date[team] = match_date

    components = []
    seen: set[str] = set()

    for team in sorted(adjacency):
        if team in seen:
            continue

        stack = [team]
        component = set()

        while stack:
            current = stack.pop()
            if current in component:
                continue
            component.add(current)
            stack.extend(adjacency[current] - component)

        seen.update(component)
        components.append(component)

    components = sorted(
        components,
        key=lambda component: (
            min(first_date[team] for team in component),
            sorted(component)[0],
        ),
    )

    rows = []
    for index, component in enumerate(components):
        group_name = GROUP_LETTERS[index]
        for team in sorted(component):
            rows.append({"team_name": team, "group_name": group_name})

    return pd.DataFrame(rows)


def build_scheduled_group_tables(groups: pd.DataFrame) -> pd.DataFrame:
    if groups.empty:
        return pd.DataFrame()

    table = groups.copy()
    table["played"] = 0
    table["wins"] = 0
    table["draws"] = 0
    table["losses"] = 0
    table["goals_for"] = 0
    table["goals_against"] = 0
    table["goal_difference"] = 0
    table["points"] = 0

    return table[
        [
            "edition_year",
            "group_name",
            "position",
            "team_name",
            "played",
            "wins",
            "draws",
            "losses",
            "goals_for",
            "goals_against",
            "goal_difference",
            "points",
        ]
    ].sort_values(["group_name", "position"])


def build_competition_group_tables(
    matches: pd.DataFrame,
    edition_year: int,
    scheduled_groups: pd.DataFrame | None = None,
) -> pd.DataFrame:
    if scheduled_groups is not None and not scheduled_groups.empty:
        edition_groups = scheduled_groups[
            scheduled_groups["edition_year"].eq(edition_year)
        ].copy()
        if not edition_groups.empty:
            return build_scheduled_group_tables(edition_groups)

    historical = build_group_table(matches, edition_year)
    if historical.empty:
        return historical

    assignments = infer_group_assignments(matches, edition_year)
    historical = historical.merge(assignments, on="team_name", how="left")
    historical["group_name"] = historical["group_name"].fillna(historical["stage"])
    historical["edition_year"] = edition_year
    historical["position"] = (
        historical.groupby("group_name")
        .cumcount()
        .add(1)
    )

    return historical[
        [
            "edition_year",
            "group_name",
            "position",
            "team_name",
            "played",
            "wins",
            "draws",
            "losses",
            "goals_for",
            "goals_against",
            "goal_difference",
            "points",
        ]
    ]


def build_group_fixtures(
    matches: pd.DataFrame,
    edition_year: int,
    scheduled_fixtures: pd.DataFrame | None = None,
) -> pd.DataFrame:
    if scheduled_fixtures is not None and not scheduled_fixtures.empty:
        scheduled = scheduled_fixtures[
            scheduled_fixtures["edition_year"].eq(edition_year)
            & scheduled_fixtures["stage"].eq("Group Stage")
        ].copy()

        if not scheduled.empty:
            scheduled["competition_stage"] = scheduled["stage"]
            scheduled["score"] = "x"
            scheduled["match_label_date"] = "A definir"
            scheduled["stadium"] = pd.NA
            return scheduled.sort_values(
                ["group_name", "round_number", "match_number"]
            ).reset_index(drop=True)

    data = prepare_matches(matches)
    group_matches = data[
        data["edition_year"].eq(edition_year)
        & data["competition_stage"].isin(GROUP_STAGES)
    ].copy()

    if group_matches.empty:
        return group_matches

    assignments = infer_group_assignments(matches, edition_year)
    group_matches = group_matches.merge(
        assignments.rename(columns={"team_name": "home_team", "group_name": "home_group"}),
        on="home_team",
        how="left",
    )
    group_matches = group_matches.merge(
        assignments.rename(columns={"team_name": "away_team", "group_name": "away_group"}),
        on="away_team",
        how="left",
    )
    group_matches["group_name"] = group_matches["home_group"].fillna(
        group_matches["away_group"]
    )
    group_matches["match_label_date"] = group_matches["match_date"].dt.strftime(
        "%d/%m/%Y"
    )

    return group_matches.sort_values(
        ["group_name", "match_date", "match_id"]
    ).reset_index(drop=True)


def build_knockout_matches(
    matches: pd.DataFrame,
    player_shots: pd.DataFrame | None = None,
    edition_year: int | str | None = None,
) -> pd.DataFrame:
    data = prepare_matches(matches)
    data = data[~data["competition_stage"].isin(GROUP_STAGES)].copy()

    if edition_year not in (None, "Todas"):
        data = data[data["edition_year"].eq(int(edition_year))]

    winners = []
    penalty_scores = []

    for match in data.itertuples(index=False):
        winner = infer_match_winner(pd.Series(match._asdict()), player_shots)
        winners.append(winner.winner)
        penalty_scores.append(winner.penalty_score)

    data["winner"] = winners
    data["penalty_score"] = penalty_scores

    return data.sort_values(
        ["edition_year", "stage_order", "match_date", "match_id"],
        ascending=[False, True, True, True],
    ).reset_index(drop=True)


def build_competition_knockouts(
    matches: pd.DataFrame,
    player_shots: pd.DataFrame | None = None,
    edition_year: int | str | None = None,
    scheduled_fixtures: pd.DataFrame | None = None,
) -> pd.DataFrame:
    if scheduled_fixtures is not None and not scheduled_fixtures.empty:
        scheduled = scheduled_fixtures[
            scheduled_fixtures["stage"].ne("Group Stage")
        ].copy()
        if edition_year not in (None, "Todas"):
            scheduled = scheduled[scheduled["edition_year"].eq(int(edition_year))]

        if not scheduled.empty:
            scheduled["competition_stage"] = scheduled["stage"]
            scheduled["score"] = "TBD"
            scheduled["winner"] = "TBD"
            scheduled["penalty_score"] = pd.NA
            scheduled["stadium"] = pd.NA
            scheduled["stage_order"] = scheduled["competition_stage"].map(
                STAGE_ORDER
            ).fillna(99)
            return scheduled.sort_values(
                ["edition_year", "stage_order", "round_number", "match_number"],
                ascending=[False, True, True, True],
            ).reset_index(drop=True)

    return build_knockout_matches(matches, player_shots, edition_year)


def build_edition_overview(
    matches: pd.DataFrame,
    player_summary: pd.DataFrame,
    player_shots: pd.DataFrame | None = None,
) -> pd.DataFrame:
    prepared_matches = prepare_matches(matches)
    champions = build_champions(matches, player_shots)

    match_stats = (
        prepared_matches.groupby("edition_year", as_index=False)
        .agg(
            matches=("match_id", "count"),
            goals=("total_goals", "sum"),
            first_match=("match_date", "min"),
            last_match=("match_date", "max"),
        )
    )

    teams = pd.concat(
        [
            prepared_matches[["edition_year", "home_team"]].rename(
                columns={"home_team": "team_name"}
            ),
            prepared_matches[["edition_year", "away_team"]].rename(
                columns={"away_team": "team_name"}
            ),
        ],
        ignore_index=True,
    )

    team_counts = (
        teams.drop_duplicates()
        .groupby("edition_year", as_index=False)
        .agg(teams=("team_name", "count"))
    )

    attacking = (
        player_summary.groupby("edition_year", as_index=False)
        .agg(
            shots=("shots", "sum"),
            xg=("xg", "sum"),
            players_with_shots=("player_name", "count"),
        )
    )

    overview = (
        match_stats.merge(team_counts, on="edition_year", how="left")
        .merge(attacking, on="edition_year", how="left")
        .merge(
            champions[["edition_year", "champion", "runner_up"]],
            on="edition_year",
            how="left",
        )
        .sort_values("edition_year", ascending=False)
    )

    overview["goals_per_match"] = (
        overview["goals"].div(overview["matches"]).round(2)
    )
    overview["xg"] = overview["xg"].fillna(0).round(2)

    return overview.reset_index(drop=True)
