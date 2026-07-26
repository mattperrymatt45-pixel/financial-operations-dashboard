"""
Example Airflow DAG for the Financial Operations KPI Dashboard pipeline.

Copy this into your Airflow `dags/` folder and adjust PROJECT_PATH and the
python executable path for your environment.
"""

from datetime import datetime
import subprocess

from airflow import DAG
from airflow.operators.python import PythonOperator

PROJECT_PATH = "/opt/airflow/financial-operations-dashboard"
PYTHON_BIN = f"{PROJECT_PATH}/venv/bin/python"


def run_pipeline():
    result = subprocess.run(
        [PYTHON_BIN, f"{PROJECT_PATH}/automation/run_pipeline.py"],
        capture_output=True, text=True,
    )
    print(result.stdout)
    if result.returncode != 0:
        raise RuntimeError(result.stderr)


with DAG(
    dag_id="financial_ops_pipeline",
    description="ETL -> Power BI refresh -> AI summary -> email report",
    start_date=datetime(2026, 1, 1),
    schedule_interval="0 6 * * *",   # daily at 06:00
    catchup=False,
) as dag:
    PythonOperator(
        task_id="run_full_pipeline",
        python_callable=run_pipeline,
    )
