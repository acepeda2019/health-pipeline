"""
Daily Whoop ingestion DAG.
Fetches recovery, sleep, and workout records for the previous day
and writes raw JSON to raw.whoop_events.
"""

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

import psycopg2
from airflow.sdk import dag, task

WHOOP_API = "https://api.prod.whoop.com/developer"
DB_CONN = "postgresql://{user}:{password}@postgres:5432/{db}".format(
    user=os.environ["POSTGRES_USER"],
    password=os.environ["POSTGRES_PASSWORD"],
    db=os.environ["POSTGRES_DB"],
)

ENDPOINTS = {
    "recovery": "/v2/recovery",
    "sleep": "/v2/activity/sleep",
    "workout": "/v2/activity/workout",
}


def _fetch_records(token: str, path: str, start: str, end: str) -> list[dict]:
    """Fetch all pages for a given endpoint and date window."""
    records = []
    next_token = None

    while True:
        params = {"start": start, "end": end, "limit": "25"}
        if next_token:
            params["nextToken"] = next_token

        url = f"{WHOOP_API}{path}?" + "&".join(f"{k}={v}" for k, v in params.items())
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("User-Agent", "health-pipeline/1.0")

        try:
            with urllib.request.urlopen(req) as resp:
                body = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"Whoop API {url} → {e.code}: {e.read().decode()}") from e

        records.extend(body.get("records", []))
        next_token = body.get("next_token")
        if not next_token:
            break

    return records


def _upsert(conn, endpoint: str, records: list[dict], id_key: str) -> int:
    with conn.cursor() as cur:
        for rec in records:
            cur.execute(
                """
                INSERT INTO raw.whoop_events (endpoint, record_id, data)
                VALUES (%s, %s, %s)
                ON CONFLICT (endpoint, record_id) DO NOTHING
                """,
                (endpoint, rec[id_key], json.dumps(rec)),
            )
    conn.commit()
    return len(records)


@dag(
    dag_id="whoop_ingest",
    schedule="@daily",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["whoop", "ingest"],
)
def whoop_ingest():

    @task
    def ensure_token():
        """Refresh the Whoop token if needed before parallel fetch tasks run."""
        from whoop_auth import get_valid_access_token
        get_valid_access_token()

    @task
    def fetch_recovery(start: str, end: str):
        from whoop_auth import get_valid_access_token
        token = get_valid_access_token()
        records = _fetch_records(token, ENDPOINTS["recovery"], start, end)
        with psycopg2.connect(DB_CONN) as conn:
            count = _upsert(conn, "recovery", records, "cycle_id")
        return count

    @task
    def fetch_sleep(start: str, end: str):
        from whoop_auth import get_valid_access_token
        token = get_valid_access_token()
        records = _fetch_records(token, ENDPOINTS["sleep"], start, end)
        with psycopg2.connect(DB_CONN) as conn:
            count = _upsert(conn, "sleep", records, "id")
        return count

    @task
    def fetch_workouts(start: str, end: str):
        from whoop_auth import get_valid_access_token
        token = get_valid_access_token()
        records = _fetch_records(token, ENDPOINTS["workout"], start, end)
        with psycopg2.connect(DB_CONN) as conn:
            count = _upsert(conn, "workout", records, "id")
        return count

    @task
    def get_window(**context) -> dict:
        logical_date = context["logical_date"]
        start = logical_date.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
        end = start + timedelta(days=1)
        return {
            "start": start.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "end": end.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        }

    token_ready = ensure_token()
    window = get_window()
    token_ready >> window
    window >> [
        fetch_recovery(window["start"], window["end"]),
        fetch_sleep(window["start"], window["end"]),
        fetch_workouts(window["start"], window["end"]),
    ]


whoop_ingest()
