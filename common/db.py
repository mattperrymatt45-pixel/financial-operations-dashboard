"""
Shared PostgreSQL access for the AI assistant (Phase 6) and automation (Phase 7).

IMPORTANT: get_engine(readonly=True) is what the LLM-generated SQL runs through.
run_readonly_query() additionally enforces, in code (not just via DB role), that
only a single SELECT statement can execute - defense in depth in case the
readonly_user role hasn't been set up yet.
"""

import os
from sqlalchemy import create_engine, text
import pandas as pd

FORBIDDEN_TOKENS = [
    "insert", "update", "delete", "drop", "alter", "truncate",
    "grant", "revoke", "create", "--", "/*", "copy ", "call ",
]


def get_engine(readonly: bool = True):
    if readonly:
        user = os.getenv("DB_READONLY_USER", "readonly_user")
        password = os.getenv("DB_READONLY_PASSWORD", "readonly_pass")
    else:
        user = os.getenv("DB_USER", "postgres")
        password = os.getenv("DB_PASSWORD", "postgres")
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    dbname = os.getenv("DB_NAME", "financial_ops")
    sslmode = os.getenv("DB_SSLMODE")  # e.g. "require" for Neon/Supabase/Render
    uri = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{dbname}"
    if sslmode:
        uri += f"?sslmode={sslmode}"
    return create_engine(uri)


def is_safe_select(sql: str) -> bool:
    """Only a single, unadorned SELECT statement is allowed."""
    s = sql.strip().lower()
    if not s.startswith("select"):
        return False
    body = s[:-1] if s.endswith(";") else s
    if ";" in body:            # no stacked statements
        return False
    return not any(tok in body for tok in FORBIDDEN_TOKENS)


def run_readonly_query(sql: str) -> pd.DataFrame:
    if not is_safe_select(sql):
        raise ValueError(
            "Refusing to run this query: only a single read-only SELECT "
            "statement is allowed. Got:\n" + sql
        )
    engine = get_engine(readonly=True)
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn)
