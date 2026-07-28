select
    loan_id,
    borrower_id,
    principal,
    currency,
    interest_rate,
    tenor_days,
    disbursed_date,
    round(principal * (1+interest_rate), 2) as amount_due_total
from {{ source('raw', 'loans') }}