"""Build manual jersey-number candidates from the Wikipedia squad page.

This is a curation helper, not a runtime source. The public app only trusts
`webapp.jersey_overrides.JERSEY_NUMBER_OVERRIDES`; this script creates a review
artifact that can be copied into that dictionary after manual checking.
"""

from __future__ import annotations

import argparse
import csv
import html
import io
import json
import re
import unicodedata
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen


DEFAULT_URL = (
    "https://pt.wikipedia.org/wiki/"
    "Convoca%C3%A7%C3%B5es_para_a_Copa_do_Mundo_FIFA_de_2026"
)
DEFAULT_OUTPUT = Path("data/admin/jersey_curation/wikipedia_2026_candidates.json")
DEFAULT_MISSING_OUTPUT = Path("data/admin/jersey_curation/wikipedia_2026_unmatched.csv")
LEGACY_MISSING_OUTPUT = Path("data/admin/jersey_curation/wikipedia_2026_unmatched.md")
CSV_FIELDNAMES = [
    "selecao",
    "numero_wikipedia",
    "player_id_curado",
    "posicao",
    "jogador_wikipedia",
    "motivo",
    "observacao",
]
NON_SQUAD_HEADINGS = {"Idade", "Jogadores de campo", "Goleiros", "Capitães", "Treinadores por país"}

PT_TEAM_TO_SOURCE = {
    "África do Sul": "South Africa",
    "Alemanha": "Germany",
    "Arábia Saudita": "Saudi Arabia",
    "Argélia": "Algeria",
    "Argentina": "Argentina",
    "Austrália": "Australia",
    "Áustria": "Austria",
    "Bélgica": "Belgium",
    "Bósnia e Herzegovina": "Bosnia & Herzegovina",
    "Brasil": "Brazil",
    "Cabo Verde": "Cape Verde",
    "Canadá": "Canada",
    "Catar": "Qatar",
    "Colômbia": "Colombia",
    "Coreia do Sul": "South Korea",
    "Costa do Marfim": "Côte d'Ivoire",
    "Croácia": "Croatia",
    "Curaçau": "Curacao",
    "Egito": "Egypt",
    "Equador": "Ecuador",
    "Escócia": "Scotland",
    "Espanha": "Spain",
    "Estados Unidos": "USA",
    "França": "France",
    "Gana": "Ghana",
    "Haiti": "Haiti",
    "Inglaterra": "England",
    "Irã": "Iran",
    "Iraque": "Iraq",
    "Japão": "Japan",
    "Jordânia": "Jordan",
    "Marrocos": "Morocco",
    "México": "Mexico",
    "Noruega": "Norway",
    "Nova Zelândia": "New Zealand",
    "Países Baixos": "Netherlands",
    "Panamá": "Panama",
    "Paraguai": "Paraguay",
    "Portugal": "Portugal",
    "RD Congo": "DR Congo",
    "República Checa": "Czechia",
    "Senegal": "Senegal",
    "Suécia": "Sweden",
    "Suíça": "Switzerland",
    "Tunísia": "Tunisia",
    "Turquia": "Türkiye",
    "Uruguai": "Uruguay",
    "Uzbequistão": "Uzbekistan",
}


PLAYER_NAME_ALIASES = {
    ("USA", "Alex Freeman"): "Alexander Freeman",
    ("USA", "Matt Freese"): "Matthew Freese",
    ("USA", "Alejandro Zendejas"): "Alex Zendejas",
    ("Uruguay", "José Giménez"): "José María Giménez",
}


@dataclass(frozen=True)
class WikipediaSquadRow:
    team_pt: str
    team_name: str | None
    jersey_number: int
    player_name: str
    position: str | None = None


class SquadTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.current_team: str | None = None
        self._heading_level: str | None = None
        self._heading_parts: list[str] = []
        self._in_table = False
        self._table_depth = 0
        self._in_row = False
        self._in_cell = False
        self._cell_parts: list[str] = []
        self._row_cells: list[str] = []
        self.rows: list[WikipediaSquadRow] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if tag in {"h2", "h3"}:
            self._heading_level = tag
            self._heading_parts = []
            return
        if tag == "table" and self.current_team and attrs_dict.get("data-mw"):
            self._append_transclusion_rows(attrs_dict["data-mw"] or "")
        if tag == "table" and self.current_team and "wikitable" in (attrs_dict.get("class") or ""):
            self._in_table = True
            self._table_depth = 1
            return
        if self._in_table and tag == "table":
            self._table_depth += 1
        if self._in_table and tag == "tr":
            self._in_row = True
            self._row_cells = []
        if self._in_table and tag in {"td", "th"}:
            self._in_cell = True
            self._cell_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag == self._heading_level:
            heading = clean_cell(" ".join(self._heading_parts))
            self._heading_level = None
            self._heading_parts = []
            if tag == "h2" and heading.startswith(("Grupo ", "Estat")):
                self.current_team = None
                return
            if tag == "h3" and heading and heading not in NON_SQUAD_HEADINGS:
                self.current_team = heading
            elif tag == "h3":
                self.current_team = None
            return
        if self._in_cell and tag in {"td", "th"}:
            self._row_cells.append(clean_cell(" ".join(self._cell_parts)))
            self._in_cell = False
            self._cell_parts = []
        if self._in_table and self._in_row and tag == "tr":
            self._append_row(self._row_cells)
            self._in_row = False
            self._row_cells = []
        if self._in_table and tag == "table":
            self._table_depth -= 1
            if self._table_depth <= 0:
                self._in_table = False

    def handle_data(self, data: str) -> None:
        if self._heading_level:
            self._heading_parts.append(data)
        if self._in_cell:
            self._cell_parts.append(data)

    def _append_row(self, cells: list[str]) -> None:
        if not self.current_team or len(cells) < 3:
            return
        jersey = parse_int(cells[0])
        if jersey is None or not 1 <= jersey <= 26:
            return
        position = cells[1] or None
        player = clean_player_name(cells[2])
        if not player or player.lower() == "jogador":
            return
        self.rows.append(
            WikipediaSquadRow(
                team_pt=self.current_team,
                team_name=PT_TEAM_TO_SOURCE.get(self.current_team),
                jersey_number=jersey,
                player_name=player,
                position=position,
            )
        )

    def _append_transclusion_rows(self, data_mw: str) -> None:
        try:
            payload = json.loads(html.unescape(data_mw))
        except json.JSONDecodeError:
            return
        for part in payload.get("parts", []):
            template = part.get("template") if isinstance(part, dict) else None
            if not isinstance(template, dict):
                continue
            target = (template.get("target") or {}).get("wt")
            if str(target or "").casefold() != "nat fs g player":
                continue
            params = template.get("params") if isinstance(template.get("params"), dict) else {}
            jersey = parse_int((params.get("no") or {}).get("wt"))
            if jersey is None or not 1 <= jersey <= 26:
                continue
            player = clean_player_name(wiki_text((params.get("name") or {}).get("wt") or ""))
            if not player:
                continue
            self.rows.append(
                WikipediaSquadRow(
                    team_pt=self.current_team or "",
                    team_name=PT_TEAM_TO_SOURCE.get(self.current_team or ""),
                    jersey_number=jersey,
                    player_name=player,
                    position=wiki_text((params.get("pos") or {}).get("wt") or "") or None,
                )
            )


def parse_int(value: Any) -> int | None:
    match = re.search(r"\d+", str(value or ""))
    return int(match.group(0)) if match else None


