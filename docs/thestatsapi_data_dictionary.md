# Dicionário de dados — TheStatsAPI 2026

Fonte analisada: TheStatsAPI  
Competição: FIFA World Cup 2026  
`competition_id`: `comp_6107`  
`season_id`: `sn_118868`  
Amostra validada: México 2–0 África do Sul, Grupo A, `match_id=mt_153637999`  
Data da partida na fonte: `2026-06-11T19:00:00.000Z`

Este dicionário descreve o contrato observado na camada Bronze raw da
TheStatsAPI. Por enquanto ele é a fonte prioritária do produto 2026; FIFA PDF e
StatsBomb ficam fora deste documento.

O catálogo tabular campo a campo está em
[`thestatsapi_data_dictionary.csv`](thestatsapi_data_dictionary.csv).

## Organização Bronze

```text
data/bronze/thestatsapi/world_cup/2026/
  fixtures/
    page=1/
      response.json
      metadata.json
  standings/
    response.json
    metadata.json
  matches/
    match_id=<match_id>/
      match_detail/
        response.json
        metadata.json
      lineups/
        response.json
        metadata.json
      match_stats/
        response.json
        metadata.json
      player_stats/
        response.json
        metadata.json
      events/
        response.json
        metadata.json
      shotmap/
        response.json
        metadata.json
      match_referee/
        response.json
        metadata.json
```

`response.json` preserva a resposta da API. `metadata.json` guarda a linhagem da
request, status HTTP e hash da resposta para idempotência.

## Perfil da amostra

| Produto | Endpoint lógico | Grão observado | Registros |
|---|---|---|---:|
| `fixtures` | `fixtures` | uma partida do calendário | 96 |
| `standings` | `standings` | uma seleção por grupo | 60 |
| `match_detail` | `match_detail` | uma partida detalhada | 1 |
| `lineups` | `lineups` | uma partida com dois elencos | 1 |
| `match_stats` | `match_stats` | uma partida com métricas por time/período | 1 |
| `player_stats` | `player_stats` | um jogador por partida | 52 |
| `events` | `events` via rota `timeline` | um evento de timeline | 46 |
| `shotmap` | `shotmap` | uma finalização | 19 |
| `match_referee` | `match_referee` | uma partida com árbitro nullable | 1 |

Na amostra real, `match_detail.venue` retornou `Estadio Azteca`, em
`Mexico City`.

Na amostra real, `match_referee.referee.name` retornou
`Wilton Pereira Sampaio`.

Na partida de abertura, os endpoints retornaram:

| Endpoint | Status | HTTP | Rota efetiva |
|---|---|---:|---|
| `match_detail` | `success` | 200 | `/football/matches/mt_153637999` |
| `lineups` | `success` | 200 | `/football/matches/mt_153637999/lineups` |
| `match_stats` | `success` | 200 | `/football/matches/mt_153637999/stats` |
| `player_stats` | `success` | 200 | `/football/matches/mt_153637999/player-stats` |
| `events` | `success` | 200 | `/football/matches/mt_153637999/timeline` |
| `shotmap` | `success` | 200 | `/football/matches/mt_153637999/shotmap` |
| `match_referee` | `success` | 200 | `/football/matches/mt_153637999/referee` |

Observação: o produto interno se chama `events`, mas a rota da API validada para
esta amostra é `timeline`. A rota de árbitro foi confirmada na documentação
oficial e no API tester autenticado; não foram criadas rotas especulativas para
assistentes ou VAR.

## Linhagem e metadata

Todos os `metadata.json` têm:

| Campo | Significado |
|---|---|
| `source` | Fonte externa, atualmente `thestatsapi`. |
| `edition_year` | Edição da Copa, atualmente `2026`. |
| `endpoint_name` | Nome lógico do endpoint no projeto. |
| `fetch_stage` | Etapa de ingestão: `fixtures`, `core` ou `match_bundle`. |
| `fetch_status` | Resultado operacional: `success`, `unavailable` ou `failed`. |
| `request_url` | URL chamada, sem expor a API key. |
| `fetched_at` | Timestamp UTC da coleta. |
| `http_status` | Código HTTP recebido. |
| `response_hash` | SHA-256 da resposta JSON canônica. |
| `page` | Página do calendário, somente em fixtures. |
| `match_id` | Identificador da partida, somente no bundle de partida. |

## Produtos

