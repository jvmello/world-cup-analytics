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

validate:
	docker compose run --rm app python src/validate_world_cup_data.py

pipeline:
	docker compose run --rm app python src/extract_statsbomb_world_cup.py
	docker compose run --rm app python src/build_silver_world_cup.py
	docker compose run --rm app python src/build_gold_world_cup.py
	docker compose run --rm app python src/validate_world_cup_data.py

streamlit:
	docker compose up streamlit