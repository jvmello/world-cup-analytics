# World Cup Analytics

World Cup Analytics is a local analytics project for exploring FIFA World Cup data with a bronze/silver/gold data pipeline and a Streamlit application.

The current focus is turning StatsBomb World Cup data into usable competition, team, and player views.

The application supports two source profiles:

- 2022: granular StatsBomb event data.
- 2026: aggregate FIFA post-match PDF reports plus the scheduled tournament structure.

## Primary Web Application

The product interface is now a FastAPI-served web application with an edition
switcher at the top, navigation derived from data coverage, and a cross-edition
history area. Streamlit remains available as an internal exploration interface.

The edition pages prioritize sports analysis: KPIs, rankings, scorecards,
goals-versus-xG comparison, shot maps, match-level xG flow, and mirrored FIFA
official metrics. Source availability is kept in a separate technical view.

Build and start the web application:

```bash
make web_build
make web_up
```

Open:

```text
http://localhost:8010
```

Stop it with:

```bash
make web_down
```

The web API is read-only and consumes the same Parquet and CSV outputs used by
the existing dashboard.

## What Exists Today

### Data Pipeline

The project uses layered parquet datasets:

- `data/bronze/statsbomb/world_cup/`: raw extracted StatsBomb competition data.
- `data/silver/world_cup/`: normalized events, matches, shots, metadata, and player dimensions.
- `data/gold/world_cup/`: application-ready analytical tables.

Current gold outputs include:

- Match summary.
- Team shot summary.
- Match/team shot summary.
- xG timeline.
- Player shots.
- Player offensive summary.
- Tournament group structure for 2026.
- Tournament fixture placeholders for 2026.

FIFA PDF outputs are written as CSV datasets:

- Bronze audit: documents, page text, and raw extracted table cells.
- Silver domains: match summary, team key statistics, phases of play,
  attempts at goal, player metrics, and extraction issues.

### Streamlit Application

The app currently contains these views:

- Main match-level shot and xG overview.
- Player shot map.
- Player analytics with radar, heatmap, goal-mouth view, time bins, body-part profile, percentiles, and shot table.
- Player rankings by xG, goals, shots, conversion, accuracy, G-xG, xG per shot, and big chances.
- Tournament history/competition view with 2026 groups as the default, group standings cards, group fixtures, knockout bracket boxes, champions, scorers, and historical summary.
- Team analytics with team showcase, performance card, xG ranking, radar, accumulated xG, rolling xG form, heatmap, and shot breakdown.

### 2026 Competition Structure

The app has a local gold seed for the 2026 World Cup:

- `gold_tournament_groups`: 12 groups with four teams each.
- `gold_tournament_fixtures`: group-stage scheduled placeholders and knockout placeholders from Round of 32 through the final.

These tables allow the UI to show the 2026 tournament structure before match results exist.

## How To Run

Build/start the Docker services:

```bash
make build
make up
```

Run the full data pipeline:

```bash
make pipeline
make dim_player
make player_offensive
make tournament_structure
```

Start the Streamlit application:

```bash
make streamlit
```

The app is served at:

```text
http://localhost:8501
```

Use the edition selector in the application header to switch between 2022 and
2026. Views that require granular event coordinates remain available only when
the selected edition provides them.

## Useful Commands

Generate the main gold layer:

```bash
make gold
```

Generate player offensive gold tables:

```bash
make player_offensive
```

Generate the 2026 tournament structure:

```bash
make tournament_structure
```

Validate World Cup data availability:

```bash
make validate
```

### Ingest TheStatsAPI 2026 data

TheStatsAPI is the structured source prepared for World Cup 2026 schedule and
match-level data. Add the API key to `.env`:

```text
THESTATSAPI_API_KEY=...
```

The default World Cup registry uses:

- `competition_id`: `comp_6107`
- `season_id`: `sn_118868`
- base URL: `https://api.thestatsapi.com/api`

The observed Bronze contract is documented in
[`docs/thestatsapi_data_dictionary.md`](docs/thestatsapi_data_dictionary.md)
and
[`docs/thestatsapi_data_dictionary.csv`](docs/thestatsapi_data_dictionary.csv).

Fetch the 2026 core data. This includes fixtures/schedule, official standings,
and the `ingestion.match_control` upsert:

```bash
make thestatsapi-fixtures
```

Fetch the raw bundle for one match:

```bash
make thestatsapi-match MATCH_ID=<match_id>
```

Run the environment smoke test for the opening match, Mexico x South Africa:

```bash
make thestatsapi-opening-match
```

This command refreshes/uses the schedule, finds the fixture by team names, and
fetches the full match bundle for the discovered `match_id`. Use the force
variant when you intentionally want to re-hit the API:

```bash
make thestatsapi-opening-match-force
```

Fetch partial coverage for every World Cup 2026 group-stage match:

```bash
make thestatsapi-group-stage
```

This resumable profile fetches `match_detail` and `match_referee` for all 72
group-stage fixtures and `match_stats` for fixtures whose schedule status is
finished. It provides match context and the main team comparison while avoiding
the larger player/event payloads. To add lineups, player stats, events and
shotmap for every finished fixture, run:

```bash
make thestatsapi-group-stage-rich
```

Both commands reuse successful jobs and existing Bronze files. They can be
partitioned for a pilot or a future Airflow task without changing the storage
contract:

```bash
make thestatsapi-group-stage GROUP=A
make thestatsapi-group-stage-rich GROUP=B LIMIT=2
make thestatsapi-group-stage REFRESH_FIXTURES=1 REQUEST_INTERVAL=6
```

