# Session 2 — Whoop OAuth2, Ingest DAG, Airflow 3.x Debugging

## Goals
Get Whoop API credentials, build the daily ingestion DAG, and get data into Postgres.

---

## Whoop OAuth2 Setup

**How Whoop auth works:**
- Register an app at developer.whoop.com → get `client_id` + `client_secret`
- Complete a one-time OAuth2 browser flow → get `access_token` + `refresh_token`
- Access tokens expire in 1 hour; refresh tokens auto-renew them
- No UI to generate tokens — the OAuth flow is required every time tokens expire completely

**Issues hit:**
- Redirect URI in Whoop developer portal must exactly match the script (`http://localhost:9090/callback`) — port 8080 conflicts with Airflow
- Whoop requires `state` param ≥ 8 chars — added `secrets.token_hex(16)`
- Whoop uses `client_secret_post` auth (credentials in POST body), not `client_secret_basic` (Basic auth header)
- Cloudflare blocks requests without a browser User-Agent header

**Script:** `scripts/whoop_auth.py` — local server on port 9090, opens browser, captures callback, exchanges code for tokens. Run with `uv run scripts/whoop_auth.py`.

---

## DAG Architecture

`airflow/dags/whoop_ingest.py` task graph:

```
ensure_token → get_window → [fetch_recovery, fetch_sleep, fetch_workouts]
```

- **ensure_token:** Refreshes OAuth2 token before parallel tasks run — prevents race condition where all three tasks try to refresh simultaneously with a single-use refresh token
- **get_window:** Derives `start`/`end` from Airflow's `logical_date` (critical for backfills — `date.today()` causes all backfill runs to fetch the same day)
- **fetch_recovery/sleep/workouts:** Hit Whoop API, upsert results to `raw.whoop_events`

**Token storage:** `raw.tokens` Postgres table (not Airflow Variables). Airflow 3 blocks `SQL_ALCHEMY_CONN` inside tasks, and Variables require HTTP calls to the API server which can fail.

---

## Airflow 3.x Issues Resolved

**Connection refused (httpx.ConnectError):**
Task workers connect to an "execution API" server. LocalExecutor defaults to `http://localhost:8080/execution/` but in Docker the API server is in a different container.
Fix: `AIRFLOW__API__BASE_URL=http://airflow-webserver:8080` in the scheduler's environment block in `docker-compose.yml`.

**Invalid auth token (Signature verification failed):**
Airflow 3 Task SDK signs JWTs using `AIRFLOW__API_AUTH__JWT_SECRET`. If not set, each container generates a random key — scheduler and webserver then have mismatched keys.
Fix: Set `AIRFLOW__API_AUTH__JWT_SECRET` to the same value in `.env` for all services.

**DAG not appearing in UI:**
`dag_processor.refresh_interval` defaults to 300s. Force immediate refresh: `airflow dags reserialize`.
Fix for dev: `AIRFLOW__DAG_PROCESSOR__REFRESH_INTERVAL=10` in `.env`.

**Deprecated imports:**
`from airflow.decorators import dag, task` is removed in Airflow 3.
Fix: `from airflow.sdk import dag, task`.

**Database connection blocked:**
Airflow 3 blocks `AIRFLOW__DATABASE__SQL_ALCHEMY_CONN` inside tasks (returns `airflow-db-not-allowed:///`).
Fix: Build connection string from `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` env vars directly.

**Race condition on token refresh:**
All 3 parallel tasks called `_refresh()` simultaneously — the single-use refresh token was consumed by the first, causing the other two to 500/400.
Fix: Added `ensure_token` task as upstream dependency before any parallel fetch tasks.

**XCom tuple indexing:**
`window[0]` fails — Airflow 3 XCom only supports string key lookup.
Fix: Return `{"start": ..., "end": ...}` dict and access as `window["start"]`, `window["end"]`.

---

## Whoop API Endpoint Discovery

Several endpoints 404 vs the documented paths:

| Endpoint | Working Path | Notes |
|---|---|---|
| Recovery | `/developer/v2/recovery` | v2, not v1 |
| Sleep | `/developer/v2/activity/sleep` | v2, not v1 |
| Workout | `/developer/v1/activity/workout` | v1 works |

Whoop returns 404 (not 401) for unauthenticated/wrong-scope requests on v2 endpoints — makes debugging harder. Test with `/developer/v1/user/profile/basic` first to confirm token validity.

**record_id column:** Changed from `BIGINT` to `TEXT` — recovery uses integer `cycle_id` but sleep uses UUID `id`.

---

## Backfill

- Ran backfill 2026-04-01 → 2026-04-30 via Airflow UI (Backfills tab)
- First attempt: only 1 record fetched — DAG used `date.today()`, all 30 runs fetched the same day
- Fixed: `get_window` task using `context["logical_date"]`
- Second backfill: 30 days of data landed correctly

---

## dbt Staging Models

Two staging views created over `raw.whoop_events`:

- `stg_whoop__recovery` — cycle_id, recovery score, HRV, resting HR, SpO2, skin temp
- `stg_whoop__sleep` — sleep stages (light/SWS/REM in ms), efficiency, consistency, performance %, respiratory rate

Staging models are views — no data copy, queries execute against the raw table in real time. Marts will be materialized tables.

**dbt command:** Use `dbt run` (not `uv run dbt run`) after removing the `dbt-fusion` binary at `~/.local/bin/dbt` that was shadowing the venv's dbt. Remove with: `rm ~/.local/bin/dbt`.

---

## Misc

- `.env` accidentally got shell command text pasted into it — caused "unexpected character" parse error. Always edit `.env` with an editor, not by appending from terminal.
- Lightdash internal port is 8080, mapped to host 3000: `"3000:8080"` in docker-compose.yml.
