# Plano técnico: Camada gold de serving em PostgreSQL

## Fluxo

```text
TheStatsAPI
 -> bronze JSON na VPS (fixtures + match bundles, fonte da verdade)
 -> make thestatsapi-serving (leitura única do bronze)
 -> PostgreSQL schema gold (substrato + api_payloads)
 -> FastAPI: SELECT payload -> resposta
```

## Schema `gold` (por edição/ano)

Substrato normalizado (base dos payloads e de consultas futuras):

- `matches` — 1 linha/partida: ids, fase, grupo, datas, placares (incl.
  pênaltis), status, venue, vencedor, xg/finalizações por lado, `detail JSONB`
  (timeline, stats_comparison, lineups condensados).
- `match_players` — 1 linha/(partida, jogador): stats do jogo + posição
  inferida. Alimenta match_log e agregados por recorte.
- `match_shots` — linhas do shot map (mapas e agregados corpo/situação).
- `players_agg` — 1 linha/(jogador, recorte ∈ {all, group_stage, knockout}):
  totais, por-90, eixos do radar, `radar_dimensions JSONB`,
  `benchmarks JSONB` (percentis vs posição, calculados no build sobre a
  população completa).
- `teams_agg` — 1 linha/seleção: campanha completa (semântica do fix de
  2026-07-09 em team_rows), taxas por jogo, percentis vs Copa, radar.
- `standings`, `edition_summary` (resumo da home, incl. finished/matches para
  a barra de progresso).

Serving:

- `api_payloads (year, endpoint, entity_id NULL, scope NULL, payload JSONB,
  built_at)` — o JSON exato de cada endpoint atual: overview, competition,
  teams, players, profiles, matches, shots, official-metrics, availability,
  team_detail por seleção e player_detail por jogador × recorte (incluindo
  `match:<id>`).

## Builder

- Novo módulo `src/thestatsapi/serving.py` + alvo `make thestatsapi-serving`.
- Refatorar as agregações de `webapp/thestatsapi_service.py` em funções puras
  reutilizadas pelo builder e pelo caminho legado (evita duplicação e mantém
  os testes golden simétricos).
- Leitura única do bronze, escrita em transação: tabelas staging + swap.
  Rebuild total por edição (~100 partidas, uma passada) — sem incrementalidade
  fina.
- Runbook passa a ser: fixtures → match bundles → `make thestatsapi-serving`.

## API

- `DataService` ganha o caminho gold: se houver `api_payloads` materializado
  para a edição, serve dele; senão, fallback automático ao caminho bronze
  atual. Conexão via SQLAlchemy/psycopg2 (já nos requirements), URL pelo
  mesmo `THESTATSAPI_DATABASE_URL`/`POSTGRES_*` do compose.

## Fases

1. Schema `gold` + builder populando o substrato.
2. `api_payloads` + flag no `DataService` com fallback bronze; testes golden
   comparando payload gold vs legado, endpoint a endpoint.
3. Cutover: bronze sai do request path (meta: <100ms/endpoint vs segundos).
4. Opcional: `archive_*` para edições históricas; admin overrides no Postgres.

## Produção (VPS)

- Bronze em caminho persistido da VPS (volume montado, incluído no backup).
- Extração (fixtures/match_bundle/bulk) roda na VPS via cron ou manual, com a
  chave no `.env`; cada extração é seguida do build do gold no Postgres local.
- Reextração possível a qualquer momento; gold sempre reconstruível do bronze
  local sem novas chamadas à API.

## Arquivos

- `src/thestatsapi/serving.py` (novo)
- `webapp/thestatsapi_service.py` (refatoração das agregações em funções puras)
- `webapp/data_service.py` (roteamento gold/fallback)
- `docker/postgres/` (migração do schema `gold`)
- `Makefile` (`thestatsapi-serving`)
- `tests/test_gold_serving.py` (novo — golden payloads)
