from __future__ import annotations

from typing import Iterable

import pandas as pd
import streamlit as st

from edition_context import get_data_coverage, render_coverage_notice
from fifa_pdf_data import FifaPdfData


def _first_present(columns: Iterable[str], candidates: Iterable[str]) -> str | None:
    available = set(columns)
    return next((candidate for candidate in candidates if candidate in available), None)


def _match_label(row: pd.Series) -> str:
    match_id = row.get("match_id", "Partida")
    home = row.get("home_team")
    away = row.get("away_team")
    home_score = row.get("home_score")
    away_score = row.get("away_score")

    if pd.notna(home) and pd.notna(away):
        if pd.notna(home_score) and pd.notna(away_score):
            return f"{match_id} · {home} {home_score} x {away_score} {away}"
        return f"{match_id} · {home} x {away}"
    return str(match_id)


def _select_match(data: FifaPdfData) -> FifaPdfData:
    match_ids = data.match_ids()
    if not match_ids:
        return data

    labels = {match_id: match_id for match_id in match_ids}
    if not data.matches.empty and "match_id" in data.matches.columns:
        for _, row in data.matches.iterrows():
            labels[str(row["match_id"])] = _match_label(row)

    selected = st.selectbox(
        "Partida",
        match_ids,
        format_func=lambda value: labels.get(value, value),
        key="fifa_pdf_match_id",
    )
    return data.for_match(selected)


def _render_frame(title: str, frame: pd.DataFrame, empty_message: str) -> None:
    st.subheader(title)
    if frame.empty:
        st.info(empty_message)
        return
    st.dataframe(frame, use_container_width=True, hide_index=True)


def _render_metric_cards(frame: pd.DataFrame) -> None:
    if frame.empty:
        return

    metric_column = _first_present(
        frame.columns,
        ("metric", "metric_name", "statistic", "name"),
    )
    value_column = _first_present(
        frame.columns,
        ("value", "metric_value", "stat_value", "total"),
    )
    team_column = _first_present(
        frame.columns,
        ("team_name", "team"),
    )
    if not metric_column or not value_column:
        return

    cards = frame.dropna(subset=[metric_column]).head(8)
    if cards.empty:
        return

    columns = st.columns(min(4, len(cards)))
    for index, (_, row) in enumerate(cards.iterrows()):
        label = str(row[metric_column])
        if team_column and pd.notna(row.get(team_column)):
            label = f"{row[team_column]} · {label}"
        columns[index % len(columns)].metric(label, row[value_column])


def _team_values(data: FifaPdfData) -> list[str]:
    values: set[str] = set()
    for frame in (
        data.team_metrics,
        data.phases,
        data.attempts,
        data.player_metrics,
    ):
        team_column = _first_present(frame.columns, ("team_name", "team"))
        if team_column:
            values.update(frame[team_column].dropna().astype(str).tolist())
    return sorted(values)


def _filter_team(frame: pd.DataFrame, team_name: str) -> pd.DataFrame:
    team_column = _first_present(frame.columns, ("team_name", "team"))
    if frame.empty or not team_column:
        return frame.copy()
    return frame[frame[team_column].astype(str).eq(team_name)].copy()


def _filter_player(frame: pd.DataFrame, player_name: str) -> pd.DataFrame:
    player_column = _first_present(frame.columns, ("player_name", "player"))
    if frame.empty or not player_column:
        return frame.copy()
    return frame[frame[player_column].astype(str).eq(player_name)].copy()


def _render_match_overview(data: FifaPdfData) -> None:
    selected = _select_match(data)
    _render_frame(
        "Resumo da partida",
        selected.matches,
        "O CSV de resumo da partida ainda não contém esta partida.",
    )
    _render_metric_cards(selected.team_metrics)
    _render_frame(
        "Estatísticas das seleções",
        selected.team_metrics,
        "Estatísticas agregadas de times ainda não foram extraídas.",
    )
    _render_frame(
        "Fases de jogo",
        selected.phases,
        "Fases de jogo ainda não foram extraídas.",
    )
    _render_frame(
        "Tentativas de gol",
        selected.attempts,
        "Tentativas agregadas ainda não foram extraídas.",
    )


