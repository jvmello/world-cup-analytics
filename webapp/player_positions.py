from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any


FORMATION_SLOTS: dict[str, tuple[str, ...]] = {
    "4-3-3": ("Goleiro", "Lateral esquerdo", "Zagueiro", "Zagueiro", "Lateral direito", "Meio-campista central", "Meio-campista central", "Meio-campista central", "Ponta esquerda", "Centroavante", "Ponta direita"),
    "4-2-3-1": ("Goleiro", "Lateral esquerdo", "Zagueiro", "Zagueiro", "Lateral direito", "Volante", "Volante", "Ponta esquerda", "Meia ofensivo", "Ponta direita", "Centroavante"),
    "4-4-2": ("Goleiro", "Lateral esquerdo", "Zagueiro", "Zagueiro", "Lateral direito", "Meia lateral esquerdo", "Meio-campista central", "Meio-campista central", "Meia lateral direito", "Segundo atacante", "Centroavante"),
    "3-5-2": ("Goleiro", "Zagueiro", "Zagueiro", "Zagueiro", "Ala esquerdo", "Meio-campista central", "Volante", "Meio-campista central", "Ala direito", "Segundo atacante", "Centroavante"),
    "3-4-3": ("Goleiro", "Zagueiro", "Zagueiro", "Zagueiro", "Ala esquerdo", "Meio-campista central", "Meio-campista central", "Ala direito", "Ponta esquerda", "Centroavante", "Ponta direita"),
    "5-3-2": ("Goleiro", "Ala esquerdo", "Zagueiro", "Zagueiro", "Zagueiro", "Ala direito", "Meio-campista central", "Volante", "Meio-campista central", "Segundo atacante", "Centroavante"),
    "4-1-4-1": ("Goleiro", "Lateral esquerdo", "Zagueiro", "Zagueiro", "Lateral direito", "Volante", "Meia lateral esquerdo", "Meio-campista central", "Meio-campista central", "Meia lateral direito", "Centroavante"),
    "4-3-1-2": ("Goleiro", "Lateral esquerdo", "Zagueiro", "Zagueiro", "Lateral direito", "Meio-campista central", "Volante", "Meio-campista central", "Meia ofensivo", "Segundo atacante", "Centroavante"),
    "3-4-2-1": ("Goleiro", "Zagueiro", "Zagueiro", "Zagueiro", "Ala esquerdo", "Meio-campista central", "Meio-campista central", "Ala direito", "Meia ofensivo", "Segundo atacante", "Centroavante"),
    "5-4-1": ("Goleiro", "Ala esquerdo", "Zagueiro", "Zagueiro", "Zagueiro", "Ala direito", "Meia lateral esquerdo", "Meio-campista central", "Meio-campista central", "Meia lateral direito", "Centroavante"),
    "3-1-4-2": ("Goleiro", "Zagueiro", "Zagueiro", "Zagueiro", "Volante", "Ala esquerdo", "Meio-campista central", "Meio-campista central", "Ala direito", "Segundo atacante", "Centroavante"),
    "4-4-1-1": ("Goleiro", "Lateral esquerdo", "Zagueiro", "Zagueiro", "Lateral direito", "Meia lateral esquerdo", "Meio-campista central", "Meio-campista central", "Meia lateral direito", "Segundo atacante", "Centroavante"),
}

API_POSITION_GROUPS = {
    "G": "Goleiro", "GK": "Goleiro", "GOL": "Goleiro",
    "D": "Defensor", "DF": "Defensor", "DEF": "Defensor",
    "M": "Meio-campista", "MF": "Meio-campista", "MEI": "Meio-campista",
    "F": "Atacante", "FW": "Atacante", "ATA": "Atacante",
}

