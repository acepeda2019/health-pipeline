# Development Log

This document tracks the development history of the health pipeline — decisions made, problems encountered, and how they were resolved. Reference this at the start of new sessions to restore context quickly.

---

## Current State (as of 2026-05-01)

**Phase:** 1 — Local MVP  
**What's working:** Whoop ingestion DAG running daily, data landing in Postgres, dbt staging views for recovery and sleep  
**What's next:** Remaining data sources (Withings, MFP, Apple Health, Zozofit), dbt marts, Lightdash dashboards

---

## Session 1 — Stack Setup & Lightdash

**Goals:** Get the full Docker Compose stack running and connect Lightdash.

**Steps:**
1. Confirmed `docker-compose.yml` had all services (Airflow, Postgres, Lightdash)
2. Lightdash login via CLI: `lightdash login http://localhost:3000 --token <pat>`
3. `lightdash deploy --create` failed — no `dbt_project.yml` existed yet

**dbt Setup:**
- Created `dbt/dbt_project.yml` with staging/marts schema config
- Created `dbt/profiles.yml.example` as committed template
- Created `dbt/profiles.yml` (gitignored) with real credentials
- dbt looks in `~/.dbt/profiles.yml` by default — copied local profiles there
- Ran `dbt debug` to verify Postgres connection
- Ran `lightdash deploy --create` to register project with Lightdash

**Outcome:** Lightdash connected and accessible at `localhost:3000`

---

## Session 2 — Whoop OAuth2 & First DAG

**Goals:** Get Whoop API credentials and build the daily ingestion DAG.

### Whoop OAuth2 Setup

**How Whoop auth works:**
- Register an app at developer.whoop.com to get client_id + client_secret
- Complete a one-time OAuth2 browser flow to get access_token + refresh_token
- Access tokens expire in 1 hour; refresh tokens are used to get new ones automatically
- Whoop does not have a UI to generate tokens — the OAuth flow is required

**Issues encountered:**
- Redirect URI in Whoop developer portal must exactly match the script (`http://localhost:9090/callback`) — using port 8080 conflicts with Airflow
- Whoop requires a `state` parameter ≥ 8 characters — added `secrets.token_hex(16)`
- Whoop uses `client_secret_post` auth (credentials in POST body), not `client_secret_basic` (Basic auth header)
- Cloudflare blocks requests without a browser User-Agent header

**Script:** `scripts/whoop_auth.py` — runs a local server on port 9090, opens browser, captures callback, exchanges code for tokens.

### DAG Architecture

The `whoop_ingest` DAG (`airflow/dags/whoop_ingest.py`) has this task graph:

```
ensure_token → get_window → [fetch_recovery, fetch_sleep, fetch_workouts]
```

- **ensure_token:** Refreshes OAuth2 token before parallel tasks run (prevents race condition where all three tasks try to refresh simultaneously with a single-use refresh token)
- **get_window:** Derives `start`/`end` date window from Airflow's `logical_date` (critical for backfills — using `date.today()` caused all backfill runs to fetch the same day)
- **fetch_recovery/sleep/workouts:** Hit Whoop API, upsert results to `raw.whoop_events`

**Token storage:** Stored in `raw.tokens` Postgres table (not Airflow Variables) — Airflow 3 blocks database connection string access from tasks, and Variables require HTTP calls to the API server which can fail.

### Airflow 3.x Issues Resolved

**Connection refused (httpx.ConnectError):**  
Airflow 3 uses a new Task SDK architecture. Task workers connect to an "execution API" server. The LocalExecutor defaults to `http://localhost:8080/execution/` but in Docker the API server is in a different container (`airflow-webserver`).  
**Fix:** Add `AIRFLOW__API__BASE_URL=http://airflow-webserver:8080` to the scheduler's environment in `docker-compose.yml`.

**Invalid auth token (Signature verification failed):**  
Airflow 3 Task SDK signs JWTs using `AIRFLOW__API_AUTH__JWT_SECRET`. If not set, each container generates a random key — scheduler and webserver then have mismatched keys.  
**Fix:** Set `AIRFLOW__API_AUTH__JWT_SECRET` to the same value in `.env` for all services.

**DAG not appearing in UI:**  
Airflow 3's `dag_processor.refresh_interval` defaults to 300 seconds (5 minutes). To force immediate refresh: `airflow dags reserialize`.  
**Fix for dev:** Set `AIRFLOW__DAG_PROCESSOR__REFRESH_INTERVAL=10` in `.env`.

