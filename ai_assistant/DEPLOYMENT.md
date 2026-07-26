# Deploying the AI Assistant (Phase 6) to Streamlit Community Cloud

The Streamlit app currently talks to your local PostgreSQL database. A cloud-hosted
app can't reach `localhost` on your machine, so deployment has two parts: getting
your database somewhere reachable from the internet, then deploying the app itself.

---

## Part 1 — Move the database to a free cloud host

Pick one (all have generous free tiers, all are plain PostgreSQL so nothing in
the project changes except connection details):

- **[Neon](https://neon.tech)** — serverless Postgres, generous free tier, easiest setup
- **[Supabase](https://supabase.com)** — Postgres + extras, free tier
- **[Render](https://render.com)** — free Postgres instance (expires after 90 days on free tier)

### Steps (using Neon as the example)

1. Sign up at neon.tech → **Create a project** → name it `financial-ops`.
2. Neon gives you a connection string immediately, looking like:
   ```
   postgresql://<user>:<password>@<host>.neon.tech/<dbname>?sslmode=require
   ```
   Note the **host**, **user**, **password**, and **dbname** separately — you'll need them individually.
3. From your local machine, point the pipeline at this new database instead of
   local Postgres. Update your local `.env`:
   ```
   DB_HOST=<host>.neon.tech
   DB_PORT=5432
   DB_NAME=<dbname>
   DB_USER=<user>
   DB_PASSWORD=<password>
   DB_SSLMODE=require
   ```
4. Re-run the pipeline against this new remote DB to populate it:
   ```powershell
   python database\load_data.py
   psql "postgresql://<user>:<password>@<host>.neon.tech/<dbname>?sslmode=require" -f analytics\views.sql
   python etl\etl_pipeline.py
   ```
5. Create the read-only role on the cloud DB too:
   ```powershell
   psql "postgresql://<user>:<password>@<host>.neon.tech/<dbname>?sslmode=require" -f ai_assistant\setup_readonly_role.sql
   ```
6. Update Power BI's data source to point at this same host if you want your
   dashboard and AI assistant reading from the same live data (Get Data →
   change connection, or Transform Data → Data Source Settings).

---

## Part 2 — Deploy the Streamlit app

1. Make sure your latest code (including the `common/` folder, `ai_assistant/app.py`,
   and `requirements.txt`) is pushed to GitHub:
   ```powershell
   git add .
   git commit -m "Cloud DB support + Streamlit Cloud secrets bridging"
   git push
   ```
2. Go to **[share.streamlit.io](https://share.streamlit.io)** → sign in with GitHub.
3. Click **New app** → select your repository → branch `main` → set
   **Main file path** to:
   ```
   ai_assistant/app.py
   ```
4. Click **Advanced settings** before deploying, and paste your secrets in
   TOML format (this is the cloud equivalent of your local `.env` — nothing
   here should ever go into the git repo):
   ```toml
   OPENAI_API_KEY = "sk-..."
   OPENAI_MODEL = "gpt-4o-mini"

   DB_HOST = "<host>.neon.tech"
   DB_PORT = "5432"
   DB_NAME = "<dbname>"
   DB_READONLY_USER = "readonly_user"
   DB_READONLY_PASSWORD = "readonly_pass"
   DB_SSLMODE = "require"
   ```
   (Only `DB_READONLY_USER`/`DB_READONLY_PASSWORD` are needed here — the app
   only ever queries through the read-only role, never the full `DB_USER`.)
5. Click **Deploy**. First build takes a few minutes (installing everything
   in `requirements.txt`).
6. Once live, you get a public URL like:
   ```
   https://<your-app-name>.streamlit.app
   ```
   This is shareable — put it in your resume/portfolio/LinkedIn.

---

## Part 3 — Verify it works

1. Open the deployed URL.
2. Click one of the example question buttons in the sidebar (e.g. "Which
   counterparty caused the most failures?").
3. Confirm it generates SQL, returns a results table, and produces an AI summary.
4. If something fails, click **Manage app → Logs** in the Streamlit Cloud
   dashboard — the error will point at exactly which step failed (usually a
   missing/misnamed secret).

---

## Notes on cost and limits

- Neon/Supabase free tiers can pause/sleep an idle database after inactivity
  — the first query after a period of no use may take a few seconds longer
  while it wakes up. Fine for a portfolio demo, not for production traffic.
- Streamlit Community Cloud apps also sleep after inactivity and take a
  moment to "wake up" on the next visit — this is normal on the free tier.
- OpenAI API calls are billed per token — the assistant makes 2 calls per
  question (SQL generation + summary), both using short prompts, so cost per
  question is a fraction of a cent with `gpt-4o-mini`.
