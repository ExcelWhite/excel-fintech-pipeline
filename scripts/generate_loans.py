"""
Synthetic loan-book generator (origination + performance).

Stateful, incremental, deterministic. Reads existing state from BigQuery,
backfills missing days up to today, appends only new events. Each loan's fate
(on-time / late / default) is a fixed function of its loan_id, so history is
reproducible and events land on their real dates.
"""

import os
import datetime
import random
from google.cloud import bigquery
from google.oauth2 import service_account

# --- Config ---------------------------------------------------------------
KEY_PATH = os.path.join(os.path.dirname(__file__), "..", "sa-key.json")
DATASET = "raw"
SEED = "excel-fintech-2026"
HISTORY_DAYS = 180
STATES = ["Lagos", "Kano", "Rivers", "Oyo", "Kaduna", "Abuja", "Enugu", "Anambra"]
SEGMENTS = ["retail", "food", "pharmacy", "electronics", "general"]
CHANNELS = ["field_sales", "referral", "app_signup", "partner"]
PRINCIPALS = [50000, 100000, 200000, 500000]
TENORS = [30, 60, 90]
FLAT_RATE = 0.05
P_ONTIME, P_LATE = 0.70, 0.20   # remainder (0.10) default
WRITEOFF_DAYS = 120

credentials = service_account.Credentials.from_service_account_file(KEY_PATH)
client = bigquery.Client(credentials=credentials, project=credentials.project_id)
PROJECT = client.project

def tbl(name): return f"{PROJECT}.{DATASET}.{name}"

def table_exists(name):
    try:
        client.get_table(tbl(name)); return True
    except Exception:
        return False

def query(sql):
    return list(client.query(sql).result())

# --- 1. Read existing state ----------------------------------------------
client.create_dataset(bigquery.Dataset(f"{PROJECT}.{DATASET}"), exists_ok=True)

borrower_ids = []
if table_exists("borrowers"):
    borrower_ids = [r["borrower_id"] for r in query(f"SELECT borrower_id FROM `{tbl('borrowers')}`")]

# meta for planning: every loan we already know about
loan_meta = {}
if table_exists("loans"):
    for r in query(f"SELECT loan_id, disbursed_date, tenor_days, principal, interest_rate FROM `{tbl('loans')}`"):
        loan_meta[r["loan_id"]] = {
            "disbursed": r["disbursed_date"],
            "tenor": r["tenor_days"],
            "amount_due": round(r["principal"] * (1 + r["interest_rate"]), 2),
        }

generated = set()
if table_exists("_generation_log"):
    generated = {r["gen_date"] for r in query(f"SELECT gen_date FROM `{tbl('_generation_log')}`")}

b_idx = len(borrower_ids)
l_idx = len(loan_meta)

# --- 2. Which days to generate -------------------------------------------
today = datetime.date.today()
start = today - datetime.timedelta(days=HISTORY_DAYS)
all_days = [start + datetime.timedelta(days=i) for i in range((today - start).days + 1)]
days_to_generate = [d for d in all_days if d not in generated]
if not days_to_generate:
    print("Nothing to generate — all days up to today already exist.")
    raise SystemExit

# --- 3. Deterministic fate -> event plan for a loan ----------------------
def loan_plan(loan_id, disbursed, tenor, amount_due):
    due = disbursed + datetime.timedelta(days=tenor)
    fr = random.Random(f"{SEED}-fate-{loan_id}")
    roll = fr.random()
    status_changes, repayments = [], []
    if roll < P_ONTIME:                                   # on time
        repayments.append((due, amount_due))
        status_changes.append((due, "active", "repaid"))
    elif roll < P_ONTIME + P_LATE:                        # late
        late = fr.randint(5, 40)
        status_changes.append((due + datetime.timedelta(days=1), "active", "overdue"))
        repayments.append((due + datetime.timedelta(days=late), amount_due))
        status_changes.append((due + datetime.timedelta(days=late), "overdue", "repaid"))
    else:                                                 # default
        status_changes.append((due + datetime.timedelta(days=1), "active", "overdue"))
        status_changes.append((due + datetime.timedelta(days=WRITEOFF_DAYS), "overdue", "written_off"))
    return {"status_changes": status_changes, "repayments": repayments}

plans = {lid: loan_plan(lid, m["disbursed"], m["tenor"], m["amount_due"]) for lid, m in loan_meta.items()}

