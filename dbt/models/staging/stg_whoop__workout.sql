with source as (
    select data from {{ source('whoop', 'whoop_events') }}
    where endpoint = 'workout'
),

parsed as (
    select
        (data->>'id')::text                                                         as workout_id,
        (data->>'sport_id')::int                                                    as sport_id,
        (data->>'sport_name')::text                                                 as sport_name,
        (data->>'score_state')::text                                                as score_state,
        (data->>'timezone_offset')::text                                            as timezone_offset,
        (data->>'start')::timestamptz                                               as workout_start,
        (data->>'end')::timestamptz                                                 as workout_end,

        -- score
        (data->'score'->>'strain')::numeric                                         as strain,
        (data->'score'->>'average_heart_rate')::int                                 as average_heart_rate,
        (data->'score'->>'max_heart_rate')::int                                     as max_heart_rate,
        (data->'score'->>'kilojoule')::numeric                                      as kilojoule,
        (data->'score'->>'percent_recorded')::numeric                               as percent_recorded,
        (data->'score'->>'distance_meter')::numeric                                 as distance_meter,
        (data->'score'->>'altitude_gain_meter')::numeric                            as altitude_gain_meter,
        (data->'score'->>'altitude_change_meter')::numeric                          as altitude_change_meter,

        -- heart rate zones (milliseconds)
        (data->'score'->'zone_durations'->>'zone_zero_milli')::bigint              as zone_zero_milli,
        (data->'score'->'zone_durations'->>'zone_one_milli')::bigint               as zone_one_milli,
        (data->'score'->'zone_durations'->>'zone_two_milli')::bigint               as zone_two_milli,
        (data->'score'->'zone_durations'->>'zone_three_milli')::bigint             as zone_three_milli,
        (data->'score'->'zone_durations'->>'zone_four_milli')::bigint              as zone_four_milli,
        (data->'score'->'zone_durations'->>'zone_five_milli')::bigint              as zone_five_milli,

        (data->>'created_at')::timestamptz                                          as created_at,
        (data->>'updated_at')::timestamptz                                          as updated_at
    from source
)

select * from parsed
