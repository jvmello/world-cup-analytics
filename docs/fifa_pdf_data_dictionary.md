# Dicionário de dados — FIFA PDF 2026

Fonte analisada: `data/pdf/PMSR-M07-BRA-V-MAR.pdf`  
Partida: Brasil 1–1 Marrocos, Grupo C, jogo 7, 13 de junho de 2026  
Documento: `9eecf6ac406cdf38836a855d3d0ef2885afe5ec7cf9d140a5f5c60d229adc42f`  
Versão do parser: `1.0.0`

Este dicionário descreve o contrato observado no primeiro PDF. Os CSVs bronze
preservam a fonte; os CSVs silver apresentam entidades e métricas normalizadas.
O catálogo tabular campo a campo está em
[`fifa_pdf_data_dictionary.csv`](fifa_pdf_data_dictionary.csv).

## Perfil da extração

| Dataset | Camada | Grão | Linhas |
|---|---|---|---:|
| `documents` | bronze | um documento PDF | 1 |
| `pages` | bronze | uma página | 52 |
| `raw_tables` | bronze | uma célula de tabela extraída | 2.319 |
| `match_summary` | silver | uma partida por documento | 1 |
| `team_key_statistics` | silver | uma métrica por partida e seleção | 36 |
| `phases_of_play` | silver | uma fase por estado de posse e seleção | 34 |
| `attempts_at_goal` | silver | uma tentativa interpretada | 26 |
| `player_metrics` | silver | uma métrica por jogador e grupo | 1.473 |
| `extraction_issues` | silver | um problema ou aviso de extração | 65 |

## Campos de linhagem compartilhados

Todos os datasets possuem:

| Campo | Significado |
|---|---|
| `document_id` | SHA-256 do PDF; identidade estável do documento. |
| `match_id` | Identificador canônico da partida: `2026-match-7-brazil-morocco`. |
| `source_file` | Nome do PDF de origem. |
| `page_number` | Página física de origem; `0` representa o documento. |
| `confidence` | Confiança do registro, entre 0 e 1. |

`raw_value` sempre representa o valor mais próximo da fonte. `value`,
`percentage` e demais campos tipados são versões normalizadas para análise.

## Bronze

### `documents.csv`

Manifesto do PDF: hash, caminho, edição, versão do parser, status, número de
páginas e metadados do arquivo.

Chave: `document_id`.

### `pages.csv`

Texto integral de cada página e domínio atribuído pelo classificador.

Domínios observados:

| Domínio | Páginas |
|---|---:|
| `cover` | 1 |
| `key_statistics` | 1 |
| `phases_of_play` | 1 |
| `attempts_at_goal` | 6 |
| `player_in_possession` | 4 |
| `player_out_of_possession` | 2 |
| `player_physical` | 2 |
| `unknown` | 34 |
| `blank` | 1 |

`unknown` significa “preservado, mas ainda sem parser de domínio”; não significa
que a página esteja vazia.

Chave: `document_id`, `page_number`.

### `raw_tables.csv`

Representação célula a célula das tabelas detectadas pelo `pdfplumber`.
Coordenadas são base zero para tabela, linha e coluna.

Chave: `document_id`, `page_number`, `table_number`, `row_number`,
`column_number`.

## Silver

### `match_summary.csv`

Metadados canônicos da partida: edição, grupo, número, data, horário, estádio,
seleções, placar e nível de cobertura.

Chave: `document_id`, `match_id`.

### `team_key_statistics.csv`

Formato longo, com uma linha para cada seleção e métrica. O primeiro PDF contém
18 métricas para Brasil e Marrocos:

`attempts_at_goal`, `attempts_on_target`, `ball_progressions`,
`completed_line_breaks`, `crosses`, `defensive_line_breaks`,
`defensive_pressures`, `direct_pressures`, `expected_goals`,
`final_third_receptions`, `forced_turnovers`, `goals`,
`pass_completion_pct`, `passes_complete`, `passes_total`, `second_balls`,
`total_distance_km` e `zone_4_distance_km`.

Chave: `document_id`, `match_id`, `team_name`, `metric_name`.

### `phases_of_play.csv`

Percentual de tempo associado a cada fase de jogo, separado por seleção e estado
de posse.

- Com posse: `attacking_transition`, `build_up_opposed`,
  `build_up_unopposed`, `counter_attack`, `final_third`, `long_ball`,
  `progression`, `set_piece`.
- Sem posse: `counter_press`, `defensive_transition`, `high_block`,
  `high_press`, `low_block`, `low_press`, `mid_block`, `mid_press`,
  `recovery`.

Chave: `document_id`, `match_id`, `team_name`, `possession_state`,
`phase_name`.

### `attempts_at_goal.csv`

Tentativas interpretadas com minuto, camisa, jogador, desfecho, parte do corpo e
origem da entrega. O PDF contém 26 registros aceitos. Dez linhas adicionais
foram preservadas como `attempt_unparsed`.

Chave: `document_id`, `attempt_id`.

### `player_metrics.csv`

Formato longo por jogador. Foram identificados 33 jogadores, 46 métricas e quatro
grupos:

- `in_possession_distribution` — 14 métricas de passe, progressão, cruzamento,
  quebra de linha, drible e finalização.
- `in_possession_offers` — 8 métricas de oferta e movimentação.
- `out_of_possession` — 15 métricas defensivas, pressão, duelos e recuperação.
- `physical` — 9 métricas de distância, corrida, sprint e velocidade.

Unidades observadas: `count`, `percent`, `m`, `km/h`.

Chave: `document_id`, `match_id`, `team_name`, `shirt_number`,
`metric_group`, `metric_name`.

### `extraction_issues.csv`

Registro de qualidade e cobertura do parser. O primeiro PDF gerou:

| Severidade | Linhas |
|---|---:|
| `info` | 34 |
| `warning` | 31 |

| Tipo | Linhas | Interpretação |
|---|---:|---|
| `unsupported_domain` | 34 | Página preservada sem parser especializado. |
| `player_metric_invalid_value` | 14 | Valor mantido em bruto, sem normalização segura. |
| `attempt_unparsed` | 10 | Linha de tentativa não convertida em entidade. |
| `player_metric_column_mismatch` | 6 | Quantidade de colunas diferente do layout esperado. |
| `blank_page` | 1 | Página sem texto extraível. |

Uma issue não invalida automaticamente o documento. Ela explicita quais partes
precisam de revisão ou de um parser futuro.

## Regras de uso

- Use silver para métricas e bronze para auditoria/reprocessamento.
- Não some percentuais ou velocidades máximas entre partidas.
- Ao agregar novos PDFs, agrupe métricas por `match_id` antes de comparar times.
- Trate string vazia como ausência, não como zero.
- Filtre ou sinalize baixa `confidence` em análises publicadas.
- Consulte `extraction_issues` antes de afirmar cobertura completa.

