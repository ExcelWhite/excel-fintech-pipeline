with bounds as (
    select
        least(
            (select min(disbursed_date) from {{ ref('stg_loans') }}),
            (select min(signup_date) from {{ ref('stg_borrowers') }})
        ) as start_date,
        greatest(
            current_date(),
            (select max(due_date) from {{ ref('stg_repayment_schedule') }})
        ) as end_date
    ),

spine as (
    select day
    from bounds, unnest(generate_date_array(start_date, end_date)) as day
)

select
    day as date_day,
    extract(year from day) as year,
    extract(quarter from day) as quarter,
    extract(month from day) as month,
    extract(day from day) as day_of_month,
    format_date('%A', day) as weekday_name,
    date_trunc(day, month) as month_start
from spine