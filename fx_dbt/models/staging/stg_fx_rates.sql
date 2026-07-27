-- parse the JSON blob into 1 tidy row per 
-- rate_date x quote_currency deduped to the latest pull per day

with source as (
    select * from {{ source('raw', 'fx_rates_raw') }}
),

latest as (
    select
        rate_date,
        base_currency,
        rates_json,
        ingested_at
    from source
    qualify row_number() over (
        partition by rate_date, base_currency
        order by ingested_at desc
    ) = 1
),

exploded as (
    select
        rate_date,
        base_currency,
        pair.quote_currency,
        cast(pair.rate_str as float64) as rate
    from latest
    unnest([
        struct('NGN' as quote_currency, json_value(rates_json, '$.NGN') as rate_str),
        struct('EUR', json_value(rates_json, '$.EUR')),
        struct('GBP', json_value(rates_json, '$.GBP')),
        struct('JPY', json_value(rates_json, '$.JPY')),
        struct('CAD', json_value(rates_json, '$.CAD')),
        struct('AUD', json_value(rates_json, '$.AUD')),
        struct('CHF', json_value(rates_json, '$.CHF'))
    ])
) as pair

select
    concat(cast(rate_date as string), '_', quote_currency) as fx_key,
    rate_date,
    base_currency,
    quote_currency,
    rate
from exploded
where rate is not null