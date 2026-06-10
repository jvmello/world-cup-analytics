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

streamlit:
	docker compose up streamlit

player_offensive:
	docker compose run --rm app python src/build_gold_player_offensive.py

dim_player:
	docker compose run --rm app python src/silver_players.py
