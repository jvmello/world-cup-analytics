from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

from .extractor import PdfExtractor
from .models import ExtractedDocument
from .pipeline import FifaPdfPipeline


PRODUCT_NAMES = (
    "aerial_control_summary",
    "attempts_at_goal_details",
    "attempts_at_goal_summary",
    "crosses_open_play_players",
    "crosses_open_play_summary",
    "data_dictionary",
    "defensive_actions_summary",
    "defensive_pressure_summary",
    "extraction_notes",
    "goal_prevention_summary",
    "goalkeeping_distribution_summary",
    "goalkeeping_involvement",
    "individual_in_possession_distribution",
    "individual_offers_receptions",
    "individual_out_of_possession",
    "line_breaks_players",
    "line_breaks_summary",
    "line_height_team_length",
    "lineups_players",
    "match_info",
    "movement_to_receive_by_phase",
    "movement_to_receive_by_pitch_third",
    "movement_to_receive_top_players",
    "offers_summary",
    "passing_network_edges",
    "passing_network_matrix",
    "passing_network_top5",
    "phases_of_play",
    "physical_data",
    "set_plays_summary",
    "team_key_statistics",
)

BASE_DESCRIPTIONS = {
    "year": ("integer", "Edição da Copa."),
    "match_number": ("integer", "Número oficial da partida na edição."),
    "match_id": ("string", "Identificador esportivo canônico da partida."),
    "team_name": ("string", "Seleção associada ao registro."),
    "player_name": ("string", "Nome do jogador."),
    "shirt_number": ("integer", "Número da camisa."),
    "metric_name": ("string", "Nome canônico da métrica."),
    "value": ("number", "Valor normalizado."),
    "unit": ("string", "Unidade da métrica."),
    "raw_value": ("string", "Valor textual preservado quando necessário."),
    "record_number": ("integer", "Ordem do registro dentro da seção."),
    "text": ("string", "Linha temática extraída e limpa."),
    "attempt_id": ("string", "Identificador determinístico da tentativa."),
    "group_name": ("string", "Grupo da competição."),
    "match_date": ("date", "Data oficial da partida no padrão ISO."),
    "kickoff_time": ("time", "Horário informado para o início da partida."),
    "stadium": ("string", "Estádio informado no relatório."),
    "home_team": ("string", "Seleção mandante."),
    "away_team": ("string", "Seleção visitante."),
    "home_score": ("integer", "Gols da seleção mandante."),
    "away_score": ("integer", "Gols da seleção visitante."),
    "minute": ("integer", "Minuto da ocorrência."),
    "outcome": ("string", "Desfecho da tentativa."),
    "outcome_group": ("string", "Categoria consolidada do desfecho."),
    "body_part": ("string", "Parte do corpo usada na tentativa."),
    "delivery_type": ("string", "Origem ou tipo da jogada."),
    "attempts": ("integer", "Quantidade de tentativas."),
    "page_number": ("integer", "Página relacionada à nota de extração."),
    "severity": ("string", "Severidade da nota de extração."),
    "note_type": ("string", "Tipo da nota de extração."),
    "message": ("string", "Descrição da nota de extração."),
    "passer_name": ("string", "Jogador que realizou o passe."),
    "recipient_name": ("string", "Jogador que recebeu o passe."),
    "passes": ("integer", "Quantidade de passes na conexão."),
    "rank": ("integer", "Posição no ranking."),
    "share_of_team_passes_pct": (
        "number",
        "Participação percentual da conexão no volume do time.",
    ),
    "recipient_order": (
        "json",
        "Lista ordenada de receptores usada pela matriz.",
    ),
    "pass_counts": ("json", "Vetor de contagens alinhado a recipient_order."),
    "possession_state": ("string", "Estado com ou sem posse."),
    "phase_name": ("string", "Nome da fase de jogo."),
    "percentage": ("number", "Percentual atribuído à fase."),
}


@dataclass(frozen=True)
class PublicationResult:
    path: Path
    status: str
    version: int


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _clean(value: Any) -> Any:
    if value is None:
        return ""
    return str(value).replace("\x00", "").strip()


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _clean(row.get(field)) for field in fields})


def _team_from_text(text: str, teams: tuple[str, str]) -> str:
    for team in teams:
        if re.search(rf"\b{re.escape(team)}\b", text, re.I):
            return team
    return ""


def _content_lines(page_text: str) -> list[str]:
    lines = [
        re.sub(r"\s+", " ", line.replace("\x00", "ff")).strip()
        for line in page_text.splitlines()
        if line.strip()
    ]
    return [
        line
        for line in lines
        if not re.match(
            r"^\d{1,2} June 2026 - .* - \d{2}:\d{2}$",
            line,
        )
    ]


