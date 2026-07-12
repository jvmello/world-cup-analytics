from __future__ import annotations

from thestatsapi.wikipedia_jerseys import (
    build_candidates,
    load_missing_curation,
    missing_csv,
    normalize_name,
    parse_wikipedia_squads,
    python_snippet,
)


def test_wikipedia_squad_parser_extracts_numbered_players() -> None:
    html = """
    <html><body>
      <h2>Grupo I</h2>
      <h3>Noruega</h3>
      <table class="wikitable">
        <tbody>
          <tr><th>No.</th><th>Pos.</th><th>Jogador</th><th>Idade</th><th>Jogos</th><th>Gols</th><th>Clube</th></tr>
          <tr><td>9</td><td>A</td><td>Erling Haaland</td><td>25 anos</td><td>50</td><td>40</td><td>Manchester City</td></tr>
          <tr><td>30</td><td>M</td><td>Fora da Copa</td><td>25 anos</td><td>0</td><td>0</td><td>Clube</td></tr>
        </tbody>
      </table>
      <h3>Senegal</h3>
      <table class="wikitable">
        <tr><th>No.</th><th>Pos.</th><th>Jogador</th><th>Idade</th><th>Jogos</th><th>Gols</th><th>Clube</th></tr>
        <tr><td>16</td><td>GR</td><td>Edouard Mendy (capitão)</td><td>34</td><td>60</td><td>0</td><td>Clube</td></tr>
      </table>
    </body></html>
    """

    rows = parse_wikipedia_squads(html)

    assert [(row.team_pt, row.team_name, row.jersey_number, row.player_name) for row in rows] == [
        ("Noruega", "Norway", 9, "Erling Haaland"),
        ("Senegal", "Senegal", 16, "Edouard Mendy"),
    ]


def test_wikipedia_parser_extracts_mediawiki_transclusion_rows() -> None:
    html = """
    <h3 id="Noruega">Noruega</h3>
    <table data-mw='{"parts":[
      {"template":{"target":{"wt":"nat fs g start"},"params":{}}},
      {"template":{"target":{"wt":"nat fs g player"},"params":{
        "no":{"wt":"9"},"pos":{"wt":"FW"},"name":{"wt":"[[Erling Haaland]]"}
      }}},
      {"template":{"target":{"wt":"nat fs g player"},"params":{
        "no":{"wt":"10"},"pos":{"wt":"MF"},"name":{"wt":"[[Martin Ødegaard]] ({{Capitão}})"}
      }}}
    ]}'></table>
    """

    rows = parse_wikipedia_squads(html)

    assert [(row.jersey_number, row.position, row.player_name) for row in rows] == [
        (9, "FW", "Erling Haaland"),
        (10, "MF", "Martin Ødegaard"),
    ]


def test_wikipedia_parser_ignores_non_squad_tables() -> None:
    html = """
    <h3>Noruega</h3>
    <table class="wikitable">
      <tr><th>No.</th><th>Pos.</th><th>Jogador</th></tr>
      <tr><td>9</td><td>FW</td><td>Erling Haaland</td></tr>
    </table>
    <h3>Treinadores por país</h3>
    <table class="wikitable">
      <tr><th>No.</th><th>País</th><th>Treinador</th></tr>
      <tr><td>1</td><td>Bélgica</td><td>Hugo Broos</td></tr>
    </table>
    """

    rows = parse_wikipedia_squads(html)

    assert [(row.team_pt, row.jersey_number, row.player_name) for row in rows] == [
        ("Noruega", 9, "Erling Haaland")
    ]


def test_wikipedia_candidates_match_local_bronze_names() -> None:
    rows = parse_wikipedia_squads(
        """
        <h3>Noruega</h3>
        <table class="wikitable">
          <tr><th>No.</th><th>Pos.</th><th>Jogador</th></tr>
          <tr><td>8</td><td>M</td><td>Martin Ødegaard</td></tr>
        </table>
        <h3>Senegal</h3>
        <table class="wikitable">
          <tr><th>No.</th><th>Pos.</th><th>Jogador</th></tr>
          <tr><td>16</td><td>GR</td><td>Edouard Mendy</td></tr>
        </table>
        """
    )
    local_index = {
        (normalize_name("Norway"), normalize_name("Martin Odegaard")): [
            {"player_id": "pl_odegaard", "player_name": "Martin Ødegaard", "team_name": "Norway"}
        ],
        (normalize_name("Senegal"), normalize_name("Edouard Mendy")): [
            {"player_id": "pl_mendy", "player_name": "Edouard Mendy", "team_name": "Senegal"}
        ],
    }

    candidates = build_candidates(rows, local_index)

    assert candidates["matched_count"] == 2
    assert candidates["unmatched_count"] == 0
    assert {item["player_id"]: item["jersey_number"] for item in candidates["matched"]} == {
        "pl_odegaard": 8,
        "pl_mendy": 16,
    }