### `fixtures`

Calendário da competição. O grão é uma partida. A amostra atual tem 96 jogos.

Campos principais:

- `id`: identificador da partida na TheStatsAPI.
- `competition_id` e `season_id`: chaves da competição/temporada.
- `utc_date`: data/hora UTC da partida.
- `status`: estado da partida, por exemplo `scheduled` ou `finished`.
- `home_team` e `away_team`: objetos com `id` e `name`.
- `score`: objeto com `home`, `away` e `final_score`.
- `group_label`, `stage_name`, `matchday`: posição competitiva.
- `xg_available`: indica se há xG disponível para a partida.
- `odds_available` e `live_odds_available`: disponibilidade de odds; não são
  usados no produto analítico neste momento.

### `match_detail`

Detalhe oficial de uma partida, coletado por
`/football/matches/{match_id}`. Ele complementa a listagem de fixtures, que não
expõe venue. O endpoint é opcional e sua ausência não bloqueia os demais dados
do bundle.

Campos complementares principais:

- `competition_name`: nome da competição.
- `venue.name`: nome do estádio.
- `venue.city`: cidade do estádio.
- `score.half_time_home` e `score.half_time_away`: placar no intervalo, quando
  disponível.
- `referee`: identificação resumida do árbitro, também validada pelo endpoint
  dedicado `match_referee`.

Na camada pública, `venue.name` é normalizado como `stadium` e `venue.city` como
`venue_city`. Ambos permanecem nullable e não são exibidos quando ausentes.

### `lineups`

Escalações da partida. O grão do arquivo é uma partida; dentro dele há dois
objetos, `home` e `away`.

Campos de time:

- `id`: id da seleção.
- `name`: nome da seleção.
- `formation`: formação declarada.
- `starting_xi`: lista de titulares.
- `substitutes`: lista de reservas.

Campos de jogador em `starting_xi[]` e `substitutes[]`:

- `id`: id do jogador.
- `jersey_number`: número da camisa.
- `name`: nome exibido.
- `position`: posição curta, como `G`, `D`, `M` ou `F`.

Na partida de abertura foram observados 11 titulares e 15 reservas para cada
seleção.

### `standings`

Classificação oficial da temporada, coletada como parte do core em
`/football/competitions/comp_6107/seasons/sn_118868/standings`. O grão é uma
seleção por grupo. Linhas com `group_label: null` são preservadas no Bronze,
mas não entram nos cards públicos de grupos.

Campos:

- `team.id` e `team.name`: identificação da seleção.
- `group_label` e `position`: grupo e posição oficial.
- `matches_played`, `wins`, `draws` e `losses`: campanha.
- `goals_for`, `goals_against` e `goal_difference`: saldo ofensivo/defensivo.
- `points`: pontuação oficial.

### `match_stats`

Métricas agregadas de partida. O grão é uma partida, com métricas agrupadas por
domínio e separadas por período.

Formato recorrente:

```json
{
  "<metric_name>": {
    "all": {"home": 1.46, "away": 0.07},
    "first_half": {"home": 0.69, "away": 0.06},
    "second_half": {"home": 0.77, "away": 0.02}
  }
}
```

Nem toda métrica possui `first_half` e `second_half`; alguns valores podem ser
`null`.

Domínios observados:

- `overview`: posse, passes, chutes, xG, faltas, cartões e escanteios.
- `shots`: chutes por alvo/localização/bloqueio.
- `passes`: passes certos, bolas longas, cruzamentos, laterais e entradas no terço final.
- `attack`: impedimentos, toques na área, grandes chances perdidas.
- `defending`: recuperações, cortes, interceptações e desarmes.
- `duels`: duelos, dribles, perdas de posse e percentuais de disputa.
- `goalkeeping`: defesas, tiros de meta, high claims e gols prevenidos.
- `np_expected_goals`: xG sem pênaltis, separado por período.

### `player_stats`

Estatísticas individuais. O grão é um jogador por partida. A partida de abertura
tem 52 registros, incluindo titulares e reservas.

Campos de identidade:

- `player_id`, `player_name`, `team_id`, `club_team_id`.
- `position`, `started`, `played`, `minutes_played`, `rating`.

Grupos observados:

