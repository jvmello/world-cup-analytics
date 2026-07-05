from __future__ import annotations

from math import floor
from typing import Any
import unicodedata

from .player_positions import radar_profile_group


OUTFIELD_RADAR_CONFIG: dict[str, dict[str, float]] = {
    "Ataque": {
        "xg": 0.35,
        "shots": 0.20,
        "shots_on_target": 0.20,
        "xg_per_shot": 0.15,
        "successful_dribbles": 0.10,
    },
    "Criação": {
        "xa": 0.35,
        "key_passes": 0.30,
        "big_chances_created": 0.20,
        "assists": 0.15,
    },
    "Progressão": {
        "progressive_passes": 0.45,
        "progressive_carries": 0.35,
        "progressive_distance": 0.20,
    },
    "Passe": {
        "accurate_passes": 0.30,
        "pass_accuracy": 0.25,
        "pressured_pass_accuracy": 0.25,
        "long_pass_accuracy": 0.20,
    },
    "Defesa": {
        "recoveries": 0.25,
        "tackles": 0.30,
        "interceptions": 0.25,
        "clearances": 0.20,
    },
    "Duelos": {
        "duels_won": 0.45,
        "aerial_won": 0.35,
        "successful_dribbles": 0.20,
    },
    "Participação": {"touches": 0.55, "passes": 0.25, "minutes_played": 0.20},
    "Pressão": {
        "pressures": 0.45,
        "counterpressures": 0.35,
        "final_third_pressures": 0.20,
    },
}

GOALKEEPER_RADAR_CONFIG: dict[str, dict[str, float]] = {
    "Defesa do gol": {"saves": 0.55, "save_percentage": 0.45},
    "Distribuição": {
        "accurate_passes": 0.45,
        "pass_accuracy": 0.35,
        "passes": 0.20,
    },
    "Passe longo": {
        "accurate_long_balls": 0.55,
        "long_pass_accuracy": 0.45,
    },
    "Participação com bola": {"touches": 0.55, "passes": 0.45},
    "Ações fora da área": {"clearances": 0.60, "recoveries": 0.40},
    "Pressão sofrida": {"pressures_faced": 0.60, "pressured_pass_accuracy": 0.40},
}

DIMENSION_IMPORTANCE: dict[str, dict[str, float]] = {
    "Goleiro": {
        "Defesa do gol": 1.0,
        "Distribuição": 0.75,
        "Passe longo": 0.70,
        "Participação com bola": 0.65,
        "Ações fora da área": 0.45,
        "Pressão sofrida": 0.40,
    },
    "Zagueiro": {"Defesa": 1.0, "Duelos": 0.90, "Passe": 0.85, "Participação": 0.55, "Criação": 0.30, "Ataque": 0.25},
    "Lateral/Ala": {"Duelos": 0.85, "Criação": 0.85, "Defesa": 0.70, "Participação": 0.70, "Passe": 0.65, "Ataque": 0.45},
    "Volante/Meio-campista": {"Passe": 1.0, "Participação": 0.85, "Defesa": 0.80, "Duelos": 0.80, "Criação": 0.65, "Ataque": 0.30},
    "Meia ofensivo/Ponta": {"Criação": 1.0, "Ataque": 1.0, "Duelos": 0.65, "Participação": 0.70, "Passe": 0.60, "Defesa": 0.25},
    "Centroavante": {"Ataque": 1.0, "Duelos": 0.70, "Participação": 0.55, "Criação": 0.50, "Passe": 0.40, "Defesa": 0.20},
}

METRIC_LABELS = {
    "xg": "xG",
    "shots": "finalizações",
    "shots_on_target": "chutes no alvo",
    "xg_per_shot": "xG por chute",
    "successful_dribbles": "dribles completos",
    "xa": "xA",
    "key_passes": "passes para finalização",
    "big_chances_created": "grandes chances criadas",
    "assists": "assistências",
    "progressive_passes": "passes progressivos",
    "progressive_carries": "conduções progressivas",
    "progressive_distance": "distância em progressão",
    "accurate_passes": "passes certos",
    "pass_accuracy": "precisão de passe",
    "pressured_pass_accuracy": "precisão sob pressão",
    "long_pass_accuracy": "precisão de passe longo",
    "recoveries": "recuperações",
    "tackles": "desarmes",
    "interceptions": "interceptações",
    "clearances": "cortes",
    "aerial_won": "duelos aéreos vencidos",
    "duels_won": "duelos vencidos",
    "pressures": "pressões",
    "counterpressures": "counterpress",
    "final_third_pressures": "pressões no terço final",
    "saves": "defesas",
    "save_percentage": "taxa de defesas",
    "passes": "passes",
    "accurate_long_balls": "passes longos certos",
    "touches": "toques",
    "minutes_played": "minutos",
    "pressures_faced": "pressões sofridas",
}

