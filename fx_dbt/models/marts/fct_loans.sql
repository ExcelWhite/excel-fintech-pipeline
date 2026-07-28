with loans as (select * from {{ ref('stg_loans') }}),
balances as (select * from {{ ref('int_loan_balances') }}),

latest_status as (
    select loan_id, new_status as current_status
    from {{ ref('stg_loan_status_changes') }}
    qualify row_number() over (partition by loan_id order by changed_at desc) = 1
)

select
    l.loan_id,
    l.borrower_id,
    l.principal,
    l.currency,
    l.interest_rate,
    l.tenor_days,
    l.disbursed_date,
    l.amount_due_total,
    b.total_repaid,
    b.outstanding_balance,
    s.current_status
from loans l
left join balances b using (loan_id)
left join latest_status s using (loan_id)