# --- 4. Generate, day by day ---------------------------------------------
new_borrowers, new_loans, new_schedule, new_status, new_repay = [], [], [], [], []

for day in days_to_generate:
    rng = random.Random(f"{SEED}-{day.isoformat()}")

    # origination
    for _ in range(rng.randint(0, 3)):
        b_idx += 1
        bid = f"B{b_idx:05d}"
        borrower_ids.append(bid)
        new_borrowers.append({"borrower_id": bid, "segment": rng.choice(SEGMENTS),
                              "state": rng.choice(STATES), "channel": rng.choice(CHANNELS),
                              "signup_date": day.isoformat()})
    if borrower_ids:
        for _ in range(rng.randint(1, 4)):
            l_idx += 1
            lid = f"L{l_idx:06d}"
            principal = rng.choice(PRINCIPALS)
            tenor = rng.choice(TENORS)
            amount_due = round(principal * (1 + FLAT_RATE), 2)
            new_loans.append({"loan_id": lid, "borrower_id": rng.choice(borrower_ids),
                              "principal": principal, "currency": "NGN",
                              "interest_rate": FLAT_RATE, "tenor_days": tenor,
                              "disbursed_date": day.isoformat()})
            new_schedule.append({"loan_id": lid, "installment_no": 1,
                                 "due_date": (day + datetime.timedelta(days=tenor)).isoformat(),
                                 "amount_due": amount_due})
            new_status.append({"loan_id": lid, "changed_at": day.isoformat(),
                               "old_status": None, "new_status": "active"})
            plans[lid] = loan_plan(lid, day, tenor, amount_due)

    # performance: emit any event that falls on this day
    for lid, plan in plans.items():
        for (edate, old_s, new_s) in plan["status_changes"]:
            if edate == day:
                new_status.append({"loan_id": lid, "changed_at": day.isoformat(),
                                   "old_status": old_s, "new_status": new_s})
        for (edate, amount) in plan["repayments"]:
            if edate == day:
                new_repay.append({"repayment_id": f"RP{lid}", "loan_id": lid,
                                  "paid_date": day.isoformat(), "amount_paid": amount})

# --- 5. Append to BigQuery -----------------------------------------------
SCHEMAS = {
    "borrowers": [bigquery.SchemaField(c, t) for c, t in [
        ("borrower_id","STRING"),("segment","STRING"),("state","STRING"),("channel","STRING"),("signup_date","DATE")]],
    "loans": [bigquery.SchemaField(c, t) for c, t in [
        ("loan_id","STRING"),("borrower_id","STRING"),("principal","FLOAT64"),("currency","STRING"),
        ("interest_rate","FLOAT64"),("tenor_days","INT64"),("disbursed_date","DATE")]],
    "repayment_schedule": [bigquery.SchemaField(c, t) for c, t in [
        ("loan_id","STRING"),("installment_no","INT64"),("due_date","DATE"),("amount_due","FLOAT64")]],
    "repayments": [bigquery.SchemaField(c, t) for c, t in [
        ("repayment_id","STRING"),("loan_id","STRING"),("paid_date","DATE"),("amount_paid","FLOAT64")]],
    "loan_status_changes": [bigquery.SchemaField(c, t) for c, t in [
        ("loan_id","STRING"),("changed_at","DATE"),("old_status","STRING"),("new_status","STRING")]],
}

def append(name, rows):
    if not rows: return
    cfg = bigquery.LoadJobConfig(schema=SCHEMAS[name], write_disposition="WRITE_APPEND")
    client.load_table_from_json(rows, tbl(name), job_config=cfg).result()

append("borrowers", new_borrowers)
append("loans", new_loans)
append("repayment_schedule", new_schedule)
append("repayments", new_repay)
append("loan_status_changes", new_status)

client.load_table_from_json(
    [{"gen_date": d.isoformat()} for d in days_to_generate], tbl("_generation_log"),
    job_config=bigquery.LoadJobConfig(
        schema=[bigquery.SchemaField("gen_date","DATE")], write_disposition="WRITE_APPEND"),
).result()

print(f"Generated {len(days_to_generate)} day(s): {len(new_borrowers)} borrowers, "
      f"{len(new_loans)} loans, {len(new_repay)} repayments, {len(new_status)} status rows.")