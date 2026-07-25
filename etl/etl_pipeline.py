"""
Phase 4: Python ETL Pipeline
Financial Operations KPI Dashboard

Extract  : read raw transactions (+ calendar) from PostgreSQL
Transform: dedupe, handle missing values, standardize currency to USD,
           compute Profit / Settlement_Delay / Failure_Rate style KPIs
Load     : write Daily_KPI, Monthly_KPI, Region_KPI tables back to PostgreSQL
"""

import pandas as pd
from sqlalchemy import create_engine

DB_URI = "postgresql+psycopg2://postgres:Rlmmlk%40810@localhost:5432/financial_ops"

# Static FX-to-USD rates (synthetic project - approximate, fixed rates are fine here)
FX_TO_USD = {
    "USD": 1.00, "EUR": 1.08, "GBP": 1.27, "CHF": 1.12,
    "JPY": 0.0067, "AUD": 0.66, "SGD": 0.74, "HKD": 0.128, "CAD": 0.73,
}


# ------------------------------------------------------------
# Extract
# ------------------------------------------------------------
def extract(engine):
    query = """
        SELECT
            t.transaction_id, t.trade_date, t.settlement_date, t.asset_class,
            t.counterparty_id, t.region, t.currency, t.trade_value, t.revenue,
            t.operational_cost, t.processing_time, t.status, t.failure_reason,
            t.sla_met, t.employee_id,
            c.fiscal_quarter, c.fiscal_year
        FROM transactions t
        JOIN calendar c ON c.cal_date = t.trade_date
    """
    df = pd.read_sql(query, engine)
    print(f"Extracted {len(df):,} rows from PostgreSQL.")
    return df


# ------------------------------------------------------------
# Transform
# ------------------------------------------------------------
def transform(df):
    before = len(df)
    df = df.drop_duplicates(subset="transaction_id").copy()
    print(f"Removed {before - len(df):,} duplicate rows.")

    # Standardize dates
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    df["settlement_date"] = pd.to_datetime(df["settlement_date"])

    # Handle missing values
    # failure_reason is legitimately null for Settled trades - fill for clarity, not a data quality issue
    df["failure_reason"] = df["failure_reason"].fillna("N/A")
    numeric_cols = ["trade_value", "revenue", "operational_cost", "processing_time"]
    missing_before = df[numeric_cols].isna().sum().sum()
    for col in numeric_cols:
        if df[col].isna().any():
            df[col] = df[col].fillna(df[col].median())
    if missing_before:
        print(f"Filled {missing_before} missing numeric values with column medians.")
    else:
        print("No missing numeric values found.")

    # Standardize currency -> USD
    df["fx_rate"] = df["currency"].map(FX_TO_USD)
    if df["fx_rate"].isna().any():
        unknown = df.loc[df["fx_rate"].isna(), "currency"].unique()
        raise ValueError(f"Missing FX rate for currencies: {unknown}")
    df["trade_value_usd"] = (df["trade_value"] * df["fx_rate"]).round(2)
    df["revenue_usd"] = (df["revenue"] * df["fx_rate"]).round(2)
    df["operational_cost_usd"] = (df["operational_cost"] * df["fx_rate"]).round(2)

    # KPI: Profit
    df["profit_usd"] = (df["revenue_usd"] - df["operational_cost_usd"]).round(2)

    # KPI: Settlement Delay (calendar days between trade and settlement)
    df["settlement_delay_days"] = (df["settlement_date"] - df["trade_date"]).dt.days

    # Flags used for downstream aggregation
    df["is_failed"] = (df["status"] == "Failed").astype(int)
    df["is_sla_met"] = df["sla_met"].astype(int)

    df["year_month"] = df["trade_date"].dt.to_period("M").astype(str)

    print(f"Transform complete. {len(df):,} clean rows ready to aggregate.")
    return df


