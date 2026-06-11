from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


PLAYER_SHOTS_PATH = Path(
    "data/gold/world_cup/gold_player_shots/gold_player_shots.parquet"
)

PLAYER_SUMMARY_PATH = Path(
    "data/gold/world_cup/gold_player_offensive_summary/gold_player_offensive_summary.parquet"
)


PRIMARY_COLOR = "#9cff00"
SECONDARY_COLOR = "#00e5ff"
DANGER_COLOR = "#ff4d4d"
BACKGROUND_COLOR = "#050805"
PITCH_COLOR = "#071207"
GRID_COLOR = "#243319"


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
            border-radius: 10px;
        }

        h1, h2, h3 {
            color: #f3f3f3;
        }

        .small-caption {
            color: #a0a0a0;
            font-size: 13px;
            letter-spacing: 0.04em;
        }

        .section-label {
            color: #9cff00;
            font-weight: 700;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            font-size: 13px;
            margin-top: 10px;
        }

        div[role="radiogroup"] {
            background: #050805;
            border: 1px solid #1d2518;
            border-radius: 8px;
            padding: 6px;
            gap: 4px;
            margin-bottom: 14px;
        }

        div[role="radiogroup"] label {
            border-radius: 6px;
            padding: 8px 12px;
        }

        div[role="radiogroup"] label:has(input:checked) {
            background: #9cff00;
            color: #050805;
            box-shadow: 0 0 18px rgba(156, 255, 0, 0.28);
        }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data
def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    shots = pd.read_parquet(PLAYER_SHOTS_PATH)
    summary = pd.read_parquet(PLAYER_SUMMARY_PATH)

    if "player_display_name" not in shots.columns:
        shots["player_display_name"] = shots["player_name"]

    if "player_display_name" not in summary.columns:
        summary["player_display_name"] = summary["player_name"]

    return shots, summary


def draw_pitch(fig: go.Figure) -> go.Figure:
    line_color = PRIMARY_COLOR

    shapes = [
        dict(type="rect", x0=0, y0=0, x1=120, y1=80, line=dict(color=line_color, width=1)),
        dict(type="line", x0=60, y0=0, x1=60, y1=80, line=dict(color=line_color, width=1)),
        dict(type="rect", x0=102, y0=18, x1=120, y1=62, line=dict(color=line_color, width=1)),
        dict(type="rect", x0=114, y0=30, x1=120, y1=50, line=dict(color=line_color, width=1)),
        dict(type="rect", x0=120, y0=36, x1=122, y1=44, line=dict(color=line_color, width=1)),
        dict(type="circle", x0=48, y0=28, x1=72, y1=52, line=dict(color=line_color, width=1)),
    ]

    fig.update_layout(
        shapes=shapes,
        height=560,
        paper_bgcolor=BACKGROUND_COLOR,
        plot_bgcolor=PITCH_COLOR,
        margin=dict(l=10, r=10, t=40, b=10),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.12,
            xanchor="center",
            x=0.5,
        ),
    )

    fig.update_xaxes(
        range=[0, 122],
        showgrid=False,
        zeroline=False,
        visible=False,
    )

    fig.update_yaxes(
        range=[0, 80],
        showgrid=False,
        zeroline=False,
        visible=False,
        scaleanchor="x",
        scaleratio=1,
    )

    return fig


def draw_goal(fig: go.Figure) -> go.Figure:
    line_color = PRIMARY_COLOR

    fig.update_layout(
        height=500,
        paper_bgcolor=BACKGROUND_COLOR,
        plot_bgcolor=PITCH_COLOR,
        margin=dict(l=10, r=10, t=40, b=10),
        shapes=[
            dict(
                type="rect",
                x0=36,
                y0=0,
                x1=44,
                y1=2.67,
                line=dict(color=line_color, width=4),
            )
        ],
    )

    fig.update_xaxes(
        range=[34, 46],
        showgrid=True,
        gridcolor=GRID_COLOR,
        zeroline=False,
        title=None,
    )

    fig.update_yaxes(
        range=[0, 3.2],
        showgrid=True,
        gridcolor=GRID_COLOR,
        zeroline=False,
        title=None,
    )

    return fig