def clean_cell(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()


def clean_player_name(value: str) -> str:
    value = re.sub(r"\([^)]*\)", "", value)
    value = re.sub(r"\[[^\]]*\]", "", value)
    return clean_cell(value)


def wiki_text(value: str) -> str:
    value = re.sub(r"\{\{[^{}]*\}\}", "", value or "")
    value = re.sub(r"\[\[([^|\]]+)\|([^\]]+)\]\]", r"\2", value)
    value = re.sub(r"\[\[([^\]]+)\]\]", r"\1", value)
    return clean_cell(value)


def normalize_name(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value or "")
    ascii_text = "".join(char for char in decomposed if not unicodedata.combining(char))
    ascii_text = ascii_text.replace("ø", "o").replace("Ø", "O").replace("ð", "d").replace("Ð", "D")
    ascii_text = re.sub(r"[^a-zA-Z0-9 ]+", " ", ascii_text)
    return re.sub(r"\s+", " ", ascii_text).strip().casefold()


def fetch_html(url: str) -> str:
    request = Request(url, headers={"User-Agent": "world-cup-analytics/jersey-curation"})
    with urlopen(request, timeout=30) as response:  # noqa: S310 - explicit curation helper URL
        return response.read().decode("utf-8", errors="replace")


def parse_wikipedia_squads(html: str) -> list[WikipediaSquadRow]:
    parser = SquadTableParser()
    parser.feed(html)
    return parser.rows


def local_players(data_root: Path, year: int) -> dict[tuple[str, str], list[dict[str, Any]]]:
    players: dict[tuple[str, str], dict[str, Any]] = {}
    base = data_root / "bronze/thestatsapi/world_cup" / str(year) / "matches"
    for path in sorted(base.glob("match_id=*/lineups/response.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        data = payload.get("data") if isinstance(payload, dict) else {}
        if not isinstance(data, dict):
            continue
        for side in ("home", "away"):
            team = data.get(side) if isinstance(data.get(side), dict) else {}
            team_name = str(team.get("name") or "")
            for group in ("starting_xi", "substitutes"):
                for entry in team.get(group) or []:
                    if not isinstance(entry, dict):
                        continue
                    player_id = entry.get("id")
                    name = entry.get("name")
                    if not player_id or not name or not team_name:
                        continue
                    key = (normalize_name(team_name), normalize_name(str(name)))
                    players.setdefault(key, {
                        "player_id": player_id,
                        "player_name": name,
                        "team_name": team_name,
                    })
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for key, value in players.items():
        grouped.setdefault(key, []).append(value)
    return grouped


def build_candidates(rows: list[WikipediaSquadRow], player_index: dict[tuple[str, str], list[dict[str, Any]]]) -> dict[str, Any]:
    matched: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    for row in rows:
        if not row.team_name:
            unmatched.append({**asdict(row), "reason": "team_mapping_missing"})
            continue
        lookup_names = [row.player_name]
        alias = PLAYER_NAME_ALIASES.get((row.team_name, row.player_name))
        if alias and alias not in lookup_names:
            lookup_names.append(alias)
        matches: list[dict[str, Any]] = []
        for lookup_name in lookup_names:
            key = (normalize_name(row.team_name), normalize_name(lookup_name))
            matches = player_index.get(key, [])
            if matches:
                break
        record = asdict(row)
        if len(matches) == 1:
            matched.append({**record, **matches[0]})
        elif len(matches) > 1:
            conflicts.append({**record, "matches": matches})
        else:
            unmatched.append({**record, "reason": "player_not_found"})
    return {
        "source": DEFAULT_URL,
        "source_license": "Wikipedia content is available under CC BY-SA; manually review before copying into project curation.",
        "matched_count": len(matched),
        "unmatched_count": len(unmatched),
        "conflict_count": len(conflicts),
        "matched": sorted(matched, key=lambda item: (item["team_name"], item["jersey_number"], item["player_name"])),
        "unmatched": sorted(unmatched, key=lambda item: (str(item.get("team_pt")), item["jersey_number"], item["player_name"])),
        "conflicts": conflicts,
    }


def curation_key(team: str | None, player_name: str | None, jersey_number: Any) -> str:
    return "|".join(
        [
            normalize_name(str(team or "")),
            normalize_name(str(player_name or "")),
            str(parse_int(jersey_number) or ""),
        ]
    )


def clean_manual_value(value: str) -> str:
    value = value.strip().strip("`").strip()
    return "" if value in {"", "-"} else value


def load_csv_curation(path: Path) -> dict[str, dict[str, Any]]:
    curations: dict[str, dict[str, Any]] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            team = clean_manual_value(row.get("selecao") or "")
            wiki_number = parse_int(row.get("numero_wikipedia"))
            player_name = clean_manual_value(row.get("jogador_wikipedia") or "")
            record = {
                "wiki_number": wiki_number,
                "curated_player_id": clean_manual_value(row.get("player_id_curado") or ""),
                "note": clean_manual_value(row.get("observacao") or ""),
            }
            if team and wiki_number is not None and player_name and (record["curated_player_id"] or record["note"]):
                curations[curation_key(team, player_name, wiki_number)] = record
    return curations


def load_markdown_curation(path: Path) -> dict[str, dict[str, Any]]:
    current_team: str | None = None
    curations: dict[str, dict[str, Any]] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("## "):
            current_team = line[3:].strip()
            continue
        if not current_team or not line.startswith("|") or line.startswith("| ---"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if not cells or cells[0].casefold().startswith("nº"):
            continue
        if len(cells) >= 7:
            wiki_number = parse_int(cells[0])
            player_name = clean_manual_value(cells[4])
            record = {
                "wiki_number": wiki_number,
                "curated_player_id": clean_manual_value(cells[2]),
                "note": clean_manual_value(cells[6]),
            }
        elif len(cells) >= 6:
            wiki_number = parse_int(cells[0])
            player_name = clean_manual_value(cells[3])
            record = {
                "wiki_number": wiki_number,
                "curated_player_id": clean_manual_value(cells[1]),
                "note": clean_manual_value(cells[5]),
            }
        elif len(cells) >= 4:
            wiki_number = parse_int(cells[0])
            player_name = clean_manual_value(cells[2])
            record = {
                "wiki_number": wiki_number,
                "curated_player_id": "",
                "note": "",
            }
        else:
            continue
        if wiki_number is None or not player_name:
            continue
        if record["curated_player_id"] or record["note"]:
            curations[curation_key(current_team, player_name, wiki_number)] = record
    return curations


def load_missing_curation(path: Path) -> dict[str, dict[str, Any]]:
    if path.exists():
        if path.suffix.casefold() == ".csv":
            return load_csv_curation(path)
        return load_markdown_curation(path)
    if path == DEFAULT_MISSING_OUTPUT and LEGACY_MISSING_OUTPUT.exists():
        return load_markdown_curation(LEGACY_MISSING_OUTPUT)
    return {}


def manual_override_records(
    candidates: dict[str, Any],
    curations: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    if not curations:
        return []
    records: list[dict[str, Any]] = []
    for item in candidates.get("unmatched", []):
        key = curation_key(item.get("team_pt") or item.get("team_name"), item.get("player_name"), item.get("jersey_number"))
        curation = curations.get(key)
        if not curation or not curation.get("curated_player_id"):
            continue
        records.append(
            {
                "player_id": curation["curated_player_id"],
                "jersey_number": item.get("jersey_number"),
                "player_name": item.get("player_name"),
                "team_name": item.get("team_name") or item.get("team_pt"),
            }
        )
    return records


def python_snippet(
    candidates: dict[str, Any],
    curations: dict[str, dict[str, Any]] | None = None,
) -> str:
    lines = [
        "# Review before copying into webapp/jersey_overrides.py.",
        "# Source: Wikipedia squads page, CC BY-SA.",
    ]
    records = list(candidates.get("matched", [])) + manual_override_records(candidates, curations)
    for item in sorted(records, key=lambda record: (str(record.get("team_name")), str(record.get("player_name")))):
        lines.append(
            f"    {item['player_id']!r}: {int(item['jersey_number'])},"
            f"  # {item['player_name']} ({item['team_name']})"
        )
    return "\n".join(lines) + "\n"


def markdown_cell(value: Any) -> str:
    return str(value or "").replace("|", "\\|").strip()


def missing_rows(
    candidates: dict[str, Any],
    curations: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in sorted(
        candidates.get("unmatched", []),
        key=lambda record: (
            str(record.get("team_pt") or record.get("team_name")),
            int(record.get("jersey_number") or 999),
            str(record.get("player_name") or ""),
        ),
    ):
        team = str(item.get("team_pt") or item.get("team_name") or "Seleção não mapeada")
        key = curation_key(team, item.get("player_name"), item.get("jersey_number"))
        curation = (curations or {}).get(key, {})
        rows.append(
            {
                "selecao": team,
                "numero_wikipedia": int(item.get("jersey_number") or 0),
                "player_id_curado": curation.get("curated_player_id") or "",
                "posicao": item.get("position") or "",
                "jogador_wikipedia": item.get("player_name") or "",
                "motivo": item.get("reason") or "",
                "observacao": curation.get("note") or "",
            }
        )
    return rows


def missing_csv(
    candidates: dict[str, Any],
    curations: dict[str, dict[str, Any]] | None = None,
) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_FIELDNAMES, lineterminator="\n")
    writer.writeheader()
    writer.writerows(missing_rows(candidates, curations))
    return buffer.getvalue()


def missing_markdown(
    candidates: dict[str, Any],
    curations: dict[str, dict[str, Any]] | None = None,
) -> str:
    unmatched = candidates.get("unmatched", [])
    lines = [
        "# Camisas pendentes de curadoria",
        "",
        "Fonte: Wikipedia - Convocações para a Copa do Mundo FIFA de 2026.",
        "",
        "Estes jogadores aparecem com número na página de convocações, mas não foram",
        "casados automaticamente com um `player_id` local da TheStatsAPI. Revise nome,",
        "seleção e possível grafia alternativa antes de copiar para `webapp/jersey_overrides.py`.",
        "",
        "Preencha apenas `player_id curado` quando souber o id local. O número usado",
        "será sempre o `Nº Wikipedia` desta linha.",
        "",
        f"Total pendente: {len(unmatched)}",
        "",
    ]
    by_team: dict[str, list[dict[str, Any]]] = {}
    for item in missing_rows(candidates, curations):
        by_team.setdefault(str(item["selecao"]), []).append(item)
    for team in sorted(by_team):
        lines.extend(
            [
                f"## {team}",
                "",
                "| Nº Wikipedia | player_id curado | Pos. | Jogador na Wikipedia | Motivo | Observação |",
                "| ---: | --- | --- | --- | --- | --- |",
            ]
        )
        rows = sorted(by_team[team], key=lambda item: (int(item.get("numero_wikipedia") or 999), str(item.get("jogador_wikipedia") or "")))
        for item in rows:
            lines.append(
                f"| {int(item.get('numero_wikipedia') or 0)} "
                f"| {markdown_cell(item.get('player_id_curado'))} "
                f"| {item.get('posicao') or ''} "
                f"| {markdown_cell(item.get('jogador_wikipedia'))} "
                f"| {item.get('motivo') or ''} "
                f"| {markdown_cell(item.get('observacao'))} |"
            )
        lines.append("")
    return "\n".join(lines) + "\n"


def missing_artifact(
    candidates: dict[str, Any],
    curations: dict[str, dict[str, Any]] | None,
    output_path: Path,
) -> str:
    if output_path.suffix.casefold() == ".csv":
        return missing_csv(candidates, curations)
    return missing_markdown(candidates, curations)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--html-file", type=Path, help="Use a local HTML snapshot instead of downloading.")
    parser.add_argument("--data-root", type=Path, default=Path("data"))
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--snippet-output", type=Path, help="Optional Python snippet for manual review.")
    parser.add_argument("--missing-output", type=Path, default=DEFAULT_MISSING_OUTPUT)
    parser.add_argument(
        "--curation-input",
        type=Path,
        default=DEFAULT_MISSING_OUTPUT,
        help="Existing unmatched markdown with manual player_id/number edits to preserve and apply.",
    )
    args = parser.parse_args(argv)

    html = args.html_file.read_text(encoding="utf-8") if args.html_file else fetch_html(args.url)
    rows = parse_wikipedia_squads(html)
    candidates = build_candidates(rows, local_players(args.data_root, args.year))
    curations = load_missing_curation(args.curation_input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(candidates, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.snippet_output:
        args.snippet_output.parent.mkdir(parents=True, exist_ok=True)
        args.snippet_output.write_text(python_snippet(candidates, curations), encoding="utf-8")
    if args.missing_output:
        args.missing_output.parent.mkdir(parents=True, exist_ok=True)
        args.missing_output.write_text(missing_artifact(candidates, curations, args.missing_output), encoding="utf-8")
    print(
        f"wrote {args.output} "
        f"({candidates['matched_count']} matched, {candidates['unmatched_count']} unmatched, "
        f"{candidates['conflict_count']} conflicts)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
