from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from typing import Any


PRIVATE_DIGIT_MAP = {
    "\ue071": "0",
    "\ue072": "1",
    "\ue073": "2",
    "\ue074": "3",
    "\ue075": "4",
    "\ue076": "5",
    "\ue077": "6",
    "\ue078": "7",
    "\ue079": "8",
    "\ue07a": "9",
    "\ue094": ".",
}

PROVENANCE_FIELDS = (
    "document_id",
    "match_id",
    "source_file",
    "page_number",
    "confidence",
)


def _clean_text(text: str) -> str:
    return unicodedata.normalize("NFKC", text.replace("\x00", "ff"))


def _slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", ascii_value.lower()).strip("-")


def _provenance(
    *,
    document_id: str,
    match_id: str,
    source_file: str,
    page_number: int,
    confidence: float,
) -> dict[str, Any]:
    return {
        "document_id": document_id,
        "match_id": match_id,
        "source_file": source_file,
        "page_number": page_number,
        "confidence": confidence,
    }


def issue_row(
    *,
    document_id: str,
    match_id: str,
    source_file: str,
    page_number: int,
    severity: str,
    issue_type: str,
    message: str,
    raw_value: str = "",
    confidence: float = 0.0,
) -> dict[str, Any]:
    issue_id = "|".join(
        [
            document_id,
            str(page_number),
            issue_type,
            _slug(message)[:80],
        ]
    )
    return {
        **_provenance(
            document_id=document_id,
            match_id=match_id,
            source_file=source_file,
            page_number=page_number,
            confidence=confidence,
        ),
        "issue_id": issue_id,
        "severity": severity,
        "issue_type": issue_type,
        "message": message,
        "raw_value": raw_value,
    }


def classify_page(text: str) -> str:
    clean_text = _clean_text(text)
    clean = clean_text.lower()
    lines = [line.strip().lower() for line in clean_text.splitlines() if line.strip()]
    title = lines[1] if len(lines) > 1 and re.match(r"^\d{1,2}\s+\w+\s+\d{4}\s+-", lines[0]) else (lines[0] if lines else "")
    if "post match summary report" in clean:
        return "cover"
    if title.startswith("match summary - key statistics"):
        return "key_statistics"
    if "phases of play" in title:
        return "phases_of_play"
    if (
        title.startswith("attempts at goal")
        and (
            len(lines) == 1
            or "time player outcome body part delivery type" in clean
        )
    ):
        return "attempts_at_goal"
    if title.startswith("physical data"):
        return "player_physical"
    if title.startswith("out of possession "):
        return "player_out_of_possession"
    if (
        title.startswith("in possession - distributions")
        or title.startswith("in possession - offers & receptions")
    ):
        return "player_in_possession"
    if not clean.strip():
        return "blank"
    return "unknown"


def parse_cover(
    text: str,
    *,
    document_id: str,
    source_file: str,
    page_number: int,
    edition: int,
) -> dict[str, Any]:
    clean = _clean_text(text)
    lines = [line.strip() for line in clean.splitlines() if line.strip()]
    score = re.search(
        r"^(.+?)\s+(\d+)\s*-\s*(\d+)\s+(.+?)$",
        lines[0] if lines else "",
    )
    group_match = re.search(r"Group\s+(.+?)\s*-\s*Match\s+(\d+)", clean, re.I)
    date_match = re.search(r"(\d{1,2}\s+[A-Za-z]+\s+\d{4})", clean)
    time_match = re.search(r"\b(\d{1,2}:\d{2})\b", clean)
    if not all((score, group_match, date_match, time_match)):
        raise ValueError("Cover metadata could not be parsed")

    home_team = score.group(1).strip()
    away_team = score.group(4).strip()
    match_number = int(group_match.group(2))
    match_id = (
        f"{edition}-match-{match_number}-{_slug(home_team)}-{_slug(away_team)}"
    )
    match_date = datetime.strptime(
        date_match.group(1), "%d %B %Y"
    ).date().isoformat()
    stadium = ""
    for index, line in enumerate(lines):
        if time_match.group(1) in line and index + 1 < len(lines):
            stadium = lines[index + 1]
            break

    return {
        **_provenance(
            document_id=document_id,
            match_id=match_id,
            source_file=source_file,
            page_number=page_number,
            confidence=1.0,
        ),
        "edition": edition,
        "group_name": group_match.group(1).strip(),
        "match_number": match_number,
        "match_date": match_date,
        "kickoff_time": time_match.group(1),
        "stadium": stadium,
        "home_team": home_team,
        "away_team": away_team,
        "home_score": int(score.group(2)),
        "away_score": int(score.group(3)),
        "data_coverage_level": "fifa_pdf",
    }


