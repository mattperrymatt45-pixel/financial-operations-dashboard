# Setup & Execution Guide

Full step-by-step instructions for installing prerequisites and running every
phase locally. For a project overview, see [README.md](README.md).

---

## 0. Prerequisites (install once)

| Tool | Why | Where to get it |
|---|---|---|
| Python 3.10+ | data generation, ETL | python.org |
| PostgreSQL 14+ | database | postgresql.org (or `brew install postgresql` / `apt install postgresql`) |
| Power BI Desktop | dashboards (Phase 5) | Windows only — Microsoft Store or powerbi.microsoft.com |
| Git | version control | git-scm.com |

Python packages (install into a virtual environment):
```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install pandas numpy faker sqlalchemy psycopg2-binary
```

---

## 1. Project structure

Unzip the deliverable into a working folder:
```text
financial-operations-dashboard/
├── data/
│   ├── generate_data.py
│   └── *.csv                (generated, not committed to git - see .gitignore below)
├── database/
│   ├── schema.sql
│   └── load_data.py
├── analytics/
│   └── views.sql
├── etl/
│   └── etl_pipeline.py
├── dashboard/
│   └── PowerBI_Build_Guide.md
├── requirements.txt
├── README.md                 (this file)
└── .env                       (create this yourself - never commit it)
```

---

## 2. Where each phase executes

| Phase | Runs on | Command |
|---|---|---|
| 1. Data generation | Your machine, terminal | `python3 data/generate_data.py` |
| 2. Database load | Your machine, terminal (needs local Postgres running) | `python3 database/load_data.py` |
| 3. SQL views | Your machine, via `psql` | `psql -d financial_ops -f analytics/views.sql` |
| 4. ETL | Your machine, terminal | `python3 etl/etl_pipeline.py` |
| 5. Power BI | Power BI Desktop app (GUI, not terminal) | Follow `dashboard/PowerBI_Build_Guide.md` |
| 6. AI Assistant (upcoming) | Your machine, terminal | `streamlit run ai_assistant/app.py` |
| 7. Automation (upcoming) | Task Scheduler / cron / Airflow | scheduled, not manual |

Run 1 → 2 → 3 → 4 in that exact order every time you regenerate data — each
step depends on the previous one's output.

---

## 3. Step-by-step: getting a working local Postgres

**macOS:**
```bash
brew install postgresql@16
brew services start postgresql@16
createdb financial_ops
```

**Windows:** install via the EDB installer (postgresql.org/download/windows),
then use pgAdmin or `psql` (installed alongside) to run `CREATE DATABASE financial_ops;`.

**Linux (Ubuntu/Debian):**
```bash
sudo apt update && sudo apt install postgresql postgresql-contrib
sudo service postgresql start
sudo -u postgres psql -c "ALTER USER postgres PASSWORD 'postgres';"
sudo -u postgres createdb financial_ops
```

Then update the connection strings in `database/load_data.py` and
`etl/etl_pipeline.py` if your username/password/host differ from the defaults
(`postgres` / `postgres` / `localhost:5432`).

---

## 4. Full run, start to finish

```bash
cd financial-operations-dashboard

# Phase 1: generate synthetic data (writes CSVs into data/)
python3 data/generate_data.py

# Phase 2: create schema + load CSVs into Postgres
python3 database/load_data.py

# Phase 3: create analytics views
psql -d financial_ops -U postgres -f analytics/views.sql

# Phase 4: run ETL, populate daily_kpi / monthly_kpi / region_kpi
python3 etl/etl_pipeline.py

# Phase 5: open Power BI Desktop, connect to financial_ops, follow the guide
```

Verify at any point with:
```bash
psql -d financial_ops -U postgres -c "\dt"
psql -d financial_ops -U postgres -c "SELECT * FROM region_kpi;"
```

---

## 5. Re-running after changes

If you edit `generate_data.py` (e.g. tweak volumes or business rules), you must
re-run **all four** steps in order — the database tables get dropped/recreated
each time (`load_data.py` uses `DROP TABLE ... CASCADE`, which also drops the
Phase 3 views, so re-run `views.sql` after every reload).

---

## 6. requirements.txt

```text
pandas
numpy
faker
sqlalchemy
psycopg2-binary
streamlit          # for the upcoming AI assistant phase
openai              # or google-generativeai, depending on which LLM you use
```

---

## 7. .gitignore (create this in the project root)

```text
venv/
.env
data/*.csv
__pycache__/
*.pyc
```

Don't commit the generated CSVs (they're large and reproducible from the seeded
script) or your `.env` file (will hold DB credentials / API keys once Phase 6
adds the LLM integration).
