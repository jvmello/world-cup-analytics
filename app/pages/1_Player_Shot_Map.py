from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


PLAYER_SHOTS_PATH = Path(
    "data/gold/world_cup/gold_player_shots/gold_player_shots.parquet"
)

PLAYER_SUMMARY_PATH = Path(
    "data/gold/world_cup/gold_player_offensive_summary/gold_player_offensive_summary.parquet"
)


st.set_page_config(
    page_title="Player Shot Map",
    layout="wide",
)


def draw_pitch(fig: go.Figure) -> go.Figure:
    fig.update_xaxes(range=[0, 120], visible=False)
    fig.update_yaxes(range=[0, 80], visible=False, scaleanchor="x", scaleratio=1)

    line_color = "#8cff00"

    shapes = [
        # Pitch outline
        dict(type="rect", x0=0, y0=0, x1=120, y1=80, line=dict(color=line_color, width=1)),
        # Halfway line
        dict(type="line", x0=60, y0=0, x1=60, y1=80, line=dict(color=line_color, width=1)),
        # Penalty area
        dict(type="rect", x0=102, y0=18, x1=120, y1=62, line=dict(color=line_color, width=1)),
        # Six-yard box
        dict(type="rect", x0=114, y0=30, x1=120, y1=50, line=dict(color=line_color, width=1)),
        # Goal
        dict(type="rect", x0=120, y0=36, x1=122, y1=44, line=dict(color=line_color, width=1)),
    ]

    fig.update_layout(shapes=shapes)

    return fig


def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    shots = pd.read_parquet(PLAYER_SHOTS_PATH)
    summary = pd.read_parquet(PLAYER_SUMMARY_PATH)
    return shots, summary


if not PLAYER_SHOTS_PATH.exists() or not PLAYER_SUMMARY_PATH.exists():
    st.warning("Run `make player_offensive` first.")
    st.stop()


shots, summary = load_data()

st.title("Player Shot Map")

editions = sorted(shots["edition_year"].unique(), reverse=True)
selected_edition = st.selectbox("Edition", editions)

edition_shots = shots[shots["edition_year"] == selected_edition].copy()

teams = sorted(edition_shots["team_name"].dropna().unique())
selected_team = st.selectbox("Team", teams)

team_shots = edition_shots[edition_shots["team_name"] == selected_team].copy()

players = (
    team_shots.groupby("player_name", as_index=False)
    .agg(
        shots=("shot_id", "count"),
        xg=("statsbomb_xg", "sum"),
        goals=("is_goal", "sum"),
    )
    .sort_values(["xg", "goals", "shots"], ascending=False)
)

selected_player = st.selectbox("Player", players["player_name"])

player_shots = team_shots[team_shots["player_name"] == selected_player].copy()

player_summary = summary[
    (summary["edition_year"] == selected_edition)
    & (summary["team_name"] == selected_team)
    & (summary["player_name"] == selected_player)
].copy()

if player_summary.empty:
    st.warning("No summary found for selected player.")
    st.stop()

row = player_summary.iloc[0]

col1, col2, col3, col4, col5 = st.columns(5)

col1.metric("Shots", int(row["shots"]))
col2.metric("Goals", int(row["goals"]))
col3.metric("xG", round(float(row["xg"]), 2))
col4.metric("xG/shot", round(float(row["avg_xg_per_shot"]), 3))
col5.metric("On target", int(row["shots_on_target"]))

st.subheader("Shot map")

player_shots["marker_symbol"] = player_shots["is_goal"].apply(
    lambda value: "star" if value else "circle"
)

player_shots["result_label"] = player_shots["shot_outcome"].astype(str)

fig = go.Figure()

for is_goal, data in player_shots.groupby("is_goal"):
    fig.add_trace(
        go.Scatter(
            x=data["x"],
            y=data["y"],
            mode="markers",
            marker=dict(
                size=(data["statsbomb_xg"] * 70) + 8,
                symbol="star" if is_goal else "circle",
                opacity=0.85,
                line=dict(width=1),
            ),
            name="Goal" if is_goal else "Shot",
            text=(
                data["minute"].astype(str)
                + "' - "
                + data["shot_outcome"].astype(str)
                + "<br>xG: "
                + data["statsbomb_xg"].round(3).astype(str)
                + "<br>"
                + data["body_part"].astype(str)
                + " / "
                + data["shot_type"].astype(str)
            ),
            hoverinfo="text",
        )
    )

fig = draw_pitch(fig)

fig.update_layout(
    height=520,
    margin=dict(l=10, r=10, t=30, b=10),
    paper_bgcolor="#050805",
    plot_bgcolor="#071207",
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=-0.12,
        xanchor="center",
        x=0.5,
    ),
)

st.plotly_chart(fig, use_container_width=True)

st.caption("Marker size = xG. Stars = goals.")

st.subheader("Shots")

visible_columns = [
    "match_date",
    "home_team",
    "away_team",
    "minute",
    "second",
    "statsbomb_xg",
    "shot_outcome",
    "body_part",
    "shot_type",
    "technique",
    "play_pattern",
]

st.dataframe(
    player_shots[visible_columns].sort_values(
        ["match_date", "minute", "second"]
    ),
    use_container_width=True,
)