def _number(value: str) -> int | float:
    clean = normalize_private_digits(value).replace("%", "").replace("km", "").strip()
    number = float(clean)
    return int(number) if number.is_integer() else number


def _metric_rows(
    *,
    metric_name: str,
    values: tuple[str, str],
    teams: tuple[str, str],
    unit: str,
    document_id: str,
    match_id: str,
    source_file: str,
    page_number: int,
    confidence: float = 1.0,
) -> list[dict[str, Any]]:
    return [
        {
            **_provenance(
                document_id=document_id,
                match_id=match_id,
                source_file=source_file,
                page_number=page_number,
                confidence=confidence,
            ),
            "team_name": team,
            "metric_name": metric_name,
            "value": _number(raw),
            "unit": unit,
            "raw_value": raw,
        }
        for team, raw in zip(teams, values)
    ]


def parse_key_statistics(
    text: str,
    *,
    teams: tuple[str, str],
    document_id: str,
    match_id: str,
    source_file: str,
    page_number: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    clean = _clean_text(text)
    rows: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    simple_patterns = [
        ("goals", r"(?m)^(\d+)\s+Goals\s+(\d+)$", "count"),
        (
            "expected_goals",
            r"(?m)^(\d+(?:\.\d+)?)\s+xG \(Expected Goals\)\s+(\d+(?:\.\d+)?)$",
            "goals",
        ),
        (
            "pass_completion_pct",
            r"(?m)^(\d+)\s+%\s+Pass Completion\s+%\s+(\d+)\s+%$",
            "percent",
        ),
        (
            "completed_line_breaks",
            r"(?m)^(\d+)\s+Completed Line Breaks\s+(\d+)$",
            "count",
        ),
        (
            "defensive_line_breaks",
            r"(?m)^(\d+)\s+Defensive Line Breaks\s+(\d+)$",
            "count",
        ),
        (
            "final_third_receptions",
            r"(?m)^(\d+)\s+Receptions in the Final Third\s+(\d+)$",
            "count",
        ),
        ("crosses", r"(?m)^(\d+)\s+Crosses\s+(\d+)$", "count"),
        (
            "ball_progressions",
            r"(?m)^(\d+)\s+Ball Progressions\s+(\d+)$",
            "count",
        ),
        (
            "forced_turnovers",
            r"(?m)^(\d+)\s+Forced Turnovers\s+(\d+)$",
            "count",
        ),
        ("second_balls", r"(?m)^(\d+)\s+Second Balls\s+(\d+)$", "count"),
        (
            "total_distance_km",
            r"(?m)^(\d+(?:\.\d+)?)\s+km\s+Total Distance Covered\s+(\d+(?:\.\d+)?)\s+km$",
            "km",
        ),
        (
            "zone_4_distance_km",
            r"(?m)^(\d+(?:\.\d+)?)\s+km\s+Zone 4.+?\s+(\d+(?:\.\d+)?)\s+km$",
            "km",
        ),
    ]
    for metric_name, pattern, unit in simple_patterns:
        match = re.search(pattern, clean)
        if match:
            rows.extend(
                _metric_rows(
                    metric_name=metric_name,
                    values=(match.group(1), match.group(2)),
                    teams=teams,
                    unit=unit,
                    document_id=document_id,
                    match_id=match_id,
                    source_file=source_file,
                    page_number=page_number,
                )
            )

    paired_patterns = [
        (
            r"(?m)^(\d+)\s+\((\d+)\)\s+Attempts at Goal \(On Target\)\s+(\d+)\s+\((\d+)\)$",
            ("attempts_at_goal", "attempts_on_target"),
        ),
        (
            r"(?m)^(\d+)\s+\((\d+)\)\s+Total Passes \(Complete\)\s+(\d+)\s+\((\d+)\)$",
            ("passes_total", "passes_complete"),
        ),
        (
            r"(?m)^(\d+)\s+\((\d+)\)\s+Defensive Pressures Applied \(Direct Pressures\)\s+(\d+)\s+\((\d+)\)$",
            ("defensive_pressures", "direct_pressures"),
        ),
    ]
    for pattern, metric_names in paired_patterns:
        match = re.search(pattern, clean)
        if not match:
            continue
        rows.extend(
            _metric_rows(
                metric_name=metric_names[0],
                values=(match.group(1), match.group(3)),
                teams=teams,
                unit="count",
                document_id=document_id,
                match_id=match_id,
                source_file=source_file,
                page_number=page_number,
            )
        )
        rows.extend(
            _metric_rows(
                metric_name=metric_names[1],
                values=(match.group(2), match.group(4)),
                teams=teams,
                unit="count",
                document_id=document_id,
                match_id=match_id,
                source_file=source_file,
                page_number=page_number,
            )
        )

    if not rows:
        issues.append(
            issue_row(
                document_id=document_id,
                match_id=match_id,
                source_file=source_file,
                page_number=page_number,
                severity="warning",
                issue_type="key_statistics_unparsed",
                message="No known key statistics were parsed",
                raw_value=clean,
            )
        )
    return rows, issues


def parse_phases_of_play(
    text: str,
    *,
    teams: tuple[str, str],
    document_id: str,
    match_id: str,
    source_file: str,
    page_number: int,
) -> list[dict[str, Any]]:
    state = ""
    rows: list[dict[str, Any]] = []
    for raw_line in _clean_text(text).splitlines():
        line = raw_line.strip()
        if line == "IN POSSESSION":
            state = "in_possession"
            continue
        if line == "OUT OF POSSESSION":
            state = "out_of_possession"
            continue
        match = re.match(r"^(\d+)%\s+(.+?)\s+(\d+)%$", line)
        if not match or not state:
            continue
        phase_name = _slug(match.group(2)).replace("-", "_")
        for team, percentage, raw_value in (
            (teams[0], int(match.group(1)), match.group(1) + "%"),
            (teams[1], int(match.group(3)), match.group(3) + "%"),
        ):
            rows.append(
                {
                    **_provenance(
                        document_id=document_id,
                        match_id=match_id,
                        source_file=source_file,
                        page_number=page_number,
                        confidence=1.0,
                    ),
                    "team_name": team,
                    "possession_state": state,
                    "phase_name": phase_name,
                    "percentage": percentage,
                    "raw_value": raw_value,
                }
            )
    return rows


BODY_PARTS = ("Right Foot", "Left Foot", "Head", "Other")
DELIVERY_TYPES = (
    "Ball Progression",
    "Loose Ball",
    "Defensive Event",
    "Interception",
    "Freekick",
    "Corner",
    "Cross",
    "Pass",
    "Other",
)


def parse_attempts(
    text: str,
    *,
    team_name: str,
    document_id: str,
    match_id: str,
    source_file: str,
    page_number: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    body_pattern = "|".join(map(re.escape, BODY_PARTS))
    delivery_pattern = "|".join(map(re.escape, DELIVERY_TYPES))
    pattern = re.compile(
        rf"^(\d+)\s+(\d+)\s*(.+)\s+"
        rf"((?:Deflected\s+)?(?:On Target|Off Target)(?:\s+-\s+.+?)?"
        rf"|Incomplete\s+-\s+.+?)\s+"
        rf"({body_pattern})\s+({delivery_pattern})$"
    )
    for line_number, raw_line in enumerate(_clean_text(text).splitlines(), start=1):
        line = raw_line.strip()
        if not re.match(r"^\d+\s+\d+", line):
            continue
        match = pattern.match(line)
        if not match:
            issues.append(
                issue_row(
                    document_id=document_id,
                    match_id=match_id,
                    source_file=source_file,
                    page_number=page_number,
                    severity="warning",
                    issue_type="attempt_unparsed",
                    message=f"Attempt row {line_number} could not be parsed",
                    raw_value=line,
                    confidence=0.25,
                )
            )
            continue
        minute, shirt_number, player_name, outcome, body_part, delivery_type = (
            match.groups()
        )
        rows.append(
            {
                **_provenance(
                    document_id=document_id,
                    match_id=match_id,
                    source_file=source_file,
                    page_number=page_number,
                    confidence=0.98,
                ),
                "attempt_id": (
                    f"{match_id}|{team_name}|{page_number}|{line_number}|"
                    f"{minute}|{shirt_number}"
                ),
                "team_name": team_name,
                "minute": int(minute),
                "shirt_number": int(shirt_number),
                "player_name": player_name.strip(),
                "outcome": outcome.strip(),
                "body_part": body_part,
                "delivery_type": delivery_type,
                "raw_value": line,
            }
        )
    return rows, issues


def normalize_private_digits(value: str) -> str:
    return "".join(PRIVATE_DIGIT_MAP.get(character, character) for character in value)


PLAYER_SCHEMAS = {
    "distribution": (
        "passes_attempted",
        "passes_completed",
        "pass_completion_pct",
        "switches_of_play",
        "crosses_attempted",
        "crosses_completed",
        "line_breaks_attempted",
        "line_breaks_completed",
        "line_break_completion_pct",
        "ball_progressions",
        "take_ons",
        "step_ins",
        "attempts_at_goal",
        "goals",
    ),
    "offers": (
        "total_offers",
        "offers_in_front",
        "offers_in_between",
        "offers_out_to_in",
        "offers_in_to_out",
        "offers_in_behind",
        "offers_no_movement",
        "offers_received",
    ),
    "out_of_possession": (
        "tackles_made",
        "tackles_won",
        "blocks",
        "interceptions",
        "pressing_direct",
        "pressing_indirect",
        "aerial_duels_won",
        "physical_duels_won",
        "possession_contests_won",
        "clearances",
        "loose_ball_receptions",
        "pushing_on",
        "pushing_on_into_pressing",
        "possession_regains",
        "possession_interrupted",
    ),
    "physical": (
        "total_distance_m",
        "zone_1_distance_m",
        "zone_2_distance_m",
        "zone_3_distance_m",
        "zone_4_distance_m",
        "zone_5_distance_m",
        "high_speed_runs",
        "sprints",
        "top_speed_kmh",
    ),
}


def _player_layout(text: str, domain: str) -> tuple[str, str]:
    clean = _clean_text(text)
    if domain == "player_physical":
        return "physical", "physical"
    if domain == "player_out_of_possession":
        return "out_of_possession", "out_of_possession"
    if "Offers & Receptions" in clean:
        return "offers", "in_possession_offers"
    return "distribution", "in_possession_distribution"


def _split_player_row(line: str) -> tuple[int, str, list[str]] | None:
    match = re.match(r"^(\d+)\s+(.+)$", line)
    if not match:
        return None
    shirt_number = int(match.group(1))
    tokens = match.group(2).split()
    value_index = next(
        (
            index
            for index, token in enumerate(tokens)
            if re.fullmatch(r"(?:[\d.%]+|[\ue071-\ue07a\ue094]+)", token)
        ),
        None,
    )
    if value_index is None or value_index == 0:
        return None
    player_name = " ".join(tokens[:value_index])
    if player_name.lower() in {
        "january",
        "february",
        "march",
        "april",
        "may",
        "june",
        "july",
        "august",
        "september",
        "october",
        "november",
        "december",
    }:
        return None
    values = tokens[value_index:]
    return shirt_number, player_name, values


def parse_player_metrics(
    text: str,
    *,
    domain: str,
    team_name: str,
    document_id: str,
    match_id: str,
    source_file: str,
    page_number: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    layout, metric_group = _player_layout(text, domain)
    schema = PLAYER_SCHEMAS[layout]
    rows: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        parsed = _split_player_row(line)
        if not parsed:
            continue
        shirt_number, player_name, raw_values = parsed
        if layout == "out_of_possession" and len(raw_values) >= 3 and raw_values[1] == "/":
            raw_values = [raw_values[0], raw_values[2], *raw_values[3:]]
        if len(raw_values) != len(schema):
            if any(character in line for character in PRIVATE_DIGIT_MAP) or len(raw_values) >= 5:
                issues.append(
                    issue_row(
                        document_id=document_id,
                        match_id=match_id,
                        source_file=source_file,
                        page_number=page_number,
                        severity="warning",
                        issue_type="player_metric_column_mismatch",
                        message=(
                            f"Player row {line_number} has {len(raw_values)} values; "
                            f"expected {len(schema)}"
                        ),
                        raw_value=line,
                        confidence=0.3,
                    )
                )
            continue
        for metric_name, raw_value in zip(schema, raw_values):
            try:
                value = _number(raw_value)
            except ValueError:
                issues.append(
                    issue_row(
                        document_id=document_id,
                        match_id=match_id,
                        source_file=source_file,
                        page_number=page_number,
                        severity="warning",
                        issue_type="player_metric_invalid_value",
                        message=f"Could not normalize {metric_name} for {player_name}",
                        raw_value=raw_value,
                        confidence=0.2,
                    )
                )
                continue
            rows.append(
                {
                    **_provenance(
                        document_id=document_id,
                        match_id=match_id,
                        source_file=source_file,
                        page_number=page_number,
                        confidence=0.99 if layout == "physical" else 0.98,
                    ),
                    "team_name": team_name,
                    "shirt_number": shirt_number,
                    "player_name": player_name,
                    "metric_group": metric_group,
                    "metric_name": metric_name,
                    "value": value,
                    "unit": (
                        "percent"
                        if metric_name.endswith("_pct")
                        else "km/h"
                        if metric_name == "top_speed_kmh"
                        else "m"
                        if "distance_m" in metric_name
                        else "count"
                    ),
                    "raw_value": raw_value,
                }
            )
    if not rows:
        issues.append(
            issue_row(
                document_id=document_id,
                match_id=match_id,
                source_file=source_file,
                page_number=page_number,
                severity="warning",
                issue_type="player_metrics_unparsed",
                message=f"No player metrics parsed for {domain}",
                raw_value=_clean_text(text),
            )
        )
    return rows, issues
