from __future__ import annotations

import pytest

from webapp.player_analytics import (
    calculate_player_radar,
    robust_score,
    weighted_dimension_score,
)


def test_robust_score_handles_missing_flat_inverted_and_clipped_values() -> None:
    assert robust_score(None, 0, 10) is None
    assert robust_score(5, None, 10) is None
    assert robust_score(5, 4, 4) == 50
    assert robust_score(15, 0, 10) == 100
    assert robust_score(-5, 0, 10) == 0
    assert robust_score(2, 0, 10, higher_is_better=False) == 80


def test_weighted_dimension_score_ignores_missing_scores_and_reweights() -> None:
    result = weighted_dimension_score(
        {"xg": 80, "shots": 20, "dribbles": None},
        {"xg": 0.6, "shots": 0.3, "dribbles": 0.1},
    )

    assert result["score"] == 60
    assert result["available_metrics_count"] == 2
    assert result["expected_metrics_count"] == 3
    assert result["coverage_pct"] == pytest.approx(66.7)
    assert result["confidence"] == "medium"
    assert result["available_metrics"] == ["xg", "shots"]
    assert result["missing_metrics"] == ["dribbles"]


def test_player_radar_keeps_real_zero_and_omits_unavailable_dimensions() -> None:
    reference = {
        "Centroavante": {
            "xg": {"p05": 0, "p50": 0.5, "p95": 1.0, "mean": 0.5, "samples": 8},
            "shots_on_target": {"p05": 0, "p50": 1, "p95": 2, "mean": 1, "samples": 8},
        }
    }
    player = {
        "player_id": "p1",
        "player_name": "Atacante",
        "position": "F",
        "xg": 0,
        "shots": None,
        "shots_on_target": 1,
        "xg_per_shot": None,
    }

    result = calculate_player_radar(player, reference, "Centroavante")

    attack = result["dimensions"]["Ataque"]
    assert attack["score"] == pytest.approx(18.2)
    assert attack["metric_scores"]["xg"]["raw_value"] == 0
    assert "xg" in attack["available_metrics"]
    assert "shots" in attack["missing_metrics"]
    assert result["dimensions"]["Progressão"]["score"] is None
    assert all(axis["axis"] != "Progressão" for axis in result["radar"])


def test_outfield_radar_adds_duels_and_participation_when_supported() -> None:
    metrics = {
        "xg": 0.4,
        "xa": 0.2,
        "accurate_passes": 30,
        "tackles": 2,
        "duels_won": 5,
        "touches": 48,
    }
    reference = {
        "Volante/Meio-campista": {
            metric: {"p05": 0, "p50": value / 2, "p95": value * 2, "mean": value, "samples": 8}
            for metric, value in metrics.items()
        }
    }
    player = {
        "player_id": "p2",
        "player_name": "Meio-campista",
        "position": "M",
        **metrics,
    }

    result = calculate_player_radar(
        player,
        reference,
        "Volante/Meio-campista",
    )

    axes = {axis["axis"] for axis in result["radar"]}
    assert axes == {"Ataque", "Criação", "Passe", "Defesa", "Duelos", "Participação"}