- `general`: toques, faltas, impedimentos, cartões, perda de posse e substituições.
- `shooting`: gols, chutes, xG, xG sem pênalti, xA e grandes chances criadas.
- `passing`: passes, passes certos, bolas longas, cruzamentos, assistências e key passes.
- `duels`: duelos ganhos/perdidos, disputa aérea, contestes e perdas.
- `defending`: cortes, interceptações e desarmes.
- `goalkeeping`: defesas.

### `events`

Timeline de eventos da partida. O endpoint lógico é `events`, mas a rota efetiva
validada foi `/timeline`.

Campos:

- `match_id`: partida.
- `coverage`: nível de cobertura, observado como `full`.
- `events[]`: lista ordenada por `sequence`.

Campos de `events[]`:

- `sequence`: ordem do evento.
- `minute` e `extra_time`: minuto regulamentar e acréscimo.
- `period`: período, como `first_half` ou `second_half`.
- `type`: tipo do evento, como `goal`, `shot_on_target`, `foul`,
  `yellow_card`, `red_card`, `substitution`, `corner_kick`, `var`,
  `period_start` e `period_end`.
- `team`: objeto opcional com `id`, `name` e `slug`.
- `player`: objeto opcional com `id`, `name` e `slug`.

### `shotmap`

Finalizações com coordenadas e xG. O grão é uma finalização.

Campos principais:

- `id`: id do chute.
- `team_id`, `team_name`, `player_id`, `player_name`.
- `minute`: minuto do chute.
- `x`, `y`: coordenadas do chute no sistema da TheStatsAPI.
- `expected_goals`: xG da finalização.
- `result`: desfecho, por exemplo `goal`, `save`, `miss` ou `block`.
- `body_part`, `situation`, `goal_type`.
- `is_goal`, `is_on_target`, `is_blocked_shot`, `is_headed`,
  `is_outside_box`, `is_penalty`.
- `goalkeeper`: objeto com `id` e `name`.
- `goal_mouth_coordinates`: ponto de chegada no gol, com `x`, `y`, `z`.
- `goal_mouth_location`: zona do gol.
- `block_coordinates` e `blocked_by_player_id`: informação de bloqueio quando
  disponível.

### `match_referee`

Árbitro principal da partida. O endpoint opcional confirmado é
`/football/matches/{match_id}/referee`; `referee` pode ser `null` quando não há
designação. O arquivo Bronze preserva o objeto oficial com:

- `match_id`: partida.
- `referee.id`, `referee.name` e `referee.slug`: identidade do árbitro.
- `referee.country`, `country_code` e `country_slug`: país, quando informado.
- `referee.career.games`, `yellow_cards`, `red_cards` e `yellow_red_cards`:
  resumo de carreira retornado pela fonte.

O adapter público aceita também `main_referee`, `officials`,
`assistant_referees`, `fourth_official`, `var` e `avar` como campos nullable.
Esses papéis não aparecem no schema nem na resposta real validada do endpoint
atual; por isso nenhum path adicional foi inventado. Se não houver árbitro, a
UI simplesmente omite o item do contexto da partida.

## Banco de controle

A ingestão também alimenta tabelas operacionais:

| Tabela | Grão | Uso |
|---|---|---|
| `ingestion.match_control` | uma partida da fonte | Controle de jogos descobertos e status de coleta. |
| `ingestion.source_fetch_jobs` | uma request lógica | Idempotência por endpoint/stage/match. |
| `ingestion.api_usage_log` | uma chamada de API | Auditoria de uso, status HTTP e hash. |

Essas tabelas não são produtos analíticos; são controle de ingestão e futura
base para Airflow.

## Regras de uso

- Use `response.json` como Bronze auditável, não como modelo final de consumo.
- Use `metadata.json` para idempotência, auditoria e diagnóstico de falhas.
- Trate `404` ou payload vazio como `unavailable`, não como zero esportivo.
- Trate `match_referee` como opcional; sua ausência nunca bloqueia o bundle nem
  a página da partida.
- Não use odds no produto analítico atual.
- Não faça agregação de percentuais sem entender o denominador.
- `match_stats` usa lados `home`/`away`; a UI deve resolver os nomes dos times a
  partir de fixtures ou lineups.
- `shotmap.x`/`y` são coordenadas da TheStatsAPI; não assumir que equivalem ao
  sistema StatsBomb.
- Este contrato é observado na primeira amostra real. Quando novas partidas
  entrarem, campos opcionais devem ser tratados como nullable até serem
  confirmados em Silver.
