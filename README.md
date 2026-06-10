# World Cup Analytics

World Cup Analytics is a local analytics project for exploring FIFA World Cup data with a bronze/silver/gold data pipeline and a Streamlit application.

The current focus is turning StatsBomb World Cup data into usable competition, team, and player views.

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
