.PHONY: up down rebuild logs test seed psql health

BASE=http://127.0.0.1:8010
GOOD=secret123

up:
docker compose up -d

down:
docker compose down -v

rebuild:
docker compose down -v
docker compose build --no-cache app
docker compose up -d

logs:
docker logs -f mep-app

health:
curl -fsS $(BASE)/health && echo
curl -fsS $(BASE)/metrics | grep -i process_max_fds

seed:
cat seeds/ohlcv_seed.sql | docker exec -i mep-db psql -U postgres -d market_edge -f -

psql:
docker exec -it mep-db psql -U postgres -d market_edge

test:
BASE=$(BASE) BASE_URL=$(BASE) GOOD=$(GOOD) pytest -q -k "smoke_endpoints or http" -s
