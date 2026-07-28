select cohort_month, channel, default_rate
from {{ ref('fct_cohort_default') }}
where default_rate < 0 or default_rate > 1