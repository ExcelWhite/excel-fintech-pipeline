with daily as (
    select * from {{ ref('fct_loan_daily') }}
    where status in ('active', 'overdue')   -- live portfolio only
),

borrowers as (
    select borrower_id, segment, channel from {{ ref('dim_borrower') }}
)

select
    d.status_date,
    b.segment,
    b.channel,
    count(*) as loans_outstanding,
    round(sum(d.outstanding_balance), 2) as total_outstanding,
    round(sum(if(d.is_par30, d.outstanding_balance, 0)), 2) as par30_balance,
    round(sum(if(d.is_par90, d.outstanding_balance, 0)), 2) as par90_balance,
    round(safe_divide(
        sum(if(d.is_par30, d.outstanding_balance, 0)),
        sum(d.outstanding_balance)), 4) as par30_ratio,
    round(safe_divide(
        sum(if(d.is_par90, d.outstanding_balance, 0)),
        sum(d.outstanding_balance)), 4) as par90_ratio
from daily d
left join borrowers b using (borrower_id)
group by 1, 2, 3