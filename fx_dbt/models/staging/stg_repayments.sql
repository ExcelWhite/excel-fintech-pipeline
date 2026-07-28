select
    repayment_id,
    loan_id,
    paid_date,
    amount_paid
from {{ source('raw', 'repayments') }}