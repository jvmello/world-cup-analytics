-- Tracking de uso da API: qual endpoint é mais chamado, latência, taxa de erro.
-- Schema `analytics` já existe desde a baseline (init.sql) e estava sem uso.
-- Tabela alimentada por um middleware fire-and-forget em webapp/main.py; nunca
-- é tocada pelo rebuild do gold (staging+swap não sabe que ela existe).

CREATE SCHEMA IF NOT EXISTS analytics;

CREATE TABLE IF NOT EXISTS analytics.api_requests (
    id BIGSERIAL PRIMARY KEY,
    ts TIMESTAMPTZ NOT NULL DEFAULT now(),
    method TEXT NOT NULL,
    path_template TEXT NOT NULL,
    status_code INTEGER NOT NULL,
    duration_ms NUMERIC NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_api_requests_ts ON analytics.api_requests (ts);
CREATE INDEX IF NOT EXISTS idx_api_requests_path_ts ON analytics.api_requests (path_template, ts);
