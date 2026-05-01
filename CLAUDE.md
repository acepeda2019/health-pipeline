# Health Pipeline — Claude Context

This file gives Claude Code full context on this project. Read it before making any changes.

**At the start of every session:** read `docs/dev-log/index.md` to restore current state, then open the most recent session file if you need detail on recent decisions.

---

## Project goal

Personal health data pipeline built as a learning project for end-to-end data engineering.
Primary goals: understand real-world pipeline architecture, GCP infrastructure, and the full
dev → staging → production lifecycle. Health insights are secondary.

## Owner

- Male, 36, 5'7", 163 lbs
- Goal: weight loss / body recomp
- Right ankle injury (recurring since 2023, most recently reinjured surfing)
- Fitness: 3–4 workouts/week, mixed strength + cardio

---

## Architecture phases

### Phase 1 — Local MVP (current)
Docker Compose on local machine. Airflow + Postgres + dbt + Lightdash.
Goal: get all sources ingesting, validate data quality, understand what metrics matter.

### Phase 2 — Harden
Fix schema issues found in Phase 1. Add dbt tests. Nail down stable schema.
Goal: a data model you're confident promoting to production.

### Phase 3 — GCP productionization
Migrate to GCP VM running same Docker Compose stack, swap Postgres for BigQuery,
add Terraform, Secret Manager, Cloud Monitoring.
Goal: always-on, resilient, good GCP learning project.

### Phase 4 — Observability
Airflow alerting, dbt source freshness tests, row count anomaly detection.
Goal: a pipeline you trust vs one you babysit.

---

## Data sources

| Source | Frequency | Method | Data |
|---|---|---|---|
| Whoop | Daily | API (OAuth2) | Sleep, recovery, HRV, strain |
| MyFitnessPal | Daily | Unofficial API | Nutrition, calories, macros |
| Apple Health | Daily | Manual XML export → FileSensor | General aggregator |
| Withings | Weekly | API (OAuth2) | Weight |
| Zozofit | Weekly | Manual PDF export → FileSensor | Body measurements |

### DAG schedules
- `@daily` → whoop_ingest, mfp_ingest, apple_health_sensor
- `@weekly` → withings_ingest, zozofit_sensor

---

## Stack

| Layer | Tool | Notes |
|---|---|---|
| Orchestration | Apache Airflow 3.2.1 | LocalExecutor, Simple auth manager |
| Storage | Postgres 15 | Dual purpose: Airflow metadata + health warehouse |
| Transformation | dbt | Connects to Postgres |
| Visualization | Lightdash | Connects to Postgres marts schema |
| Containers | Docker Compose | Single file, all services |
| IaC (Phase 3) | Terraform | GCP resources |
| Python | 3.12 via uv | uv for dependency management |

---

## Services & ports

| Service | Local URL | Container port | Notes |
|---|---|---|---|
| Airflow UI | http://localhost:8080 | 8080 | `api-server` command (renamed in Airflow 3) |
| Lightdash | http://localhost:3000 | 8080 | Host 3000 → container 8080 |
| Postgres | localhost:5432 | 5432 | |

---

## Postgres schemas

```sql
raw      -- landing zone: raw JSON blobs from APIs, parsed file data
staging  -- validated, typed rows
marts    -- dbt-produced clean models for Lightdash
```

`graphile_worker` and `public` schemas are created by Lightdash and Postgres respectively — leave them alone.

---

## Key Airflow 3.x breaking changes (vs 2.x)

- `airflow webserver` → renamed to `airflow api-server`
- `AIRFLOW__WEBSERVER__SECRET_KEY` → renamed to `AIRFLOW__API__SECRET_KEY`
- Auth manager: Airflow 3 defaults to **Simple auth manager**, not FAB
  - Users defined via `AIRFLOW__CORE__SIMPLE_AUTH_MANAGER_USERS=username:role`
  - Passwords are auto-generated and printed in webserver logs
  - Saved to `$AIRFLOW_HOME/simple_auth_manager_passwords.json.generated`
  - For local dev, disable auth entirely: `AIRFLOW__CORE__SIMPLE_AUTH_MANAGER_ALL_ADMINS=True`
- `airflow users create` CLI command broken in Airflow 3 with FAB provider
- DB init uses `_AIRFLOW_DB_MIGRATE=true` env var pattern

---

## Environment variables (.env — never commit)

```bash
# Postgres
POSTGRES_USER=health
POSTGRES_PASSWORD=<your_password>
POSTGRES_DB=health_pipeline

# Airflow core
AIRFLOW__CORE__EXECUTOR=LocalExecutor
AIRFLOW__CORE__LOAD_EXAMPLES=False
AIRFLOW__CORE__FERNET_KEY=<generated>
AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=postgresql+psycopg2://health:<password>@postgres:5432/health_pipeline
AIRFLOW__API__SECRET_KEY=<generated>
AIRFLOW__CORE__SIMPLE_AUTH_MANAGER_ALL_ADMINS=True  # local dev only

# Whoop
WHOOP_CLIENT_ID=
WHOOP_CLIENT_SECRET=

# Withings
WITHINGS_CLIENT_ID=
WITHINGS_CLIENT_SECRET=
WITHINGS_ACCESS_TOKEN=
WITHINGS_REFRESH_TOKEN=

# MyFitnessPal
MFP_USERNAME=
MFP_PASSWORD=

# File paths (inside container)
RAW_DATA_PATH=/opt/airflow/data/raw
```

Generate keys:
```bash
# Fernet key
uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# API secret key
openssl rand -hex 32
```

---

## Docker Compose notes

