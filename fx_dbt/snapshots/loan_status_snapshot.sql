{% snapshot loan_status_snapshot %}

{{ config(
    target_schema='dbt_fx',
    unique_key='loan_id',
    strategy='check',
    check_cols=['current_status'],
    tags=['requires_billing']
) }}


select
    loan_id,
    current_status
from {{ ref('fct_loans') }}

{% endsnapshot %}