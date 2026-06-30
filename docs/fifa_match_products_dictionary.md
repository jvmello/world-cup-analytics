# Dicionário dos produtos FIFA por partida

## Organização

Cada PDF processado publica uma partição:

```text
data/parsed/fifa_pdf/
  year=<ano>/
    match=<número>/
      *.csv
      data_dictionary.csv
      _manifest.json
```

Os CSVs contêm somente dados esportivos. `_manifest.json` é técnico e existe
apenas para idempotência, versão do parser e controle de atualização.

O dicionário campo a campo de cada partição é o arquivo
`data_dictionary.csv` contido na própria pasta da partida.

## Produtos normalizados

| Produto | Grão | Conteúdo |
|---|---|---|
| `match_info` | uma partida | Data, grupo, estádio, times e placar. |
| `team_key_statistics` | uma métrica por time | Indicadores oficiais agregados. |
| `phases_of_play` | uma fase por time e estado de posse | Percentuais de fases de jogo. |
| `attempts_at_goal_details` | uma tentativa | Minuto, jogador, desfecho, parte do corpo e origem. |
| `attempts_at_goal_summary` | um desfecho por time | Contagens de gols, no alvo, fora, bloqueadas e incompletas. |
| `individual_in_possession_distribution` | um jogador | Passes, progressões, cruzamentos, quebras de linha e finalizações. |
| `individual_offers_receptions` | um jogador | Ofertas, movimentos e recepções. |
| `individual_out_of_possession` | um jogador | Pressão, duelos, desarmes, interceptações e recuperações. |
| `physical_data` | um jogador | Distância, zonas de velocidade, corridas, sprints e velocidade máxima. |
| `passing_network_matrix` | um passador | Ordem dos receptores e vetor de passes. |
| `passing_network_edges` | uma conexão dirigida | Passador, receptor e número de passes. |
| `passing_network_top5` | uma conexão ranqueada | Cinco conexões mais frequentes de cada time. |
| `extraction_notes` | uma nota acionável | Avisos que exigem revisão; páginas apenas não suportadas não são expostas. |

## Produtos temáticos semiestruturados

Os arquivos abaixo já estão separados por tema, time e ordem do registro. Seu
contrato atual é `team_name`, `record_number`, `text`. Eles preservam a
informação da seção enquanto os parsers posicionais específicos evoluem:

- `aerial_control_summary`
- `crosses_open_play_players`
- `crosses_open_play_summary`
- `defensive_actions_summary`
- `defensive_pressure_summary`
- `goal_prevention_summary`
- `goalkeeping_distribution_summary`
- `goalkeeping_involvement`
- `line_breaks_players`
- `line_breaks_summary`
- `line_height_team_length`
- `lineups_players`
- `movement_to_receive_by_phase`
- `movement_to_receive_by_pitch_third`
- `movement_to_receive_top_players`
- `offers_summary`
- `set_plays_summary`

Esses arquivos não contêm hash, nome do PDF, `document_id` ou caminho de origem.

## Idempotência

- Mesmo hash e mesma versão do parser: nenhuma reescrita.
- Mesmo PDF com parser atualizado: os produtos são regenerados e a versão da
  partição é incrementada.
- Novo número de partida: uma nova pasta `match=<número>` é criada.

## Primeira partição

O relatório Brasil 1–1 Marrocos foi publicado em:

```text
data/parsed/fifa_pdf/year=2026/match=7/
```