VOLUME_DENOMINATORS = {
    "pass_accuracy": "passes",
    "long_pass_accuracy": "total_long_balls",
    "save_percentage": "shots_on_target_faced",
    "pressured_pass_accuracy": "pressured_passes",
}


def _number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed


def robust_score(
    value: Any,
    p05: Any,
    p95: Any,
    higher_is_better: bool = True,
) -> float | None:
    """Normalize a value to 0-100 while preserving unavailable values."""
    resolved_value = _number(value)
    lower = _number(p05)
    upper = _number(p95)
    if resolved_value is None or lower is None or upper is None:
        return None
    if upper <= lower:
        return 50.0
    score = max(0.0, min(100.0, (resolved_value - lower) / (upper - lower) * 100))
    if not higher_is_better:
        score = 100 - score
    return round(score, 1)


def weighted_dimension_score(
    metric_scores: dict[str, float | None],
    metric_weights: dict[str, float],
) -> dict[str, Any]:
    """Combine only available metric scores and renormalize their weights."""
    available = [name for name in metric_weights if metric_scores.get(name) is not None]
    missing = [name for name in metric_weights if metric_scores.get(name) is None]
    total_weight = sum(max(0.0, metric_weights[name]) for name in available)
    score = None
    if available and total_weight > 0:
        score = round(
            sum(float(metric_scores[name]) * max(0.0, metric_weights[name]) for name in available)
            / total_weight,
            1,
        )
    expected = len(metric_weights)
    coverage = round(len(available) / expected * 100, 1) if expected else 0.0
    if not available:
        confidence = "unavailable"
    elif len(available) == 1:
        confidence = "low"
    elif coverage >= 75:
        confidence = "high"
    else:
        confidence = "medium"
    return {
        "score": score,
        "available_metrics_count": len(available),
        "expected_metrics_count": expected,
        "coverage_pct": coverage,
        "confidence": confidence,
        "available_metrics": available,
        "missing_metrics": missing,
    }


def macroposition_for(position: Any) -> str:
    raw = unicodedata.normalize("NFD", str(position or ""))
    normalized = "".join(char for char in raw if unicodedata.category(char) != "Mn").casefold()
    if normalized in {"g", "gk", "gol", "goalkeeper", "goleiro"}:
        return "Goleiro"
    if any(term in normalized for term in ("lateral", "ala", "wingback")):
        return "Lateral/Ala"
    if normalized in {"d", "df", "def"} or any(term in normalized for term in ("zague", "defender")):
        return "Zagueiro"
    if any(term in normalized for term in ("ponta", "meia ofens", "winger", "attacking midfield")):
        return "Meia ofensivo/Ponta"
    if normalized in {"m", "mf", "mei"} or any(term in normalized for term in ("volante", "midfield", "meio")):
        return "Volante/Meio-campista"
    return "Centroavante"


def _percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower_index = floor(position)
    upper_index = min(lower_index + 1, len(ordered) - 1)
    fraction = position - lower_index
    return ordered[lower_index] + (ordered[upper_index] - ordered[lower_index]) * fraction


def _radar_config(macroposition: str) -> dict[str, dict[str, float]]:
    return GOALKEEPER_RADAR_CONFIG if macroposition == "Goleiro" else OUTFIELD_RADAR_CONFIG


