# Lightdash Whoop Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `mart_daily_health` dbt model joining Whoop recovery + sleep data, mount it into Lightdash, and configure Lightdash to surface it as an explorable dataset for dashboards.

**Architecture:** A single dbt mart model (`mart_daily_health`) joins `stg_whoop__recovery` and `stg_whoop__sleep` on `cycle_id`, computes derived sleep metrics, and materializes as a Postgres table in the `marts` schema. Lightdash connects to this via a dbt local CLI connection, reading the compiled project from a shared Docker volume. Dashboards are built in the Lightdash UI after connection is verified.

**Tech Stack:** dbt Core, Postgres 15, Lightdash (self-hosted Docker), Docker Compose

---

## File Map

| Action | File | Purpose |
|---|---|---|
| Create | `dbt/models/marts/mart_daily_health.sql` | Wide join of recovery + sleep, computed columns |
| Create | `dbt/models/marts/schema.yml` | Column descriptions + dbt tests for Lightdash metadata |
| Modify | `docker-compose.yml` | Mount `./dbt:/dbt` into Lightdash container |

---

## Task 1: Write mart_daily_health SQL model

**Files:**
- Create: `dbt/models/marts/mart_daily_health.sql`

- [ ] **Step 1: Create the mart model**

Create `dbt/models/marts/mart_daily_health.sql` with this content:

```sql
with recovery as (
    select * from {{ ref('stg_whoop__recovery') }}
),

sleep as (
    select * from {{ ref('stg_whoop__sleep') }}
    where is_nap = false
)

select
    r.created_at::date                                                        as date,
    r.cycle_id,

    -- recovery
    r.recovery_score,
    r.hrv_rmssd_milli,
    r.resting_heart_rate,
    r.spo2_percentage,
    r.skin_temp_celsius,
    false::boolean                                                            as is_cpap_night,

    -- sleep timestamps
    s.sleep_start,
    s.sleep_end,

    -- computed sleep hours
    round(
        (s.total_in_bed_time_milli - s.total_awake_time_milli) / 3600000.0, 2
    )                                                                         as total_sleep_hours,
    round(
        (s.total_slow_wave_sleep_time_milli + s.total_rem_sleep_time_milli) / 3600000.0, 2
    )                                                                         as restorative_sleep_hours,
    round(s.total_slow_wave_sleep_time_milli / 3600000.0, 2)                 as slow_wave_hours,
    round(s.total_rem_sleep_time_milli / 3600000.0, 2)                       as rem_hours,

    -- sleep scores
    s.sleep_performance_pct,
    s.sleep_efficiency_pct,
    s.disturbance_count

from recovery r
left join sleep s on r.cycle_id = s.cycle_id
```

- [ ] **Step 2: Run the model**

From the repo root (with dbt configured and Postgres running):

```bash
cd dbt && dbt run -s mart_daily_health
```

Expected output:
```
1 of 1 START sql table model marts.mart_daily_health ......................... [RUN]
1 of 1 OK created sql table model marts.mart_daily_health .................... [SELECT 30 in X.XXs]
```

If you see `0 rows`, confirm the staging views have data:
```bash
docker compose exec postgres psql -U health -d health_pipeline \
  -c "SELECT count(*) FROM staging.stg_whoop__recovery;"
```

- [ ] **Step 3: Verify rows and spot-check columns**

```bash
docker compose exec postgres psql -U health -d health_pipeline -c "
SELECT date, recovery_score, hrv_rmssd_milli, total_sleep_hours, restorative_sleep_hours, is_cpap_night
FROM marts.mart_daily_health
ORDER BY date DESC
LIMIT 5;
"
```

Expected: 5 rows with non-null `date`, `recovery_score`, and numeric sleep hours. `is_cpap_night` should be `f` (false) for all rows.

- [ ] **Step 4: Commit**

```bash
git add dbt/models/marts/mart_daily_health.sql
git commit -m "feat: add mart_daily_health wide table joining recovery and sleep"
```

---

## Task 2: Add schema.yml with column descriptions and tests

