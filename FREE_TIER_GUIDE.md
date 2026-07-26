# Running This Entire Project on Free Tiers

Every piece of this project can run at $0/month except one: Power BI's
*automated* scheduled refresh. That specific feature requires a Pro license.
Everything else below is genuinely free, verified as of mid-2026 pricing.

## The stack

| Service | Free tier | Good enough for this project? |
|---|---|---|
| GitHub | Free, unlimited public repos | Yes |
| Neon (PostgreSQL) | 0.5 GB storage/project, 100 CU-hours/month, no card required | Yes — our DB is ~74 MB |
| Groq (LLM API) | Every model, no card, ~30 requests/min, ~1,000-14,400 requests/day | Yes — plenty for a demo assistant |
| Streamlit Community Cloud | Free hosting, 1 GB RAM per app, public repo required | Yes |
| Gmail SMTP | Free with an App Password | Yes |
| Power BI Desktop | Completely free | Yes |
| Power BI Service (personal workspace) | Free — publish + view your own reports, manual refresh | Yes |
| Power BI **scheduled/API** refresh | **Requires Pro ($14/mo)** | **No free option** — see below |

---

## 1. Database: Neon (free, no card)

1. Sign up at [neon.tech](https://neon.tech) → **Create a project**.
2. Copy the connection details (host, user, password, dbname) it gives you.
3. Update your local `.env`:
   ```
   DB_HOST=<your-project>.neon.tech
   DB_PORT=5432
   DB_NAME=<dbname>
   DB_USER=<user>
   DB_PASSWORD=<password>
   DB_SSLMODE=require
   ```
4. Run the pipeline against it (same commands as local, just pointed at Neon now):
   ```powershell
   python database\load_data.py
   psql "postgresql://<user>:<password>@<host>.neon.tech/<dbname>?sslmode=require" -f analytics\views.sql
   python etl\etl_pipeline.py
   psql "postgresql://<user>:<password>@<host>.neon.tech/<dbname>?sslmode=require" -f ai_assistant\setup_readonly_role.sql
   ```
5. Our full database (calendar, employees, counterparties, transactions, 3 KPI
   tables) is ~74 MB — comfortably inside Neon's 500 MB free cap, with room
   to grow the transaction volume if you want.

## 2. LLM: Groq (free, no card)

1. Sign up at [console.groq.com](https://console.groq.com/keys) with an email
   or Google account → generate an API key. Takes under a minute.
2. Set in `.env`:
   ```
   OPENAI_API_KEY=<your groq key>
   OPENAI_BASE_URL=https://api.groq.com/openai/v1
   OPENAI_MODEL=llama-3.3-70b-versatile
   ```
   Groq's API is OpenAI-compatible, so no code changes are needed — `common/llm.py`
   already reads `OPENAI_BASE_URL` and routes there automatically if it's set.
3. Free tier gives ~30 requests/minute and roughly 1,000+ requests/day
   depending on the model — the AI assistant makes 2 calls per question (SQL
   generation + summary), so this comfortably covers demo/portfolio traffic.
   It is **not** meant for production-scale concurrent usage.

## 3. Hosting the AI assistant: Streamlit Community Cloud (free)

1. Push your code to a **public** GitHub repo (Community Cloud requires this
   on the free tier).
2. Go to [share.streamlit.io](https://share.streamlit.io) → sign in with GitHub
   → **New app** → point at `ai_assistant/app.py`.
3. Add your secrets (Advanced settings → Secrets) in TOML format:
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
4. Deploy. You get a public `https://<name>.streamlit.app` URL, free forever
   on the Community Cloud tier (apps sleep after inactivity and wake on the
   next visit — normal, not a problem for a portfolio piece).

## 4. Email report: Gmail SMTP (free)

1. Turn on 2-Step Verification on your Google account.
2. Google Account → Security → **App passwords** → generate one for "Mail".
3. Set in `.env`:
   ```
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USER=<your gmail address>
   SMTP_PASSWORD=<the app password>
   REPORT_RECIPIENT=<where to send the report>
   ```
No cost, no separate signup — this is your existing Gmail account.

## 5. Power BI — the one thing that isn't fully free

**What's free:** Power BI Desktop (build everything, unlimited), and
publishing your report to your **personal workspace** in the Power BI
Service, where you can view it and hit **Refresh** manually any time.

**What requires Pro ($14/user/month):** scheduled/automatic refresh, sharing
with other people, and — relevant to Phase 7 — triggering a refresh via the
Power BI REST API (`refresh_powerbi_dataset()` in `automation/run_pipeline.py`
needs a dataset that supports API-triggered refresh, which is a Pro/PPU
feature on shared capacity).

**Free-tier-compatible options:**
- **Manual refresh workflow** (recommended, $0): whenever you re-run the ETL,
  open Power BI Desktop → click **Refresh** → **Publish** again. Takes under
  a minute. The automation script's Power BI step will just print "skipped"
  since `PBI_*` env vars aren't set — everything else (ETL, AI summary,
  email) still runs automatically on schedule.
- **60-day Pro trial**: Microsoft offers a free trial if you want to test
  the fully automated refresh path temporarily — just know it reverts to
  Free (and scheduled refresh stops working) after 60 days unless you pay.

Given the goal is a free, portfolio-grade deployment, the honest recommendation
is: automate everything except the Power BI refresh, and refresh/republish
that one piece manually. It's a two-click step, not a real burden.

---

## Summary: what "done" looks like on pure free tier

- Data pipeline (Phases 1-4): runs locally or via Task Scheduler/cron, $0
- Database: Neon, $0
- AI assistant: Streamlit Community Cloud + Groq, $0, publicly accessible
- Email reports: Gmail SMTP, $0, automated on schedule
- Power BI dashboard: published and viewable in your personal workspace, $0,
  refreshed with one manual click whenever you update the data