def get_player_context(
    shots: pd.DataFrame,
    summary: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
    editions = sorted(shots["edition_year"].dropna().unique(), reverse=True)

    filter_col1, filter_col2, filter_col3 = st.columns([1, 1.4, 2])

    with filter_col1:
        selected_edition = st.selectbox("Edição", editions)

    edition_shots = shots[shots["edition_year"] == selected_edition].copy()

    teams = sorted(edition_shots["team_name"].dropna().unique())

    with filter_col2:
        selected_team = st.selectbox("Time", teams)

    team_shots = edition_shots[edition_shots["team_name"] == selected_team].copy()

    players_rank = (
        team_shots.groupby(["player_name", "player_display_name"], as_index=False)
        .agg(
            shots=("shot_id", "count"),
            goals=("is_goal", "sum"),
            xg=("statsbomb_xg", "sum"),
        )
        .sort_values(["xg", "goals", "shots"], ascending=False)
    )

    with filter_col3:
        selected_display_name = st.selectbox(
            "Jogador",
            players_rank["player_display_name"].tolist(),
        )

    selected_player_name = players_rank.loc[
        players_rank["player_display_name"] == selected_display_name,
        "player_name",
    ].iloc[0]

    player_shots = team_shots[
        team_shots["player_name"] == selected_player_name
    ].copy()

    player_summary = summary[
        (summary["edition_year"] == selected_edition)
        & (summary["team_name"] == selected_team)
        & (summary["player_name"] == selected_player_name)
    ].copy()

    if player_summary.empty:
        st.warning("No summary found for selected player.")
        st.stop()

    return player_shots, team_shots, player_summary.iloc[0]


def render_header(player_summary: pd.Series) -> None:
    player_name = player_summary["player_display_name"]
    team_name = player_summary["team_name"]
    edition_year = player_summary["edition_year"]

    st.markdown(
        f"""
        <div class="small-caption">
            {player_name} · {team_name} · Copa do Mundo {edition_year}
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2, col3, col4, col5, col6 = st.columns(6)

    col1.metric("Finalizações", int(player_summary["shots"]))
    col2.metric("Gols", int(player_summary["goals"]))
    col3.metric("xG", round(float(player_summary["xg"]), 2))
    col4.metric("xG/finaliz.", round(float(player_summary["avg_xg_per_shot"]), 3))
    col5.metric("No alvo", int(player_summary["shots_on_target"]))
    col6.metric("G - xG", round(float(player_summary["goals_minus_xg"]), 2))


def render_shot_map(player_shots: pd.DataFrame) -> None:
    st.markdown('<div class="section-label">Mapa de finalizações</div>', unsafe_allow_html=True)

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
                    color=PRIMARY_COLOR if is_goal else SECONDARY_COLOR,
                    opacity=0.85,
                    line=dict(width=1, color="#ffffff"),
                ),
                name="Gol" if is_goal else "Finalização",
                text=(
                    data["minute"].astype(str)
                    + "' · "
                    + data["shot_outcome"].astype(str)
                    + "<br>xG: "
                    + data["statsbomb_xg"].round(3).astype(str)
                    + "<br>"
                    + data["body_part"].astype(str)
                    + " · "
                    + data["shot_type"].astype(str)
                ),
                hoverinfo="text",
            )
        )

    fig = draw_pitch(fig)
    st.plotly_chart(fig, use_container_width=True)

    st.caption("Tamanho do ponto = xG. Estrela = gol.")


def render_goal_mouth(player_shots: pd.DataFrame) -> None:
    st.markdown('<div class="section-label">Local no alvo</div>', unsafe_allow_html=True)

    target_shots = player_shots[
        player_shots["end_y"].notna()
        & player_shots["end_z"].notna()
        & player_shots["shot_outcome"].isin(["Goal", "Saved", "Saved to Post", "Post"])
    ].copy()

    if target_shots.empty:
        st.info("Este jogador não tem dados suficientes de localização no alvo.")
        return

    fig = go.Figure()

    for is_goal, data in target_shots.groupby("is_goal"):
        fig.add_trace(
            go.Scatter(
                x=data["end_y"],
                y=data["end_z"],
                mode="markers",
                marker=dict(
                    size=(data["statsbomb_xg"] * 70) + 10,
                    symbol="star" if is_goal else "circle",
                    color=PRIMARY_COLOR if is_goal else SECONDARY_COLOR,
                    opacity=0.9,
                    line=dict(width=1, color="#ffffff"),
                ),
                name="Gol" if is_goal else "No alvo",
                text=(
                    data["minute"].astype(str)
                    + "' · "
                    + data["shot_outcome"].astype(str)
                    + "<br>xG: "
                    + data["statsbomb_xg"].round(3).astype(str)
                ),
                hoverinfo="text",
            )
        )

    fig = draw_goal(fig)
    st.plotly_chart(fig, use_container_width=True)


def render_heatmap(player_shots: pd.DataFrame) -> None:
    st.markdown('<div class="section-label">Mapa de calor</div>', unsafe_allow_html=True)

    data = player_shots[player_shots["x"].notna() & player_shots["y"].notna()].copy()

    if data.empty:
        st.info("Sem dados de localização para mapa de calor.")
        return

    fig = px.density_heatmap(
        data,
        x="x",
        y="y",
        nbinsx=24,
        nbinsy=16,
        color_continuous_scale=["#071207", "#315c00", PRIMARY_COLOR],
    )

    goals = data[data["is_goal"]].copy()

    if not goals.empty:
        fig.add_trace(
            go.Scatter(
                x=goals["x"],
                y=goals["y"],
                mode="markers",
                marker=dict(
                    symbol="star",
                    size=12,
                    color="#ffffff",
                    line=dict(color=PRIMARY_COLOR, width=1),
                ),
                name="Gols",
            )
        )

    fig = draw_pitch(fig)
    st.plotly_chart(fig, use_container_width=True)


def render_time_bins(player_shots: pd.DataFrame) -> None:
    st.markdown('<div class="section-label">Finalizações por minuto</div>', unsafe_allow_html=True)

    data = player_shots[player_shots["minute"].notna()].copy()
    data["minute_bin"] = (data["minute"] // 5) * 5

    bins = (
        data.groupby("minute_bin", as_index=False)
        .agg(
            shots=("shot_id", "count"),
            goals=("is_goal", "sum"),
        )
        .sort_values("minute_bin")
    )

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=bins["minute_bin"],
            y=bins["shots"],
            name="Finalizações",
            marker_color="#315c00",
        )
    )

    fig.add_trace(
        go.Bar(
            x=bins["minute_bin"],
            y=bins["goals"],
            name="Gols",
            marker_color=PRIMARY_COLOR,
        )
    )

    fig.update_layout(
        barmode="overlay",
        height=500,
        paper_bgcolor=BACKGROUND_COLOR,
        plot_bgcolor=BACKGROUND_COLOR,
        font=dict(color="#f2f2f2"),
        xaxis=dict(title="Minuto", gridcolor="#151515"),
        yaxis=dict(title="Finalizações", gridcolor="#151515"),
        legend=dict(orientation="h"),
    )

    st.plotly_chart(fig, use_container_width=True)


def render_body_and_pattern(player_shots: pd.DataFrame) -> None:
    st.markdown('<div class="section-label">Corpo & situação</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    body = (
        player_shots.groupby("body_part", as_index=False)
        .agg(shots=("shot_id", "count"))
        .sort_values("shots", ascending=False)
    )

    pattern = (
        player_shots.groupby("play_pattern", as_index=False)
        .agg(shots=("shot_id", "count"))
        .sort_values("shots", ascending=False)
    )

    with col1:
        fig = px.pie(
            body,
            names="body_part",
            values="shots",
            hole=0.55,
            title="Parte do corpo",
            color_discrete_sequence=[PRIMARY_COLOR, SECONDARY_COLOR, "#a970ff", DANGER_COLOR],
        )
        fig.update_layout(
            height=460,
            paper_bgcolor=BACKGROUND_COLOR,
            plot_bgcolor=BACKGROUND_COLOR,
            font=dict(color="#f2f2f2"),
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        fig = px.pie(
            pattern,
            names="play_pattern",
            values="shots",
            hole=0.55,
            title="Situação de jogo",
            color_discrete_sequence=[PRIMARY_COLOR, DANGER_COLOR, "#a970ff", SECONDARY_COLOR],
        )
        fig.update_layout(
            height=460,
            paper_bgcolor=BACKGROUND_COLOR,
            plot_bgcolor=BACKGROUND_COLOR,
            font=dict(color="#f2f2f2"),
        )
        st.plotly_chart(fig, use_container_width=True)


def render_xg_goals_scatter(
    summary: pd.DataFrame,
    selected_player: str,
    selected_edition: int,
) -> None:
    st.markdown('<div class="section-label">Scatter xG × Gols</div>', unsafe_allow_html=True)

    data = summary[
        (summary["edition_year"] == selected_edition)
        & (summary["shots"] >= 3)
    ].copy()

    data["is_selected"] = data["player_name"].eq(selected_player)

    max_value = max(data["xg"].max(), data["goals"].max()) + 1

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=[0, max_value],
            y=[0, max_value],
            mode="lines",
            line=dict(color="#888888", dash="dash"),
            name="xG = Gols",
        )
    )

    fig.add_trace(
        go.Scatter(
            x=data["xg"],
            y=data["goals"],
            mode="markers",
            marker=dict(
                size=data["shots"] + 6,
                color=data["goals_minus_xg"],
                colorscale=[[0, DANGER_COLOR], [0.5, "#777777"], [1, PRIMARY_COLOR]],
                showscale=True,
            ),
            text=(
                data["player_display_name"].astype(str)
                + "<br>Time: "
                + data["team_name"].astype(str)
                + "<br>Gols: "
                + data["goals"].astype(str)
                + "<br>xG: "
                + data["xg"].round(2).astype(str)
                + "<br>G-xG: "
                + data["goals_minus_xg"].round(2).astype(str)
            ),
            hoverinfo="text",
            name="Jogadores",
        )
    )

    selected = data[data["is_selected"]]

    if not selected.empty:
        fig.add_trace(
            go.Scatter(
                x=selected["xg"],
                y=selected["goals"],
                mode="markers+text",
                marker=dict(
                    size=20,
                    color=PRIMARY_COLOR,
                    line=dict(color="#ffffff", width=2),
                ),
                text=selected["player_display_name"],
                textposition="top center",
                name="Selecionado",
            )
        )

    fig.update_layout(
        height=560,
        paper_bgcolor=BACKGROUND_COLOR,
        plot_bgcolor=BACKGROUND_COLOR,
        font=dict(color="#f2f2f2"),
        xaxis=dict(title="xG", gridcolor="#151515"),
        yaxis=dict(title="Gols", gridcolor="#151515"),
        legend=dict(orientation="h"),
    )

    st.plotly_chart(fig, use_container_width=True)


def percentile_rank(series: pd.Series, value: float) -> int:
    return int(round((series <= value).mean() * 100, 0))


def render_percentiles(
    summary: pd.DataFrame,
    player_row: pd.Series,
) -> None:
    st.markdown('<div class="section-label">Percentis</div>', unsafe_allow_html=True)

    edition = player_row["edition_year"]

    comparison = summary[
        (summary["edition_year"] == edition)
        & (summary["shots"] >= 3)
    ].copy()

    metrics = [
        ("Finalizações", "shots"),
        ("Gols", "goals"),
        ("xG", "xg"),
        ("xG/finaliz.", "avg_xg_per_shot"),
        ("% no alvo", "shot_accuracy"),
        ("Conversão", None),
    ]

    player_conversion = (
        player_row["goals"] / player_row["shots"]
        if player_row["shots"] > 0
        else 0
    )

    comparison["conversion"] = comparison["goals"] / comparison["shots"]

    values = []

    for label, column in metrics:
        if column is None:
            value = player_conversion
            series = comparison["conversion"].fillna(0)
        else:
            value = player_row[column]
            series = comparison[column].fillna(0)

        values.append(
            {
                "metric": label,
                "percentile": percentile_rank(series, value),
            }
        )

    df = pd.DataFrame(values)

    fig = go.Figure(
        go.Bar(
            x=df["percentile"],
            y=df["metric"],
            orientation="h",
            marker_color=[
                PRIMARY_COLOR if value >= 75 else SECONDARY_COLOR if value >= 50 else "#46503f"
                for value in df["percentile"]
            ],
            text=df["percentile"],
            textposition="outside",
        )
    )

    fig.update_layout(
        height=520,
        paper_bgcolor=BACKGROUND_COLOR,
        plot_bgcolor=BACKGROUND_COLOR,
        font=dict(color="#f2f2f2"),
        xaxis=dict(range=[0, 100], title="Percentil", gridcolor="#151515"),
        yaxis=dict(title=None),
        margin=dict(l=120, r=40, t=30, b=30),
    )

    st.plotly_chart(fig, use_container_width=True)

    st.caption("Percentil calculado contra jogadores da mesma edição com pelo menos 3 finalizações.")


def render_radar(
    summary: pd.DataFrame,
    player_row: pd.Series,
) -> None:
    st.markdown('<div class="section-label">Radar do jogador</div>', unsafe_allow_html=True)

    edition = player_row["edition_year"]

    comparison = summary[
        (summary["edition_year"] == edition)
        & (summary["shots"] >= 3)
    ].copy()

    comparison["conversion"] = comparison["goals"] / comparison["shots"]

    player_conversion = (
        player_row["goals"] / player_row["shots"]
        if player_row["shots"] > 0
        else 0
    )

    radar_metrics = [
        ("Finalizações", "shots", player_row["shots"]),
        ("Gols", "goals", player_row["goals"]),
        ("xG", "xg", player_row["xg"]),
        ("xG/finaliz.", "avg_xg_per_shot", player_row["avg_xg_per_shot"]),
        ("% no alvo", "shot_accuracy", player_row["shot_accuracy"]),
        ("Conversão", "conversion", player_conversion),
    ]

    categories = []
    player_values = []
    average_values = []

    for label, column, player_value in radar_metrics:
        categories.append(label)
        player_values.append(percentile_rank(comparison[column].fillna(0), player_value))
        average_values.append(50)

    categories.append(categories[0])
    player_values.append(player_values[0])
    average_values.append(average_values[0])

    fig = go.Figure()

    fig.add_trace(
        go.Scatterpolar(
            r=player_values,
            theta=categories,
            fill="toself",
            name=player_row["player_display_name"],
            line=dict(color=PRIMARY_COLOR, width=3),
            fillcolor="rgba(156,255,0,0.25)",
        )
    )

    fig.add_trace(
        go.Scatterpolar(
            r=average_values,
            theta=categories,
            fill="toself",
            name="Mediana da edição",
            line=dict(color="#cccccc", width=2),
            fillcolor="rgba(200,200,200,0.12)",
        )
    )

    fig.update_layout(
        height=580,
        paper_bgcolor=BACKGROUND_COLOR,
        plot_bgcolor=BACKGROUND_COLOR,
        font=dict(color="#f2f2f2"),
        polar=dict(
            bgcolor=BACKGROUND_COLOR,
            radialaxis=dict(
                visible=True,
                range=[0, 100],
                gridcolor="#1d2518",
                tickfont=dict(color="#777777"),
            ),
            angularaxis=dict(gridcolor="#1d2518"),
        ),
        legend=dict(orientation="h"),
    )

    st.plotly_chart(fig, use_container_width=True)


if not PLAYER_SHOTS_PATH.exists() or not PLAYER_SUMMARY_PATH.exists():
    st.warning("Run `make player_offensive` first.")
    st.stop()


shots_df, summary_df = load_data()

st.title("Jogadores")
st.markdown(
    '<div class="small-caption">Análise ofensiva por jogador, edição e seleção.</div>',
    unsafe_allow_html=True,
)

player_shots_df, team_shots_df, player_summary_row = get_player_context(
    shots_df,
    summary_df,
)

render_header(player_summary_row)

view = st.radio(
    "View",
    [
        "Radar do jogador",
        "Mapa de finalizações",
        "Local no alvo",
        "Mapa de calor",
        "Finalizações por minuto",
        "Corpo & situação",
        "Scatter xG x Gols",
        "Percentis vs edição",
        "Tabela de chutes",
    ],
    horizontal=True,
    label_visibility="collapsed",
)

st.divider()

if view == "Radar do jogador":
    render_radar(summary_df, player_summary_row)

elif view == "Mapa de finalizações":
    render_shot_map(player_shots_df)

elif view == "Local no alvo":
    render_goal_mouth(player_shots_df)

elif view == "Mapa de calor":
    render_heatmap(player_shots_df)

elif view == "Finalizações por minuto":
    render_time_bins(player_shots_df)

elif view == "Corpo & situação":
    render_body_and_pattern(player_shots_df)

elif view == "Scatter xG x Gols":
    render_xg_goals_scatter(
        summary_df,
        selected_player=player_summary_row["player_name"],
        selected_edition=player_summary_row["edition_year"],
    )

elif view == "Percentis vs edição":
    render_percentiles(summary_df, player_summary_row)

elif view == "Tabela de chutes":
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

    existing_columns = [
        column for column in visible_columns if column in player_shots_df.columns
    ]

    st.dataframe(
        player_shots_df[existing_columns].sort_values(
            ["match_date", "minute", "second"]
        ),
        use_container_width=True,
    )
