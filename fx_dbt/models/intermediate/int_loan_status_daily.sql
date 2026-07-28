with status_changes as (
    select
        loan_id,
        changed_at,
        new_status,
        lead(changed_at) over (partition by loan_id order by changed_at) as next_change
        from {{ ref('stg_loan_status_changes') }}
),

loans as (
    select loan_id, disbursed_date from {{ ref('stg_loans') }}
),

loan_end as (
    select
        loan_id,
        coalesce(
            min(case when new_status in ('repaid', 'written_off') then changed_at end),
            current_date()
        ) as end_date
    from {{ ref('stg_loan_status_changes') }}
    group by loan_id
),

spine as (
    select l.loan_id, day
    from loans l
    join loan_end le using (loan_id),
    unnest(generate_date_array(l.disbursed_date, le.end_date)) as day
),

daily as (
    select
        sp.loan_id,
        sp.day as status_date,
        sc.new_status as status
    from spine sp
    join status_changes sc
      on sp.loan_id = sc.loan_id
     and sp.day >= sc.changed_at
     and (sc.next_change is null or sp.day < sc.next_change)
)

select
    concat(loan_id, '-', cast(status_date as string)) as loan_day_key,
    loan_id,
    status_date,
    status
from daily