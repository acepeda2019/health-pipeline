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
