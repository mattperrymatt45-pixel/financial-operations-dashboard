"""
Phase 7: End-to-end automation
Financial Operations KPI Dashboard

Data Generation -> PostgreSQL -> ETL -> Analytics Tables -> Power BI Refresh
                                                          -> AI Summary -> Email Report

This script re-runs the ETL, triggers a Power BI dataset refresh (if
configured), generates an AI narrative summary of the latest KPIs, and
emails it out. It's meant to be triggered on a schedule - see
automation/README.md for Windows Task Scheduler / cron / Airflow setup.

Data generation (Phase 1) is deliberately NOT re-run automatically here -
in a real pipeline the raw transactions already exist; only the ETL/refresh/
report steps repeat. Pass --regenerate if you explicitly want fresh synthetic
data too (mainly useful for demos).
"""

import argparse
import os
import smtplib
import subprocess
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

sys.path.append(str(Path(__file__).resolve().parents[1]))
from common.db import get_engine
from common.llm import summarize_results

load_dotenv()

ROOT = Path(__file__).resolve().parents[1]


# ------------------------------------------------------------
# Step: Data generation (optional)
# ------------------------------------------------------------
def run_data_generation():
    print("Regenerating synthetic data (Phase 1)...")
    result = subprocess.run(
        [sys.executable, str(ROOT / "data" / "generate_data.py")],
        capture_output=True, text=True,
    )
    print(result.stdout)
    if result.returncode != 0:
        raise RuntimeError(f"Data generation failed:\n{result.stderr}")


# ------------------------------------------------------------
# Step: ETL (Phase 4)
# ------------------------------------------------------------
def run_etl():
    print("Running ETL pipeline...")
    result = subprocess.run(
        [sys.executable, str(ROOT / "etl" / "etl_pipeline.py")],
        capture_output=True, text=True,
    )
    print(result.stdout)
    if result.returncode != 0:
        raise RuntimeError(f"ETL failed:\n{result.stderr}")


# ------------------------------------------------------------
# Step: Power BI dataset refresh
# ------------------------------------------------------------
def refresh_powerbi_dataset() -> bool:
    """
    Triggers a Power BI dataset refresh via the REST API.

    Requires an Azure AD app registration (service principal) that has:
      - Power BI Service API permission: Dataset.ReadWrite.All (admin consented)
      - Been added as a member/admin of the target Power BI workspace

    Set these env vars: PBI_TENANT_ID, PBI_CLIENT_ID, PBI_CLIENT_SECRET,
    PBI_WORKSPACE_ID, PBI_DATASET_ID (workspace/dataset IDs are in the
    Power BI Service URL when viewing the dataset settings page).
    """
    required = ["PBI_TENANT_ID", "PBI_CLIENT_ID", "PBI_CLIENT_SECRET",
                "PBI_WORKSPACE_ID", "PBI_DATASET_ID"]
    if not all(os.getenv(v) for v in required):
        print("Power BI refresh skipped: PBI_* environment variables not set "
              "(see automation/README.md). Note: API-triggered/scheduled "
              "refresh requires Power BI Pro - see FREE_TIER_GUIDE.md for the "
              "free-tier workaround (manual refresh + republish).")
        return False

    import msal
    authority = f"https://login.microsoftonline.com/{os.getenv('PBI_TENANT_ID')}"
    app = msal.ConfidentialClientApplication(
        os.getenv("PBI_CLIENT_ID"),
        authority=authority,
        client_credential=os.getenv("PBI_CLIENT_SECRET"),
    )
    token_resp = app.acquire_token_for_client(
        scopes=["https://analysis.windows.net/powerbi/api/.default"]
    )
    if "access_token" not in token_resp:
        raise RuntimeError(f"Power BI auth failed: {token_resp.get('error_description')}")

    url = (
        f"https://api.powerbi.com/v1.0/myorg/groups/{os.getenv('PBI_WORKSPACE_ID')}"
        f"/datasets/{os.getenv('PBI_DATASET_ID')}/refreshes"
    )
    headers = {"Authorization": f"Bearer {token_resp['access_token']}"}
    resp = requests.post(url, headers=headers, timeout=30)
    if resp.status_code == 202:
        print("Power BI dataset refresh triggered successfully.")
        return True
    raise RuntimeError(f"Power BI refresh request failed: {resp.status_code} {resp.text}")


# ------------------------------------------------------------
# Step: AI summary
# ------------------------------------------------------------
def generate_ai_summary() -> str:
    engine = get_engine(readonly=False)
    region_kpi = pd.read_sql("SELECT * FROM region_kpi ORDER BY region", engine)
    monthly_kpi = pd.read_sql(
        "SELECT * FROM monthly_kpi ORDER BY year_month DESC LIMIT 3", engine
    )
    combined = pd.concat(
        [region_kpi.assign(grain="region_total"),
         monthly_kpi.assign(grain="last_3_months")],
        ignore_index=True,
    )
    question = (
        "Summarize overall business performance across regions and recent "
        "months, and flag any risks (e.g. rising failure rate, falling SLA "
        "adherence, or shrinking profit)."
    )
    return summarize_results(question, combined)


# ------------------------------------------------------------
# Step: Email report
# ------------------------------------------------------------
def send_email_report(summary_text: str) -> bool:
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")
    recipient = os.getenv("REPORT_RECIPIENT")

    if not all([host, user, password, recipient]):
        print("Email skipped: SMTP_* / REPORT_RECIPIENT environment variables "
              "not set (see automation/README.md).")
        return False

    msg = MIMEMultipart()
    msg["Subject"] = "Financial Operations KPI Report"
    msg["From"] = user
    msg["To"] = recipient
    html = f"""
    <html><body>
        <h2>Financial Operations KPI Report</h2>
        <p>{summary_text.replace(chr(10), '<br>')}</p>
        <hr>
        <p style="color:#888;font-size:12px;">Automatically generated by the
        Financial Operations KPI Dashboard pipeline.</p>
    </body></html>
    """
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP(host, port) as server:
        server.starttls()
        server.login(user, password)
        server.sendmail(user, recipient, msg.as_string())
    print(f"Email report sent to {recipient}.")
    return True


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Run the full automated KPI pipeline.")
    parser.add_argument("--regenerate", action="store_true",
                         help="Also regenerate synthetic source data (Phase 1) before the ETL run.")
    args = parser.parse_args()

    print("=== Financial Ops Pipeline: automated run ===")

    if args.regenerate:
        print("\n[1/5] Regenerating source data...")
        run_data_generation()
    else:
        print("\n[1/5] Skipping data regeneration (use --regenerate to include it).")

    print("\n[2/5] Running ETL...")
    run_etl()

    print("\n[3/5] Refreshing Power BI dataset...")
    refresh_powerbi_dataset()

    print("\n[4/5] Generating AI summary...")
    try:
        summary = generate_ai_summary()
        print(summary)
    except Exception as e:
        print(f"AI summary skipped: {e}")
        summary = None

    print("\n[5/5] Sending email report...")
    if summary:
        send_email_report(summary)
    else:
        print("Email skipped: no summary was generated.")

    print("\n=== Pipeline run complete ===")


if __name__ == "__main__":
    main()
