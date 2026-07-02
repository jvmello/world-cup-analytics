from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from webapp.player_positions import (
    FORMATION_SLOTS,
    assign_benchmark_cohorts,
    audit_lineup_order,
    infer_match_positions,
    resolve_public_position,
    summarize_tournament_positions,
)
from thestatsapi.position_report import build_position_report


def _player(
    player_id: str,
    position: str,
    *,
    started: bool = True,
    minutes: int = 90,
    **metrics: object,
) -> dict[str, object]:
    return {
        "player_id": player_id,
        "player_name": player_id,
        "team_id": "team-1",
        "position": position,
        "started": started,
        "played": minutes > 0,
        "minutes_played": minutes,
        **metrics,
    }


def test_known_formations_have_controlled_tactical_slots() -> None:
    assert FORMATION_SLOTS["4-3-3"] == (
        "Goleiro",
        "Lateral esquerdo",
        "Zagueiro",
        "Zagueiro",
        "Lateral direito",
        "Meio-campista central",
        "Meio-campista central",
        "Meio-campista central",
        "Ponta esquerda",
        "Centroavante",
        "Ponta direita",
    )
    assert {
        "4-2-3-1", "4-4-2", "3-5-2", "3-4-3", "5-3-2",
        "4-1-4-1", "4-3-1-2",
    }.issubset(FORMATION_SLOTS)


def test_coarse_grouped_lineup_order_is_not_treated_as_tactical_order() -> None:
    lineup = {
        "formation": "4-3-3",
        "starting_xi": [
            {"id": "g", "position": "G"},
            *({"id": f"d-{index}", "position": "D"} for index in range(4)),
            *({"id": f"m-{index}", "position": "M"} for index in range(3)),
            *({"id": f"f-{index}", "position": "F"} for index in range(3)),
        ],
    }

    audit = audit_lineup_order(lineup)

    assert audit["formation_mapped"] is True
    assert audit["grouped_api_order"] is True
    assert audit["slot_order_reliable"] is False
    assert audit["reason"] == "coarse_api_groups_only"


def test_match_inference_uses_statistics_and_safe_substitution_inheritance() -> None:
    lineups = {
        "home": {
            "id": "team-1",
            "name": "Team One",
            "formation": "4-3-3",
            "starting_xi": [
                {"id": "keeper", "position": "G"},
                {"id": "starter-defender", "position": "D"},
            ],
            "substitutes": [{"id": "bench-defender", "position": "D"}],
        }
    }
    players = [
        _player("keeper", "G"),
        _player("starter-defender", "D", minutes=45, clearances=6, interceptions=2, total_crosses=0),
        _player("bench-defender", "D", started=False, minutes=45),
    ]
    events = [
        {
            "minute": 46,
            "type": "substitution",
            "team": {"id": "team-1", "name": "Team One"},
            "player": {"id": "bench-defender", "name": "bench-defender"},
        }
    ]

    inferred = {
        row["player_id"]: row
        for row in infer_match_positions("match-1", lineups, players, events)
    }

    assert inferred["keeper"]["inferred_role"] == "Goleiro"
    assert inferred["keeper"]["role_confidence"] == "high"
    assert inferred["starter-defender"]["inferred_role"] == "Zagueiro"
    assert inferred["starter-defender"]["role_source"] == "statistics_profile"
    assert inferred["bench-defender"]["inferred_role"] == "Zagueiro"
    assert inferred["bench-defender"]["role_source"] == "substitution_inheritance"
    assert inferred["bench-defender"]["role_confidence"] == "medium"


def test_simultaneous_substitutions_do_not_claim_role_inheritance() -> None:
    lineups = {
        "home": {
            "id": "team-1",
            "formation": "4-4-2",
            "starting_xi": [
                {"id": "starter-a", "position": "M"},
                {"id": "starter-b", "position": "M"},
            ],
            "substitutes": [
                {"id": "bench-a", "position": "M"},
                {"id": "bench-b", "position": "M"},
            ],
        }
    }
    players = [
        _player("starter-a", "M", minutes=60),
        _player("starter-b", "M", minutes=60),
        _player("bench-a", "M", started=False, minutes=30),
        _player("bench-b", "M", started=False, minutes=30),
    ]
    events = [
        {"minute": 60, "type": "substitution", "team": {"id": "team-1"}, "player": {"id": player_id}}
        for player_id in ("bench-a", "bench-b")
    ]

    inferred = infer_match_positions("match-1", lineups, players, events)
    substitutes = [row for row in inferred if not row["is_starter"]]

    assert all(row["role_source"] != "substitution_inheritance" for row in substitutes)
    assert all(row["role_confidence"] == "low" for row in substitutes)


