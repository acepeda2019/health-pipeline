with source as (
    select data from {{ source('whoop', 'whoop_events') }}
    where endpoint = 'sleep'
),

parsed as (
    select
        (data->>'id')::text                                                             as sleep_id,
        (data->>'cycle_id')::bigint                                                     as cycle_id,
        (data->>'nap')::boolean                                                         as is_nap,
        (data->>'score_state')::text                                                    as score_state,
        (data->>'timezone_offset')::text                                                as timezone_offset,
        (data->>'start')::timestamptz                                                   as sleep_start,
        (data->>'end')::timestamptz                                                     as sleep_end,

        -- performance
        (data->'score'->>'sleep_performance_percentage')::numeric                      as sleep_performance_pct,
        (data->'score'->>'sleep_efficiency_percentage')::numeric                        as sleep_efficiency_pct,
        (data->'score'->>'sleep_consistency_percentage')::numeric                       as sleep_consistency_pct,
        (data->'score'->>'respiratory_rate')::numeric                                   as respiratory_rate,

        -- stage summary (milliseconds)
        (data->'score'->'stage_summary'->>'total_in_bed_time_milli')::bigint           as total_in_bed_time_milli,
        (data->'score'->'stage_summary'->>'total_awake_time_milli')::bigint            as total_awake_time_milli,
        (data->'score'->'stage_summary'->>'total_light_sleep_time_milli')::bigint      as total_light_sleep_time_milli,
        (data->'score'->'stage_summary'->>'total_slow_wave_sleep_time_milli')::bigint  as total_slow_wave_sleep_time_milli,
        (data->'score'->'stage_summary'->>'total_rem_sleep_time_milli')::bigint        as total_rem_sleep_time_milli,
        (data->'score'->'stage_summary'->>'sleep_cycle_count')::int                    as sleep_cycle_count,
        (data->'score'->'stage_summary'->>'disturbance_count')::int                    as disturbance_count,

        (data->>'created_at')::timestamptz                                              as created_at,
        (data->>'updated_at')::timestamptz                                              as updated_at
    from source
)

select * from parsed
