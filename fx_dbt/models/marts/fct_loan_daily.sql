with status_daily as (
    select * from {{ ref('int_loan_status_daily') }}
),

loans as (
    select loan_id, borrower_id, principal, amount_due_total
    from {{ ref('stg_loans') }}
),

schedule as (
    select loan_id, due_date from {{ ref('stg_repayment_schedule') }}
),

repaid_daily as (
    select
        sd.loan_id,
        sd.status_date,
        coalesce(sum(rp.amount_paid), 0) as repaid_to_date
    from status_daily sd
    left join {{ ref('stg_repayments') }} rp
      on rp.loan_id = sd.loan_id
     and rp.paid_date <= sd.status_date
    group by 1, 2
)

select
    sd.loan_day_key,
    sd.loan_id,
    l.borrower_id,
    sd.status_date,
    sd.status,
    l.principal,
    l.amount_due_total,
    sch.due_date,
    case when sd.status = 'overdue'
         then date_diff(sd.status_date, sch.due_date, day)
         else 0 end as days_overdue,
    rd.repaid_to_date,
    greatest(l.amount_due_total - rd.repaid_to_date, 0) as outstanding_balance,
    sd.status = 'overdue'
        and date_diff(sd.status_date, sch.due_date, day) >= 30 as is_par30,
    sd.status = 'overdue'
        and date_diff(sd.status_date, sch.due_date, day) >= 90 as is_par90
from status_daily sd
join loans l on l.loan_id = sd.loan_id
left join schedule sch on sch.loan_id = sd.loan_id
left join repaid_daily rd on rd.loan_id = sd.loan_id and rd.status_date = sd.status_date