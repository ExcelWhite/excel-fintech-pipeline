{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key='loan_day_key',
    tags=['requires_billing']
) }}

select *
from {{ ref('fct_loan_daily') }}

{% if is_incremental() %}
where status_date >= date_sub(
    (select max(status_date) from {{ this }}), interval 3 day
)
{% endif %}
