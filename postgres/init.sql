-- Health pipeline schema setup
-- Runs once on first Postgres container start

-- Raw layer: landing zone for API responses and parsed files
CREATE SCHEMA IF NOT EXISTS raw;

-- Staging layer: validated, typed rows
CREATE SCHEMA IF NOT EXISTS staging;

-- Marts layer: dbt-produced clean models for Lightdash
CREATE SCHEMA IF NOT EXISTS marts;

-- Grant all to the pipeline user
GRANT ALL PRIVILEGES ON SCHEMA raw TO health;
GRANT ALL PRIVILEGES ON SCHEMA staging TO health;
GRANT ALL PRIVILEGES ON SCHEMA marts TO health;
