with repay as (select * from {{ ref('stg_repayments') }}),
loans as (select loan_id, borrower_id from {{ ref('stg_loans') }})

select
    r.repayment_id,
    r.loan_id,
    l.borrower_id,
    r.paid_date,
    r.amount_paid
from repay r
left join loans l using (loan_id)