ROLE_LABELS = {
    "Goleiro": "Média dos goleiros", "Zagueiro": "Média dos zagueiros",
    "Lateral": "Média dos laterais", "Lateral direito": "Média dos laterais direitos",
    "Lateral esquerdo": "Média dos laterais esquerdos", "Ala": "Média dos alas",
    "Ala direito": "Média dos alas direitos", "Ala esquerdo": "Média dos alas esquerdos",
    "Volante": "Média dos volantes", "Meio-campista central": "Média dos meias centrais",
    "Meia ofensivo": "Média dos meias ofensivos", "Meia lateral direito": "Média dos meias laterais direitos",
    "Meia lateral esquerdo": "Média dos meias laterais esquerdos", "Ponta": "Média das pontas",
    "Ponta direita": "Média das pontas direitas", "Ponta esquerda": "Média das pontas esquerdas",
    "Segundo atacante": "Média dos segundos atacantes", "Centroavante": "Média dos centroavantes",
    "Goleiros": "Média dos goleiros", "Defensores": "Média dos defensores",
    "Defensores laterais": "Média dos defensores laterais", "Meio-campistas": "Média dos meio-campistas",
    "Meias centrais": "Média dos meias centrais", "Meias laterais": "Média dos meias laterais",
    "Pontas": "Média das pontas", "Atacantes": "Média dos atacantes",
}


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def api_position_group(value: Any) -> str | None:
    raw = str(value or "").strip()
    return API_POSITION_GROUPS.get(raw.upper()) or (raw if raw in set(API_POSITION_GROUPS.values()) else None)


def role_side(role: str | None) -> str:
    normalized = str(role or "").casefold()
    if "esquerd" in normalized:
        return "Esquerda"
    if "direit" in normalized:
        return "Direita"
    if role in {"Goleiro", "Zagueiro", "Volante", "Meio-campista central", "Meia ofensivo", "Segundo atacante", "Centroavante"}:
        return "Centro"
    return "Indefinido"


def audit_lineup_order(lineup: dict[str, Any]) -> dict[str, Any]:
    formation = str(lineup.get("formation") or "")
    starters = lineup.get("starting_xi") if isinstance(lineup.get("starting_xi"), list) else []
    group_order = {"G": 0, "D": 1, "M": 2, "F": 3}
    groups = [str(player.get("position") or "").upper() for player in starters if isinstance(player, dict)]
    grouped = bool(groups) and all(group_order.get(left, 9) <= group_order.get(right, 9) for left, right in zip(groups, groups[1:]))
    explicit_slots = [player.get("slot_index") for player in starters if isinstance(player, dict)]
    reliable = (
        len(starters) == 11
        and formation in FORMATION_SLOTS
        and all(isinstance(slot, int) for slot in explicit_slots)
        and sorted(explicit_slots) == list(range(11))
    )
    reason = "explicit_tactical_slots" if reliable else "coarse_api_groups_only" if grouped else "lineup_order_unverified"
    return {
        "formation": formation or None,
        "formation_mapped": formation in FORMATION_SLOTS,
        "grouped_api_order": grouped,
        "slot_order_reliable": reliable,
        "reason": reason,
    }


def _statistics_role(player: dict[str, Any], formation: str | None) -> tuple[str, str, str]:
    group = api_position_group(player.get("position"))
    crosses = _number(player.get("total_crosses"))
    key_passes = _number(player.get("key_passes"))
    shots = _number(player.get("shots"))
    xa = _number(player.get("xa"))
    defensive = sum(_number(player.get(metric)) for metric in ("tackles", "interceptions", "clearances"))
    passes = _number(player.get("passes"))
    if group == "Goleiro":
        return "Goleiro", "api_position", "high"
    if group == "Defensor":
        if crosses >= 2:
            role = "Ala" if str(formation or "").startswith(("3-", "5-")) else "Lateral"
            return role, "statistics_profile", "medium"
        if defensive >= 4:
            return "Zagueiro", "statistics_profile", "medium"
    elif group == "Meio-campista":
        if key_passes >= 2 or xa >= 0.15 or shots >= 3:
            return "Meia ofensivo", "statistics_profile", "medium"
        if defensive >= 4 and key_passes + shots <= 2:
            return "Volante", "statistics_profile", "medium"
        if passes >= 30:
            return "Meio-campista central", "statistics_profile", "medium"
    elif group == "Atacante":
        if crosses >= 2:
            return "Ponta", "statistics_profile", "medium"
        if shots >= 3 and (key_passes >= 2 or xa >= 0.3):
            return "Segundo atacante", "statistics_profile", "medium"
        if shots >= 3:
            return "Centroavante", "statistics_profile", "medium"
        if key_passes >= 2 or xa >= 0.15:
            return "Ponta", "statistics_profile", "medium"
        if shots >= 2 and key_passes >= 1:
            return "Segundo atacante", "statistics_profile", "medium"
    return group or "Posição não informada", "fallback", "low"