**Files:**
- Create: `dbt/models/marts/schema.yml`

This file does two things: adds column metadata that Lightdash surfaces as labels/descriptions in the UI, and adds dbt data quality tests.

- [ ] **Step 1: Create the schema file**

Create `dbt/models/marts/schema.yml`:

```yaml
version: 2

models:
  - name: mart_daily_health
    description: "One row per night. Joins Whoop recovery and sleep data on cycle_id. Naps excluded."
    columns:
      - name: date
        description: "Calendar date of the recovery/sleep record"
        tests:
          - not_null
          - unique
      - name: cycle_id
        description: "Whoop cycle ID — primary key"
        tests:
          - not_null
          - unique
      - name: recovery_score
        description: "Whoop recovery score 0–100. Higher is better readiness."
        tests:
          - not_null
      - name: hrv_rmssd_milli
        description: "Heart rate variability in milliseconds. Inflated on non-CPAP nights."
      - name: resting_heart_rate
        description: "Resting heart rate in BPM"
      - name: spo2_percentage
        description: "Blood oxygen percentage. Dips on non-CPAP nights."
      - name: skin_temp_celsius
        description: "Skin temperature in Celsius"
      - name: is_cpap_night
        description: "Whether CPAP was worn. Currently hardcoded false — placeholder for future data."
      - name: sleep_start
        description: "Timestamp when sleep session started"
      - name: sleep_end
        description: "Timestamp when sleep session ended"
      - name: total_sleep_hours
        description: "Total sleep time in hours (in-bed time minus awake time)"
      - name: restorative_sleep_hours
        description: "Slow wave + REM sleep in hours — the most recovery-relevant sleep"
      - name: slow_wave_hours
        description: "Deep (slow wave) sleep in hours"
      - name: rem_hours
        description: "REM sleep in hours"
      - name: sleep_performance_pct
        description: "Whoop's overall sleep performance score 0–100"
      - name: sleep_efficiency_pct
        description: "Percentage of time in bed spent asleep"
      - name: disturbance_count
        description: "Number of sleep disturbances detected"
```

- [ ] **Step 2: Run dbt tests**

```bash
cd dbt && dbt test -s mart_daily_health
```

Expected output:
```
4 of 4 PASS not_null_mart_daily_health_date ................................. [PASS]
4 of 4 PASS not_null_mart_daily_health_recovery_score ....................... [PASS]
4 of 4 PASS unique_mart_daily_health_cycle_id ............................... [PASS]
4 of 4 PASS unique_mart_daily_health_date ................................... [PASS]
```

If `unique_mart_daily_health_date` fails, there are multiple recovery records per date. Inspect with:
```bash
docker compose exec postgres psql -U health -d health_pipeline -c "
SELECT date, count(*) FROM marts.mart_daily_health GROUP BY date HAVING count(*) > 1;
"
```

- [ ] **Step 3: Commit**

```bash
git add dbt/models/marts/schema.yml
git commit -m "feat: add mart_daily_health schema with column descriptions and tests"
```

---

## Task 3: Mount dbt project into Lightdash container

**Files:**
- Modify: `docker-compose.yml`

Lightdash needs access to the dbt project directory (where `dbt_project.yml` lives) so it can compile models and read metadata. The `lightdash/lightdash` Docker image ships with dbt bundled.

- [ ] **Step 1: Add volume mount to docker-compose.yml**

In `docker-compose.yml`, add a `volumes` block to the `lightdash` service:

```yaml
  lightdash:
    image: lightdash/lightdash:latest
    platform: linux/amd64
    env_file: .env
    environment:
      DATABASE_URL: postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
      PGHOST: postgres
      PGPORT: 5432
      PGUSER: ${POSTGRES_USER}
      PGPASSWORD: ${POSTGRES_PASSWORD}
      PGDATABASE: ${POSTGRES_DB}
      LIGHTDASH_SECRET: changeme-lightdash-secret
      SITE_URL: http://localhost:3000
    volumes:
      - ./dbt:/dbt                          # dbt project for Lightdash to compile
    ports:
      - "3000:8080"
    depends_on:
      postgres:
        condition: service_healthy
    networks:
      - health-net
    restart: unless-stopped
```