# ------------------------------------------------------------
# Load - aggregate into the three analytics tables
# ------------------------------------------------------------
def build_daily_kpi(df):
    g = df.groupby(["trade_date", "region"], as_index=False).agg(
        transaction_count=("transaction_id", "count"),
        total_trade_value_usd=("trade_value_usd", "sum"),
        total_revenue_usd=("revenue_usd", "sum"),
        total_operational_cost_usd=("operational_cost_usd", "sum"),
        profit_usd=("profit_usd", "sum"),
        avg_processing_time=("processing_time", "mean"),
        avg_settlement_delay_days=("settlement_delay_days", "mean"),
        failed_count=("is_failed", "sum"),
        sla_met_count=("is_sla_met", "sum"),
    )
    g["failure_rate_pct"] = (100 * g["failed_count"] / g["transaction_count"]).round(2)
    g["sla_adherence_pct"] = (100 * g["sla_met_count"] / g["transaction_count"]).round(2)
    g["avg_processing_time"] = g["avg_processing_time"].round(1)
    g["avg_settlement_delay_days"] = g["avg_settlement_delay_days"].round(2)
    g = g.drop(columns=["failed_count", "sla_met_count"])
    return g.sort_values(["trade_date", "region"]).reset_index(drop=True)


def build_monthly_kpi(df):
    g = df.groupby("year_month", as_index=False).agg(
        transaction_count=("transaction_id", "count"),
        total_trade_value_usd=("trade_value_usd", "sum"),
        total_revenue_usd=("revenue_usd", "sum"),
        total_operational_cost_usd=("operational_cost_usd", "sum"),
        profit_usd=("profit_usd", "sum"),
        avg_processing_time=("processing_time", "mean"),
        avg_settlement_delay_days=("settlement_delay_days", "mean"),
        failed_count=("is_failed", "sum"),
        sla_met_count=("is_sla_met", "sum"),
    )
    g["failure_rate_pct"] = (100 * g["failed_count"] / g["transaction_count"]).round(2)
    g["sla_adherence_pct"] = (100 * g["sla_met_count"] / g["transaction_count"]).round(2)
    g["avg_processing_time"] = g["avg_processing_time"].round(1)
    g["avg_settlement_delay_days"] = g["avg_settlement_delay_days"].round(2)
    g = g.drop(columns=["failed_count", "sla_met_count"])
    return g.sort_values("year_month").reset_index(drop=True)


def build_region_kpi(df):
    g = df.groupby("region", as_index=False).agg(
        transaction_count=("transaction_id", "count"),
        total_trade_value_usd=("trade_value_usd", "sum"),
        total_revenue_usd=("revenue_usd", "sum"),
        total_operational_cost_usd=("operational_cost_usd", "sum"),
        profit_usd=("profit_usd", "sum"),
        avg_processing_time=("processing_time", "mean"),
        avg_settlement_delay_days=("settlement_delay_days", "mean"),
        failed_count=("is_failed", "sum"),
        sla_met_count=("is_sla_met", "sum"),
        active_counterparties=("counterparty_id", "nunique"),
    )
    g["failure_rate_pct"] = (100 * g["failed_count"] / g["transaction_count"]).round(2)
    g["sla_adherence_pct"] = (100 * g["sla_met_count"] / g["transaction_count"]).round(2)
    g["avg_processing_time"] = g["avg_processing_time"].round(1)
    g["avg_settlement_delay_days"] = g["avg_settlement_delay_days"].round(2)
    g = g.drop(columns=["failed_count", "sla_met_count"])
    return g.sort_values("region").reset_index(drop=True)


def load(engine, daily_kpi, monthly_kpi, region_kpi):
    daily_kpi.to_sql("daily_kpi", engine, if_exists="replace", index=False)
    monthly_kpi.to_sql("monthly_kpi", engine, if_exists="replace", index=False)
    region_kpi.to_sql("region_kpi", engine, if_exists="replace", index=False)
    print("Loaded daily_kpi, monthly_kpi, region_kpi into PostgreSQL.")


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------
def main():
    engine = create_engine(DB_URI)

    raw = extract(engine)
    clean = transform(raw)

    daily_kpi = build_daily_kpi(clean)
    monthly_kpi = build_monthly_kpi(clean)
    region_kpi = build_region_kpi(clean)

    load(engine, daily_kpi, monthly_kpi, region_kpi)

    print("\n--- Region_KPI summary ---")
    print(region_kpi.to_string(index=False))

    print("\n--- Monthly_KPI (first 3 rows) ---")
    print(monthly_kpi.head(3).to_string(index=False))

    print(f"\nDaily_KPI rows: {len(daily_kpi):,}")
    print(f"Monthly_KPI rows: {len(monthly_kpi):,}")
    print(f"Region_KPI rows: {len(region_kpi):,}")


if __name__ == "__main__":
    main()
