# Dev Log Index

Read this at the start of every session to restore context. For deep detail on a specific problem, open the relevant session file.

---

## Current State (2026-05-01)

**Phase:** 1 — Local MVP
**Stack:** Airflow 3.2.1 + Postgres 15 + dbt + Lightdash, all via Docker Compose

**Working:**
- Whoop ingestion DAG running daily (`whoop_ingest`) — recovery, sleep, workouts
- Data landing in `raw.whoop_events` (JSONB)
- OAuth2 token auto-refresh via `raw.tokens` Postgres table
- dbt staging views: `staging.stg_whoop__recovery`, `staging.stg_whoop__sleep`
- Lightdash connected at `localhost:3000`
- 30 days of backfill loaded (2026-04-01 → 2026-04-30)

**Not yet started:**
- Withings, MFP, Apple Health, Zozofit ingestion DAGs
- dbt marts models (needed for Lightdash dashboards)
- dbt tests (`not_null`, `unique`)
- `stg_whoop__workout` staging model

**Known gaps:**
- `raw.tokens` table is created at DAG runtime, not in `postgres/init.sql`
- Token refresh always runs (expires_at resets to 0 after each `whoop_auth.py` run)

**Dev log:**
- Per-session files in `docs/dev-log/`, index stays lean
- Use `/session-log` at end of each session to generate and commit the log

---

## Sessions

| # | Date | Focus | File |
|---|------|-------|------|
| 1 | 2026-04-?? | Stack setup, Lightdash connection, dbt scaffold | [session-001.md](session-001.md) |
| 2 | 2026-05-01 | Whoop OAuth2, daily ingest DAG, Airflow 3.x debugging, dbt staging models, backfill | [session-002.md](session-002.md) |
| 3 | 2026-05-01 | im trying to start up lightdash. npm install -g npm@11.13... | [session-003.md](session-003.md) |
| 4 | 2026-05-01 | Dev log restructure, session logging automation via `/session-log` skill | [session-004.md](session-004.md) |