- [ ] **Step 2: Restart Lightdash**

```bash
docker compose restart lightdash
```

Wait ~30 seconds, then confirm it's healthy:
```bash
docker compose ps lightdash
```

Expected: `STATUS` shows `Up` (not `Restarting` or `Exit`).

- [ ] **Step 3: Verify the volume is mounted**

```bash
docker compose exec lightdash ls /dbt
```

Expected output includes: `dbt_project.yml  models  profiles.yml.example  target`

- [ ] **Step 4: Commit**

```bash
git add docker-compose.yml
git commit -m "feat: mount dbt project into Lightdash container"
```

---

## Task 4: Configure Lightdash project via UI

This task is manual UI configuration. Lightdash needs to know the dbt project path and warehouse credentials before it can surface models.

- [ ] **Step 1: Open Lightdash and start project setup**

Open http://localhost:3000 in your browser.

If this is your first time, Lightdash will prompt you to create a project. If not, go to **Settings → Projects → + New project**.

- [ ] **Step 2: Select connection type**

Choose **dbt local CLI** (not dbt Cloud, not GitHub).

- [ ] **Step 3: Configure dbt project path**

Set the dbt project directory to:
```
/dbt
```

This is the path inside the container where you mounted `./dbt`.

- [ ] **Step 4: Configure warehouse connection**

Fill in the Postgres connection:
- **Host:** `postgres` (the Docker Compose service name, not `localhost`)
- **Port:** `5432`
- **Database:** `health_pipeline`
- **Username:** `health` (or whatever `POSTGRES_USER` is in your `.env`)
- **Password:** your `POSTGRES_PASSWORD` from `.env`
- **Schema:** `marts`

- [ ] **Step 5: Test the connection and compile**

Click **Test connection**. Expected: green checkmark.

Then click **Compile project** (or equivalent). Lightdash will run `dbt compile` inside the container against your project. Expected: it finds `mart_daily_health` and lists it as an available model.

If compilation fails with a profiles error, Lightdash manages its own warehouse connection for dbt — you don't need a `profiles.yml` inside the container. Proceed to next step.

- [ ] **Step 6: Verify mart_daily_health appears**

After compilation, navigate to **Explore → Tables**. You should see `Mart Daily Health` listed as an explorable table with all columns from `schema.yml` visible with their descriptions.

---

## Task 5: Build initial dashboard

Build the **Daily Health Overview** dashboard with four charts. All charts use `mart_daily_health` as the data source.

- [ ] **Step 1: Create a new dashboard**

In Lightdash: **Dashboards → + New dashboard**. Name it `Daily Health Overview`.

- [ ] **Step 2: Add recovery score trend (line chart)**

Click **+ Add tile → Chart → Explore from here**.

- Table: `Mart Daily Health`
- X axis: `Date`
- Y axis: `Recovery Score`
- Chart type: Line
- Save as: `Recovery Score — 30 Days`

- [ ] **Step 3: Add HRV trend (line chart)**

Add another tile:

- Table: `Mart Daily Health`
- X axis: `Date`
- Y axis: `Hrv Rmssd Milli`
- Chart type: Line
- Save as: `HRV Trend`

- [ ] **Step 4: Add restorative sleep bar chart**

Add another tile:

- Table: `Mart Daily Health`
- X axis: `Date`
- Y axis: `Restorative Sleep Hours`
- Chart type: Bar
- Save as: `Restorative Sleep per Night`

- [ ] **Step 5: Add sleep stage breakdown (stacked bar)**

Add another tile:

- Table: `Mart Daily Health`
- X axis: `Date`
- Y axis: `Slow Wave Hours`, `Rem Hours` (add both as separate metrics)
- Chart type: Bar (stacked)
- Save as: `Sleep Stage Breakdown`

- [ ] **Step 6: Save and review dashboard**

Save the dashboard. Confirm all four charts render with 30 days of data. The `Is Cpap Night` column should be available as a filter (all values `false` for now).
