# Demo Defence Script

Цель документа: дать оператору готовый demo script для текущего продукта на
`Next.js + FastAPI`, основанный на реальных доступных flow:
- `login/register`
- `chat`
- `preview`
- `recommend`
- `share`
- `scan`

Основной demo source:
- `Pagila Demo (PostgreSQL)`

## Preconditions

Перед live demo убедитесь, что:
- `assistant-web`, `assistant-api`, `superset`, `mcp-http`, `pagila-db` подняты;
- login работает;
- в Superset видны datasets:
  - `sales_by_store`
  - `sales_by_film_category`
  - `payment`
- generated links открываются на том же `SUPERSET_PUBLIC_URL`.

## 1. Short 5-Minute Demo Path

### Step 1. Open The Product
- What to click:
  - открыть `/login`
  - войти под demo user
- What to say:
  - `Это единый assistant на Next.js + FastAPI. Основной сценарий business-first: можно задать вопрос, посмотреть данные, подобрать график и сразу открыть результат в Superset.`
- What to point out:
  - single supported stack;
  - main navigation: `Чат`, `Предпросмотр`, `Рекомендации`, `Шеринг`, `Сканер схем`.

### Step 2. Show Business Question In Chat
- What to click:
  - открыть `/app/chat`
- Prompt to enter:
  - `Покажи выручку по магазинам`
- What to say:
  - `Начинаем с бизнес-вопроса, без SQL и без ручного выбора таблицы.`
- What result to point out:
  - user message appears immediately;
  - assistant gives business-oriented answer;
  - chat can serve as the top-level entry point.

### Step 3. Show The Data Behind The Answer
- What to click:
  - перейти в `/app/preview`
  - выбрать `Pagila Demo (PostgreSQL)` and `sales_by_store`
  - нажать `Быстро посмотреть данные`
- What to say:
  - `Если нужно понять, что именно лежит в данных, можно быстро посмотреть строки и описания полей.`
- What result to point out:
  - rows visible;
  - field explanations visible;
  - this step is optional but useful.

### Step 4. Show Recommendation
- What to click:
  - перейти в `/app/recommend`
  - нажать `Подобрать тип графика`
- What to say:
  - `Следующий шаг использует контекст preview и подсказывает, как лучше визуализировать вопрос.`
- What result to point out:
  - recommendation is not blank;
  - preview context carried forward;
  - selected chart type makes sense.

### Step 5. Create And Open Result
- What to click:
  - перейти в `/app/share`
  - нажать `Создать виджет`
- What to say:
  - `Финальный шаг создаёт chart и dashboard через существующий backend flow и сразу даёт рабочие ссылки.`
- What result to point out:
  - chart created;
  - dashboard created;
  - useful links open in Superset.

## 2. Full 10-12 Minute Demo Path

### Step 1. Frame The Product
- What to click:
  - login and open `/app/chat`
- What to say:
  - `Продукт поддерживает два естественных пути: можно начать с бизнес-вопроса, либо сначала открыть данные и понять поля.`
- What result to point out:
  - navigation reflects these two entry paths.

### Step 2. Business Chat Scenario
- Prompt to enter:
  - `Какие категории фильмов приносят больше всего выручки?`
- What to say:
  - `Это типичный запрос менеджера или аналитика: вопрос не про таблицу, а про вывод.`
- What result to point out:
  - assistant stays in business scope;
  - answer is useful even before deep technical setup.

### Step 3. Multi-Chat Confidence
- What to click:
  - создать `Новый чат`
- Prompt to enter:
  - `Сделай график по платежам по месяцам`
- What to say:
  - `У пользователя может быть несколько независимых диалогов: один про категории, другой про платежи.`
- What result to point out:
  - first reply appears without refresh;
  - chat list and active chat stay stable;
  - histories do not mix.

### Step 4. Preview For Analytical Confidence
- What to click:
  - открыть `/app/preview`
  - database `Pagila Demo (PostgreSQL)`
  - dataset `payment`
  - нажать `Быстро посмотреть данные`
- What to say:
  - `Preview нужен, если хочется быстро увидеть реальные строки и понять поля до настройки графика.`
- What result to point out:
  - rows;
  - field explanations;
  - preview context is visible and concrete.

### Step 5. Recommendation
- What to click:
  - открыть `/app/recommend`
  - нажать `Подобрать тип графика`
- What to say:
  - `Рекомендация использует уже просмотренные строки и поля, чтобы не заставлять пользователя выбирать всё руками.`
- What result to point out:
  - no empty/confusing state after preview;
  - recommended type, metric and grouping look plausible.

### Step 6. Share / Create Widget
- What to click:
  - открыть `/app/share`
  - проверить prefilled dataset, chart type and fields
  - нажать `Создать виджет`
- What to say:
  - `В конце path мы уже не теряем контекст: тип графика и данные частично перенесены автоматически.`
- What result to point out:
  - form is meaningfully prefilled;
  - chart/dashboard links appear;
  - share page feels like continuation, not a separate tool.

### Step 7. Scan As Optional Support Flow
- What to click:
  - открыть `/app/scan`
  - нажать `Запустить сканирование`
- What to say:
  - `Если нужно понять, откуда assistant берёт знание об источниках, можно запустить scan и увидеть базы, таблицы и связи.`
- What result to point out:
  - database candidates;
  - profiled tables;
  - relations overview.

### Step 8. Security / Safety Finish
- What to click:
  - вернуться в `/app/chat`
- Prompt to enter:
  - `DELETE FROM payment WHERE 1=1`
- What to say:
  - `Продукт не только помогает строить аналитику, но и намеренно блокирует небезопасные запросы.`
- What result to point out:
  - clear safe denial;
  - blocked behavior looks intentional.

## 3. Backup Demo Path

Use this path if chat quality or a specific business answer is flaky during the
demo.

### Backup Step 1. Skip Chat
- What to click:
  - открыть `/app/preview`
- What to say:
  - `Даже если начать не с чата, продукт позволяет быстро перейти от данных к результату.`

### Backup Step 2. Preview A Reliable Dataset
- What to click:
  - `Pagila Demo (PostgreSQL)`
  - dataset `sales_by_film_category`
  - `Быстро посмотреть данные`
- What result to point out:
  - rows and field explanations appear quickly.

### Backup Step 3. Recommend A Chart
- What to click:
  - открыть `/app/recommend`
  - `Подобрать тип графика`
- What result to point out:
  - recommendation appears with carried context.

### Backup Step 4. Create Widget
- What to click:
  - открыть `/app/share`
  - `Создать виджет`
- What result to point out:
  - working chart/dashboard links.

### Backup Step 5. Optional Scan
- What to click:
  - открыть `/app/scan`
  - `Запустить сканирование`
- What to say:
  - `Это supporting flow для понимания структуры источников, а не обязательный шаг.`

## 4. Demo Narration Notes

Use these phrases consistently:
- `Здесь сценарий business-first, а не SQL-first.`
- `Preview нужен, если сначала хочется увидеть данные и поля.`
- `Recommendation и Share продолжают уже начатый контекст, а не заставляют начинать заново.`
- `Scan — это support flow для понимания источников.`
- `Блокировка unsafe-запросов intentional и полезна, а не случайна.`

Avoid during defence:
- погружаться в MCP internals без прямого вопроса;
- перегружать зрителя schema names and ids;
- показывать scan раньше, чем value path.
