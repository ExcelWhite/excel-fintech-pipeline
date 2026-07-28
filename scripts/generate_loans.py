"""
Synthetic loan-book generator — Part 1: ORIGINATION.

Stateful + incremental: reads what already exists in BigQuery, backfills any
missing days from (today - HISTORY_DAYS) up to today, and appends only new
events. Deterministic: a given date always yields the same events (seeded RNG),
so re-running a day is idempotent.

Creates: borrowers, loans, repayment_schedule, and initial 'active' rows in
loan_status_changes. Repayments and delinquency arrive in Part 2.
"""

import datetime
import os
import random
from google.cloud import bigquery
from google.oauth2 import service_account

# --- Config ---------------------------------------------------------------
KEY_PATH = os.path.join(os.path.dirname(__file__), "..", "sa-key.json")
DATASET = "raw"
SEED = "excel-fintech-2026"
HISTORY_DAYS = 120
STATES = ["Lagos", "Kano", "Rivers", "Oyo", "Kaduna", "Abuja", "Enugu", "Anambra"]
SEGMENTS = ["retail", "food", "pharmacy", "electronics", "general"]
CHANNELS = ["field_sales", "referral", "app_signup", "partner"]
PRINCIPALS = [50000, 100000, 200000, 500000]
TENORS = [30, 60, 90]
FLAT_RATE = 0.05

credentials = service_account.Credentials.from_service_account_file(KEY_PATH)
client = bigquery.Client(credentials=credentials, project=credentials.project_id)
PROJECT = client.project

def tbl(name):
    return f"{PROJECT}.{DATASET}.{name}"

def table_exists(name):
    try:
        client.get_table(tbl(name))
        return True
    except Exception:
        return False

def count(name):
    if not table_exists(name):
        return 0
    return list(client.query(f"SELECT COUNT(*) AS n FROM `{tbl(name)}`").result())[0]["n"]

# --- 1. Read current state ------------------------------------------------
client.create_dataset(bigquery.Dataset(f"{PROJECT}.{DATASET}"), exists_ok=True)

borrower_count = count("borrowers")
loan_count = count("loans")

borrower_ids = []
if table_exists("borrowers"):
    for r in client.query(f"SELECT borrower_id FROM `{tbl('borrowers')}`").result():
        borrower_ids.append(r["borrower_id"])

generated = set()
if table_exists("_generation_log"):
    for r in client.query(f"SELECT gen_date FROM `{tbl('_generation_log')}`").result():
        generated.add(r["gen_date"])

# --- 2. Which days to generate --------------------------------------------
today = datetime.date.today()
start = today - datetime.timedelta(days=HISTORY_DAYS)
all_days = [start + datetime.timedelta(days=i) for i in range((today - start).days + 1)]
days_to_generate = [d for d in all_days if d not in generated]

if not days_to_generate:
    print("Nothing to generate — all days up to today already exist.")
    raise SystemExit

# --- 3. Generate origination events, day by day ---------------------------
new_borrowers, new_loans, new_schedule, new_status = [], [], [], []
b_idx, l_idx = borrower_count, loan_count

for day in days_to_generate:
    rng = random.Random(f"{SEED}-{day.isoformat()}")

    for _ in range(rng.randint(0, 3)):
        b_idx += 1
        bid = f"B{b_idx:05d}"
        borrower_ids.append(bid)
        new_borrowers.append({
            "borrower_id": bid,
            "segment": rng.choice(SEGMENTS),
            "state": rng.choice(STATES),
            "channel": rng.choice(CHANNELS),
            "signup_date": day.isoformat(),
        })

    if borrower_ids:
        for _ in range(rng.randint(1, 4)):
            l_idx += 1
            lid = f"L{l_idx:06d}"
            principal = rng.choice(PRINCIPALS)
            tenor = rng.choice(TENORS)
            due = day + datetime.timedelta(days=tenor)
            new_loans.append({
                "loan_id": lid,
                "borrower_id": rng.choice(borrower_ids),
                "principal": principal,
                "currency": "NGN",
                "interest_rate": FLAT_RATE,
                "tenor_days": tenor,
                "disbursed_date": day.isoformat(),
            })
            new_schedule.append({
                "loan_id": lid,
                "installment_no": 1,
                "due_date": due.isoformat(),
                "amount_due": round(principal * (1 + FLAT_RATE), 2),
            })
            new_status.append({
                "loan_id": lid,
                "changed_at": day.isoformat(),
                "old_status": None,
                "new_status": "active",
            })

# --- 4. Append to BigQuery ------------------------------------------------
SCHEMAS = {
    "borrowers": [
        bigquery.SchemaField("borrower_id", "STRING"),
        bigquery.SchemaField("segment", "STRING"),
        bigquery.SchemaField("state", "STRING"),
        bigquery.SchemaField("channel", "STRING"),
        bigquery.SchemaField("signup_date", "DATE"),
    ],
    "loans": [
        bigquery.SchemaField("loan_id", "STRING"),
        bigquery.SchemaField("borrower_id", "STRING"),
        bigquery.SchemaField("principal", "FLOAT64"),
        bigquery.SchemaField("currency", "STRING"),
        bigquery.SchemaField("interest_rate", "FLOAT64"),
        bigquery.SchemaField("tenor_days", "INT64"),
        bigquery.SchemaField("disbursed_date", "DATE"),
    ],
    "repayment_schedule": [
        bigquery.SchemaField("loan_id", "STRING"),
        bigquery.SchemaField("installment_no", "INT64"),
        bigquery.SchemaField("due_date", "DATE"),
        bigquery.SchemaField("amount_due", "FLOAT64"),
    ],
    "loan_status_changes": [
        bigquery.SchemaField("loan_id", "STRING"),
        bigquery.SchemaField("changed_at", "DATE"),
        bigquery.SchemaField("old_status", "STRING"),
        bigquery.SchemaField("new_status", "STRING"),
    ],
}

def append(name, rows):
    if not rows:
        return
    cfg = bigquery.LoadJobConfig(schema=SCHEMAS[name], write_disposition="WRITE_APPEND")
    client.load_table_from_json(rows, tbl(name), job_config=cfg).result()

append("borrowers", new_borrowers)
append("loans", new_loans)
append("repayment_schedule", new_schedule)
append("loan_status_changes", new_status)

log_cfg = bigquery.LoadJobConfig(
    schema=[bigquery.SchemaField("gen_date", "DATE")],
    write_disposition="WRITE_APPEND",
)
client.load_table_from_json(
    [{"gen_date": d.isoformat()} for d in days_to_generate],
    tbl("_generation_log"), job_config=log_cfg,
).result()

print(f"Generated {len(days_to_generate)} day(s): "
      f"{len(new_borrowers)} borrowers, {len(new_loans)} loans.")