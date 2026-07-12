# Migrações de DDL (a partir da v1)

Baseline: `../init.sql` na v1.0.0 (2026-07-11) — não editar retroativamente.

Convenção: `NNN_descricao.sql` (ex.: `001_add_kit_columns.sql`), idempotente
quando possível. Aplicar na VPS antes do rebuild do serving:

```bash
docker compose exec -T worldcup-db \
  psql -U "$WORLDCUP_DB_USER" -d "$WORLDCUP_DB_NAME" < docker/postgres/migrations/NNN_descricao.sql
```

Mudanças só de payload (JSONB) não são DDL: basta `thestatsapi.serving`.
