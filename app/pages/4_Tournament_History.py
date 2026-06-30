from pathlib import Path
from html import escape

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from edition_context import get_selected_edition

from world_cup_history import (
    build_assist_leaderboard,
    build_champions,
    build_competition_group_tables,
    build_competition_knockouts,
    build_edition_overview,
    build_group_fixtures,
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

        div[role="radiogroup"] {
            background: #050805;
            border: 1px solid #1d2518;
            border-radius: 8px;
            padding: 6px;
            gap: 4px;
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

        .group-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
            gap: 18px;
            margin-top: 16px;
        }

        .group-card {
            border: 1px solid #1d2518;
            border-radius: 8px;
            background: #080d08;
            overflow: hidden;
        }

        .group-title {
            padding: 14px 16px 10px;
            font-size: 18px;
            font-weight: 800;
            color: #f2f2f2;
            border-bottom: 1px solid #1d2518;
        }

        .group-table {
            width: 100%;
            border-collapse: collapse;
            table-layout: fixed;
            font-size: 13px;
        }

        .group-table th {
            color: #a0a0a0;
            background: #0d130d;
            border-bottom: 1px solid #243319;
            padding: 8px 6px;
            text-align: right;
        }

        .group-table th.team-col,
        .group-table td.team-col {
            text-align: left;
            width: 34%;
        }

        .group-table th.status-col,
        .group-table td.status-col {
            width: 24%;
        }

        .group-table td {
            border-bottom: 1px solid #172017;
            padding: 8px 6px;
            text-align: right;
            font-variant-numeric: tabular-nums;
        }

        .group-table tr.qualified td {
            background: rgba(156, 255, 0, 0.16);
        }

        .group-table tr.possible td {
            background: rgba(0, 229, 255, 0.12);
        }

        .group-table tr.eliminated td {
            background: rgba(255, 77, 77, 0.16);
        }

        .group-table tr.pending td {
            background: rgba(255, 255, 255, 0.03);
        }

        .team-name {
            color: #f2f2f2;
            font-weight: 700;
        }

        .points-cell {
            color: #9cff00;
            font-weight: 900;
        }

        .fixtures-list {
            padding: 12px 16px 16px;
        }

        .fixture-row {
            display: grid;
            grid-template-columns: 86px 1fr 54px 1fr;
            gap: 10px;
            align-items: center;
            padding: 7px 0;
            border-bottom: 1px solid #172017;
            font-size: 13px;
        }

        .fixture-row:last-child {
            border-bottom: 0;
        }

        .fixture-date {
            color: #a0a0a0;
            font-size: 12px;
        }

        .fixture-team {
            color: #f2f2f2;
            font-weight: 700;
        }

        .fixture-score {
            color: #f2f2f2;
            font-weight: 900;
            text-align: center;
            font-variant-numeric: tabular-nums;
        }

        .bracket-scroll {
            overflow-x: auto;
            padding-bottom: 10px;
        }

        .bracket-grid {
            display: grid;
            grid-auto-flow: column;
            grid-auto-columns: minmax(230px, 1fr);
            gap: 14px;
            min-width: 980px;
            margin-top: 16px;
        }

        .bracket-round-title {
            border: 1px solid #1d2518;
            border-radius: 8px;
            background: #0d130d;
            color: #9cff00;
            font-weight: 800;
            letter-spacing: 0.04em;
            padding: 10px;
            text-align: center;
            margin-bottom: 12px;
        }

        .match-box {
            border: 1px solid #243319;
            border-radius: 8px;
            background: #080d08;
            margin-bottom: 12px;
            overflow: hidden;
        }

        .match-meta {
            color: #a0a0a0;
            font-size: 12px;
            padding: 8px 10px;
            border-bottom: 1px solid #172017;
        }

        .match-team-row {
            display: grid;
            grid-template-columns: 1fr 46px;
            gap: 10px;
            padding: 8px 10px;
            border-bottom: 1px solid #172017;
            align-items: center;
        }

        .match-team-row:last-child {
            border-bottom: 0;
        }

        .match-team-name {
            color: #f2f2f2;
            font-weight: 800;
        }

        .match-team-score {
            color: #9cff00;
            font-weight: 900;
            text-align: right;
            font-variant-numeric: tabular-nums;
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

    st.markdown(
        render_group_cards(group_table, pd.DataFrame()),
        unsafe_allow_html=True,
    )


def score_text(home_score: object, away_score: object) -> str:
    if pd.isna(home_score) or pd.isna(away_score):
        return "x"

    return f"{int(home_score)} - {int(away_score)}"


def group_status(position: int, played: int) -> tuple[str, str]:
    if played == 0:
        if position <= 2:
            return "pending", "Zona direta"
        if position == 3:
            return "possible", "Possível 3º"
        return "pending", "A disputar"

    if position <= 2:
        return "qualified", "Classificado"

    return "eliminated", "Eliminado"


def render_group_cards(group_table: pd.DataFrame, group_fixtures: pd.DataFrame) -> str:
    cards = []
    groups = group_table["group_name"].dropna().unique().tolist()

    for group_name in groups:
        table = group_table[group_table["group_name"].eq(group_name)].copy()
        fixtures = group_fixtures[
            group_fixtures.get("group_name", pd.Series(dtype=object)).eq(group_name)
        ].copy()

        rows = []
        total_played = int(table["played"].sum())

        for row in table.itertuples(index=False):
            css_class, status = group_status(int(row.position), total_played)
            rows.append(
                (
                    f'<tr class="{css_class}">'
                    f"<td>{int(row.position)}</td>"
                    f'<td class="team-col"><span class="team-name">{escape(str(row.team_name))}</span></td>'
                    f'<td class="points-cell">{int(row.points)}</td>'
                    f"<td>{int(row.played)}</td>"
                    f"<td>{int(row.wins)}</td>"
                    f"<td>{int(row.draws)}</td>"
                    f"<td>{int(row.losses)}</td>"
                    f"<td>{int(row.goals_for)}</td>"
                    f"<td>{int(row.goals_against)}</td>"
                    f"<td>{int(row.goal_difference):+d}</td>"
                    f'<td class="status-col">{status}</td>'
                    "</tr>"
                )
            )

        fixture_rows = []
        for fixture in fixtures.itertuples(index=False):
            date_label = getattr(fixture, "match_label_date", None)
            if pd.isna(date_label) or date_label is None:
                date_label = "A definir"
            fixture_rows.append(
                (
                    '<div class="fixture-row">'
                    f'<div class="fixture-date">{escape(str(date_label))}</div>'
                    f'<div class="fixture-team">{escape(str(fixture.home_team))}</div>'
                    f'<div class="fixture-score">{escape(score_text(fixture.home_score, fixture.away_score))}</div>'
                    f'<div class="fixture-team">{escape(str(fixture.away_team))}</div>'
                    "</div>"
                )
            )

        if not fixture_rows:
            fixture_rows.append(
                '<div class="fixture-row"><div class="fixture-date">-</div><div class="fixture-team">Sem jogos detalhados</div><div></div><div></div></div>'
            )

        cards.append(
            (
                '<section class="group-card">'
                f'<div class="group-title">Grupo {escape(str(group_name))}</div>'
                '<table class="group-table">'
                "<thead><tr>"
                "<th>Pos</th>"
                '<th class="team-col">Equipe</th>'
                "<th>Pts</th>"
                "<th>J</th>"
                "<th>V</th>"
                "<th>E</th>"
                "<th>D</th>"
                "<th>GP</th>"
                "<th>GC</th>"
                "<th>SG</th>"
                '<th class="status-col">Status</th>'
                "</tr></thead>"
                f'<tbody>{"".join(rows)}</tbody>'
                "</table>"
                f'<div class="fixtures-list">{"".join(fixture_rows)}</div>'
                "</section>"
            )
        )

    return f'<div class="group-grid">{"".join(cards)}</div>'


def render_knockouts(knockouts: pd.DataFrame) -> None:
    st.markdown('<div class="section-label">Mata-mata</div>', unsafe_allow_html=True)

    if knockouts.empty:
        st.info("Não há mata-mata para a edição selecionada.")
        return

    st.markdown(
        render_knockout_bracket(knockouts),
        unsafe_allow_html=True,
    )


def format_match_date(value: object) -> str:
    if pd.isna(value):
        return "A definir"

    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return str(value)

    return parsed.strftime("%d/%m/%Y")


def team_score(value: object) -> str:
    if pd.isna(value):
        return "-"

    try:
        return str(int(value))
    except (TypeError, ValueError):
        return str(value)


def render_knockout_bracket(knockouts: pd.DataFrame) -> str:
    stage_order = [
        "Round of 32",
        "Round of 16",
        "Quarter-finals",
        "Semi-finals",
        "3rd Place Final",
        "Final",
    ]
    stages = [
        stage for stage in stage_order
        if stage in knockouts["competition_stage"].dropna().unique().tolist()
    ]

    columns = []
    for stage in stages:
        matches = knockouts[knockouts["competition_stage"].eq(stage)].copy()
        boxes = []

        for match in matches.itertuples(index=False):
            match_date = format_match_date(getattr(match, "match_date", None))
            stadium = getattr(match, "stadium", None)
            meta = match_date
            if stadium is not None and not pd.isna(stadium):
                meta = f"{meta} - {stadium}"

            boxes.append(
                (
                    '<div class="match-box">'
                    f'<div class="match-meta">{escape(str(meta))}</div>'
                    '<div class="match-team-row">'
                    f'<div class="match-team-name">{escape(str(match.home_team))}</div>'
                    f'<div class="match-team-score">{escape(team_score(getattr(match, "home_score", None)))}</div>'
                    "</div>"
                    '<div class="match-team-row">'
                    f'<div class="match-team-name">{escape(str(match.away_team))}</div>'
                    f'<div class="match-team-score">{escape(team_score(getattr(match, "away_score", None)))}</div>'
                    "</div>"
                    "</div>"
                )
            )

        columns.append(
            (
                '<section class="bracket-round">'
                f'<div class="bracket-round-title">{escape(stage)}</div>'
                f'{"".join(boxes)}'
                "</section>"
            )
        )

    return f'<div class="bracket-scroll"><div class="bracket-grid">{"".join(columns)}</div></div>'


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

competition_sources = []
if "competition" in matches_df.columns:
    competition_sources.extend(matches_df["competition"].dropna().unique().tolist())
if "competition" in tournament_groups_df.columns:
    competition_sources.extend(tournament_groups_df["competition"].dropna().unique().tolist())
if "competition" in tournament_fixtures_df.columns:
    competition_sources.extend(tournament_fixtures_df["competition"].dropna().unique().tolist())

competition_values = sorted(set(competition_sources)) or ["FIFA World Cup"]
selected_competition = st.session_state.get(
    "selected_competition",
    competition_values[0],
)
if selected_competition not in competition_values:
    selected_competition = competition_values[0]

st.title("Copa do Mundo")
st.markdown(
    '<div class="small-caption">Classificação, mata-mata, histórico e caminho para atualização incremental.</div>',
    unsafe_allow_html=True,
)

historical_editions = matches_df["edition_year"].dropna().unique().tolist()
scheduled_editions = tournament_groups_df["edition_year"].dropna().unique().tolist()
edition_values = sorted(set(historical_editions + scheduled_editions), reverse=True)
selected_edition = get_selected_edition(st.session_state)
if selected_edition not in edition_values:
    selected_edition = edition_values[0]

control_col1, control_col2 = st.columns([1, 1])
with control_col1:
    st.metric("Edição", selected_edition)
with control_col2:
    top_limit = st.selectbox("Linhas dos rankings", [10, 20, 30, 50], index=1)

if "competition" in tournament_groups_df.columns:
    tournament_groups_df = tournament_groups_df[
        tournament_groups_df["competition"].eq(selected_competition)
    ].copy()
if "competition" in tournament_fixtures_df.columns:
    tournament_fixtures_df = tournament_fixtures_df[
        tournament_fixtures_df["competition"].eq(selected_competition)
    ].copy()
if "competition" in matches_df.columns:
    matches_df = matches_df[matches_df["competition"].eq(selected_competition)].copy()

overview_df = build_edition_overview(matches_df, player_summary_df, player_shots_df)
champions_df = build_champions(matches_df, player_shots_df)

selected_section = st.radio(
    "Seção",
    [
        "Classificação",
        "Competição",
        "Resumo histórico",
        "Campeãs",
        "Artilheiros",
        "Assistentes",
        "Próxima Copa",
    ],
    horizontal=True,
    label_visibility="collapsed",
)

if selected_section in ("Classificação", "Competição"):
    group_tables_df = build_competition_group_tables(
        matches_df,
        int(selected_edition),
        tournament_groups_df,
    )
    group_fixtures_df = build_group_fixtures(
        matches_df,
        int(selected_edition),
        tournament_fixtures_df,
    )
    st.markdown('<div class="section-label">Classificação em grupos</div>', unsafe_allow_html=True)
    if group_tables_df.empty:
        st.info("Não há partidas de fase de grupos para a edição selecionada.")
    else:
        st.markdown(
            render_group_cards(group_tables_df, group_fixtures_df),
            unsafe_allow_html=True,
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

elif selected_section == "Resumo histórico":
    render_overview(overview_df)

elif selected_section == "Campeãs":
    render_champions(champions_df)

elif selected_section == "Artilheiros":
    render_top_scorers(
        build_top_scorers(
            player_summary_df,
            selected_edition,
            limit=top_limit,
        )
    )

elif selected_section == "Assistentes":
    render_assists()

elif selected_section == "Próxima Copa":
    render_next_world_cup_plan()
