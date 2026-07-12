# Spec: Governança a partir da v1 (2026-07-11)

A v1.0.0 fecha o produto em produção (worldcup.jvmello.dev): gold serving no
PostgreSQL, sync automático de partidas, kit colors, mapa de pênaltis,
insights/comparar, e as revisões editoriais das telas (specs 008–016).

## Política de DDL versionado

- `docker/postgres/init.sql` fica **congelado como baseline da v1** — só vale
  para a primeira inicialização de um volume novo.
- Toda mudança de DDL (nova coluna/tabela/índice no substrato gold ou em
  ingestion) entra como migração numerada em `docker/postgres/migrations/`
  (`NNN_descricao.sql`), idempotente quando possível (`IF NOT EXISTS`).
- Migrações são aplicadas manualmente na VPS **antes** do rebuild do serving:
  `docker compose exec -T worldcup-db psql -U $USER -d $DB < migrations/NNN_x.sql`
- Mudanças que vivem só dentro de JSONB (payloads) **não** são DDL e não
  precisam de migração — basta o rebuild do serving.
- O `SCHEMA_STATEMENTS` do builder continua criando o schema do zero em
  ambientes novos; migrações e statements devem ser mantidos em sincronia.

## Política de changelog

- `CHANGELOG.md` na raiz, formato Keep a Changelog, em PT-BR.
- Toda alteração relevante (feature, fix, DDL, mudança de contrato de API)
  ganha entrada na seção "Não lançado" no mesmo commit/PR.
- Ao fechar uma versão: mover para uma seção `vX.Y.Z — data` e criar tag git.
