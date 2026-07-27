-- Gold: business-ready FX fact. One row per day per pair, with inverse rate.

select
    fx_key,
    rate_date,
    base_currency,
    quote_currency,
    rate,
    round(1/rate, 6) as inverse_rate
from {{ ref('stg_fx_rates') }}