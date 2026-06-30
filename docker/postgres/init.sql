CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS gold;
CREATE SCHEMA IF NOT EXISTS analytics;
CREATE SCHEMA IF NOT EXISTS ingestion;

CREATE TABLE IF NOT EXISTS ingestion.match_control (
    source_match_id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    edition_year INTEGER NOT NULL,
    competition_id TEXT NOT NULL,
    season_id TEXT NOT NULL,
    match_number TEXT,
    group_label TEXT,
    stage_name TEXT,
    status TEXT,
    fetch_status TEXT NOT NULL DEFAULT 'scheduled',
    kickoff_utc TIMESTAMPTZ,
    venue_name TEXT,
    home_team_id TEXT,
    home_team_name TEXT,
    away_team_id TEXT,
    away_team_name TEXT,
    first_seen_at TIMESTAMPTZ DEFAULT now(),
    last_seen_at TIMESTAMPTZ DEFAULT now(),
    raw_path TEXT,
    metadata_path TEXT
);

CREATE TABLE IF NOT EXISTS ingestion.source_fetch_jobs (
    id BIGSERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    endpoint_name TEXT NOT NULL,
    fetch_stage TEXT NOT NULL,
    match_id TEXT NOT NULL DEFAULT '',
    request_fingerprint TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL,
    request_url TEXT,
    http_status INTEGER,
    response_hash TEXT,
    raw_path TEXT,
    metadata_path TEXT,
    attempts INTEGER NOT NULL DEFAULT 1,
    last_error TEXT,
    started_at TIMESTAMPTZ DEFAULT now(),
    finished_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (source, endpoint_name, fetch_stage, match_id, request_fingerprint)
);

CREATE TABLE IF NOT EXISTS ingestion.api_usage_log (
    id BIGSERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    endpoint_name TEXT NOT NULL,
    fetch_stage TEXT NOT NULL,
    match_id TEXT NOT NULL DEFAULT '',
    request_url TEXT,
    http_status INTEGER,
    response_hash TEXT,
    fetched_at TIMESTAMPTZ DEFAULT now(),
    status TEXT NOT NULL
);
