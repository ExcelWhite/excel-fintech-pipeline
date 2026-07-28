with loans as (
    select loan_id, borrower_id, principal, disbursed_date, current_status
    from {{ ref('fct_loans') }}
),

borrowers as (
    select borrower_id, channel from {{ ref('dim_borrower') }}
)

select
    date_trunc(l.disbursed_date, month) as cohort_month,
    b.channel,
    count(*) as loans_originated,
    countif(l.current_status = 'written_off') as loans_defaulted,
    round(safe_divide(countif(l.current_status = 'written_off'), count(*)), 4) as default_rate,
    round(sum(l.principal), 2) as principal_originated
from loans l
left join borrowers b using (borrower_id)
group by 1, 2
order by 1, 2