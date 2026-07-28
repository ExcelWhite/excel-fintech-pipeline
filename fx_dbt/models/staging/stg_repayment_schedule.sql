select loan_id, installment_no, due_date, amount_due
from {{ source('raw', 'repayment_schedule') }}