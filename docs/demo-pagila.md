# Demo Data: Pagila PostgreSQL

This runbook documents the reproducible Pagila demo source used by the local `docker-compose.dev.yml` stack.

In command examples below, `<repo-root>` means the root directory of this repository checkout.

## What gets started
- a dedicated `pagila-db` container on PostgreSQL 16
- the real relational `pagila` demo database
- automatic registration of the demo database and key datasets in Superset during `superset-init`

In Superset the source appears as `Pagila Demo (PostgreSQL)`.

## How to run
```bash
cd <repo-root>
cp .env.dev.example .env.dev
docker compose --env-file .env.dev -f docker-compose.dev.yml up -d
```

Verification:
```bash
docker compose --env-file .env.dev -f docker-compose.dev.yml ps
docker compose --env-file .env.dev -f docker-compose.dev.yml logs --tail=100 superset-init
docker compose --env-file .env.dev -f docker-compose.dev.yml exec pagila-db psql -U pagila -d pagila -c "\\dt"
```

Host port for direct database access:
- `localhost:${DEV_PAGILA_PORT:-5433}`

## Datasets prepared automatically
- `sales_by_store`
- `sales_by_film_category`
- `payment`
- `rental`
- `customer_list`
- `film_list`
- `film`
- `category`
- `customer`
- `inventory`

That is enough for the primary demo flows:
- browse databases
- browse datasets
- preview data
- explain fields
- recommend visualization
- create chart
- create dashboard
- open useful links

## Recommended demo prompts
- `Show revenue by store`
- `Which film categories generate the most revenue?`
- `Build a monthly payments chart`
- `Which customers rent films most often?`
- `Show film categories and average rental duration`
- `Create a dashboard for store and category revenue`

## Fast smoke check before a demo
1. In Superset open `Data -> Databases` and confirm `Pagila Demo (PostgreSQL)` exists.
2. In `Data -> Datasets` confirm `sales_by_store`, `sales_by_film_category`, `payment`, and `rental` are present.
3. In the assistant run:
   - browse databases
   - preview `sales_by_store` or `payment`
   - recommendation on `sales_by_film_category`
   - chart creation
   - dashboard creation
4. Confirm generated links open on the same `SUPERSET_PUBLIC_URL`.

## What still requires manual runtime validation
- the first full container bootstrap and Pagila SQL load
- actual appearance of the source and datasets in the Superset UI
- end-to-end chat business-question flow against live Pagila data
- availability of generated chart and dashboard links from the target demo network
