CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS gold;
CREATE SCHEMA IF NOT EXISTS analytics;
CREATE SCHEMA IF NOT EXISTS ingestion;

CREATE TABLE IF NOT EXISTS gold.matches (
    edition_year INTEGER NOT NULL,
    match_id TEXT NOT NULL,
    match_date TIMESTAMPTZ,
    stage TEXT,
    group_name TEXT,
    status TEXT,
    venue_name TEXT,
    venue_city TEXT,
    referee TEXT,
    home_team_id TEXT,
    home_team_name TEXT,
    away_team_id TEXT,
    away_team_name TEXT,
    home_score NUMERIC,
    away_score NUMERIC,
    penalty_home_score NUMERIC,
    penalty_away_score NUMERIC,
    winner_name TEXT,
    decided_by TEXT,
    home_xg NUMERIC,
    away_xg NUMERIC,
    home_shots INTEGER,
    away_shots INTEGER,
    detail JSONB NOT NULL DEFAULT '{}'::jsonb,
    built_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (edition_year, match_id)
);

CREATE TABLE IF NOT EXISTS gold.match_players (
    edition_year INTEGER NOT NULL,
    match_id TEXT NOT NULL,
    player_id TEXT NOT NULL,
    team_id TEXT,
    team_name TEXT,
    player_name TEXT,
    position TEXT,
    resolved_position TEXT,
    benchmark_position TEXT,
    scope TEXT NOT NULL DEFAULT 'match',
    minutes_played NUMERIC,
    goals NUMERIC,
    assists NUMERIC,
    xg NUMERIC,
    xa NUMERIC,
    shots NUMERIC,
    rating NUMERIC,
    impact_score NUMERIC,
    stats JSONB NOT NULL DEFAULT '{}'::jsonb,
    built_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (edition_year, match_id, player_id)
);

CREATE TABLE IF NOT EXISTS gold.match_shots (
    edition_year INTEGER NOT NULL,
    match_id TEXT NOT NULL,
    shot_id TEXT NOT NULL,
    team_id TEXT,
    team_name TEXT,
    player_id TEXT,
    player_name TEXT,
    minute NUMERIC,
    x NUMERIC,
    y NUMERIC,
    xg NUMERIC,
    body_part TEXT,
    shot_type TEXT,
    shot_outcome TEXT,
    is_goal BOOLEAN,
    is_on_target BOOLEAN,
    is_penalty BOOLEAN,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    built_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (edition_year, match_id, shot_id)
);

CREATE TABLE IF NOT EXISTS gold.players_agg (
    edition_year INTEGER NOT NULL,
    scope TEXT NOT NULL,
    player_id TEXT NOT NULL,
    player_name TEXT,
    team_id TEXT,
    team_name TEXT,
    position TEXT,
    resolved_position TEXT,
    benchmark_position TEXT,
    games INTEGER,
    minutes_played NUMERIC,
    goals NUMERIC,
    assists NUMERIC,
    xg NUMERIC,
    xa NUMERIC,
    shots NUMERIC,
    rating NUMERIC,
    impact_score NUMERIC,
    radar JSONB NOT NULL DEFAULT '[]'::jsonb,
    radar_dimensions JSONB NOT NULL DEFAULT '{}'::jsonb,
    benchmarks JSONB NOT NULL DEFAULT '{}'::jsonb,
    stats JSONB NOT NULL DEFAULT '{}'::jsonb,
    built_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (edition_year, scope, player_id)
);

CREATE TABLE IF NOT EXISTS gold.teams_agg (
    edition_year INTEGER NOT NULL,
    team_id TEXT NOT NULL,
    team_name TEXT,
    group_name TEXT,
    played INTEGER,
    wins INTEGER,
    draws INTEGER,
    losses INTEGER,
    points INTEGER,
    goals_for INTEGER,
    goals_against INTEGER,
    goal_difference INTEGER,
    xg NUMERIC,
    xga NUMERIC,
    xg_difference NUMERIC,
    shots INTEGER,
    stats JSONB NOT NULL DEFAULT '{}'::jsonb,
    built_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (edition_year, team_id)
);

CREATE TABLE IF NOT EXISTS gold.standings (
    edition_year INTEGER NOT NULL,
    group_name TEXT NOT NULL,
    position INTEGER NOT NULL,
    team_id TEXT NOT NULL,
    team_name TEXT,
    played INTEGER,
    wins INTEGER,
    draws INTEGER,
    losses INTEGER,
    points INTEGER,
    goals_for INTEGER,
    goals_against INTEGER,
    goal_difference INTEGER,
    classification_status TEXT,
    row JSONB NOT NULL DEFAULT '{}'::jsonb,
    built_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (edition_year, group_name, position, team_id)
);

CREATE TABLE IF NOT EXISTS gold.edition_summary (
    edition_year INTEGER PRIMARY KEY,
    matches INTEGER,
    finished INTEGER,
    teams INTEGER,
    players INTEGER,
    goals INTEGER,
    shots INTEGER,
    xg NUMERIC,
    summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    built_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS gold.api_payloads (
    edition_year INTEGER NOT NULL,
    endpoint TEXT NOT NULL,
    entity_id TEXT NOT NULL DEFAULT '',
    scope TEXT NOT NULL DEFAULT '',
    payload JSONB NOT NULL,
    built_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (edition_year, endpoint, entity_id, scope)
);

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