def _render_player_view(data: FifaPdfData, shot_map: bool = False) -> None:
    if shot_map:
        st.warning(
            "O relatório FIFA 2026 não fornece coordenadas por finalização. "
            "O mapa de chutes permanece disponível somente para 2022 (StatsBomb)."
        )

    selected = _select_match(data)
    metrics = selected.player_metrics
    player_column = _first_present(metrics.columns, ("player_name", "player"))
    if metrics.empty or not player_column:
        _render_frame(
            "Métricas de jogadores",
            metrics,
            "Métricas agregadas de jogadores ainda não foram extraídas dos PDFs.",
        )
        _render_frame(
            "Tentativas agregadas",
            selected.attempts,
            "Tentativas agregadas ainda não foram extraídas.",
        )
        return

    players = sorted(metrics[player_column].dropna().astype(str).unique().tolist())
    selected_player = st.selectbox("Jogador", players, key="fifa_pdf_player")
    player_metrics = _filter_player(metrics, selected_player)
    _render_metric_cards(player_metrics)
    _render_frame(
        "Métricas agregadas do jogador",
        player_metrics,
        "Não há métricas para o jogador selecionado.",
    )


def _render_rankings(data: FifaPdfData) -> None:
    metrics = data.player_metrics.copy()
    metric_column = _first_present(metrics.columns, ("metric", "metric_name"))
    value_column = _first_present(metrics.columns, ("value", "metric_value"))

    if metrics.empty:
        _render_frame(
            "Rankings de jogadores",
            metrics,
            "Métricas de jogadores ainda não foram extraídas.",
        )
        return

    if metric_column and value_column:
        metric_names = sorted(
            metrics[metric_column].dropna().astype(str).unique().tolist()
        )
        selected_metric = st.selectbox(
            "Métrica",
            metric_names,
            key="fifa_pdf_ranking_metric",
        )
        ranking = metrics[
            metrics[metric_column].astype(str).eq(selected_metric)
        ].copy()
        ranking["_numeric_value"] = pd.to_numeric(
            ranking[value_column],
            errors="coerce",
        )
        ranking = ranking.sort_values(
            ["_numeric_value", value_column],
            ascending=False,
            na_position="last",
        ).drop(columns="_numeric_value")
    else:
        ranking = metrics

    _render_frame(
        "Rankings FIFA 2026",
        ranking,
        "Não há linhas para a métrica selecionada.",
    )


def _render_team_view(data: FifaPdfData) -> None:
    selected = _select_match(data)
    teams = _team_values(selected)
    if not teams:
        st.info("Nenhuma seleção foi identificada nos CSVs FIFA disponíveis.")
        return

    selected_team = st.selectbox("Time", teams, key="fifa_pdf_team")
    team_metrics = _filter_team(selected.team_metrics, selected_team)
    _render_metric_cards(team_metrics)
    _render_frame(
        "Estatísticas agregadas",
        team_metrics,
        "Não há estatísticas agregadas para a seleção.",
    )
    _render_frame(
        "Fases de jogo",
        _filter_team(selected.phases, selected_team),
        "Não há fases de jogo para a seleção.",
    )
    _render_frame(
        "Tentativas de gol",
        _filter_team(selected.attempts, selected_team),
        "Não há tentativas agregadas para a seleção.",
    )
    st.info(
        "Mapa de calor, evolução de xG e perfil por tipo de evento exigem dados "
        "granulares e permanecem exclusivos da edição 2022."
    )


def _render_tournament(data: FifaPdfData) -> None:
    _render_frame(
        "Partidas processadas",
        data.matches,
        "Nenhum resumo de partida FIFA 2026 foi processado.",
    )
    st.info(
        "A cobertura FIFA PDF é incremental e contém somente as partidas já "
        "processadas. Classificação completa, chave do torneio, artilharia e "
        "assistências não são inferidas a partir de relatórios parciais."
    )


def render_fifa_2026_page(page: str, title: str) -> None:
    data = FifaPdfData.load()
    coverage = get_data_coverage(2026, fifa_data_available=data.available)

    st.title(title)
    st.markdown(
        '<div class="small-caption">Copa do Mundo 2026 · dados agregados de relatórios FIFA.</div>',
        unsafe_allow_html=True,
    )
    render_coverage_notice(st, coverage)

    if not data.available:
        st.code(str(data.output_dir))
        return

    if page == "match_overview":
        _render_match_overview(data)
    elif page == "shot_map":
        _render_player_view(data, shot_map=True)
    elif page == "player_analytics":
        _render_player_view(data)
        st.info(
            "Radar, mapa de calor, localização no alvo, linha do tempo e xG por "
            "finalização exigem eventos granulares de 2022."
        )
    elif page == "player_rankings":
        _render_rankings(data)
    elif page == "tournament_history":
        _render_tournament(data)
    elif page == "team_analytics":
        _render_team_view(data)
    else:
        raise ValueError(f"Unknown FIFA 2026 page: {page}")
