from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from team_analytics import (
    build_team_match_log,
    build_team_rankings,
    build_team_shot_profile,
    enrich_team_summary,
    get_team_row,
)


TEAM_SUMMARY_PATH = Path(
    "data/gold/world_cup/gold_team_shot_summary/gold_team_shot_summary.parquet"
)
MATCH_TEAM_SUMMARY_PATH = Path(
    "data/gold/world_cup/gold_match_team_shot_summary/"
    "gold_match_team_shot_summary.parquet"
)
PLAYER_SHOTS_PATH = Path(
    "data/gold/world_cup/gold_player_shots/gold_player_shots.parquet"
)

BACKGROUND_COLOR = "#050805"
SURFACE_COLOR = "#080d08"
PRIMARY_COLOR = "#9cff00"
SECONDARY_COLOR = "#00e5ff"
DANGER_COLOR = "#ff4d4d"


st.set_page_config(page_title="Team Analytics", layout="wide")

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

        .team-hero {
            min-height: 350px;
            border: 1px solid #1d2518;
            border-radius: 8px;
            background:
                radial-gradient(circle at 35% 45%, rgba(156,255,0,0.20), transparent 28%),
                radial-gradient(circle at 68% 35%, rgba(0,229,255,0.12), transparent 30%),
                linear-gradient(135deg, #061006 0%, #050805 70%);
            padding: 64px 72px;
        }

        .hero-kicker {
            color: #9cff00;
            font-size: 13px;
            font-weight: 700;
            letter-spacing: 0.22em;
            text-transform: uppercase;
        }

        .hero-title {
            color: #f2f2f2;
            font-size: 54px;
            font-weight: 800;
            line-height: 1;
            margin: 10px 0 12px;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data
def load_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    return (
        enrich_team_summary(pd.read_parquet(TEAM_SUMMARY_PATH)),
        pd.read_parquet(MATCH_TEAM_SUMMARY_PATH),
        pd.read_parquet(PLAYER_SHOTS_PATH),
    )


def render_hero(team_row: pd.Series) -> None:
    st.markdown(
        f"""
        <div class="team-hero">
            <div class="hero-kicker">Vitrine do time</div>
            <div class="hero-title">{team_row["team_name"]}</div>
            <div class="small-caption">Copa do Mundo {team_row["edition_year"]}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("xG criado", round(float(team_row["xg"]), 2))
    col2.metric("Gols", int(team_row["goals"]))
    col3.metric("Finalizações", int(team_row["shots"]))
    col4.metric("Gols / xG", round(float(team_row["goals"] / team_row["xg"]), 2) if team_row["xg"] else 0)


def render_performance_card(team_row: pd.Series) -> None:
    st.markdown('<div class="section-label">Cartão de performance</div>', unsafe_allow_html=True)
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Finalizações", int(team_row["shots"]))
    col2.metric("No alvo", int(team_row["shots_on_target"]))
    col3.metric("Precisão", f"{float(team_row['shot_accuracy']):.1%}")
    col4.metric("Conversão", f"{float(team_row['conversion_rate']):.1%}")
    col5.metric("G - xG", round(float(team_row["goals_minus_xg"]), 2))


def render_xg_ranking(team_summary: pd.DataFrame, edition_year: int, selected_team: str) -> None:
    st.markdown('<div class="section-label">Ranking de xG</div>', unsafe_allow_html=True)
    ranking = build_team_rankings(team_summary, "xg", edition_year)
    ranking["highlight"] = ranking["team_name"].eq(selected_team)

    fig = px.bar(
        ranking.sort_values("xg", ascending=True),
        x="xg",
        y="team_name",
        orientation="h",
        color="highlight",
        color_discrete_map={True: PRIMARY_COLOR, False: "#46503f"},
        hover_data=["shots", "goals", "avg_xg_per_shot", "goals_minus_xg"],
    )
    fig.update_layout(
        height=max(480, min(820, 34 * len(ranking))),
        paper_bgcolor=BACKGROUND_COLOR,
        plot_bgcolor=BACKGROUND_COLOR,
        font=dict(color="#f2f2f2"),
        xaxis=dict(title="xG", gridcolor="#151515"),
        yaxis=dict(title=None),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)


def render_radar(team_summary: pd.DataFrame, team_row: pd.Series) -> None:
    st.markdown('<div class="section-label">Radar de performance</div>', unsafe_allow_html=True)
    edition = int(team_row["edition_year"])
    comparison = team_summary[team_summary["edition_year"].eq(edition)].copy()
    metrics = [
        ("Finalizações", "shots"),
        ("Gols", "goals"),
        ("xG", "xg"),
        ("xG/finaliz.", "avg_xg_per_shot"),
        ("Precisão", "shot_accuracy"),
        ("Conversão", "conversion_rate"),
    ]

    labels = []
    values = []
    for label, column in metrics:
        labels.append(label)
        values.append(int(round((comparison[column] <= team_row[column]).mean() * 100)))

    labels.append(labels[0])
    values.append(values[0])

    fig = go.Figure()
    fig.add_trace(
        go.Scatterpolar(
            r=values,
            theta=labels,
            fill="toself",
            name=team_row["team_name"],
            line=dict(color=PRIMARY_COLOR, width=3),
            fillcolor="rgba(156,255,0,0.25)",
        )
    )
    fig.update_layout(
        height=560,
        paper_bgcolor=BACKGROUND_COLOR,
        plot_bgcolor=BACKGROUND_COLOR,
        font=dict(color="#f2f2f2"),
        polar=dict(
            bgcolor=BACKGROUND_COLOR,
            radialaxis=dict(visible=True, range=[0, 100], gridcolor="#1d2518"),
            angularaxis=dict(gridcolor="#1d2518"),
        ),
    )
    st.plotly_chart(fig, use_container_width=True)


def render_xg_evolution(match_log: pd.DataFrame) -> None:
    st.markdown('<div class="section-label">Evolução do xG acumulado</div>', unsafe_allow_html=True)
    if match_log.empty:
        st.info("Sem resumo por partida para este time.")
        return

    data = match_log.sort_values("match_date").copy()
    data["cumulative_xg"] = data["xg"].cumsum()
    data["match"] = data["opponent"] + " (" + data["result"] + ")"

    fig = px.line(
        data,
        x="match",
        y="cumulative_xg",
        markers=True,
        hover_data=["match_date", "xg", "goals", "shots", "result"],
    )
    fig.update_layout(
        height=520,
        paper_bgcolor=BACKGROUND_COLOR,
        plot_bgcolor=BACKGROUND_COLOR,
        font=dict(color="#f2f2f2"),
        xaxis=dict(title=None, gridcolor="#151515"),
        yaxis=dict(title="xG acumulado", gridcolor="#151515"),
    )
    st.plotly_chart(fig, use_container_width=True)


def render_form(match_log: pd.DataFrame) -> None:
    st.markdown('<div class="section-label">Forma - rolling xG</div>', unsafe_allow_html=True)
    if match_log.empty:
        st.info("Sem sequência de partidas para este time.")
        return

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=match_log["opponent"],
            y=match_log["xg"],
            name="xG",
            marker_color=SECONDARY_COLOR,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=match_log["opponent"],
            y=match_log["rolling_xg"],
            name="Média móvel 3j",
            mode="lines+markers",
            line=dict(color=PRIMARY_COLOR, width=3),
        )
    )
    fig.update_layout(
        height=520,
        paper_bgcolor=BACKGROUND_COLOR,
        plot_bgcolor=BACKGROUND_COLOR,
        font=dict(color="#f2f2f2"),
        xaxis=dict(title=None, gridcolor="#151515"),
        yaxis=dict(title="xG", gridcolor="#151515"),
        legend=dict(orientation="h"),
    )
    st.plotly_chart(fig, use_container_width=True)


def render_heatmap(team_shots: pd.DataFrame) -> None:
    st.markdown('<div class="section-label">Mapa de calor</div>', unsafe_allow_html=True)
    data = team_shots[team_shots["x"].notna() & team_shots["y"].notna()].copy()
    if data.empty:
        st.info("Sem localização de finalizações para este time.")
        return

    fig = px.density_heatmap(
        data,
        x="x",
        y="y",
        nbinsx=24,
        nbinsy=16,
        color_continuous_scale=["#071207", "#315c00", PRIMARY_COLOR],
    )
    fig.update_layout(
        height=560,
        paper_bgcolor=BACKGROUND_COLOR,
        plot_bgcolor=BACKGROUND_COLOR,
        font=dict(color="#f2f2f2"),
        xaxis=dict(range=[0, 120], visible=False),
        yaxis=dict(range=[0, 80], visible=False, scaleanchor="x", scaleratio=1),
    )
    st.plotly_chart(fig, use_container_width=True)


def render_shot_breakdown(team_shots: pd.DataFrame) -> None:
    st.markdown('<div class="section-label">Finalizações por tipo</div>', unsafe_allow_html=True)
    if team_shots.empty:
        st.info("Sem finalizações para este time.")
        return

    col1, col2 = st.columns(2)
    with col1:
        body = team_shots.groupby("body_part", as_index=False).agg(shots=("shot_id", "count"))
        fig = px.pie(body, names="body_part", values="shots", hole=0.55)
        fig.update_layout(height=440, paper_bgcolor=BACKGROUND_COLOR, font=dict(color="#f2f2f2"))
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        shot_type = team_shots.groupby("shot_type", as_index=False).agg(shots=("shot_id", "count"))
        fig = px.pie(shot_type, names="shot_type", values="shots", hole=0.55)
        fig.update_layout(height=440, paper_bgcolor=BACKGROUND_COLOR, font=dict(color="#f2f2f2"))
        st.plotly_chart(fig, use_container_width=True)


missing_paths = [
    str(path)
    for path in [TEAM_SUMMARY_PATH, MATCH_TEAM_SUMMARY_PATH, PLAYER_SHOTS_PATH]
    if not path.exists()
]
if missing_paths:
    st.warning("Run `make gold` and `make player_offensive` first.")
    st.code("\n".join(missing_paths))
    st.stop()


team_summary_df, match_team_summary_df, player_shots_df = load_data()

st.title("Times")
st.markdown(
    '<div class="small-caption">Vitrine, rankings e mapas ofensivos por seleção.</div>',
    unsafe_allow_html=True,
)

editions = sorted(team_summary_df["edition_year"].dropna().unique().tolist(), reverse=True)
selected_edition = st.sidebar.selectbox("Edição", editions)
edition_teams = sorted(
    team_summary_df[team_summary_df["edition_year"].eq(selected_edition)]["team_name"]
    .dropna()
    .unique()
    .tolist()
)
selected_team = st.sidebar.selectbox("Time", edition_teams)
mode = st.sidebar.radio(
    "Menu",
    [
        "Vitrine do time",
        "Cartão de performance",
        "Ranking de xG",
        "Radar de performance",
        "Evolução do xG acumulado",
        "Forma - rolling xG",
        "Mapa de calor",
        "Finalizações por tipo",
    ],
)

team_row = get_team_row(team_summary_df, selected_edition, selected_team)
match_log_df = build_team_match_log(match_team_summary_df, selected_edition, selected_team)
team_shots_df = build_team_shot_profile(player_shots_df, selected_edition, selected_team)

if mode == "Vitrine do time":
    render_hero(team_row)
elif mode == "Cartão de performance":
    render_performance_card(team_row)
elif mode == "Ranking de xG":
    render_xg_ranking(team_summary_df, selected_edition, selected_team)
elif mode == "Radar de performance":
    render_radar(team_summary_df, team_row)
elif mode == "Evolução do xG acumulado":
    render_xg_evolution(match_log_df)
elif mode == "Forma - rolling xG":
    render_form(match_log_df)
elif mode == "Mapa de calor":
    render_heatmap(team_shots_df)
elif mode == "Finalizações por tipo":
    render_shot_breakdown(team_shots_df)
