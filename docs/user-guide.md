# User Guide

This guide describes the current released product surface of the Superset AI
Assistant. It covers the real `Next.js + FastAPI + Superset + built-in MCP`
workflow and does not describe retired Streamlit screens or backend-only code
that is not exposed in the UI.

## What This Product Is

Superset AI Assistant helps analysts, demo users, and product teams work with
data in Apache Superset without starting every task from manual SQL.

The current product is best used for:

- asking analytical questions in natural language;
- previewing datasets before charting;
- choosing a visualization type from real previewed columns;
- creating charts and dashboards in Superset;
- discovering available PostgreSQL sources through the scan flow;
- demonstrating Pagila-based analytics flows end to end.

## Who It Is For

Primary audiences:

- business users who need a readable answer first;
- analysts who want faster navigation from question to dataset to chart;
- demo users who need a reliable Pagila workflow;
- developers and QA who need a practical UI path for smoke checks.

## Entry Points

Current UI routes:

| Route | What it does |
| --- | --- |
| `/login` | Sign in |
| `/register` | Create a local assistant account |
| `/app/chat` | Main assistant workflow |
| `/app/preview` | Preview rows and inspect columns |
| `/app/recommend` | Suggest a chart type |
| `/app/share` | Create a chart and a new dashboard |
| `/app/scan` | Scan databases, schemas, tables, and relations |

`/app` redirects to `/app/chat`.

## Sign In And Registration

### Register

1. Open `/register`.
2. Enter a username and password.
3. Click `Create account`.

What happens next:

- the account is created in the assistant auth store;
- the user is signed in immediately;
- the app redirects to `/app`.

### Sign In

1. Open `/login`.
2. Enter your username and password.
3. Click `Sign in`.

### Sign Out

Use the `Выйти` button at the bottom of the left sidebar.

## Navigation Basics

The left sidebar contains:

- main product windows;
- current user information;
- sign-out action;
- on `/app/chat`, the chat list and chat actions.

Responsive behavior:

- desktop: the sidebar stays visible and can be collapsed;
- mobile: the sidebar becomes a drawer opened from the top-left menu button.

## Main Working Modes

Use the product in one of three practical ways:

### 1. Direct question in chat

Best when you already know what you want to ask.

Examples:

- `Покажи выручку по магазинам`
- `Какие категории фильмов приносят больше всего выручки?`
- `Сделай график по платежам по месяцам`

### 2. Preview -> recommend -> share

Best when you want to validate columns before creating a chart.

This path is:

1. inspect rows and fields in `Предпросмотр`;
2. get a suggested chart type in `Рекомендации`;
3. create a chart and dashboard in `Шеринг`.

### 3. Scan -> preview/chat

Best when you do not know where the source data lives.

This path is:

1. run `Сканер схем`;
2. identify the likely database and dataset;
3. continue in `Предпросмотр` or `Чат`.

## Chat

`/app/chat` is the main product surface.

### What you can do there

- create a new chat;
- switch between chats;
- rename a chat;
- delete a chat;
- clear messages in the active chat;
- ask business or technical questions;
- build chart and dashboard flows directly from the conversation;
- reuse links and artifacts from previous assistant replies inside the same chat.

### How to send a message

1. Open `Чат`.
2. If needed, create a new chat with `Новый чат`.
3. Type your request into `Опишите задачу или вопрос по данным…`.
4. Press `Enter` to send or `Shift+Enter` for a new line.

### Chat settings

Each chat has its own persistent settings:

- `Режим ответа`: `Бизнес` or `Технический`
- `Глубина ответа`: `Кратко`, `Стандартно`, `Подробно`

Important behavior:

- settings are stored per chat session, not only in the current browser tab;
- changing settings in one chat does not change other chats;
- the setting bar can be collapsed to a compact summary;
- settings apply to subsequent assistant replies.

### Business vs technical mode

`Бизнес` mode is better when you want:

- a short conclusion;
- business meaning first;
- minimal implementation detail;
- faster decision support.

`Технический` mode is better when you want:

- more structure and assumptions;
- field-level or query-level detail;
- SQL-oriented context where available;
- explicit next steps for verification.

### Detail levels

`Кратко`:

- the shortest practical answer;
- use it for quick iteration and chat follow-ups.

