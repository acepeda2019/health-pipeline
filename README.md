# health-pipeline

Personal health data pipeline. Ingests data from Whoop, Withings, MyFitnessPal, Apple Health, and Zozofit into a local Postgres warehouse, transforms with dbt, and visualizes with Lightdash.

## Stack

| Layer | Tool |
|---|---|
| Orchestration | Apache Airflow 3.2.1 |
| Storage | Postgres 15 |
| Transformation | dbt |
| Visualization | Lightdash |
| Object storage | MinIO (S3-compatible, used by Lightdash for query result pagination) |
| Containers | Docker Compose |
| IaC (Phase 3) | Terraform |

## Data sources

| Source | Frequency | Method |
|---|---|---|
| Whoop | Daily | API |
| MyFitnessPal | Daily | API |
| Apple Health | Daily | Manual XML export → file sensor |
| Withings | Weekly | API |
| Zozofit | Weekly | Manual PDF export → file sensor |

## Getting started

### 1. Clone and configure

```bash
git clone https://github.com/YOUR_USERNAME/health-pipeline.git
cd health-pipeline
cp .env.example .env
# Edit .env with your credentials
```

### 2. Generate required keys

```bash
# Fernet key for Airflow
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# API secret key
openssl rand -hex 32
```

Paste both values into `.env`.

### 3. Start the stack

```bash
docker compose up airflow-init  # run once on first start
docker compose up -d
```

### 4. Set up dbt

Install dbt with the Postgres adapter, then configure your connection profile:

```bash
pip install dbt-postgres   # or: uv add dbt-postgres

cp dbt/profiles.yml.example ~/.dbt/profiles.yml
# Edit ~/.dbt/profiles.yml — set password to match POSTGRES_PASSWORD in .env
```

Verify the connection:

```bash
cd dbt
dbt debug
```

### 5. Log into Lightdash and connect the dbt project

**Web login (first visit only)** — this creates your Lightdash user account, separate from the CLI token below:

1. Open http://localhost:3000
2. Follow the "Create your account" prompt to set up an organization admin (any email/password — it's a local install with no mail server).
3. On future visits, log in with that same email/password at http://localhost:3000.

**CLI setup** — needed to register and push the dbt project into Lightdash:

```bash
npm install -g @lightdash/cli

# Generate a personal access token: log into the web UI above first, then
# Settings → Personal access tokens → Generate
lightdash login http://localhost:3000 --token <your_token>

cd dbt
lightdash deploy --create   # first time only — registers the project
```

After the initial deploy, use `lightdash deploy` (no `--create`) to push model changes.

Optional non-interactive alternative: the CLI also reads `LIGHTDASH_URL` and `LIGHTDASH_API_KEY` from the environment instead of `lightdash login` — set them in `.env` and `export $(grep -v '^#' .env | xargs)` before running CLI commands. The Docker stack itself never reads these two vars; they only matter if you use this alternative.

### 6. Access services

| Service | URL | Notes |
|---|---|---|
| Airflow | http://localhost:8080 | Auth disabled in local dev (`SIMPLE_AUTH_MANAGER_ALL_ADMINS=True`) |
| Lightdash | http://localhost:3000 | See step 5 — create an account on first visit |
| Postgres | localhost:5432 | Credentials in `.env` |
| MinIO console | http://localhost:9001 | Login `minio` / `minio123` — backs Lightdash's query result storage, no manual setup needed |

### 7. Drop manual exports

```
data/raw/apple_health/   ← export.xml from iPhone Health app
data/raw/zozofit/        ← scan PDF from Zozofit app
```

## Troubleshooting

**Lightdash can't connect to Postgres over SSL.** The official `postgres:15` image ships with SSL
disabled, but Lightdash's Postgres client attempts an SSL handshake by default and fails to connect.
Fixed by setting `PGSSLMODE: disable` on the `lightdash` service in `docker-compose.yml` — already in
place, no action needed on a fresh clone. Revisit this when migrating to GCP (Phase 3), since a
production Postgres/Cloud SQL instance should have SSL enforced rather than disabled.

## Project structure

```
health-pipeline/
├── docker-compose.yml
├── .env.example
├── airflow/
│   └── dags/            # one DAG per source
├── dbt/
│   ├── dbt_project.yml
│   ├── profiles.yml.example   # committed template
│   └── models/
│       ├── staging/     # typed, validated source models
│       └── marts/       # clean metrics for Lightdash
├── data/
│   └── raw/             # gitignored — manual file inbox
├── postgres/
│   └── init.sql         # schema setup
└── terraform/           # Phase 3 — GCP infra
```

## Phases

- **Phase 1** — Local MVP: all sources ingesting, basic dbt models, Lightdash dashboard
- **Phase 2** — Harden: dbt tests, data quality checks, stable schema
- **Phase 3** — GCP: VM deploy, BigQuery, Terraform, Secret Manager
