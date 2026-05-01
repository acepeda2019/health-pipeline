with source as (
    select data from {{ source('whoop', 'whoop_events') }}
    where endpoint = 'recovery'
),

parsed as (
    select
        (data->>'cycle_id')::bigint                         as cycle_id,
        (data->>'sleep_id')::text                           as sleep_id,
        (data->>'score_state')::text                        as score_state,
        (data->'score'->>'recovery_score')::numeric         as recovery_score,
        (data->'score'->>'resting_heart_rate')::numeric     as resting_heart_rate,
        (data->'score'->>'hrv_rmssd_milli')::numeric        as hrv_rmssd_milli,
        (data->'score'->>'spo2_percentage')::numeric        as spo2_percentage,
        (data->'score'->>'skin_temp_celsius')::numeric      as skin_temp_celsius,
        (data->>'created_at')::timestamptz                  as created_at,
        (data->>'updated_at')::timestamptz                  as updated_at
    from source
)

select * from parsed
