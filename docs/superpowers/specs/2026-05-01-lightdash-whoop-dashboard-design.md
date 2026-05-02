# Lightdash Whoop Dashboard — Design Spec

**Date:** 2026-05-01  
**Status:** Approved

---

## Goal

Connect Lightdash to the dbt project and build an initial dashboard visualizing Whoop recovery and sleep data. The visualization layer is Lightdash (already running at port 3000), not Streamlit.

---

## Scope

1. Build `mart_daily_health` dbt mart model
2. Configure Lightdash to connect to the dbt project
3. Build initial Lightdash dashboard: recovery and sleep trends over time

Out of scope: CPAP data source integration, other ingestion sources (Withings, MFP, Apple Health), dbt tests.

---

## Data Model

### `dbt/models/marts/mart_daily_health.sql`

One row per night (naps excluded). Wide join of recovery and sleep on `cycle_id`.

| Column | Source | Notes |
|---|---|---|
| `date` | stg_whoop__recovery | Derived from `created_at::date` |
| `cycle_id` | stg_whoop__recovery | Join key |
| `recovery_score` | stg_whoop__recovery | 0–100 |
| `hrv_rmssd_milli` | stg_whoop__recovery | Inflated on non-CPAP nights |
| `resting_heart_rate` | stg_whoop__recovery | BPM |
| `spo2_percentage` | stg_whoop__recovery | Dips on non-CPAP nights |
| `skin_temp_celsius` | stg_whoop__recovery | |
| `is_cpap_night` | hardcoded | `false` for all rows — placeholder for future data |
| `sleep_start` | stg_whoop__sleep | |
| `sleep_end` | stg_whoop__sleep | |
| `total_sleep_hours` | computed | `(total_in_bed - total_awake) / 3600000.0` |
| `restorative_sleep_hours` | computed | `(slow_wave + rem) / 3600000.0` |
| `slow_wave_hours` | computed | `total_slow_wave_sleep_time_milli / 3600000.0` |
| `rem_hours` | computed | `total_rem_sleep_time_milli / 3600000.0` |
| `sleep_performance_pct` | stg_whoop__sleep | |
| `sleep_efficiency_pct` | stg_whoop__sleep | |
| `disturbance_count` | stg_whoop__sleep | |

**SQL shape:**
```sql
SELECT
  r.created_at::date AS date,
  r.cycle_id,
  r.recovery_score,
  r.hrv_rmssd_milli,
  r.resting_heart_rate,
  r.spo2_percentage,
  r.skin_temp_celsius,
  false AS is_cpap_night,
  s.sleep_start,
  s.sleep_end,
  (s.total_in_bed_time_milli - s.total_awake_time_milli) / 3600000.0 AS total_sleep_hours,
  (s.total_slow_wave_sleep_time_milli + s.total_rem_sleep_time_milli) / 3600000.0 AS restorative_sleep_hours,
  s.total_slow_wave_sleep_time_milli / 3600000.0 AS slow_wave_hours,
  s.total_rem_sleep_time_milli / 3600000.0 AS rem_hours,
  s.sleep_performance_pct,
  s.sleep_efficiency_pct,
  s.disturbance_count
FROM {{ ref('stg_whoop__recovery') }} r
LEFT JOIN {{ ref('stg_whoop__sleep') }} s
  ON r.cycle_id = s.cycle_id
WHERE s.is_nap = false OR s.is_nap IS NULL
```

---

## Lightdash Connection

Lightdash connects to the dbt project via the UI wizard using **dbt Core (local)**:

- **Warehouse:** Postgres at `postgres:5432` (already on `health-net` Docker network)
- **dbt project path:** `/opt/airflow/dags/../` — needs dbt mounted into Lightdash container, or Lightdash configured to read `manifest.json` from a shared volume
- **Connection method:** Lightdash reads `dbt/target/manifest.json` after each `dbt run`

### Docker Compose change required

The `dbt/` directory needs to be mounted into the Lightdash container so Lightdash can read the manifest:

```yaml
lightdash:
  volumes:
    - ./dbt:/dbt
```

Lightdash project config (set in UI wizard):
- Project type: dbt Core (local)
- dbt project path: `/dbt`
- Warehouse: Postgres, host `postgres`, port `5432`, database/user/password from env

---

## Dashboard

Initial Lightdash dashboard: **Daily Health Overview**

Charts:
- Recovery score over time (line chart, 30-day window)
- HRV trend over time (line chart)
- Restorative sleep hours per night (bar chart)
- Sleep stage breakdown per night (stacked bar: slow wave / REM / light / awake)
- `is_cpap_night` visible as a column/filter for future use

---

## Future

- Populate `is_cpap_night` from a source to be determined (Whoop API data discovery or manual seed)
- Add `stg_whoop__workout` staging model and join to mart
- Add dbt `not_null` and `unique` tests on `cycle_id`
