# Session 1 — Stack Setup & Lightdash

## Goals
Get the full Docker Compose stack running and connect Lightdash.

## Steps

1. Confirmed `docker-compose.yml` had all services (Airflow, Postgres, Lightdash)
2. Lightdash login via CLI: `lightdash login http://localhost:3000 --token <pat>`
3. `lightdash deploy --create` failed — no `dbt_project.yml` existed yet

## dbt Setup

- Created `dbt/dbt_project.yml` with staging/marts schema config
- Created `dbt/profiles.yml.example` as committed template
- Created `dbt/profiles.yml` (gitignored) with real credentials
- dbt looks in `~/.dbt/profiles.yml` by default — copied local profiles there
- Ran `dbt debug` to verify Postgres connection
- Ran `lightdash deploy --create` to register project with Lightdash

## Outcome

Lightdash connected and accessible at `localhost:3000`.
