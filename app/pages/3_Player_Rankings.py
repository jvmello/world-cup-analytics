from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from edition_context import get_selected_edition
from fifa_pdf_ui import render_fifa_2026_page

from player_rankings import (
    RANKING_METRICS,
    build_leaderboard,
    build_team_profiles,
    enrich_player_summary,
    metric_column,
    metric_options,
)


PLAYER_SUMMARY_PATH = Path(
    "data/gold/world_cup/gold_player_offensive_summary/"
    "gold_player_offensive_summary.parquet"
)

BACKGROUND_COLOR = "#050805"
SURFACE_COLOR = "#080d08"
PRIMARY_COLOR = "#9cff00"
SECONDARY_COLOR = "#00e5ff"
DANGER_COLOR = "#ff4d4d"
GRID_COLOR = "#1d2518"


st.markdown(
    """
    <style>
        .stApp {
            background-color: #050805;
            color: #f2f2f2;
        }

        [data-testid="stSidebar"] {
            background-color: #070907;
            border-right: 1px solid #1d2518;
        }

        div[data-testid="stMetric"] {
            background-color: #080d08;
            border: 1px solid #1d2518;
            padding: 14px;
            border-radius: 8px;
        }

        h1, h2, h3 {
            color: #f3f3f3;
        }

        .small-caption {
            color: #a0a0a0;
            font-size: 13px;
        }

        .section-label {
            color: #9cff00;
            font-weight: 700;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            font-size: 13px;
            margin-top: 10px;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data
def load_summary() -> pd.DataFrame:
    return enrich_player_summary(pd.read_parquet(PLAYER_SUMMARY_PATH))


def render_metric_context(metric_label: str) -> None:
    metric = next(item for item in RANKING_METRICS if item.label == metric_label)
    st.caption(metric.description)


def render_leaderboard_chart(
    leaderboard: pd.DataFrame,
    metric_label: str,
) -> None:
    st.markdown('<div class="section-label">Top jogadores</div>', unsafe_allow_html=True)

    if leaderboard.empty:
        st.info("Nenhum jogador encontrado com os filtros atuais.")
        return

    column = metric_column(metric_label)
    data = leaderboard.sort_values(column, ascending=True).copy()

    fig = px.bar(
        data,
        x=column,
        y="player_display_name",
        color="team_name",
        orientation="h",
        hover_data=[
            "edition_year",
            "team_name",
            "shots",
            "goals",
            "xg",
            "avg_xg_per_shot",
            "goals_minus_xg",
            "shot_accuracy",
            "conversion_rate",
            "big_chances",
        ],
        color_discrete_sequence=[
            PRIMARY_COLOR,
            SECONDARY_COLOR,
            "#a970ff",
            DANGER_COLOR,
            "#ffcc00",
            "#f2f2f2",
        ],
    )

    fig.update_layout(
        height=max(480, min(820, 42 * len(data))),
        paper_bgcolor=BACKGROUND_COLOR,
        plot_bgcolor=BACKGROUND_COLOR,
        font=dict(color="#f2f2f2"),
        xaxis=dict(title=metric_label, gridcolor="#151515"),
        yaxis=dict(title=None),
        legend=dict(orientation="h", yanchor="bottom", y=-0.2),
        margin=dict(l=10, r=20, t=30, b=80),
    )

    st.plotly_chart(fig, use_container_width=True)


def render_efficiency_scatter(filtered_players: pd.DataFrame) -> None:
    st.markdown(
        '<div class="section-label">Volume x eficiência</div>',
        unsafe_allow_html=True,
    )

    if filtered_players.empty:
        st.info("Sem dados para o scatter.")
        return

    fig = px.scatter(
        filtered_players,
        x="shots",
        y="avg_xg_per_shot",
        size="xg",
        color="goals_minus_xg",
        hover_name="player_display_name",
        hover_data=["team_name", "goals", "xg", "shot_accuracy", "conversion_rate"],
        color_continuous_scale=[DANGER_COLOR, "#777777", PRIMARY_COLOR],
    )

    fig.update_layout(
        height=560,
        paper_bgcolor=BACKGROUND_COLOR,
        plot_bgcolor=BACKGROUND_COLOR,
        font=dict(color="#f2f2f2"),
        xaxis=dict(title="Finalizações", gridcolor="#151515"),
        yaxis=dict(title="xG/finalização", gridcolor="#151515"),
        margin=dict(l=10, r=10, t=30, b=20),
    )

    st.plotly_chart(fig, use_container_width=True)


def render_team_profiles(team_profiles: pd.DataFrame) -> None:
    st.markdown(
        '<div class="section-label">Perfil das seleções</div>',
        unsafe_allow_html=True,
    )

    if team_profiles.empty:
        st.info("Selecione uma edição para comparar seleções.")
        return

    top_teams = team_profiles.head(16).copy()

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=top_teams["team_name"],
            y=top_teams["xg"],
            name="xG",
            marker_color=PRIMARY_COLOR,
        )
    )
    fig.add_trace(
        go.Bar(
            x=top_teams["team_name"],
            y=top_teams["goals"],
            name="Gols",
            marker_color=SECONDARY_COLOR,
        )
    )

    fig.update_layout(
        barmode="group",
        height=520,
        paper_bgcolor=BACKGROUND_COLOR,
        plot_bgcolor=BACKGROUND_COLOR,
        font=dict(color="#f2f2f2"),
        xaxis=dict(title=None, gridcolor="#151515"),
        yaxis=dict(title="Total", gridcolor="#151515"),
        legend=dict(orientation="h"),
        margin=dict(l=10, r=10, t=30, b=80),
    )

    st.plotly_chart(fig, use_container_width=True)


def render_table(leaderboard: pd.DataFrame) -> None:
    table = leaderboard[
        [
            "edition_year",
            "team_name",
            "player_display_name",
            "shots",
            "goals",
            "xg",
            "avg_xg_per_shot",
            "goals_minus_xg",
            "shot_accuracy",
            "conversion_rate",
            "big_chances",
        ]
    ].copy()

    table = table.rename(
        columns={
            "edition_year": "Edição",
            "team_name": "Seleção",
            "player_display_name": "Jogador",
            "shots": "Finalizações",
            "goals": "Gols",
            "xg": "xG",
            "avg_xg_per_shot": "xG/finaliz.",
            "goals_minus_xg": "G - xG",
            "shot_accuracy": "Precisão",
            "conversion_rate": "Conversão",
            "big_chances": "Grandes chances",
        }
    )

    table["Precisão"] = table["Precisão"] * 100
    table["Conversão"] = table["Conversão"] * 100

    st.dataframe(
        table,
        use_container_width=True,
        hide_index=True,
        column_config={
            "xG": st.column_config.NumberColumn(format="%.2f"),
            "xG/finaliz.": st.column_config.NumberColumn(format="%.3f"),
            "G - xG": st.column_config.NumberColumn(format="%.2f"),
            "Precisão": st.column_config.NumberColumn(format="%.1f%%"),
            "Conversão": st.column_config.NumberColumn(format="%.1f%%"),
        },
    )


if get_selected_edition(st.session_state) == 2026:
    render_fifa_2026_page("player_rankings", "Rankings ofensivos")
    st.stop()


if not PLAYER_SUMMARY_PATH.exists():
    st.warning("Run `make player_offensive` first.")
    st.stop()


summary_df = load_summary()

st.title("Rankings ofensivos")
st.markdown(
    '<div class="small-caption">Comparação de jogadores por volume, qualidade de chance e eficiência.</div>',
    unsafe_allow_html=True,
)

editions = ["Todas"] + sorted(
    summary_df["edition_year"].dropna().unique().tolist(),
    reverse=True,
)

filter_col1, filter_col2, filter_col3, filter_col4, filter_col5 = st.columns(
    [1, 1.4, 1.3, 1.2, 1.1]
)

with filter_col1:
    selected_edition = st.selectbox("Edição", editions)

edition_scope = summary_df
if selected_edition != "Todas":
    edition_scope = summary_df[summary_df["edition_year"].eq(selected_edition)]

teams = ["Todas"] + sorted(edition_scope["team_name"].dropna().unique().tolist())

with filter_col2:
    selected_team = st.selectbox("Seleção", teams)

with filter_col3:
    metric_label = st.selectbox("Métrica", metric_options())

max_shots = int(max(summary_df["shots"].max(), 1))

with filter_col4:
    min_shots = st.slider("Mínimo de finalizações", 1, max_shots, 3)

with filter_col5:
    limit = st.selectbox("Jogadores no ranking", [10, 20, 30, 50], index=1)

render_metric_context(metric_label)

leaderboard_df = build_leaderboard(
    summary_df,
    metric=metric_label,
    edition_year=selected_edition,
    team_name=selected_team,
    min_shots=min_shots,
    limit=limit,
)

filtered_df = enrich_player_summary(summary_df)
if selected_edition != "Todas":
    filtered_df = filtered_df[filtered_df["edition_year"].eq(selected_edition)]
if selected_team != "Todas":
    filtered_df = filtered_df[filtered_df["team_name"].eq(selected_team)]
filtered_df = filtered_df[filtered_df["shots"].ge(min_shots)].copy()

col1, col2, col3, col4 = st.columns(4)
col1.metric("Jogadores", len(filtered_df))
col2.metric("Finalizações", int(filtered_df["shots"].sum()))
col3.metric("Gols", int(filtered_df["goals"].sum()))
col4.metric("xG", round(float(filtered_df["xg"].sum()), 2))

st.divider()

tab1, tab2, tab3 = st.tabs(["Ranking", "Eficiência", "Seleções"])

with tab1:
    render_leaderboard_chart(leaderboard_df, metric_label)
    render_table(leaderboard_df)

with tab2:
    render_efficiency_scatter(filtered_df)

with tab3:
    if selected_edition == "Todas":
        st.info("Escolha uma edição específica para comparar seleções.")
    else:
        team_profiles_df = build_team_profiles(summary_df, selected_edition)
        render_team_profiles(team_profiles_df)
        st.dataframe(
            team_profiles_df[
                [
                    "team_name",
                    "players",
                    "shots",
                    "goals",
                    "xg",
                    "avg_xg_per_shot",
                    "shot_accuracy",
                    "conversion_rate",
                    "big_chances",
                ]
            ].assign(
                shot_accuracy=lambda data: data["shot_accuracy"] * 100,
                conversion_rate=lambda data: data["conversion_rate"] * 100,
            ).rename(
                columns={
                    "team_name": "Seleção",
                    "players": "Jogadores",
                    "shots": "Finalizações",
                    "goals": "Gols",
                    "xg": "xG",
                    "avg_xg_per_shot": "xG/finaliz.",
                    "shot_accuracy": "Precisão",
                    "conversion_rate": "Conversão",
                    "big_chances": "Grandes chances",
                }
            ),
            use_container_width=True,
            hide_index=True,
            column_config={
                "xG": st.column_config.NumberColumn(format="%.2f"),
                "xG/finaliz.": st.column_config.NumberColumn(format="%.3f"),
                "Precisão": st.column_config.NumberColumn(format="%.1f%%"),
                "Conversão": st.column_config.NumberColumn(format="%.1f%%"),
            },
        )
