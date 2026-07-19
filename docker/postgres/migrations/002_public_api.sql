-- Papéis Postgres para o split público/admin da API (fase 1: só o lado
-- público) + tabelas de api keys e rate limiting.
--
-- Dois papéis novos, propositalmente sem sobreposição de privilégios:
--   readonly_public   -> só SELECT no schema gold (o único schema que a
--                        leitura pública toca hoje, via gold.api_payloads).
--   public_api_writer -> só INSERT/UPDATE/SELECT nas tabelas de tracking
--                        (api_requests, api_keys, api_rate_limits); nunca
--                        lê nem escreve em gold/ingestion/raw/silver.
--
-- Senhas NÃO entram neste arquivo — defina/rotacione fora do controle de
-- versão, na primeira aplicação desta migração:
--   ALTER ROLE readonly_public WITH PASSWORD '...';
--   ALTER ROLE public_api_writer WITH PASSWORD '...';

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'readonly_public') THEN
        CREATE ROLE readonly_public LOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'public_api_writer') THEN
        CREATE ROLE public_api_writer LOGIN;
    END IF;
END
$$;

GRANT USAGE ON SCHEMA gold TO readonly_public;
GRANT SELECT ON ALL TABLES IN SCHEMA gold TO readonly_public;
-- Tabelas gold novas no futuro herdam o SELECT automaticamente — sem isso,
-- todo rebuild que criasse uma tabela nova exigiria reaplicar o GRANT à mão.
ALTER DEFAULT PRIVILEGES IN SCHEMA gold GRANT SELECT ON TABLES TO readonly_public;

CREATE TABLE IF NOT EXISTS analytics.api_keys (
    id BIGSERIAL PRIMARY KEY,
    key_hash TEXT NOT NULL UNIQUE,
    owner_identifier TEXT NOT NULL,
    tier TEXT NOT NULL DEFAULT 'default',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    revoked_at TIMESTAMPTZ,
    last_used_at TIMESTAMPTZ,
    request_count BIGINT NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_api_keys_key_hash ON analytics.api_keys (key_hash);

-- Contador diário por chave OU por IP (quando não há chave válida). PK
-- composta é o próprio alvo do ON CONFLICT DO UPDATE do incremento.
CREATE TABLE IF NOT EXISTS analytics.api_rate_limits (
    key_or_ip TEXT NOT NULL,
    day DATE NOT NULL,
    request_count BIGINT NOT NULL DEFAULT 0,
    PRIMARY KEY (key_or_ip, day)
);

GRANT USAGE ON SCHEMA analytics TO public_api_writer;
GRANT SELECT, INSERT, UPDATE ON analytics.api_requests TO public_api_writer;
GRANT SELECT, INSERT, UPDATE ON analytics.api_keys TO public_api_writer;
GRANT SELECT, INSERT, UPDATE ON analytics.api_rate_limits TO public_api_writer;
GRANT USAGE, SELECT ON SEQUENCE analytics.api_requests_id_seq TO public_api_writer;
GRANT USAGE, SELECT ON SEQUENCE analytics.api_keys_id_seq TO public_api_writer;
