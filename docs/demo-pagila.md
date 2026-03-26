# Demo Data: Pagila PostgreSQL

Этот runbook фиксирует воспроизводимый demo-source для локального `docker-compose.dev.yml`.

## Что поднимается
- отдельный контейнер `pagila-db` на PostgreSQL 16
- реальная реляционная демо-база `pagila`
- автоматическая регистрация demo database и ключевых datasets в Superset во время `superset-init`

В Superset источник появится как `Pagila Demo (PostgreSQL)`.

## Как запустить
```bash
cd /home/superset_ai
cp .env.dev.example .env.dev
docker compose --env-file .env.dev -f docker-compose.dev.yml up -d
```

Проверка:
```bash
docker compose --env-file .env.dev -f docker-compose.dev.yml ps
docker compose --env-file .env.dev -f docker-compose.dev.yml logs --tail=100 superset-init
docker compose --env-file .env.dev -f docker-compose.dev.yml exec pagila-db psql -U pagila -d pagila -c "\\dt"
```

Хост-порт для прямой проверки базы:
- `localhost:${DEV_PAGILA_PORT:-5433}`

## Какие datasets готовятся автоматически
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

Этого достаточно для demo-сценариев:
- browse databases
- browse datasets
- preview data
- explain fields
- recommend visualization
- create chart
- create dashboard
- open useful links

## Рекомендуемые demo-вопросы
- `Покажи выручку по магазинам`
- `Какие категории фильмов приносят больше всего выручки?`
- `Сделай график по платежам по месяцам`
- `Какие клиенты чаще всего арендуют фильмы?`
- `Покажи категории фильмов и среднюю длительность аренды`
- `Собери дашборд по выручке по магазинам и категориям`

## Быстрый smoke-check перед демо
1. В Superset откройте `Data -> Databases` и убедитесь, что есть `Pagila Demo (PostgreSQL)`.
2. В `Data -> Datasets` проверьте наличие `sales_by_store`, `sales_by_film_category`, `payment`, `rental`.
3. В ассистенте выполните:
   - browse databases
   - preview `sales_by_store` или `payment`
   - recommendation на `sales_by_film_category`
   - chart creation
   - dashboard creation
4. Убедитесь, что generated links открываются на том же `SUPERSET_PUBLIC_URL`.

## Что still requires manual runtime validation
- первый полный bootstrap контейнеров и загрузка Pagila SQL
- фактическое появление источника и datasets в UI Superset
- end-to-end chat business-question flow against live Pagila data
- доступность generated chart/dashboard links из вашей demo-сети