def infer_match_positions(
    match_id: str,
    lineups: dict[str, Any],
    players: list[dict[str, Any]],
    events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc).isoformat()
    lineup_by_player: dict[str, dict[str, Any]] = {}
    team_context: dict[str, dict[str, Any]] = {}
    for side in ("home", "away"):
        lineup = lineups.get(side) if isinstance(lineups.get(side), dict) else {}
        team_id = str(lineup.get("id") or "")
        audit = audit_lineup_order(lineup)
        team_context[team_id] = {**audit, "team_name": lineup.get("name")}
        for is_starter, key in ((True, "starting_xi"), (False, "substitutes")):
            for index, entry in enumerate(lineup.get(key) or []):
                if not isinstance(entry, dict) or not entry.get("id"):
                    continue
                lineup_by_player[str(entry["id"])] = {
                    **entry,
                    "is_starter": is_starter,
                    "lineup_index": index if is_starter else None,
                    "team_id": team_id,
                    **audit,
                }

    inferred: list[dict[str, Any]] = []
    for player in players:
        player_id = str(player.get("player_id") or "")
        lineup_entry = lineup_by_player.get(player_id, {})
        team_id = str(player.get("team_id") or lineup_entry.get("team_id") or "")
        context = team_context.get(team_id, {})
        formation = context.get("formation")
        is_starter = bool(player.get("started")) if player.get("started") is not None else bool(lineup_entry.get("is_starter"))
        role, source, confidence = _statistics_role(player, formation)
        slot_index = lineup_entry.get("slot_index")
        if is_starter and context.get("slot_order_reliable") and isinstance(slot_index, int):
            slots = FORMATION_SLOTS.get(str(formation), ())
            if 0 <= slot_index < len(slots):
                role, source, confidence = slots[slot_index], "formation_slot", "high"
        inferred.append(
            {
                "match_id": match_id,
                "player_id": player.get("player_id"),
                "player_name": player.get("player_name"),
                "team_id": player.get("team_id"),
                "api_position_group": api_position_group(player.get("position")),
                "formation": formation,
                "is_starter": is_starter,
                "minutes_played": _number(player.get("minutes_played")),
                "inferred_role": role,
                "inferred_side": role_side(role),
                "role_source": source,
                "role_confidence": confidence,
                "slot_index": slot_index if isinstance(slot_index, int) else lineup_entry.get("lineup_index"),
                "slot_label": role if source == "formation_slot" else None,
                "formation_mapped": bool(context.get("formation_mapped")),
                "lineup_order_reliable": bool(context.get("slot_order_reliable")),
                "created_at": now,
                "updated_at": now,
            }
        )

    by_id = {str(row.get("player_id")): row for row in inferred}
    grouped_events: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for event in events if isinstance(events, list) else []:
        if not isinstance(event, dict) or event.get("type") != "substitution":
            continue
        team = event.get("team") if isinstance(event.get("team"), dict) else {}
        minute = int(_number(event.get("minute")))
        grouped_events[(str(team.get("id") or ""), minute)].append(event)
    for (team_id, minute), substitutions in grouped_events.items():
        if len(substitutions) != 1:
            continue
        entrant = substitutions[0].get("player") if isinstance(substitutions[0].get("player"), dict) else {}
        entrant_row = by_id.get(str(entrant.get("id") or ""))
        if not entrant_row or entrant_row.get("is_starter"):
            continue
        candidates = [
            row for row in inferred
            if str(row.get("team_id") or "") == team_id
            and row.get("is_starter")
            and row.get("api_position_group") == entrant_row.get("api_position_group")
            and abs(float(row.get("minutes_played") or 0) - min(minute, 90)) <= 2
            and row.get("role_confidence") in {"high", "medium"}
        ]
        if len(candidates) == 1:
            outgoing = candidates[0]
            entrant_row.update(
                inferred_role=outgoing.get("inferred_role"),
                inferred_side=outgoing.get("inferred_side"),
                role_source="substitution_inheritance",
                role_confidence="medium",
                slot_label=outgoing.get("slot_label"),
            )
    return inferred