- YAML anchors (`&airflow-common` / `<<: *airflow-common`) used for DRY config across Airflow services
- YAML merge is **shallow** — if a service defines its own `environment` block it replaces the anchor's entirely
- Solution: keep all `AIRFLOW__` vars in `.env` (loaded via `env_file`), only put service-specific vars in `environment` blocks
- `airflow-init` runs once on first boot: migrates DB, creates admin user
- Lightdash runs on ARM64 Mac via `platform: linux/amd64` (Rosetta emulation)
- Lightdash internal port is 8080, mapped to host port 3000: `"3000:8080"`

---

## Raw file ingestion pattern

| Source | Pattern |
|---|---|
| API sources (Whoop, Withings, MFP) | Airflow DAG polls API → writes raw JSON to `raw` schema as JSONB |
| Apple Health | Manual XML export dropped into `./data/raw/apple_health/` → FileSensor DAG picks up |
| Zozofit | Manual PDF dropped into `./data/raw/zozofit/` → FileSensor DAG → pdfplumber parsing |

---

## dbt conventions

- `staging/` models — one per source, typed and validated, named `stg_<source>__<entity>`
- `marts/` models — clean joined metrics for Lightdash, named `mart_<domain>`
- Tests live in `dbt/tests/`
- `profiles.yml` is gitignored — use `profiles.yml.example` as template

---

## GCP migration plan (Phase 3)

Same Docker Compose file runs on a GCP e2-medium VM (~$27/mo).
Key changes from local:
- Secrets move from `.env` to GCP Secret Manager
- Postgres optionally replaced by BigQuery (requires DAG + dbt profile changes)
- DAGs synced from GitHub via git pull or Cloud Storage
- Systemd service auto-starts Docker Compose on VM boot
- `AIRFLOW__CORE__SIMPLE_AUTH_MANAGER_ALL_ADMINS` removed, proper auth configured

Terraform lives in `./terraform/` — not yet written (Phase 3).

---

## Decisions log

| Decision | Rationale |
|---|---|
| Airflow 3.2.1 not 2.x | Starting fresh, learn current version |
| LocalExecutor not CeleryExecutor | 5 sources, daily schedule — no need for distributed workers |
| Postgres not BigQuery for Phase 1 | Validate data quality locally before cloud infra investment |
| No data lake (GCS) in Phase 1 | API sources write directly to raw schema; file inbox for manual exports |
| uv not pip | Faster, modern Python package management |
| Lightdash not Looker/Tableau | Free, open source, connects directly to Postgres |
| Docker Compose not Cloud Composer | Learn infrastructure, not pay $300+/mo to abstract it away |
| Local MVP first, GCP second | Real-world dev pattern: dev → staging → prod |

---

## Things to consider as project evolves

- **Alembic**: currently using `postgres/init.sql` for schema setup. As tables evolve,
  consider migrating to Alembic for versioned, reversible schema migrations. First natural
  trigger: when you need to add/change columns after seeing real data.

- **MFP API**: MyFitnessPal has no official public API. Options:
  1. Unofficial Python library (`myfitnesspal`)
  2. Gmail weekly digest parsing (Gmail connected in Claude project)
  3. Manual CSV export → FileSensor

- **Apple Health deduplication**: XML exports contain cumulative history with duplicates.
  dbt staging model needs explicit dedup logic (window functions on timestamp + source).

- **Withings weekly forward-fill**: weight data weekly means day-over-day trending requires
  forward-fill or interpolation in dbt between weekly readings.

- **Token refresh**: Whoop and Withings use OAuth2 with expiring access tokens.
  DAGs need a token refresh helper that runs before each API call.

---

## Common commands

```bash
# Start full stack
docker compose up -d

# First time setup
docker compose up airflow-init
docker compose up -d

# View logs
docker compose logs -f airflow-webserver
docker compose logs -f airflow-scheduler
docker compose logs -f lightdash

# Restart a service
docker compose restart airflow-webserver

# Full teardown (destroys all data)
docker compose down -v

# Connect to Postgres
docker compose exec postgres psql -U health -d health_pipeline

# List schemas
docker compose exec postgres psql -U health -d health_pipeline -c "\dn"

# Run dbt (once configured)
cd dbt && dbt run
cd dbt && dbt test

# Regenerate Fernet key
uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

## Project structure

```
health-pipeline/
├── CLAUDE.md                  # this file
├── docker-compose.yml         # full local stack
├── .env.example               # committed template
├── .env                       # gitignored — real credentials
├── .gitignore
├── README.md
├── pyproject.toml             # uv-managed Python dependencies
│
├── airflow/
│   ├── dags/                  # one DAG file per source
│   │   ├── whoop_ingest.py    # @daily, OAuth2 API
│   │   ├── mfp_ingest.py      # @daily, unofficial API
│   │   ├── apple_health_sensor.py  # @daily, FileSensor
│   │   ├── withings_ingest.py # @weekly, OAuth2 API
│   │   └── zozofit_sensor.py  # @weekly, FileSensor + PDF parse
│   ├── plugins/               # shared helpers (token refresh, etc.)
│   └── logs/                  # gitignored
│
├── dbt/
│   ├── dbt_project.yml
│   ├── profiles.yml.example   # committed template
│   ├── profiles.yml           # gitignored
│   ├── models/
│   │   ├── staging/           # stg_whoop__sleep.sql, etc.
│   │   └── marts/             # mart_recovery.sql, etc.
│   └── tests/
│
├── data/
│   └── raw/                   # gitignored
│       ├── apple_health/      # drop export.xml here
│       └── zozofit/           # drop scan PDF here
│
├── postgres/
│   └── init.sql               # creates raw, staging, marts schemas
│
└── terraform/                 # Phase 3 — GCP infra (not yet written)
    ├── main.tf
    ├── variables.tf
    └── outputs.tf
```
