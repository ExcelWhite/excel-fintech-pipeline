# Nigerian Fintech SME Lending — Analytics Engineering Pipeline

**A production-grade, end-to-end data pipeline for Nigerian SME lending: live ingestion, a dbt medallion warehouse, portfolio-risk (PAR) reporting, and CI/CD — running on a schedule and tested on every run.**

[![CI](https://github.com/ExcelWhite/excel-fintech-pipeline/actions/workflows/ingest.yml/badge.svg)](https://github.com/ExcelWhite/excel-fintech-pipeline/actions/workflows/ingest.yml)
&nbsp;·&nbsp; **[🔴 ▶︎ Live Dashboard](https://datastudio.google.com/reporting/399dbd8c-102b-4b30-a927-25c514b4a52c)** &nbsp;·&nbsp; Stack: BigQuery · dbt · Python · GitHub Actions · Looker Studio

---

[![Portfolio Risk Dashboard](docs/images/dashboard.png)](REPLACE_WITH_YOUR_LOOKER_LINK)

<p align="center"><em>Live portfolio-risk dashboard — click to open the interactive version.</em></p>

---

## What this is

Most Nigerian SME lenders run on spreadsheets and gut feel: their loan, repayment, and borrower data lives in scattered systems, and questions like *"what's our PAR30 by acquisition channel?"* or *"which cohort is defaulting?"* take days to answer — if they can be answered at all.

This project is the data platform that answers them automatically. It ingests live financial data, models it into clean, tested, business-ready tables, and serves portfolio-risk metrics through a live dashboard — the same shape of system a real lending data team operates.

It combines **two data feeds**:

- **Real FX market data** — live USD→NGN and major-currency rates pulled from a public exchange-rate API, giving the pipeline genuine external data that fails, drifts, and behaves like production.
- **A synthetic loan book** — a deterministic Python generator simulating borrowers, disbursements, repayments, and delinquency for a Nigerian lending fintech, because real lending data isn't publicly available. The generator is stateful and seeded, so history is coherent and reproducible.

> **On the data:** the loan book is synthetic by design — the *engineering* (ingestion, modeling, testing, orchestration) is real and production-shaped. The FX data is genuinely live.

## Architecture

![Architecture](docs/images/architecture.png)

Data flows left to right — two live sources → Python ingestion → BigQuery (bronze) → dbt medallion transformation → Looker Studio — with **GitHub Actions** orchestrating scheduled runs, CI/CD, and running the full test suite on every build.

## The stack

| Layer | Tool | What it does |
|---|---|---|
| Ingestion | **Python** (`requests`, `google-cloud-bigquery`) | Idempotent, stateful loaders for FX and loan data |
| Warehouse | **BigQuery** | Cloud data warehouse (bronze → gold) |
| Transformation | **dbt Core** | Medallion modeling: staging → intermediate → marts |
| Orchestration & CI/CD | **GitHub Actions** | Scheduled ingestion + `dbt build`, tests gate every run |
| BI | **Looker Studio** | Live portfolio-risk dashboard |

## Key engineering decisions

This is where the project goes beyond "it runs":

- **Idempotent, stateful ingestion.** Loaders check existing warehouse state before writing, so re-runs never create duplicates, and the loan generator reads prior state to append only new events — the same pattern a real incremental pipeline uses. A deterministic seed makes the whole history reproducible.
- **Medallion architecture in dbt.** Raw data lands faithfully (bronze), staging models clean and reshape it (silver), intermediate models hold the complex business logic, and marts serve business-ready facts and dimensions (gold). Dependencies flow one direction only.
- **The PAR engine.** A `fct_loan_daily` model expands each loan into one row per day with the status in effect, which makes **PAR30 / PAR90 answerable as of any historical date** — not just today. Portfolio metrics and cohort default rates are built on top of it.
- **Data quality as a gate.** **63 dbt tests** (uniqueness, not-null, referential integrity, accepted values, plus custom singular tests like *"outstanding balance can never be negative"* and *"PAR balance can never exceed the portfolio"*) run on every scheduled build. A failing test fails the run.
- **Incremental models & SCD Type 2 snapshots.** Implemented in `models/marts/fct_loan_daily_inc.sql` and `snapshots/loan_status_snapshot.sql`. These use `MERGE`, which requires a billing-enabled BigQuery warehouse; this project runs on the free tier, so they're tagged `requires_billing` and excluded from the scheduled build. The code is production-ready — enabling billing and dropping the exclude flag activates them.

## Data model

The dbt lineage graph — sources through staging, intermediate, and marts, with tests and snapshots downstream:

![dbt lineage](docs/images/lineage.png)

**Marts (gold) include:**

- `fct_loan_daily` — one row per loan per day; the PAR engine
- `fct_portfolio_daily` — daily PAR30/PAR90 and outstanding by segment and channel
- `fct_cohort_default` — default rate by disbursement cohort and acquisition channel
- `fct_fx_rates` — daily USD→NGN and major-currency rates
- `dim_borrower`, `dim_date` — conformed dimensions

## Running it locally

**Prerequisites:** Python 3.12, a Google Cloud project with BigQuery, and a service-account key.

```bash
# 1. Install dependencies
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Add your BigQuery service-account key as sa-key.json in the repo root
#    (git-ignored — never committed)

# 3. Ingest data
python scripts/ingest_fx.py        # live FX rates → BigQuery
python scripts/generate_loans.py   # synthetic loan book → BigQuery

# 4. Build and test the warehouse
cd fx_dbt
dbt build --exclude tag:requires_billing --profiles-dir .
```

The pipeline also runs automatically via GitHub Actions on a schedule — see [`.github/workflows/ingest.yml`](.github/workflows/ingest.yml).

## Repository layout

```
├── scripts/            # Python ingestion & loan generation
├── fx_dbt/             # dbt project
│   ├── models/
│   │   ├── sources/    # bronze source declarations
│   │   ├── staging/    # silver: clean & reshape
│   │   ├── intermediate/  # business logic
│   │   └── marts/      # gold: facts & dimensions
│   ├── snapshots/      # SCD2 loan-status history
│   └── tests/          # custom singular tests
├── .github/workflows/  # scheduled ingestion + dbt build (CI/CD)
└── docs/images/        # dashboard, architecture, lineage
```

---

<p align="center">
Built by <strong>Elisha Enefu</strong> — Analytics / Data Engineer<br>
<a href="REPLACE_WITH_YOUR_LOOKER_LINK">Live Dashboard</a> · <a href="https://github.com/ExcelWhite">GitHub</a>
</p>