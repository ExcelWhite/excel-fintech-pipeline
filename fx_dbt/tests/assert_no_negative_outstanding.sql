select loan_day_key, outstanding_balance
from {{ ref('fct_loan_daily') }}
where outstanding_balance < 0