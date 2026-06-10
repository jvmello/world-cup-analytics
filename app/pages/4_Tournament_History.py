from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from world_cup_history import (
    build_assist_leaderboard,
    build_champions,
    build_competition_group_tables,
    build_competition_knockouts,
    build_edition_overview,
    build_top_scorers,
)


MATCH_SUMMARY_PATH = Path(
    "data/gold/world_cup/gold_match_summary/gold_match_summary.parquet"
)
PLAYER_SUMMARY_PATH = Path(
    "data/gold/world_cup/gold_player_offensive_summary/"
    "gold_player_offensive_summary.parquet"
)
PLAYER_SHOTS_PATH = Path(
    "data/gold/world_cup/gold_player_shots/gold_player_shots.parquet"
)
TOURNAMENT_GROUPS_PATH = Path(
    "data/gold/world_cup/gold_tournament_groups/gold_tournament_groups.parquet"
)
TOURNAMENT_FIXTURES_PATH = Path(
    "data/gold/world_cup/gold_tournament_fixtures/gold_tournament_fixtures.parquet"
)

BACKGROUND_COLOR = "#050805"
PRIMARY_COLOR = "#9cff00"
SECONDARY_COLOR = "#00e5ff"
GRID_COLOR = "#1d2518"


st.set_page_config(
    page_title="Tournament History",
    layout="wide",
)


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