**Deprecated imports:**  
`from airflow.decorators import dag, task` is deprecated in Airflow 3.  
**Fix:** Use `from airflow.sdk import dag, task`.

**Database connection blocked:**  
Airflow 3 blocks `AIRFLOW__DATABASE__SQL_ALCHEMY_CONN` inside tasks (returns `airflow-db-not-allowed:///`).  
**Fix:** Build the connection string from individual `POSTGRES_*` env vars instead.

### Whoop API Endpoint Discovery

Several endpoints return 404 vs the documented paths:

| Endpoint | Path | Notes |
|---|---|---|
| Recovery | `/developer/v2/recovery` | v2, not v1 |
| Sleep | `/developer/v2/activity/sleep` | v2, not v1 |
| Workout | `/developer/v1/activity/workout` | v1 works |
| Cycle | `/developer/v1/cycle` | Requires `read:cycles` scope (not requested) |

**Note:** Whoop returns 404 for unauthenticated/invalid-scope requests (not 401) on v2 endpoints — makes debugging harder. Test with a fresh token and `/developer/v1/user/profile/basic` to confirm token validity first.

**record_id column:** Changed from `BIGINT` to `TEXT` because recovery uses integer `cycle_id` but sleep uses UUID `id`.

### Backfill

- Ran a backfill from 2026-04-01 to 2026-04-30 via the Airflow UI (Backfills tab)
- First backfill attempt only fetched 1 record — the DAG was using `date.today()` instead of `logical_date`, so all 30 runs fetched the same day
- Fixed by using `context["logical_date"]` in a `get_window` task
- Second backfill succeeded — 30 days of data landed

### dbt Staging Models

Two staging models created, both as views over `raw.whoop_events`:

- `stg_whoop__recovery` — parses `cycle_id`, recovery score, HRV, resting HR, SpO2, skin temp
- `stg_whoop__sleep` — parses sleep stages (light/SWS/REM), efficiency, consistency, performance scores, respiratory rate

**Key decision:** Staging models are views — no data copy, queries execute against raw table in real time. Marts will be materialized tables.

**dbt command:** Use `dbt run` (not `uv run dbt run`) after removing the `dbt-fusion` binary at `~/.local/bin/dbt` that was shadowing the venv's dbt.

---

## Schema Reference

```sql
-- Raw landing zone
raw.whoop_events   -- JSONB blobs from Whoop API (endpoint, record_id, data)
raw.tokens         -- OAuth2 token storage (key, value, updated_at)

-- dbt views (auto-updated, no dbt run needed)
staging.stg_whoop__recovery
staging.stg_whoop__sleep

-- dbt tables (run `dbt run --select marts` to refresh)
-- None yet
```

---

## Known Gaps / Next Steps

- [ ] `raw.tokens` table is created at runtime but not in `postgres/init.sql` — add it
- [ ] No dbt tests yet — add `not_null`, `unique` to staging models
- [ ] No marts models yet — needed for Lightdash dashboards
- [ ] Remaining data sources not started: Withings, MFP, Apple Health, Zozofit
- [ ] Whoop workout data ingested but not modeled in dbt (no `stg_whoop__workout.sql`)
- [ ] Token refresh logic runs every DAG run (expires_at=0 resets after each auth script run) — should persist properly once token management is stable

---

## Common Commands

```bash
# Start stack
docker compose up -d

# Force Airflow to pick up DAG changes immediately
docker compose exec airflow-scheduler airflow dags reserialize

# Trigger DAG manually
docker compose exec airflow-scheduler airflow dags trigger whoop_ingest

# Check data in Postgres
docker compose exec postgres psql -U health -d health_pipeline

# Refresh Whoop tokens (when expired)
uv run scripts/whoop_auth.py
# Then update raw.tokens:
source .env && docker compose exec postgres psql -U health -d health_pipeline -c "
  UPDATE raw.tokens SET value = '$WHOOP_ACCESS_TOKEN' WHERE key = 'whoop_access_token';
  UPDATE raw.tokens SET value = '$WHOOP_REFRESH_TOKEN' WHERE key = 'whoop_refresh_token';
  UPDATE raw.tokens SET value = '0' WHERE key = 'whoop_token_expires_at';"

# Run dbt
cd dbt && dbt run
cd dbt && dbt run --select staging
cd dbt && dbt show --select stg_whoop__recovery --limit 5

# Deploy to Lightdash
cd dbt && lightdash deploy
```