`REQUEST_INTERVAL` controls the delay between requests and defaults to 5.2
seconds, matching the currently observed account limit of 12 requests per
minute. `REFRESH_FIXTURES=1` intentionally refreshes the schedule before the
selection; match endpoint responses remain idempotent unless `--force` is used
directly in the Python command.

The bundle currently requests:

- `match_detail` (optional; provides venue and city through
  `/football/matches/{match_id}`)
- `lineups`
- `match_stats`
- `player_stats`
- `events` (stored under this internal name; TheStatsAPI currently serves it
  through the match `timeline` route)
- `shotmap`
- `match_referee` (optional; official route
  `/football/matches/{match_id}/referee`)

The optional detail and referee endpoints do not block the bundle. A 404 or
empty match detail simply leaves venue data absent. A 404, empty response, or
`referee: null` is stored as `unavailable`; the remaining endpoints continue.
The current official schema documents only the main `referee` object. The web
adapter also accepts nullable fields for assistants, fourth official, VAR and
AVAR if the provider adds them to a response later.

Each response is stored independently in Bronze JSON under:

```text
data/bronze/thestatsapi/world_cup/2026/
  standings/
    response.json
    metadata.json
  matches/match_id=<match_id>/match_detail/
    response.json
    metadata.json
  matches/match_id=<match_id>/match_referee/
    response.json
    metadata.json
```

Every raw response gets a `metadata.json` with source, endpoint name, fetch
stage, request URL, fetch timestamp, HTTP status and response hash. The
ingestion layer is idempotent: successful jobs with existing Bronze files are
not requested again unless the force targets are used:

```bash
make thestatsapi-fixtures-force
make thestatsapi-match-force MATCH_ID=<match_id>
```

The database control tables are:

- `ingestion.match_control`
- `ingestion.source_fetch_jobs`
- `ingestion.api_usage_log`

The manual scripts are intentionally shaped like future Airflow tasks: one
command refreshes fixtures and standings, and one command fetches a match bundle by
`match_id`. Endpoint failures are isolated, so a 404/empty endpoint is marked
`unavailable`, while the remaining endpoints continue. Rate limits and 5xx
responses use bounded retry/backoff in the client.

Silver and Gold commands are present but intentionally non-materializing until
real response shapes are validated:

```bash
make thestatsapi-silver
make thestatsapi-gold
```

### Process FIFA 2026 PDFs

Add new reports to:

```text
data/pdf/inbox/
```

Then process every PDF in the inbox:

```bash
make fifa_pdf
```

To process the reference report directly:

```bash
make fifa_pdf_file
```

To save an isolated, auditable execution with its parsed products:

```bash
make fifa_pdf_snapshot
```

Snapshots are written to `data/runs/fifa_pdf/2026/<run_id>/` with bronze and
silver CSVs, `manifest.json`, and `execution.txt`.

### Publish match-oriented products

The canonical analytical output is partitioned by year and official match
number:

```bash
make fifa_match_products
```

To publish the reference PDF directly:

```bash
make fifa_match_products_file
```

Example output:

```text
data/parsed/fifa_pdf/year=2026/match=7/
```

This directory contains only sports-oriented CSV products and its own
`data_dictionary.csv`. The hidden `_manifest.json` is used only for
idempotency and version control. See `docs/fifa_match_products_dictionary.md`.

The pipeline is incremental. A SHA-256 based `document_id` prevents duplicate
rows when the same file is processed again, even if it has been renamed.

Generated datasets:

```text
data/bronze/fifa_pdf/world_cup/2026/
  documents.csv
  pages.csv
  raw_tables.csv

data/silver/fifa_pdf/world_cup/2026/
  match_summary.csv
  team_key_statistics.csv
  phases_of_play.csv
  attempts_at_goal.csv
  player_metrics.csv
  extraction_issues.csv
```

The physical-data pages in some FIFA reports use custom embedded fonts. The
pipeline preserves the original value and lowers extraction confidence whenever
a numeric value cannot be normalized safely.

## Current Design Direction

The project is still using Streamlit intentionally. Streamlit is useful while the data model, gold tables, and analytical flows are still evolving quickly.

The UI is moving toward richer, card-based layouts:

- Group tables rendered as visual cards.
- Fixtures listed below each group.
- Knockout rounds rendered as bracket-style match boxes.
- Team and player pages organized with sidebar menus.

If the UI needs become more product-like, the likely next frontend step is a React/Next.js app backed by FastAPI or another lightweight API layer. Streamlit can then remain as the internal exploration interface.

## Known Gaps

- Assists are not available yet because the current silver events table does not preserve detailed pass/assist fields from the original event payload.
- Historical group letters are inferred from group-stage match components when the local gold layer does not contain explicit group labels.
- 2026 fixtures are placeholders. Real dates, venues, scores, and standings should be updated incrementally when data becomes available.
- Country flags and team/player display-name administration are not implemented yet.
- Some UI pieces use custom HTML/CSS inside Streamlit; this works for now, but it is a reason to consider a dedicated frontend later.

## What Will Be Implemented Next

Planned next steps:

- Add a local country/team dimension with display names, common names, country codes, and flag asset paths.
- Add player identity support with full name and common display name.
- Preserve pass/assist fields in the silver event layer and publish a gold assists leaderboard.
- Improve 2026 tournament updates so fixtures, standings, and knockout progression can be refreshed incrementally.
- Add admin-friendly maintenance flows for flags and player/team names.
- Refine the team page with defensive metrics when the required gold tables are available.
- Keep expanding tests around tournament structure, group standings, and display-name fallbacks.