`Стандартно`:

- the default balance between explanation and speed;
- use it for most everyday questions.

`Подробно`:

- more assumptions, context, and action items;
- use it when you need to understand why the answer was produced.

### Chat replies and artifacts

Assistant replies can include:

- formatted text;
- table preview artifacts;
- inline chart preview artifacts;
- labeled links such as `Открыть график`, `Открыть дашборд`, or
  `Открыть SQL Lab`.

Why this matters:

- you do not need to copy raw Superset URLs from the text body;
- a chart/dashboard created in one reply can be reused in a follow-up such as
  `дай ссылку на дашборд`;
- recent preview and link artifacts stay available in the same chat history.

### Chat help area

At the top of the chat page there is a helper area with:

- a short explanation of when to use chat vs preview;
- the `Как начать` help drawer;
- safe-mode guidance;
- on mobile, a header button to hide or show the helper area.

### Mobile notes for chat

On mobile:

- the chat helper area is hidden by default;
- the composer stays pinned to the bottom;
- message history scrolls independently;
- the top-left menu opens navigation;
- the top-right helper toggle shows or hides onboarding hints.

## Preview

`/app/preview` helps you inspect the actual data before asking for a chart or
recommendation.

### When to use it

Use preview when:

- you are not sure which dataset to use;
- you need to see sample rows;
- you want to inspect field types and explanations;
- you want recommendation/share pages to inherit real context.

### How to run preview

1. Open `Предпросмотр`.
2. Select a database.
3. Select a dataset/table.
4. Pick a preview template.
5. Choose a row limit.
6. Click `Быстро посмотреть данные`.

### What preview shows

After a successful run you get:

- result rows;
- row count and preview limit;
- profiled columns with inferred type and explanations;
- a field-focus panel for a selected column;
- CTA buttons to continue to recommendation or sharing.

### What carries over from preview

Preview context is stored in session state for the current browser session and
reused by:

- `Рекомендации`
- `Шеринг`

That shared context includes:

- database id;
- dataset id;
- preview SQL;
- dataset label;
- preview result and column profiles.

## Recommend

`/app/recommend` suggests a chart type based on the preview result.

### When to use it

Use recommendation when:

- you already previewed the data;
- you want help choosing between table, line, bar, pie, scatter, or area;
- you want the share form to be prefilled from a recommendation.

### How to get a recommendation

1. Open `Рекомендации` after running preview.
2. Optionally choose:
   - metric;
   - grouping dimension;
   - time field.
3. Click `Подобрать тип графика`.

### What you get

The page shows:

- the recommended chart type;
- selected metric/dimension/time fields;
- ranked candidate chart types with reasoning;
- preview rows for reference.

### Important limitation

Recommendation is only useful when preview already has data. If preview is
empty or has not been run, this step will tell you to go back to preview first.

## Share

`/app/share` is the chart-and-dashboard creation step.

### What it does

This page calls the existing backend share flow and creates:

- one chart;
- one new dashboard;
- links to both objects in Superset.

### How to create a chart and dashboard

1. Open `Шеринг`.
2. Select a Superset dataset.
3. Pick a chart type.
4. Fill or adjust:
   - dashboard title;
   - widget/chart title;
   - metric;
   - dimension;
   - time field;
   - row limit;
   - description.
5. Click `Создать виджет`.

### What is prefilled automatically

If you came from preview/recommend, the page may prefill:

- dataset;
- recommended chart type;
- metric/dimension/time selection;
- dashboard title;
- chart title;
- description.

### Result of a successful share flow

You receive:

- `Dashboard ID`
- `Chart ID`
- chart type
- dashboard link
- chart link
- chart params JSON

### Important limitation

The current UI always creates a new dashboard for the new widget. Adding the
chart to an existing dashboard is not exposed in this release UI.

## Scan

`/app/scan` is the source-discovery page.

### When to use it

Use scan when:

- you do not know which database contains the data;
- you need to confirm that a PostgreSQL source exists;
- you want to inspect profiled tables and relations;
- you want evidence before starting a Pagila demo flow.

### How to run it

1. Open `Сканер схем`.
2. Click `Запустить сканирование`.
3. Wait for the report to finish.

### What the report contains