def test_wikipedia_candidates_match_usa_and_uruguay_aliases() -> None:
    rows = parse_wikipedia_squads(
        """
        <h3>Estados Unidos</h3>
        <table class="wikitable">
          <tr><th>No.</th><th>Pos.</th><th>Jogador</th></tr>
          <tr><td>16</td><td>DF</td><td>Alex Freeman</td></tr>
          <tr><td>24</td><td>GK</td><td>Matt Freese</td></tr>
          <tr><td>26</td><td>FW</td><td>Alejandro Zendejas</td></tr>
        </table>
        <h3>Uruguai</h3>
        <table class="wikitable">
          <tr><th>No.</th><th>Pos.</th><th>Jogador</th></tr>
          <tr><td>2</td><td>DF</td><td>José Giménez</td></tr>
        </table>
        """
    )
    local_index = {
        (normalize_name("USA"), normalize_name("Alexander Freeman")): [
            {"player_id": "pl_freeman", "player_name": "Alexander Freeman", "team_name": "USA"}
        ],
        (normalize_name("USA"), normalize_name("Matthew Freese")): [
            {"player_id": "pl_freese", "player_name": "Matthew Freese", "team_name": "USA"}
        ],
        (normalize_name("USA"), normalize_name("Alex Zendejas")): [
            {"player_id": "pl_zendejas", "player_name": "Alex Zendejas", "team_name": "USA"}
        ],
        (normalize_name("Uruguay"), normalize_name("José María Giménez")): [
            {"player_id": "pl_gimenez", "player_name": "José María Giménez", "team_name": "Uruguay"}
        ],
    }

    candidates = build_candidates(rows, local_index)

    assert candidates["matched_count"] == 4
    assert candidates["unmatched_count"] == 0
    assert {item["player_id"]: item["jersey_number"] for item in candidates["matched"]} == {
        "pl_freeman": 16,
        "pl_freese": 24,
        "pl_zendejas": 26,
        "pl_gimenez": 2,
    }


def test_missing_csv_lists_unmatched_players_with_numbers() -> None:
    candidates = {
        "unmatched": [
            {
                "team_pt": "Senegal",
                "team_name": "Senegal",
                "jersey_number": 16,
                "player_name": "Edouard Mendy",
                "position": "GR",
                "reason": "player_not_found",
            }
        ]
    }

    output = missing_csv(candidates)

    assert "selecao,numero_wikipedia,player_id_curado,posicao,jogador_wikipedia,motivo,observacao" in output
    assert "Senegal,16,,GR,Edouard Mendy,player_not_found," in output


def test_missing_csv_preserves_manual_curation_values(tmp_path) -> None:
    curation_path = tmp_path / "unmatched.csv"
    curation_path.write_text(
        "\n".join(
            [
                "selecao,numero_wikipedia,player_id_curado,posicao,jogador_wikipedia,motivo,observacao",
                "Senegal,16,pl_mendy_manual,GR,Edouard Mendy,player_not_found,grafia conferida",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    curations = load_missing_curation(curation_path)
    candidates = {
        "unmatched": [
            {
                "team_pt": "Senegal",
                "team_name": "Senegal",
                "jersey_number": 16,
                "player_name": "Edouard Mendy",
                "position": "GR",
                "reason": "player_not_found",
            }
        ]
    }

    output = missing_csv(candidates, curations)
    snippet = python_snippet(candidates, curations)

    assert "Senegal,16,pl_mendy_manual,GR,Edouard Mendy,player_not_found,grafia conferida" in output
    assert "'pl_mendy_manual': 16,  # Edouard Mendy (Senegal)" in snippet


def test_legacy_missing_markdown_can_still_be_read(tmp_path) -> None:
    curation_path = tmp_path / "unmatched.md"
    curation_path.write_text(
        """
# Camisas pendentes de curadoria

## Senegal

| Nº Wikipedia | player_id curado | Pos. | Jogador na Wikipedia | Motivo | Observação |
| ---: | --- | --- | --- | --- | --- |
| 16 | pl_mendy_manual | GR | Edouard Mendy | player_not_found | grafia conferida |
""",
        encoding="utf-8",
    )

    curations = load_missing_curation(curation_path)

    assert curations["senegal|edouard mendy|16"]["curated_player_id"] == "pl_mendy_manual"