def summarize_tournament_positions(rows: list[dict[str, Any]]) -> dict[str, Any]:
    active = [row for row in rows if _number(row.get("minutes_played")) > 0 and row.get("inferred_role")]
    total = sum(_number(row.get("minutes_played")) for row in active)
    role_minutes: dict[str, float] = defaultdict(float)
    side_minutes: dict[tuple[str, str], float] = defaultdict(float)
    source_summary: Counter[str] = Counter()
    confidence_minutes: dict[str, float] = defaultdict(float)
    for row in active:
        minutes = _number(row.get("minutes_played"))
        role = str(row["inferred_role"])
        role_minutes[role] += minutes
        side_minutes[(role, str(row.get("inferred_side") or "Indefinido"))] += minutes
        source_summary[str(row.get("role_source") or "unknown")] += 1
        confidence_minutes[str(row.get("role_confidence") or "low")] += minutes
    ordered = sorted(role_minutes.items(), key=lambda item: (-item[1], item[0]))
    primary = ordered[0][0] if ordered else None
    breakdown = [
        {"role": role, "minutes": round(minutes, 1), "percentage": round(minutes / total * 100, 1) if total else 0.0}
        for role, minutes in ordered
    ]
    secondary = [row["role"] for row in breakdown[1:] if row["percentage"] >= 20]
    primary_side_rows = [(side, minutes) for (role, side), minutes in side_minutes.items() if role == primary and side != "Indefinido"]
    primary_side = max(primary_side_rows, key=lambda item: item[1])[0] if primary_side_rows else "Indefinido"
    reliable_ratio = (confidence_minutes["high"] + confidence_minutes["medium"]) / total if total else 0
    high_ratio = confidence_minutes["high"] / total if total else 0
    if total < 45 or reliable_ratio < 0.6:
        confidence = "low"
    elif high_ratio >= 0.6:
        confidence = "high"
    else:
        confidence = "medium"
    multifunctional = bool(breakdown and breakdown[0]["percentage"] < 50)
    api_groups = Counter(
        group
        for row in active
        if (group := api_position_group(row.get("api_position_group") or row.get("position")))
    )
    api_group = api_groups.most_common(1)[0][0] if api_groups else None
    needs_review = confidence == "low" or multifunctional or any(not row.get("formation_mapped", True) for row in active)
    summary = {
        "api_position_group": api_group,
        "primary_inferred_role": primary,
        "primary_inferred_side": primary_side,
        "secondary_inferred_roles": secondary,
        "role_minutes_breakdown": breakdown,
        "role_source_summary": dict(source_summary),
        "role_confidence": confidence,
        "is_multifunctional": multifunctional,
        "total_minutes": round(total, 1),
        "review_status": "needs_review" if needs_review else "auto_inferred",
    }
    summary["resolved_position"] = resolve_public_position(summary)
    return summary