- summary counts for candidates, PostgreSQL databases, tables, and relations;
- database candidate rows;
- profiled PostgreSQL databases;
- relation rows;
- per-database details;
- report path and raw report JSON.

### Important limitation

The scan flow is synchronous in the current UI. The page waits until the
backend returns the report.

## Pagila Demo Workflow

The current release explicitly supports Pagila-based demo flows.

### Fastest Pagila path in chat

Use prompts like:

- `Покажи выручку по магазинам в Pagila`
- `Сделай график по платежам по месяцам в Pagila`
- `Собери дашборд по Pagila`

What the assistant now does reliably:

- recognizes `Pagila Demo (PostgreSQL)` as a real source;
- uses database-level evidence, not only dataset-name guessing;
- creates actual chart/dashboard objects;
- preserves chart/dashboard links for follow-up prompts.

### Safer Pagila path for demos

1. Open `Сканер схем` and confirm `Pagila Demo (PostgreSQL)`.
2. Go to `Предпросмотр` and select a Pagila dataset.
3. Run preview.
4. Use `Рекомендации` if you want a guided chart type.
5. Finish in `Шеринг` or ask for a chart/dashboard directly in chat.

### Useful Pagila follow-ups

After a chart or dashboard is created in chat, you can ask:

- `дай ссылку на график`
- `дай ссылку на дашборд`
- `покажи preview этого графика`

## How To Build Charts

You can build charts in two ways.

### Option 1: from chat

Best when your request is already clear.

Example:

`Построй график выручки по магазинам в Pagila`

Expected result:

- assistant reply;
- inline preview artifact;
- chart link;
- sometimes SQL Lab link when applicable.

### Option 2: from preview -> recommend -> share

Best when you want more control.

Suggested path:

1. run preview;
2. get a recommendation;
3. confirm chart settings in share;
4. create the widget/dashboard pair.

## How To Build Dashboards

Dashboard creation is currently exposed in two ways.

### Option 1: ask in chat

Example:

`Собери дашборд по Pagila`

Expected result:

- multiple chart artifacts may be created internally;
- the final assistant reply returns a dashboard link;
- the link is kept in chat history for follow-ups.

### Option 2: use share page

The share page creates one chart and one new dashboard. Use this when you want
to control the chart parameters in a form.

## Preview And Links

There are two different concepts in the product:

### Inline preview

This is the compact artifact rendered inside chat or on the preview/share pages.
Use it to validate the result quickly without leaving the assistant UI.

### External link

This opens the full object in Superset. Use it when you need:

- full chart interactivity;
- the full dashboard page;
- SQL Lab context.

Practical advice:

- use preview to validate;
- use the link to continue work in Superset.

## Desktop And Mobile Notes

### Desktop

- sidebar is persistent;
- sidebar can be collapsed;
- chat helper area is visible by default;
- long chats keep the composer in place.

### Mobile

- sidebar opens as a drawer;
- helper area can be hidden from the top-right toggle on chat;
- sticky composer keeps the input visible;
- the chat surface takes priority over extra chrome.

## Typical Problems And What To Do

### I can sign in, but `/app` looks empty

Open `/app/chat` directly. `/app` should redirect there. If it does not, reload
after sign-in and confirm cookies are enabled.

### The assistant says the source is not found

Run `Сканер схем` first and confirm the expected database exists. Then continue
in `Предпросмотр` or restate the request with the database name, for example
`в Pagila`.

### I need a chart, but chat is still too vague

Switch to `Предпросмотр`, inspect the columns, then use `Рекомендации` and
`Шеринг`.

### I got a link but not enough detail

Open the link in Superset. The assistant UI intentionally shows a compact
preview, not the full Superset object.

### I changed response mode and another chat did not change

That is expected. Settings are stored per chat session.

### I want to add a chart to an existing dashboard

That is not available from the current release UI. The share page creates a new
dashboard.

### Scan takes time and the page waits

That is expected in the current version. The scan flow is synchronous.

## Short Decision Guide

If the business question is already clear:

- start with `Чат`.

If you need to inspect fields and rows first:

- start with `Предпросмотр`.

If you want help choosing a chart:

- continue with `Рекомендации`.

If you want a chart and dashboard created in Superset:

- finish in `Шеринг` or ask directly in `Чат`.

If you do not know where the data lives:

- start with `Сканер схем`.
