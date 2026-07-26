# Master Deployment Checklist

One linear path from "code on my laptop" to "fully deployed, free, public
dashboard + AI assistant." Follow in order — later steps depend on earlier ones.

---

## Part A — Cloud database (Neon)

1. Go to [neon.tech](https://neon.tech) → sign up (no card needed) → **Create a project** → name it `financial-ops`.
2. Copy the connection info Neon shows you: host, user, password, database name.
3. Open your local `.env` file (copy from `.env.example` if you haven't yet) and set:
   ```
   DB_HOST=<your-project>.neon.tech
   DB_PORT=5432
   DB_NAME=<dbname>
   DB_USER=<user>
   DB_PASSWORD=<password>
   DB_SSLMODE=require
   ```
4. In PowerShell, from the project root, with your venv active, run the pipeline against Neon:
   ```powershell
   python database\load_data.py
   psql "postgresql://<user>:<password>@<host>.neon.tech/<dbname>?sslmode=require" -f analytics\views.sql
   python etl\etl_pipeline.py
   psql "postgresql://<user>:<password>@<host>.neon.tech/<dbname>?sslmode=require" -f ai_assistant\setup_readonly_role.sql
   ```
5. Verify: open pgAdmin, add a new server connection pointed at your Neon host, confirm all 8 tables + 8 views exist and `region_kpi` shows 3 rows with positive profit.

## Part B — Free LLM (Groq)

6. Go to [console.groq.com/keys](https://console.groq.com/keys) → sign in with email/Google → **Create API Key**.
7. Add to your local `.env`:
   ```
   OPENAI_API_KEY=<your groq key>
   OPENAI_BASE_URL=https://api.groq.com/openai/v1
   OPENAI_MODEL=llama-3.3-70b-versatile
   ```

## Part C — Test the AI assistant locally against the cloud DB

8. In PowerShell:
   ```powershell
   streamlit run ai_assistant\app.py
   ```
9. It opens in your browser at `localhost:8501`. Click one of the example questions in the sidebar. Confirm you get generated SQL, a results table, and an AI summary. If it errors, check the exact message — it'll point at whichever env var is wrong.
10. Close it (Ctrl+C in the terminal) once confirmed working.

## Part D — Push everything to GitHub

11. Make sure `.gitignore` is in place (excludes `.env`, `venv/`, generated CSVs) — never commit real credentials.
12. ```powershell
    git add .
    git commit -m "Add AI assistant, automation, free-tier config"
    git push
    ```
13. Confirm on github.com that `common/`, `ai_assistant/`, `automation/` folders are all present, and `.env` is **not** in the file list.

## Part E — Deploy the AI assistant (Streamlit Community Cloud)

14. Go to [share.streamlit.io](https://share.streamlit.io) → sign in with GitHub.
15. **New app** → select your repo → branch `main` → main file path: `ai_assistant/app.py`.
16. Before clicking Deploy, open **Advanced settings → Secrets** and paste (TOML format):
    ```toml
    OPENAI_API_KEY = "<your groq key>"
    OPENAI_BASE_URL = "https://api.groq.com/openai/v1"
    OPENAI_MODEL = "llama-3.3-70b-versatile"

    DB_HOST = "<your-project>.neon.tech"
    DB_PORT = "5432"
    DB_NAME = "<dbname>"
    DB_READONLY_USER = "readonly_user"
    DB_READONLY_PASSWORD = "readonly_pass"
    DB_SSLMODE = "require"
    ```
17. Click **Deploy**. Wait a few minutes for the build.
18. Visit your public URL (`https://<name>.streamlit.app`), test it the same way as step 9.

## Part F — Publish the Power BI dashboard

19. Open your `.pbix` in Power BI Desktop.
20. Update the data source to point at Neon instead of localhost: **Home → Transform Data → Data Source Settings** → change server to `<your-project>.neon.tech`, database to your Neon dbname, and update credentials. Click **Refresh** to confirm it pulls data successfully.
21. **Home → Publish** → sign in → choose "My workspace" → publish.
22. Open the published report link — this is free to view for yourself; sharing with others needs Pro (skip unless you want to pay for that).

## Part G — Email reports (optional, free)

23. Turn on 2-Step Verification on your Google account → Security → **App Passwords** → generate one for "Mail".
24. Add to `.env`:
    ```
    SMTP_HOST=smtp.gmail.com
    SMTP_PORT=587
    SMTP_USER=<your gmail>
    SMTP_PASSWORD=<the app password>
    REPORT_RECIPIENT=<recipient email>
    ```

## Part H — Schedule the automation pipeline (optional)

25. Test it manually first:
    ```powershell
    python automation\run_pipeline.py
    ```
    Confirm the ETL, AI summary, and email steps all run (Power BI refresh will say "skipped" — that's expected and fine, see below).
26. Schedule it with Windows Task Scheduler:
    ```powershell
    schtasks /create /tn "FinancialOpsPipeline" ^
      /tr "\"C:\path\to\venv\Scripts\python.exe\" \"C:\path\to\financial-operations-dashboard\automation\run_pipeline.py\"" ^
      /sc daily /st 06:00
    ```

## Part I — The one manual step that stays manual

27. Power BI's *automatic* scheduled refresh needs a Pro license. On the free
    tier, whenever you want the published dashboard to reflect new data:
    open Power BI Desktop → **Refresh** → **Publish**. Takes under a minute.

---

## Final verification checklist

- [ ] Neon database has all 8 tables/views, ~74MB, well under the 500MB cap
- [ ] `streamlit run ai_assistant/app.py` works locally against Neon
- [ ] Code pushed to GitHub, `.env` NOT in the repo
- [ ] Streamlit Community Cloud app is live at a public URL and answers questions
- [ ] Power BI report published to your personal workspace, data source pointed at Neon
- [ ] (Optional) Email report sends successfully via Gmail SMTP
- [ ] (Optional) Task Scheduler job created for daily automated runs

Total cost: **$0/month**, one manual click per data refresh.