def resolve_public_position(player: dict[str, Any]) -> str:
    if player.get("role_confidence") in {"high", "medium"} and player.get("primary_inferred_role"):
        return str(player["primary_inferred_role"])
    return api_position_group(player.get("api_position_group") or player.get("position")) or "Posição não informada"


def _benchmark_family(role: str | None) -> str | None:
    if role in {"Ponta", "Ponta direita", "Ponta esquerda"}:
        return "Pontas"
    if role in {"Centroavante", "Segundo atacante"}:
        return "Atacantes"
    if role in {"Lateral", "Lateral direito", "Lateral esquerdo", "Ala", "Ala direito", "Ala esquerdo"}:
        return "Defensores laterais"
    if role in {"Volante", "Meio-campista central", "Meia ofensivo"}:
        return "Meias centrais"
    if role in {"Meia lateral direito", "Meia lateral esquerdo"}:
        return "Meias laterais"
    return None


def _raw_benchmark_group(player: dict[str, Any]) -> str:
    group = api_position_group(player.get("api_position_group") or player.get("position"))
    return {"Goleiro": "Goleiros", "Defensor": "Defensores", "Meio-campista": "Meio-campistas", "Atacante": "Atacantes"}.get(group, "Jogadores")


def radar_profile_group(player: dict[str, Any]) -> str:
    role = (
        player.get("primary_inferred_role") or player.get("inferred_role")
        if player.get("role_confidence") in {"high", "medium"}
        else None
    )
    if role == "Goleiro" or api_position_group(player.get("position")) == "Goleiro":
        return "Goleiro"
    if role == "Zagueiro":
        return "Zagueiro"
    if role and any(term in role for term in ("Lateral", "Ala")):
        return "Lateral/Ala"
    if role and any(term in role for term in ("Ponta", "ofensivo")):
        return "Meia ofensivo/Ponta"
    if role and any(term in role for term in ("Volante", "Meio-campista", "Meia lateral")):
        return "Volante/Meio-campista"
    if role in {"Centroavante", "Segundo atacante"}:
        return "Centroavante"
    group = api_position_group(player.get("api_position_group") or player.get("position"))
    return {"Goleiro": "Goleiro", "Defensor": "Zagueiro", "Meio-campista": "Volante/Meio-campista", "Atacante": "Centroavante"}.get(group, "Centroavante")


def assign_benchmark_cohorts(players: list[dict[str, Any]], minimum_sample: int = 5) -> list[dict[str, Any]]:
    eligible = [row for row in players if _number(row.get("minutes_played")) >= 30]
    exact_counts = Counter(
        str(row.get("primary_inferred_role"))
        for row in eligible
        if row.get("primary_inferred_role") and row.get("role_confidence") in {"high", "medium"}
    )
    family_counts = Counter(
        family
        for row in eligible
        if row.get("role_confidence") in {"high", "medium"}
        and (family := _benchmark_family(str(row.get("primary_inferred_role") or "")))
    )
    raw_counts = Counter(_raw_benchmark_group(row) for row in eligible)
    assigned = []
    for row in players:
        role = str(row.get("primary_inferred_role") or "")
        family = _benchmark_family(role)
        if row.get("role_confidence") in {"high", "medium"} and exact_counts[role] >= minimum_sample:
            cohort, sample = role, exact_counts[role]
        elif row.get("role_confidence") in {"high", "medium"} and family and family_counts[family] >= minimum_sample:
            cohort, sample = family, family_counts[family]
        else:
            cohort = _raw_benchmark_group(row)
            sample = raw_counts[cohort]
        assigned.append(
            {
                **row,
                "benchmark_position": cohort,
                "benchmark_label": ROLE_LABELS.get(cohort, f"Média de {cohort.casefold()}"),
                "benchmark_sample_size": sample,
                "radar_profile_group": radar_profile_group(row),
            }
        )
    return assigned
