import json
import datetime
import requests
from google.cloud import bigquery
from google.oauth2 import service_account

# --- Config ---------------------------------------------------------------
KEY_PATH = "sa-key.json"   # your downloaded key (must be gitignored)
DATASET = "raw"
TABLE = "fx_rates_raw"
BASE_CURRENCY = "USD"
API_URL = "https://open.er-api.com/v6/latest/USD"

# --- 1. Authenticate ------------------------------------------------------
credentials = service_account.Credentials.from_service_account_file(KEY_PATH)
client = bigquery.Client(credentials=credentials, project=credentials.project_id)

# --- 2. Call the API ------------------------------------------------------
response = requests.get(API_URL, timeout=30)
response.raise_for_status()
payload = response.json()

# this API signals success in the body, not just the HTTP status
if payload.get("result") != "success":
    raise RuntimeError(f"API did not return success: {payload}")

# --- 3. Shape ONE row -----------------------------------------------------
# this API gives the data's vintage as a unix timestamp, not a date string
rate_date = datetime.datetime.fromtimestamp(
    payload["time_last_update_unix"], tz=datetime.timezone.utc
).date().isoformat()

row = {
    "ingested_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "rate_date": rate_date,
    "base_currency": payload["base_code"],
    "rates_json": json.dumps(payload["rates"]),
}

# --- 4. Load into BigQuery ------------------------------------------------
# Ensure the dataset exists (harmless if it already does).
client.create_dataset(bigquery.Dataset(f"{client.project}.{DATASET}"), exists_ok=True)
table_id = f"{client.project}.{DATASET}.{TABLE}"

def table_exists(tid):
    try:
        client.get_table(tid)
        return True
    except Exception:
        return False

already_have = False
if table_exists(table_id):
    check = client.query(
        f"SELECT COUNT(*) AS n FROM `{table_id}` "
        "WHERE rate_date = @d AND base_currency = @b",
        job_config=bigquery.QueryJobConfig(query_parameters=[
            bigquery.ScalarQueryParameter("d", "DATE", row["rate_date"]),
            bigquery.ScalarQueryParameter("b", "STRING", row["base_currency"]),
        ]),
    ).result()
    already_have = list(check)[0]["n"] > 0

if already_have:
    print(f"Already have {row['rate_date']} ({row['base_currency']}). Skipping.")
else:
    schema = [
        bigquery.SchemaField("ingested_at", "TIMESTAMP"),
        bigquery.SchemaField("rate_date", "DATE"),
        bigquery.SchemaField("base_currency", "STRING"),
        bigquery.SchemaField("rates_json", "STRING"),
    ]
    job_config = bigquery.LoadJobConfig(schema=schema, write_disposition="WRITE_APPEND")
    load_job = client.load_table_from_json([row], table_id, job_config=job_config)
    load_job.result()
    print(f"Loaded {load_job.output_rows} row(s) into {table_id}.")