def test_attacker_profile_prioritizes_volume_before_incidental_xa() -> None:
    lineups = {"home": {"id": "team-1", "formation": "4-3-3", "starting_xi": [], "substitutes": []}}
    players = [
        _player("striker", "F", shots=4, xg=.9, xa=.2, key_passes=1, total_crosses=0),
        _player("winger", "F", shots=2, xg=.2, xa=.25, key_passes=2, total_crosses=3),
    ]

    inferred = {row["player_id"]: row for row in infer_match_positions("match-1", lineups, players, [])}

    assert inferred["striker"]["inferred_role"] == "Centroavante"
    assert inferred["winger"]["inferred_role"] == "Ponta"


def test_tournament_summary_is_minutes_weighted_and_marks_multifunctional() -> None:
    rows = [
        {**_player("p1", "F", minutes=80), "inferred_role": "Centroavante", "inferred_side": "Centro", "role_source": "statistics_profile", "role_confidence": "medium"},
        {**_player("p1", "F", minutes=70), "inferred_role": "Ponta esquerda", "inferred_side": "Esquerda", "role_source": "formation_slot", "role_confidence": "high"},
        {**_player("p1", "F", minutes=50), "inferred_role": "Segundo atacante", "inferred_side": "Centro", "role_source": "statistics_profile", "role_confidence": "medium"},
    ]

    summary = summarize_tournament_positions(rows)

    assert summary["primary_inferred_role"] == "Centroavante"
    assert summary["secondary_inferred_roles"] == ["Ponta esquerda", "Segundo atacante"]
    assert summary["role_minutes_breakdown"][0] == {"role": "Centroavante", "minutes": 80.0, "percentage": 40.0}
    assert summary["is_multifunctional"] is True
    assert summary["review_status"] == "needs_review"
    assert summary["total_minutes"] == 200.0


def test_public_resolution_uses_only_reliable_inference() -> None:
    assert resolve_public_position({"position": "F", "primary_inferred_role": "Ponta", "role_confidence": "medium"}) == "Ponta"
    assert resolve_public_position({"position": "F", "primary_inferred_role": "Ponta", "role_confidence": "low"}) == "Atacante"
    assert resolve_public_position({}) == "Posição não informada"


def test_benchmark_cohort_falls_back_when_detailed_sample_is_small() -> None:
    players = [
        {
            **_player(f"forward-{index}", "F"),
            "primary_inferred_role": "Centroavante" if index < 4 else "Ponta",
            "role_confidence": "medium",
        }
        for index in range(6)
    ]

    assigned = assign_benchmark_cohorts(players, minimum_sample=5)

    assert {row["benchmark_position"] for row in assigned} == {"Atacantes"}
    assert {row["benchmark_label"] for row in assigned} == {"Média dos atacantes"}
    assert {row["benchmark_sample_size"] for row in assigned} == {6}

    detailed = assign_benchmark_cohorts(
        [
            {
                **_player(f"striker-{index}", "F"),
                "primary_inferred_role": "Centroavante",
                "role_confidence": "medium",
            }
            for index in range(5)
        ],
        minimum_sample=5,
    )
    assert {row["benchmark_position"] for row in detailed} == {"Centroavante"}
    assert {row["benchmark_label"] for row in detailed} == {"Média dos centroavantes"}


def test_internal_report_separates_match_and_tournament_diagnostics() -> None:
    match_role = {
        "match_id": "match-1", "player_id": "p1", "player_name": "Player",
        "team_id": "t1", "team_name": "Team", "api_position_group": "Atacante",
        "formation": "4-3-3", "minutes_played": 90, "inferred_role": "Centroavante",
        "inferred_side": "Centro", "role_source": "statistics_profile",
        "role_confidence": "medium", "formation_mapped": True,
        "lineup_order_reliable": False,
    }
    tournament_role = {
        "player_id": "p1", "player_name": "Player", "team_id": "t1", "team_name": "Team",
        "api_position_group": "Atacante", "primary_inferred_role": "Centroavante",
        "secondary_inferred_roles": [], "role_minutes_breakdown": [],
        "role_source_summary": {"statistics_profile": 1}, "role_confidence": "medium",
        "is_multifunctional": False, "total_minutes": 90, "review_status": "auto_inferred",
        "resolved_position": "Centroavante", "benchmark_position": "Atacantes",
    }

    report = build_position_report(2026, [{"players": [match_role]}], [tournament_role])

    assert report["summary"]["match_roles"] == 1
    assert report["summary"]["lineup_order_reliable"] == 0
    assert report["summary"]["confidence"] == {"medium": 1}
    assert report["player_match_position_roles"][0]["role_source"] == "statistics_profile"
    assert report["player_tournament_position_summary"][0]["resolved_position"] == "Centroavante"