def _page_title(page_text: str) -> str:
    lines = _content_lines(page_text)
    return lines[0] if lines else ""


def _section_rows(
    pages: Iterable[Any],
    matcher: Any,
    teams: tuple[str, str],
) -> list[dict[str, Any]]:
    rows = []
    for page in pages:
        normalized = page.raw_text.replace("\x00", "ff")
        title = _page_title(normalized)
        if not matcher(title):
            continue
        team = _team_from_text(normalized, teams)
        content = _content_lines(normalized)
        for index, line in enumerate(content[1:], start=1):
            rows.append(
                {
                    "team_name": team,
                    "record_number": index,
                    "text": line,
                }
            )
    return rows


def _pivot_players(
    rows: list[dict[str, object]],
    metric_group: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    selected = [
        row for row in rows if str(row.get("metric_group")) == metric_group
    ]
    players: dict[tuple[str, str, str], dict[str, Any]] = {}
    metrics: set[str] = set()
    for row in selected:
        if str(row.get("player_name", "")).strip().lower() == "june":
            continue
        key = (
            str(row.get("team_name", "")),
            str(row.get("shirt_number", "")),
            str(row.get("player_name", "")),
        )
        target = players.setdefault(
            key,
            {
                "team_name": key[0],
                "shirt_number": key[1],
                "player_name": key[2],
            },
        )
        metric = str(row.get("metric_name", ""))
        metrics.add(metric)
        target[metric] = row.get("value", "")
    metric_fields = sorted(metrics)
    return (
        sorted(
            players.values(),
            key=lambda row: (row["team_name"], int(row["shirt_number"] or 999)),
        ),
        ["team_name", "shirt_number", "player_name", *metric_fields],
    )


def _attempt_summary(rows: list[dict[str, object]]) -> list[dict[str, Any]]:
    counts: dict[tuple[str, str], int] = {}
    for row in rows:
        outcome = str(row.get("outcome", ""))
        lowered = outcome.lower()
        if "goal" in lowered:
            category = "goal"
        elif "on target" in lowered:
            category = "on_target"
        elif "off target" in lowered:
            category = "off_target"
        elif "blocked" in lowered:
            category = "blocked"
        else:
            category = "incomplete"
        key = (str(row.get("team_name", "")), category)
        counts[key] = counts.get(key, 0) + 1
    return [
        {"team_name": team, "outcome_group": group, "attempts": count}
        for (team, group), count in sorted(counts.items())
    ]


def _passing_products(
    document: ExtractedDocument,
    teams: tuple[str, str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    matrix_rows: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    top5: list[dict[str, Any]] = []
    pattern = re.compile(r"^(\d+)\s+(.+?)\s+((?:\d+\s+){7,}\d+)$")
    for page in document.pages:
        if "Passing Networks" not in page.raw_text:
            continue
        team = _team_from_text(page.raw_text, teams)
        parsed = []
        for line in _content_lines(page.raw_text):
            match = pattern.match(line)
            if not match:
                continue
            values = [int(value) for value in match.group(3).split()]
            parsed.append(
                {
                    "shirt_number": int(match.group(1)),
                    "player_name": match.group(2).strip(),
                    "values": values,
                }
            )
        names = [row["player_name"] for row in parsed]
        for sender_index, row in enumerate(parsed):
            values = list(row["values"])
            if len(values) == len(names) - 1:
                values.insert(sender_index, 0)
            matrix_rows.append(
                {
                    "team_name": team,
                    "shirt_number": row["shirt_number"],
                    "player_name": row["player_name"],
                    "recipient_order": json.dumps(names, ensure_ascii=False),
                    "pass_counts": json.dumps(values, ensure_ascii=False),
                }
            )
            for recipient, count in zip(names, values):
                if count <= 0 or recipient == row["player_name"]:
                    continue
                edges.append(
                    {
                        "team_name": team,
                        "passer_name": row["player_name"],
                        "recipient_name": recipient,
                        "passes": count,
                    }
                )
        total = sum(int(row["passes"]) for row in edges if row["team_name"] == team)
        ranked = sorted(
            [row for row in edges if row["team_name"] == team],
            key=lambda row: int(row["passes"]),
            reverse=True,
        )[:5]
        for rank, row in enumerate(ranked, start=1):
            top5.append(
                {
                    **row,
                    "rank": rank,
                    "share_of_team_passes_pct": (
                        round(int(row["passes"]) / total * 100, 2)
                        if total
                        else 0
                    ),
                }
            )
    return matrix_rows, edges, top5


def _dictionary_rows(
    products: dict[str, tuple[list[dict[str, Any]], list[str]]]
) -> list[dict[str, Any]]:
    rows = []
    for product, (_, fields) in sorted(products.items()):
        if product == "data_dictionary":
            continue
        grain = (
            "uma linha temática semiestruturada"
            if fields == ["team_name", "record_number", "text"]
            else "um registro analítico"
        )
        for field in fields:
            logical_type, description = BASE_DESCRIPTIONS.get(
                field,
                (
                    "number",
                    f"Métrica `{field}` normalizada a partir do relatório.",
                ),
            )
            rows.append(
                {
                    "product": product,
                    "grain": grain,
                    "field": field,
                    "logical_type": logical_type,
                    "description": description,
                }
            )
    return rows


def _products(
    document: ExtractedDocument,
    datasets: dict[str, list[dict[str, object]]],
) -> dict[str, tuple[list[dict[str, Any]], list[str]]]:
    match = dict(datasets["match_summary"][0])
    teams = (str(match["home_team"]), str(match["away_team"]))
    products: dict[str, tuple[list[dict[str, Any]], list[str]]] = {}

    products["match_info"] = (
        [
            {
                "year": match["edition"],
                "match_number": match["match_number"],
                "match_id": match["match_id"],
                "group_name": match["group_name"],
                "match_date": match["match_date"],
                "kickoff_time": match["kickoff_time"],
                "stadium": match["stadium"],
                "home_team": match["home_team"],
                "away_team": match["away_team"],
                "home_score": match["home_score"],
                "away_score": match["away_score"],
            }
        ],
        [
            "year",
            "match_number",
            "match_id",
            "group_name",
            "match_date",
            "kickoff_time",
            "stadium",
            "home_team",
            "away_team",
            "home_score",
            "away_score",
        ],
    )
    products["team_key_statistics"] = (
        [
            {
                key: row.get(key, "")
                for key in ("team_name", "metric_name", "value", "unit")
            }
            for row in datasets["team_key_statistics"]
        ],
        ["team_name", "metric_name", "value", "unit"],
    )
    products["phases_of_play"] = (
        [
            {
                key: row.get(key, "")
                for key in (
                    "team_name",
                    "possession_state",
                    "phase_name",
                    "percentage",
                )
            }
            for row in datasets["phases_of_play"]
        ],
        ["team_name", "possession_state", "phase_name", "percentage"],
    )
    attempt_fields = [
        "attempt_id",
        "team_name",
        "minute",
        "shirt_number",
        "player_name",
        "outcome",
        "body_part",
        "delivery_type",
    ]
    products["attempts_at_goal_details"] = (
        [
            {key: row.get(key, "") for key in attempt_fields}
            for row in datasets["attempts_at_goal"]
        ],
        attempt_fields,
    )
    products["attempts_at_goal_summary"] = (
        _attempt_summary(datasets["attempts_at_goal"]),
        ["team_name", "outcome_group", "attempts"],
    )
    player_groups = {
        "individual_in_possession_distribution": "in_possession_distribution",
        "individual_offers_receptions": "in_possession_offers",
        "individual_out_of_possession": "out_of_possession",
        "physical_data": "physical",
    }
    for product, group in player_groups.items():
        products[product] = _pivot_players(datasets["player_metrics"], group)

    products["extraction_notes"] = (
        [
            {
                "page_number": row.get("page_number", ""),
                "severity": row.get("severity", ""),
                "note_type": row.get("issue_type", ""),
                "message": row.get("message", ""),
                "raw_value": row.get("raw_value", ""),
            }
            for row in datasets["extraction_issues"]
            if str(row.get("severity", "")) != "info"
        ],
        ["page_number", "severity", "note_type", "message", "raw_value"],
    )

    section_rules = {
        "lineups_players": lambda title: title == "Match Summary - Teams",
        "line_height_team_length": lambda title: (
            title.startswith("In Possession Line Height & Team Length")
            or title.startswith("Defensive Line Height & Team Length")
        ),
        "line_breaks_summary": lambda title: title == "Line Breaks",
        "line_breaks_players": lambda title: (
            title.startswith("Line Breaks ") and title != "Line Breaks"
        ),
        "crosses_open_play_players": lambda title: title.startswith(
            "Crosses (Open Play)"
        ),
        "crosses_open_play_summary": lambda title: title.startswith(
            "Crosses (Open Play)"
        ),
        "offers_summary": lambda title: title.startswith("Offering to Receive"),
        "movement_to_receive_by_phase": lambda title: title.startswith(
            "Movement to Receive"
        ),
        "movement_to_receive_by_pitch_third": lambda title: title.startswith(
            "Movement to Receive"
        ),
        "movement_to_receive_top_players": lambda title: title.startswith(
            "Movement to Receive"
        ),
        "defensive_actions_summary": lambda title: title.startswith(
            "Defensive Actions"
        ),
        "defensive_pressure_summary": lambda title: title == "Defensive Pressure",
        "goalkeeping_involvement": lambda title: title
        == "Goalkeeping Involvement",
        "goalkeeping_distribution_summary": lambda title: title.startswith(
            "Goalkeeping Distribution"
        ),
        "goal_prevention_summary": lambda title: title.startswith(
            "Goal Prevention"
        ),
        "aerial_control_summary": lambda title: title.startswith("Aerial Control"),
        "set_plays_summary": lambda title: title.startswith("Set Plays"),
    }
    for name, matcher in section_rules.items():
        products[name] = (
            _section_rows(document.pages, matcher, teams),
            ["team_name", "record_number", "text"],
        )

    matrix, edges, top5 = _passing_products(document, teams)
    products["passing_network_matrix"] = (
        matrix,
        [
            "team_name",
            "shirt_number",
            "player_name",
            "recipient_order",
            "pass_counts",
        ],
    )
    products["passing_network_edges"] = (
        edges,
        ["team_name", "passer_name", "recipient_name", "passes"],
    )
    products["passing_network_top5"] = (
        top5,
        [
            "team_name",
            "rank",
            "passer_name",
            "recipient_name",
            "passes",
            "share_of_team_passes_pct",
        ],
    )

    for name in PRODUCT_NAMES:
        if name == "data_dictionary":
            continue
        products.setdefault(
            name,
            ([], ["team_name", "record_number", "text"]),
        )
    dictionary = _dictionary_rows(products)
    products["data_dictionary"] = (
        dictionary,
        ["product", "grain", "field", "logical_type", "description"],
    )
    return products


def publish_match_pdf(
    *,
    source_file: Path | str,
    edition: int,
    output_root: Path | str = Path("data/parsed/fifa_pdf"),
) -> PublicationResult:
    source = Path(source_file)
    source_hash = _hash(source)
    document = PdfExtractor().extract(source, edition=edition)
    parser = FifaPdfPipeline(
        bronze_dir=Path(tempfile.gettempdir()) / "fifa-pdf-unused-bronze",
        silver_dir=Path(tempfile.gettempdir()) / "fifa-pdf-unused-silver",
    )
    datasets = parser.parse_document(document)
    match = datasets["match_summary"][0]
    match_number = int(match["match_number"])
    target = Path(output_root) / f"year={edition}" / f"match={match_number}"
    manifest_path = target / "_manifest.json"
    previous_version = 0
    if manifest_path.exists():
        previous = json.loads(manifest_path.read_text(encoding="utf-8"))
        previous_version = int(previous.get("version", 0))
        if (
            previous.get("source_hash") == source_hash
            and previous.get("parser_version") == document.parser_version
        ):
            return PublicationResult(target, "unchanged", previous_version)

    products = _products(document, datasets)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=f".match={match_number}-", dir=target.parent)
    )
    try:
        for product, (rows, fields) in products.items():
            _write_csv(temporary / f"{product}.csv", rows, fields)
        version = previous_version + 1
        manifest = {
            "year": edition,
            "match_number": match_number,
            "match_id": match["match_id"],
            "version": version,
            "source_hash": source_hash,
            "parser_version": document.parser_version,
            "published_at": datetime.now(timezone.utc).isoformat(),
            "products": {
                name: {
                    "file": f"{name}.csv",
                    "rows": len(rows),
                }
                for name, (rows, _) in sorted(products.items())
            },
        }
        (temporary / "_manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        if target.exists():
            shutil.rmtree(target)
        temporary.replace(target)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return PublicationResult(target, "published", version)


def publish_directory(
    *,
    input_dir: Path | str,
    edition: int,
    output_root: Path | str = Path("data/parsed/fifa_pdf"),
) -> list[PublicationResult]:
    return [
        publish_match_pdf(
            source_file=path,
            edition=edition,
            output_root=output_root,
        )
        for path in sorted(Path(input_dir).glob("*.pdf"))
    ]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Publish FIFA PDF reports as partitioned match products."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--file", type=Path)
    source.add_argument("--input-dir", type=Path)
    parser.add_argument("--edition", required=True, type=int, choices=(2026,))
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("data/parsed/fifa_pdf"),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    results = (
        [
            publish_match_pdf(
                source_file=args.file,
                edition=args.edition,
                output_root=args.output_root,
            )
        ]
        if args.file
        else publish_directory(
            input_dir=args.input_dir,
            edition=args.edition,
            output_root=args.output_root,
        )
    )
    for result in results:
        print(
            f"FIFA match products: status={result.status} "
            f"version={result.version} path={result.path}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
