-- PAR balance can never exceed the portfolio it's a subset of
select status_date, segment, channel
from {{ ref('fct_portfolio_daily') }}
where par30_balance > total_outstanding
   or par90_balance > total_outstanding