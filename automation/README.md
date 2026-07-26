# Phase 7: Automation Setup

`run_pipeline.py` runs: ETL → Power BI refresh → AI summary → email report.
Each external integration (Power BI, OpenAI, SMTP) degrades gracefully and
just prints a "skipped" message if its environment variables aren't set, so
you can wire these up one at a time.

## 1. Environment variables

Copy `.env.example` (project root) to `.env` and fill in what you have:

| Variable | Needed for |
|---|---|
| `OPENAI_API_KEY`, `OPENAI_MODEL` | AI summary + AI assistant (Phase 6) |
| `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `DB_NAME` | ETL / DB writes |
| `DB_READONLY_USER`, `DB_READONLY_PASSWORD` | AI assistant read-only queries |
| `PBI_TENANT_ID`, `PBI_CLIENT_ID`, `PBI_CLIENT_SECRET`, `PBI_WORKSPACE_ID`, `PBI_DATASET_ID` | Power BI dataset refresh |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `REPORT_RECIPIENT` | Email report |

### Getting the Power BI service principal credentials
1. In Azure Portal → **App registrations** → **New registration**. Note the
   **Application (client) ID** and **Directory (tenant) ID**.
2. **Certificates & secrets** → new client secret → copy the value (this is
   `PBI_CLIENT_SECRET`, shown only once).
3. In the **Power BI Admin Portal** → **Tenant settings**, enable
   "Service principals can use Power BI APIs" for your security group.
4. In the Power BI Service, open your workspace → **Access** → add the app
   registration as a **Member** (or Admin).
5. `PBI_WORKSPACE_ID` and `PBI_DATASET_ID` are in the URL when you view the
   dataset's settings page in the Power BI Service
   (`.../groups/<WORKSPACE_ID>/datasets/<DATASET_ID>/...`).

### Getting SMTP credentials (Gmail example)
1. Enable 2-Step Verification on the Google account.
2. Create an **App Password** (Google Account → Security → App passwords).
3. `SMTP_HOST=smtp.gmail.com`, `SMTP_PORT=587`, `SMTP_USER=<your gmail>`,
   `SMTP_PASSWORD=<the app password>`.

## 2. Run it manually first

```powershell
venv\Scripts\activate
python automation\run_pipeline.py
```
Add `--regenerate` if you also want fresh synthetic source data before the
ETL step (mainly useful for demos, not typical in a real deployment where
transactions already exist).

## 3. Schedule it

### Windows Task Scheduler
```powershell
schtasks /create /tn "FinancialOpsPipeline" ^
  /tr "\"C:\path\to\venv\Scripts\python.exe\" \"C:\path\to\financial-operations-dashboard\automation\run_pipeline.py\"" ^
  /sc daily /st 06:00
```
Or use the GUI: Task Scheduler → Create Task → Actions → Start a Program →
point Program at your venv's `python.exe` and Arguments at the full path to
`run_pipeline.py`. Set Trigger to Daily at your preferred time.

### Cron (Linux/macOS, e.g. if you move this to a server later)
```bash
0 6 * * * /path/to/venv/bin/python /path/to/financial-operations-dashboard/automation/run_pipeline.py >> /path/to/logs/pipeline.log 2>&1
```

### Airflow
See `automation/airflow_dag_example.py` — copy it into your Airflow `dags/`
folder and adjust the path to `run_pipeline.py`.

## 4. Logs

Redirect output to a file so you can debug scheduled runs that fail silently:
```powershell
python automation\run_pipeline.py >> reports\pipeline_log.txt 2>&1
```
