"""
Phase 2: Load Phase 1 CSVs into PostgreSQL.

- Creates the schema (schema.sql)
- Loads Calendar -> Employees -> Counterparties -> Transactions (FK order matters)
- Verifies row counts against the source CSVs
"""

import os
import psycopg2
import pandas as pd

DB_CONFIG = dict(
    host="localhost",
    port=5432,
    dbname="financial_ops",
    user="postgres",
    password="Rlmmlk%40810",
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(BASE_DIR), "data")
SCHEMA_FILE = os.path.join(BASE_DIR, "schema.sql")

# (csv_filename, table_name, column_list_in_csv_order)
LOAD_PLAN = [
    ("Calendar.csv", "calendar",
     ["cal_date", "day_of_week", "is_weekend", "fiscal_quarter", "fiscal_year", "is_holiday"]),
    ("Employees.csv", "employees",
     ["employee_id", "name", "region", "department", "hire_date"]),
    ("Counterparties.csv", "counterparties",
     ["counterparty_id", "name", "region", "type", "risk_rating", "onboard_date"]),
    ("Transactions.csv", "transactions",
     ["transaction_id", "trade_date", "trade_hour", "settlement_date", "asset_class",
      "counterparty_id", "region", "currency", "trade_value", "revenue",
      "operational_cost", "processing_time", "status", "failure_reason",
      "sla_met", "employee_id"]),
]


def create_schema(conn):
    with open(SCHEMA_FILE) as f:
        ddl = f.read()
    with conn.cursor() as cur:
        cur.execute(ddl)
    conn.commit()
    print("Schema created.")


def load_table(conn, csv_file, table, columns):
    path = os.path.join(DATA_DIR, csv_file)
    col_list = ", ".join(columns)
    copy_sql = f"COPY {table} ({col_list}) FROM STDIN WITH (FORMAT CSV, HEADER TRUE)"
    with conn.cursor() as cur, open(path, "r") as f:
        cur.copy_expert(copy_sql, f)
    conn.commit()
    print(f"Loaded {table} from {csv_file}")


def verify_counts(conn):
    print("\n--- Verification: PostgreSQL row counts vs source CSVs ---")
    for csv_file, table, _ in LOAD_PLAN:
        csv_path = os.path.join(DATA_DIR, csv_file)
        csv_count = sum(1 for _ in open(csv_path)) - 1  # minus header
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            db_count = cur.fetchone()[0]
        status = "OK" if csv_count == db_count else "MISMATCH"
        print(f"{table:<16} CSV: {csv_count:>8,}   DB: {db_count:>8,}   [{status}]")


def main():
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        create_schema(conn)
        for csv_file, table, columns in LOAD_PLAN:
            load_table(conn, csv_file, table, columns)
        verify_counts(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