def read_optional_parquet(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()

    return pd.read_parquet(path)


@st.cache_data
def load_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    return (
        pd.read_parquet(MATCH_SUMMARY_PATH),
        pd.read_parquet(PLAYER_SUMMARY_PATH),
        pd.read_parquet(PLAYER_SHOTS_PATH),
        read_optional_parquet(TOURNAMENT_GROUPS_PATH),
        read_optional_parquet(TOURNAMENT_FIXTURES_PATH),
    )


def render_overview(overview: pd.DataFrame) -> None:
    st.markdown('<div class="section-label">Resumo histórico</div>', unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Copas no dataset", overview["edition_year"].nunique())
    col2.metric("Partidas", int(overview["matches"].sum()))
    col3.metric("Gols", int(overview["goals"].sum()))
    col4.metric("Finalizações", int(overview["shots"].sum()))

    fig = go.Figure()
    chart_data = overview.sort_values("edition_year")

    fig.add_trace(
        go.Bar(
            x=chart_data["edition_year"],
            y=chart_data["goals"],
            name="Gols",
            marker_color=PRIMARY_COLOR,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=chart_data["edition_year"],
            y=chart_data["goals_per_match"],
            name="Gols por jogo",
            yaxis="y2",
            mode="lines+markers",
            line=dict(color=SECONDARY_COLOR, width=3),
        )
    )

    fig.update_layout(
        height=520,
        paper_bgcolor=BACKGROUND_COLOR,
        plot_bgcolor=BACKGROUND_COLOR,
        font=dict(color="#f2f2f2"),
        xaxis=dict(title="Edição", gridcolor="#151515"),
        yaxis=dict(title="Gols", gridcolor="#151515"),
        yaxis2=dict(
            title="Gols por jogo",
            overlaying="y",
            side="right",
            gridcolor="#151515",
        ),
        legend=dict(orientation="h"),
    )

    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(
        overview.rename(
            columns={
                "edition_year": "Edição",
                "champion": "Campeã",
                "runner_up": "Vice",
                "matches": "Partidas",
                "teams": "Seleções",
                "goals": "Gols",
                "goals_per_match": "Gols/jogo",
                "shots": "Finalizações",
                "xg": "xG",
                "players_with_shots": "Jogadores com chute",
                "first_match": "Primeiro jogo",
                "last_match": "Último jogo",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )


def render_champions(champions: pd.DataFrame) -> None:
    st.markdown('<div class="section-label">Campeãs</div>', unsafe_allow_html=True)

    table = champions.copy()
    table["Decisão"] = table["winner_source"].map(
        {
            "score": "Placar",
            "penalties": "Pênaltis",
            "draw": "Não inferido",
        }
    )

    st.dataframe(
        table[
            [
                "edition_year",
                "champion",
                "runner_up",
                "final",
                "penalty_score",
                "Decisão",
            ]
        ].rename(
            columns={
                "edition_year": "Edição",
                "champion": "Campeã",
                "runner_up": "Vice",
                "final": "Final",
                "penalty_score": "Pênaltis",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )


def render_top_scorers(top_scorers: pd.DataFrame) -> None:
    st.markdown('<div class="section-label">Artilheiros</div>', unsafe_allow_html=True)

    if top_scorers.empty:
        st.info("Sem gols de jogadores para os filtros atuais.")
        return

    fig = px.bar(
        top_scorers.sort_values("goals", ascending=True),
        x="goals",
        y="player_display_name",
        color="team_name",
        orientation="h",
        hover_data=["edition_year", "shots", "xg", "goals_minus_xg"],
        color_discrete_sequence=[PRIMARY_COLOR, SECONDARY_COLOR, "#a970ff", "#ffcc00"],
    )

    fig.update_layout(
        height=max(480, min(820, 38 * len(top_scorers))),
        paper_bgcolor=BACKGROUND_COLOR,
        plot_bgcolor=BACKGROUND_COLOR,
        font=dict(color="#f2f2f2"),
        xaxis=dict(title="Gols", gridcolor="#151515"),
        yaxis=dict(title=None),
        legend=dict(orientation="h"),
        margin=dict(l=10, r=10, t=30, b=80),
    )

    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(
        top_scorers[
            [
                "edition_year",
                "team_name",
                "player_display_name",
                "goals",
                "shots",
                "xg",
                "goals_minus_xg",
            ]
        ].rename(
            columns={
                "edition_year": "Edição",
                "team_name": "Seleção",
                "player_display_name": "Jogador",
                "goals": "Gols",
                "shots": "Finalizações",
                "xg": "xG",
                "goals_minus_xg": "G - xG",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )


def render_assists() -> None:
    st.markdown('<div class="section-label">Assistentes</div>', unsafe_allow_html=True)
    assists = build_assist_leaderboard()

    if assists.empty:
        st.info(
            "Assistências ainda não estão disponíveis na camada gold. "
            "O silver de eventos atual preserva tipo, time e jogador, mas não carrega "
            "campos de passe/assistência do evento original."
        )
        return

    st.dataframe(assists, use_container_width=True, hide_index=True)


def render_group_stage(group_table: pd.DataFrame) -> None:
    st.markdown('<div class="section-label">Classificação em grupos</div>', unsafe_allow_html=True)

    if group_table.empty:
        st.info("Não há partidas de fase de grupos para a edição selecionada.")
        return

    groups = group_table["group_name"].dropna().unique().tolist()

    for index in range(0, len(groups), 3):
        columns = st.columns(3)
        for column, group_name in zip(columns, groups[index:index + 3]):
            data = group_table[group_table["group_name"].eq(group_name)].copy()
            with column:
                st.markdown(f"#### Grupo {group_name}")
                st.dataframe(
                    data[
                        [
                            "position",
                            "team_name",
                            "played",
                            "wins",
                            "draws",
                            "losses",
                            "goals_for",
                            "goals_against",
                            "goal_difference",
                            "points",
                        ]
                    ].rename(
                        columns={
                            "position": "#",
                            "team_name": "Seleção",
                            "played": "J",
                            "wins": "V",
                            "draws": "E",
                            "losses": "D",
                            "goals_for": "GP",
                            "goals_against": "GC",
                            "goal_difference": "SG",
                            "points": "Pts",
                        }
                    ),
                    use_container_width=True,
                    hide_index=True,
                )


def render_knockouts(knockouts: pd.DataFrame) -> None:
    st.markdown('<div class="section-label">Mata-mata</div>', unsafe_allow_html=True)

    if knockouts.empty:
        st.info("Não há mata-mata para a edição selecionada.")
        return

    visible_columns = [
        "edition_year",
        "competition_stage",
        "match_date",
        "home_team",
        "score",
        "away_team",
        "winner",
        "penalty_score",
        "stadium",
    ]
    existing_columns = [column for column in visible_columns if column in knockouts.columns]

    table = knockouts[existing_columns].rename(
        columns={
            "edition_year": "Edição",
            "competition_stage": "Fase",
            "match_date": "Data",
            "home_team": "Mandante",
            "score": "Placar",
            "away_team": "Visitante",
            "winner": "Vencedor",
            "penalty_score": "Pênaltis",
            "stadium": "Estádio",
        }
    )

    st.dataframe(table, use_container_width=True, hide_index=True)


def render_next_world_cup_plan() -> None:
    st.markdown(
        '<div class="section-label">Extração gradual da próxima Copa</div>',
        unsafe_allow_html=True,
    )
    st.write(
        "O caminho recomendado é manter `WORLD_CUP_SEASONS` como contrato de edições "
        "e rodar a pipeline por edição quando os dados forem publicados. Para Airflow, "
        "a DAG deve ter tarefas idempotentes por camada: extract bronze, build silver, "
        "build gold e validate."
    )

    st.code(
        """world_cup_incremental
  extract_statsbomb_world_cup(season)
  build_silver_world_cup(season)
  build_gold_world_cup(season)
  build_gold_player_offensive(season)
  validate_world_cup_data(season)""",
        language="text",
    )

    st.write(
        "O ponto que falta para assistências é preservar os campos detalhados de passe "
        "na silver de eventos, por exemplo `pass_goal_assist` e destinatário do passe, "
        "antes de publicar um gold de assistências."
    )


missing_paths = [
    str(path)
    for path in [MATCH_SUMMARY_PATH, PLAYER_SUMMARY_PATH, PLAYER_SHOTS_PATH]
    if not path.exists()
]

if missing_paths:
    st.warning("Run `make gold` and `make player_offensive` first.")
    st.code("\n".join(missing_paths))
    st.stop()


matches_df, player_summary_df, player_shots_df, tournament_groups_df, tournament_fixtures_df = load_data()
overview_df = build_edition_overview(matches_df, player_summary_df, player_shots_df)
champions_df = build_champions(matches_df, player_shots_df)

st.title("Copa do Mundo")
st.markdown(
    '<div class="small-caption">Classificação, mata-mata, histórico e caminho para atualização incremental.</div>',
    unsafe_allow_html=True,
)

historical_editions = matches_df["edition_year"].dropna().unique().tolist()
scheduled_editions = tournament_groups_df["edition_year"].dropna().unique().tolist()
edition_values = sorted(set(historical_editions + scheduled_editions), reverse=True)
default_index = edition_values.index(2026) if 2026 in edition_values else 0
selected_edition = st.sidebar.selectbox("Edição", edition_values, index=default_index)
top_limit = st.sidebar.slider("Linhas dos rankings", 5, 50, 20, step=5)

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
    [
        "Competição",
        "Resumo histórico",
        "Campeãs",
        "Artilheiros",
        "Assistentes",
        "Próxima Copa",
    ]
)

with tab1:
    render_group_stage(
        build_competition_group_tables(
            matches_df,
            int(selected_edition),
            tournament_groups_df,
        )
    )
    st.divider()
    render_knockouts(
        build_competition_knockouts(
            matches_df,
            player_shots_df,
            edition_year=selected_edition,
            scheduled_fixtures=tournament_fixtures_df,
        )
    )

with tab2:
    render_overview(overview_df)

with tab3:
    render_champions(champions_df)

with tab4:
    render_top_scorers(
        build_top_scorers(
            player_summary_df,
            selected_edition,
            limit=top_limit,
        )
    )

with tab5:
    render_assists()

with tab6:
    render_next_world_cup_plan()
