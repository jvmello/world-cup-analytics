# Tarefas: Camada gold de serving em PostgreSQL

## Fase 1 — Substrato

- [x] Migração do schema `gold` (matches, match_players, match_shots,
      players_agg, teams_agg, standings, edition_summary) em `docker/postgres/`.
- [x] Refatorar agregações de `webapp/thestatsapi_service.py` em funções puras
      compartilháveis (sem mudança de comportamento; suite atual verde).
- [x] `src/thestatsapi/serving.py`: leitura única do bronze → staging → swap
      em transação.
- [x] Alvo `make thestatsapi-serving` e atualização do runbook no README.

## Fase 2 — Payloads prontos

- [x] Tabela `gold.api_payloads` e build dos payloads de todos os endpoints,
      incluindo team_detail por seleção e player_detail por jogador × recorte
      (all, group_stage, knockout e match:<id>).
- [x] `DataService`: servir do gold quando materializado; fallback bronze
      automático caso contrário.
- [x] `tests/test_gold_serving.py`: golden tests comparando payload gold vs
      caminho legado, endpoint a endpoint, sobre um bronze de fixture.

## Fase 3 — Cutover

- [x] Remover leitura de bronze do request path (bronze permanece como fonte
      de rebuild).
- [x] Medir latência por endpoint e registrar no README.
      Observação: `/players` e `/profiles` ainda excedem a meta de 100 ms
      porque o contrato atual publica payloads completos muito grandes; o
      request path já sai do Gold e não lê Bronze.

## Fase 4 — Opcional

- [ ] Edições históricas (StatsBomb gold parquet) em tabelas `archive_*`.
- [ ] Migrar overrides do admin (SQLite) para o mesmo Postgres.

## Produção (VPS)

- [ ] Definir caminho persistido do bronze na VPS e incluir no backup.
- [ ] Cron/rotina de extração + build (fixtures → bundles → serving).
- [ ] Validar reextração completa na VPS e rebuild do gold sem chamadas à API.
