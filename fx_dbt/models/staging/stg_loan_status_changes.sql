select loan_id, changed_at, old_status, new_status
from {{ source('raw', 'loan_status_changes') }}