"""
Shared LLM helpers for the AI assistant (Phase 6) and automation (Phase 7).

Uses the OpenAI API by default. Swap the client/model lines if you'd rather
use Gemini (google-generativeai) - the question_to_sql / summarize_results
function signatures are what the rest of the app depends on, so keep those
the same.
"""

import os
import pandas as pd
from openai import OpenAI

_client = None


def _get_client():
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Add it to your .env file "
                "(see .env.example). This can be a free Groq key - see "
                "README for details."
            )
        base_url = os.getenv("OPENAI_BASE_URL")  # set to https://api.groq.com/openai/v1 for Groq
        _client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
    return _client


MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

SCHEMA_DESC = """
-- Pre-aggregated KPI tables (prefer these over raw `transactions` when possible)
daily_kpi (trade_date, region, transaction_count, total_trade_value_usd,
           total_revenue_usd, total_operational_cost_usd, profit_usd,
           avg_processing_time, avg_settlement_delay_days,
           failure_rate_pct, sla_adherence_pct)

monthly_kpi (year_month, transaction_count, total_trade_value_usd,
             total_revenue_usd, total_operational_cost_usd, profit_usd,
             avg_processing_time, avg_settlement_delay_days,
             failure_rate_pct, sla_adherence_pct)

region_kpi (region, transaction_count, total_trade_value_usd,
            total_revenue_usd, total_operational_cost_usd, profit_usd,
            avg_processing_time, avg_settlement_delay_days,
            failure_rate_pct, sla_adherence_pct, active_counterparties)

-- Analytics views
vw_top_counterparties (counterparty_id, name, region, type, risk_rating,
                       total_trades, total_revenue, avg_processing_time,
                       failed_trades, failure_rate_pct, revenue_rank)

vw_failed_trades_by_region (region, failure_reason, failed_trade_count,
                            avg_failed_trade_value, avg_processing_time,
                            pct_of_region_failures)

vw_employee_productivity (employee_id, name, region, department,
                          trades_handled, avg_processing_time,
                          failed_trades, sla_adherence_pct)

-- Raw tables (use only if the KPI tables/views above can't answer the question)
transactions (transaction_id, trade_date, settlement_date, asset_class,
              counterparty_id, region, currency, trade_value, revenue,
              operational_cost, processing_time, status, failure_reason,
              sla_met, employee_id)
calendar (cal_date, day_of_week, is_weekend, fiscal_quarter, fiscal_year, is_holiday)
employees (employee_id, name, region, department, hire_date)
counterparties (counterparty_id, name, region, type, risk_rating, onboard_date)
"""


def question_to_sql(question: str) -> str:
    prompt = f"""You are a PostgreSQL expert working against this schema:
{SCHEMA_DESC}

Write ONE read-only SQL SELECT query (PostgreSQL syntax) that answers the
question below.

Rules:
- ONLY a SELECT statement. Never write INSERT/UPDATE/DELETE/DROP/ALTER/CREATE/TRUNCATE.
- Return ONLY the raw SQL - no markdown fences, no explanation, no trailing semicolon.
- Prefer daily_kpi / monthly_kpi / region_kpi / vw_* views over the raw
  transactions table whenever they can answer the question.
- If comparing time periods (e.g. "today vs yesterday"), use daily_kpi and
  filter/order by trade_date.

Question: {question}

SQL:"""

    resp = _get_client().chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    sql = resp.choices[0].message.content.strip()

    # Defensive cleanup in case the model wraps it in a code fence anyway
    sql = sql.strip("`")
    if sql.lower().startswith("sql"):
        sql = sql[3:].strip()
    return sql.rstrip(";").strip()


def summarize_results(question: str, df: pd.DataFrame) -> str:
    preview = df.head(30).to_csv(index=False)
    prompt = f"""You are a financial operations analyst. A user asked:
"{question}"

Here is the query result (CSV, up to 30 rows):
{preview}

Write a concise 3-5 sentence natural-language summary of what this data shows.
If something looks like a risk or opportunity, name one concrete, actionable
recommendation. Do not just restate every row - synthesize the pattern."""

    resp = _get_client().chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )
    return resp.choices[0].message.content.strip()
