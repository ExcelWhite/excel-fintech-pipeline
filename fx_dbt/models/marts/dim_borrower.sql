with borrowers as (select * from {{ ref('stg_borrowers') }}),
loans as (select * from {{ ref('stg_loans') }})

select
    b.borrower_id,
    b.segment,
    b.state,
    b.channel,
    b.signup_date,
    count(l.loan_id) as total_loans,
    coalesce(sum(l.principal), 0) as total_principal_borrowed
from borrowers b
left join loans l using (borrower_id)
group by 1, 2, 3, 4, 5