def build_reference_distribution(
    players: list[dict[str, Any]],
    minimum_minutes: float = 30,
) -> dict[str, dict[str, dict[str, float | int | None]]]:
    """Build positional reference percentiles from materialized competition data."""
    grouped: dict[str, dict[str, list[float]]] = {}
    for player in players:
        minutes = _number(player.get("minutes_played"))
        if minutes is None or minutes < minimum_minutes:
            continue
        macroposition = macroposition_for(player.get("position"))
        reference_group = str(player.get("benchmark_position") or player.get("radar_profile_group") or radar_profile_group(player))
        metrics = {metric for weights in _radar_config(macroposition).values() for metric in weights}
        for metric in metrics:
            value = _number(player.get(metric))
            if value is None:
                continue
            grouped.setdefault(reference_group, {}).setdefault(metric, []).append(value)

    distribution: dict[str, dict[str, dict[str, float | int | None]]] = {}
    for macroposition, metrics in grouped.items():
        distribution[macroposition] = {}
        for metric, values in metrics.items():
            distribution[macroposition][metric] = {
                "p05": round(float(_percentile(values, 0.05) or 0), 4),
                "p50": round(float(_percentile(values, 0.50) or 0), 4),
                "p95": round(float(_percentile(values, 0.95) or 0), 4),
                "mean": round(sum(values) / len(values), 4),
                "samples": len(values),
            }
    return distribution


def _volume_confidence(player: dict[str, Any], metric: str) -> float:
    denominator_key = VOLUME_DENOMINATORS.get(metric)
    if not denominator_key:
        return 1.0
    denominator = _number(player.get(denominator_key))
    if denominator is None or denominator < 2:
        return 0.4
    if denominator < 5:
        return 0.6
    if denominator < 10:
        return 0.8
    return 1.0


def calculate_player_radar(
    player_metrics: dict[str, Any],
    reference_distribution: dict[str, dict[str, dict[str, Any]]],
    macroposition: str,
    radar_config: dict[str, dict[str, float]] | None = None,
    reference_key: str | None = None,
) -> dict[str, Any]:
    """Calculate position-aware dimensions without replacing raw match values."""
    config = radar_config or _radar_config(macroposition)
    references = reference_distribution.get(reference_key or macroposition, {})
    dimensions: dict[str, dict[str, Any]] = {}
    radar: list[dict[str, Any]] = []

    for dimension, weights in config.items():
        scores: dict[str, float | None] = {}
        adjusted_weights: dict[str, float] = {}
        metric_details: dict[str, dict[str, Any]] = {}
        reference_samples: list[int] = []
        for metric, weight in weights.items():
            raw_value = _number(player_metrics.get(metric))
            reference = references.get(metric, {})
            score = robust_score(raw_value, reference.get("p05"), reference.get("p95"))
            scores[metric] = score
            adjusted_weights[metric] = weight * _volume_confidence(player_metrics, metric)
            if reference.get("samples") is not None:
                reference_samples.append(int(reference["samples"]))
            metric_details[metric] = {
                "label": METRIC_LABELS.get(metric, metric.replace("_", " ")),
                "raw_value": raw_value,
                "score_0_100": score,
                "reference": reference or None,
            }
        result = weighted_dimension_score(scores, adjusted_weights)
        minimum_samples = min(reference_samples) if reference_samples else 0
        confidence = result["confidence"]
        if minimum_samples < 2 and confidence in {"high", "medium"}:
            confidence = "low"
        elif minimum_samples < 5 and confidence == "high":
            confidence = "medium"
        dimension_result = {
            **result,
            "confidence": confidence,
            "available_metric_labels": [METRIC_LABELS.get(metric, metric) for metric in result["available_metrics"]],
            "missing_metric_labels": [METRIC_LABELS.get(metric, metric) for metric in result["missing_metrics"]],
            "reference_samples": minimum_samples,
            "metric_scores": metric_details,
        }
        dimensions[dimension] = dimension_result
        if result["score"] is not None:
            radar.append(
                {
                    "axis": dimension,
                    "value": result["score"],
                    "coverage_pct": result["coverage_pct"],
                    "confidence": confidence,
                    "available_metrics": dimension_result["available_metric_labels"],
                    "missing_metrics": dimension_result["missing_metric_labels"],
                }
            )

    importance = DIMENSION_IMPORTANCE.get(macroposition, {})
    available_dimensions = [axis for axis in radar if importance.get(axis["axis"], 0) > 0]
    total_importance = sum(importance[axis["axis"]] for axis in available_dimensions)
    profile_score = None
    if available_dimensions and total_importance > 0:
        profile_score = round(
            sum(float(axis["value"]) * importance[axis["axis"]] for axis in available_dimensions)
            / total_importance,
            1,
        )
    return {
        "player_id": player_metrics.get("player_id"),
        "player_name": player_metrics.get("player_name"),
        "macroposition": macroposition,
        "dimensions": dimensions,
        "radar": radar,
        "profile_score": profile_score,
    }
