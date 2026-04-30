# health-pipeline

Personal health data pipeline. Ingests data from Whoop, Withings, MyFitnessPal, Apple Health, and Zozofit into a local Postgres warehouse, transforms with dbt, and visualizes with Lightdash.

## Stack

| Layer | Tool |
|---|---|
| Orchestration | Apache Airflow 2.8 |
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

# Webserver secret key
openssl rand -hex 32
```

Paste both values into `.env`.

### 3. Start the stack

```bash
docker compose up airflow-init  # run once on first start
docker compose up -d
```

### 4. Access services

| Service | URL | Default credentials |
|---|---|---|
| Airflow | http://localhost:8080 | admin / admin |
| Lightdash | http://localhost:3000 | set on first visit |
| Postgres | localhost:5432 | see .env |

### 5. Drop manual exports

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
- **Phase 3** — GCP: migrate to Cloud Composer, BigQuery, Terraform
