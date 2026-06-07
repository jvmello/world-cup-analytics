from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


SILVER_SHOTS_PATH = Path(
    "data/silver/world_cup/shots/silver_world_cup_shots.parquet"
)

AVAILABILITY_PATH = Path(
    "data/silver/world_cup/metadata/world_cup_data_availability.parquet"
)


st.set_page_config(
    page_title="World Cup Analytics",
    layout="wide",
)


st.title("World Cup Analytics")


if AVAILABILITY_PATH.exists():
    availability = pd.read_parquet(AVAILABILITY_PATH)

    st.subheader("Data availability by edition")
    st.dataframe(availability, use_container_width=True)
else:
    st.warning("Data availability report not found. Run the validation pipeline first.")


if not SILVER_SHOTS_PATH.exists():
    st.warning("Silver shots table not found. Run the Silver pipeline first.")
    st.stop()


shots = pd.read_parquet(SILVER_SHOTS_PATH)

available_editions = sorted(shots["edition_year"].dropna().unique().tolist())

selected_edition = st.selectbox(
    "Edition",
    available_editions,
    index=len(available_editions) - 1,
)

edition_shots = shots[shots["edition_year"] == selected_edition].copy()

matches = (
    edition_shots[
        [
            "match_id",
            "match_date",
            "home_team",
            "away_team",
            "home_score",
            "away_score",
        ]
    ]
    .drop_duplicates()
    .sort_values(["match_date", "match_id"])
)

matches["match_label"] = (
    matches["match_date"].astype(str)
    + " - "
    + matches["home_team"].astype(str)
    + " "
    + matches["home_score"].astype(str)
    + " x "
    + matches["away_score"].astype(str)
    + " "
    + matches["away_team"].astype(str)
)

selected_match = st.selectbox("Match", matches["match_label"])

selected_match_id = matches.loc[
    matches["match_label"] == selected_match,
    "match_id",
].iloc[0]

match_shots = edition_shots[
    edition_shots["match_id"] == selected_match_id
].copy()

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Shots", len(match_shots))

with col2:
    st.metric("Goals", int(match_shots["is_goal"].sum()))

with col3:
    st.metric("xG", round(float(match_shots["statsbomb_xg"].sum()), 2))


st.subheader("Team xG summary")

team_summary = (
    match_shots.groupby("team_name", as_index=False)
    .agg(
        shots=("shot_id", "count"),
        goals=("is_goal", "sum"),
        xg=("statsbomb_xg", "sum"),
    )
)

team_summary["xg"] = team_summary["xg"].round(2)

st.dataframe(team_summary, use_container_width=True)


st.subheader("Shot map")

shot_map = match_shots[
    match_shots["has_location"].fillna(False)
    & match_shots["has_xg"].fillna(False)
].copy()

if not shot_map.empty:
    fig = px.scatter(
        shot_map,
        x="x",
        y="y",
        size="statsbomb_xg",
        hover_data=[
            "minute",
            "team_name",
            "player_name",
            "statsbomb_xg",
            "shot_outcome",
            "body_part",
            "shot_type",
        ],
        range_x=[0, 120],
        range_y=[0, 80],
        title="Shot locations",
    )

    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No shot location data available for this match.")


st.subheader("Cumulative xG")

timeline = match_shots[
    match_shots["has_xg"].fillna(False)
    & match_shots["minute"].notna()
    & match_shots["second"].notna()
].copy()

if not timeline.empty:
    timeline["elapsed_minute"] = (
        timeline["minute"].astype(float)
        + timeline["second"].astype(float) / 60
    )

    timeline = timeline.sort_values(
        ["team_name", "period", "minute", "second"]
    )

    timeline["cumulative_xg"] = (
        timeline.groupby("team_name")["statsbomb_xg"].cumsum()
    )

    fig = px.line(
        timeline,
        x="elapsed_minute",
        y="cumulative_xg",
        color="team_name",
        markers=True,
        hover_data=[
            "minute",
            "player_name",
            "statsbomb_xg",
            "shot_outcome",
        ],
        title="Cumulative xG",
    )

    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No xG timeline available for this match.")


st.subheader("Shots")

visible_columns = [
    "minute",
    "second",
    "team_name",
    "player_name",
    "statsbomb_xg",
    "shot_outcome",
    "body_part",
    "shot_type",
    "play_pattern",
]

existing_columns = [
    column for column in visible_columns if column in match_shots.columns
]

st.dataframe(
    match_shots[existing_columns].sort_values(["minute", "second"]),
    use_container_width=True,
)