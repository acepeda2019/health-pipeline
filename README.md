# health-pipeline

Personal health data pipeline. Ingests data from Whoop, Withings, MyFitnessPal, Apple Health, and Zozofit into a local Postgres warehouse, transforms with dbt, and visualizes with Lightdash.

## Stack

| Layer | Tool |
|---|---|
| Orchestration | Apache Airflow 3.2.1 |
| Storage | Postgres 15 |
| Transformation | dbt |
| Visualization | Lightdash |
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

### 5. Connect Lightdash

Install the Lightdash CLI and link it to your local instance:

```bash
npm install -g @lightdash/cli

# Generate a personal access token at http://localhost:3000 → Settings → API tokens
lightdash login http://localhost:3000 --token <your_token>

# Register the dbt project with Lightdash (run once)
cd dbt
lightdash deploy --create
```

After the initial deploy, use `lightdash deploy` (no `--create`) to push model changes.

### 6. Access services

| Service | URL | Notes |
|---|---|---|
| Airflow | http://localhost:8080 | Auth disabled in local dev (`SIMPLE_AUTH_MANAGER_ALL_ADMINS=True`) |
| Lightdash | http://localhost:3000 | Set up on first visit |
| Postgres | localhost:5432 | Credentials in `.env` |

### 7. Drop manual exports

```
data/raw/apple_health/   ← export.xml from iPhone Health app
data/raw/zozofit/        ← scan PDF from Zozofit app
```

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
