with loans as (
    select * from {{ ref('stg_loans') }}
),

repaid as (
    select
        loan_id,
        sum(amount_paid) as total_repaid
    from {{ ref('stg_repayments') }}
    group by loan_id
)

select 
    l.loan_id,
    l.borrower_id,
    l.amount_due_total,
    coalesce(r.total_repaid, 0) as total_repaid,
    greatest(l.amount_due_total - coalesce(r.total_repaid, 0), 0) as outstanding_balance
from loans l
left join repaid r using (loan_id)