"""
Whoop OAuth2 token management.
Tokens are seeded from env vars on first use and persisted in raw.tokens
so refreshes survive container restarts without needing the Airflow API.
"""

import os
import time
import urllib.parse
import urllib.request
import json

import psycopg2

TOKEN_URL = "https://api.prod.whoop.com/oauth/oauth2/token"
DB_CONN = "postgresql://{user}:{password}@postgres:5432/{db}".format(
    user=os.environ["POSTGRES_USER"],
    password=os.environ["POSTGRES_PASSWORD"],
    db=os.environ["POSTGRES_DB"],
)


def _get_token(key: str, env_fallback: str) -> str:
    with psycopg2.connect(DB_CONN) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT value FROM raw.tokens WHERE key = %s", (key,))
            row = cur.fetchone()
            if row:
                return row[0]
            value = os.environ[env_fallback]
            cur.execute(
                "INSERT INTO raw.tokens (key, value) VALUES (%s, %s)",
                (key, value),
            )
            conn.commit()
            return value


def _set_token(key: str, value: str):
    with psycopg2.connect(DB_CONN) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO raw.tokens (key, value, updated_at)
                VALUES (%s, %s, NOW())
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
                """,
                (key, value),
            )
            conn.commit()


def get_valid_access_token() -> str:
    """Return a valid access token, refreshing if expired."""
    expires_at = float(_get_token("whoop_token_expires_at", "") if _token_exists("whoop_token_expires_at") else "0")

    if time.time() < expires_at - 60:
        return _get_token("whoop_access_token", "WHOOP_ACCESS_TOKEN")

    return _refresh()


def _token_exists(key: str) -> bool:
    with psycopg2.connect(DB_CONN) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM raw.tokens WHERE key = %s", (key,))
            return cur.fetchone() is not None


def _refresh() -> str:
    refresh_token = _get_token("whoop_refresh_token", "WHOOP_REFRESH_TOKEN")
    client_id = os.environ["WHOOP_CLIENT_ID"]
    client_secret = os.environ["WHOOP_CLIENT_SECRET"]

    data = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
        "client_secret": client_secret,
    }).encode()

    req = urllib.request.Request(TOKEN_URL, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    req.add_header("User-Agent", "health-pipeline/1.0")

    with urllib.request.urlopen(req) as resp:
        tokens = json.loads(resp.read())

    _set_token("whoop_access_token", tokens["access_token"])
    _set_token("whoop_refresh_token", tokens["refresh_token"])
    _set_token("whoop_token_expires_at", str(time.time() + tokens["expires_in"]))

    return tokens["access_token"]
