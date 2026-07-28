select
    borrower_id,
    segment,
    state,
    channel,
    signup_date
from {{ source('raw', 'borrowers') }}