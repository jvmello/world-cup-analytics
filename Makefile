up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build

bash:
	docker compose run --rm app bash

extract:
	docker compose run --rm app python src/extract_statsbomb_world_cup.py

silver:
	docker compose run --rm app python src/build_silver_world_cup.py

gold:
	docker compose run --rm app python src/build_gold_world_cup.py

tournament_structure:
	docker compose run --rm app python src/build_gold_tournament_structure.py

validate:
	docker compose run --rm app python src/validate_world_cup_data.py

pipeline:
	docker compose run --rm app python src/extract_statsbomb_world_cup.py
	docker compose run --rm app python src/build_silver_world_cup.py
	docker compose run --rm app python src/build_gold_world_cup.py
	docker compose run --rm app python src/validate_world_cup_data.py

player_offensive:
	docker compose run --rm app python src/build_gold_player_offensive.py

dim_player:
	docker compose run --rm app python src/silver_players.py

fifa_pdf:
	docker compose run --rm --no-deps app python -m fifa_pdf.cli --input-dir data/pdf/inbox --edition 2026
	docker compose run --rm --no-deps app python -m fifa_pdf.publication --input-dir data/pdf/inbox --edition 2026

fifa_pdf_file:
	docker compose run --rm --no-deps app python -m fifa_pdf.cli --file data/pdf/PMSR-M07-BRA-V-MAR.pdf --edition 2026
	docker compose run --rm --no-deps app python -m fifa_pdf.publication --file data/pdf/PMSR-M07-BRA-V-MAR.pdf --edition 2026

fifa_pdf_snapshot:
	docker compose run --rm --no-deps app python -m fifa_pdf.snapshot --file data/pdf/PMSR-M07-BRA-V-MAR.pdf --edition 2026

fifa_match_products:
	docker compose run --rm --no-deps app python -m fifa_pdf.publication --input-dir data/pdf/inbox --edition 2026

fifa_match_products_file:
	docker compose run --rm --no-deps app python -m fifa_pdf.publication --file data/pdf/PMSR-M07-BRA-V-MAR.pdf --edition 2026

thestatsapi-fixtures:
	docker compose run --rm app python -m thestatsapi.fixtures

thestatsapi-fixtures-force:
	docker compose run --rm app python -m thestatsapi.fixtures --force

thestatsapi-match:
	@test -n "$(MATCH_ID)" || (echo "Usage: make thestatsapi-match MATCH_ID=<match_id>" && exit 1)
	docker compose run --rm app python -m thestatsapi.match_bundle --match-id "$(MATCH_ID)"

thestatsapi-match-force:
	@test -n "$(MATCH_ID)" || (echo "Usage: make thestatsapi-match-force MATCH_ID=<match_id>" && exit 1)
	docker compose run --rm app python -m thestatsapi.match_bundle --match-id "$(MATCH_ID)" --force

thestatsapi-opening-match:
	docker compose run --rm app python -m thestatsapi.opening_match_smoke

thestatsapi-opening-match-force:
	docker compose run --rm app python -m thestatsapi.opening_match_smoke --force

THESTATSAPI_GROUP_STAGE_ARGS = \
	$(if $(GROUP),--group "$(GROUP)",) \
	$(if $(LIMIT),--limit "$(LIMIT)",) \
	$(if $(REQUEST_INTERVAL),--request-interval "$(REQUEST_INTERVAL)",) \
	$(if $(REFRESH_FIXTURES),--refresh-fixtures,)

thestatsapi-group-stage:
	docker compose run --rm app python -m thestatsapi.group_stage_bulk --profile overview $(THESTATSAPI_GROUP_STAGE_ARGS)

thestatsapi-group-stage-rich:
	docker compose run --rm app python -m thestatsapi.group_stage_bulk --profile available $(THESTATSAPI_GROUP_STAGE_ARGS)

thestatsapi-silver:
	docker compose run --rm --no-deps app python -m thestatsapi.silver

thestatsapi-serving:
	docker compose run --rm app python -m thestatsapi.serving

thestatsapi-sync:
	docker compose run --rm app python -m thestatsapi.sync

thestatsapi-sync-dry:
	docker compose run --rm app python -m thestatsapi.sync --dry-run --skip-fixtures

thestatsapi-gold:
	docker compose run --rm app python -m thestatsapi.gold

thestatsapi-position-report:
	docker compose run --rm --no-deps app python -m thestatsapi.position_report --year 2026

thestatsapi-wikipedia-jerseys:
	docker compose run --rm --no-deps app python -m thestatsapi.wikipedia_jerseys

test:
	docker compose run --rm --no-deps app python -m unittest discover -s tests -v

web_build:
	docker compose build web

web:
	docker compose up web

web_up:
	docker compose up -d web

web_down:
	docker compose stop web

web_test:
	docker compose run --rm --no-deps web python -m pytest tests/test_web_api.py -q
