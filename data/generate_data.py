"""
Phase 1: Synthetic Data Generation
Financial Operations KPI Dashboard

Generates four related CSV tables:
  - Calendar.csv
  - Employees.csv
  - Counterparties.csv
  - Transactions.csv  (200k-500k rows, default configurable below)

Business rules encoded:
  1. Large trades  -> longer processing time
  2. New counterparties (onboarded < 90 days before trade) -> higher settlement failure probability
  3. Trades settling on/near a holiday -> increased settlement failures
  4. Failed trades -> higher operational cost (and reduced booked revenue)
  5. SLA breach if Processing_Time > 30 minutes
  6. APAC has higher transaction volume, concentrated during APAC market hours
"""

import numpy as np
import pandas as pd
from faker import Faker
import os

# ------------------------------------------------------------------
# Config
# ------------------------------------------------------------------
SEED = 42
N_TRANSACTIONS = 300_000          # within the requested 200k-500k range
N_EMPLOYEES = 250
N_COUNTERPARTIES = 1500
START_DATE = pd.Timestamp("2023-01-01")
END_DATE = pd.Timestamp("2024-12-31")          # trade dates are sampled up to here
CALENDAR_END = END_DATE + pd.Timedelta(days=10)  # buffer so T+2 settlement dates stay in-calendar
OUT_DIR = os.path.dirname(os.path.abspath(__file__))

np.random.seed(SEED)
fake = Faker()
Faker.seed(SEED)

REGIONS = ["APAC", "EMEA", "NA"]
REGION_WEIGHTS = [0.40, 0.30, 0.30]   # APAC gets the largest overall share

REGION_CURRENCIES = {
    "APAC": ["JPY", "AUD", "SGD", "HKD"],
    "EMEA": ["EUR", "GBP", "CHF"],
    "NA": ["USD", "CAD"],
}

# APAC market hours concentrated 00:00-08:00 UTC, EMEA 07:00-16:00 UTC, NA 13:00-21:00 UTC
REGION_HOUR_RANGE = {
    "APAC": (0, 8),
    "EMEA": (7, 16),
    "NA": (13, 21),
}

ASSET_CLASSES = ["Equity", "Fixed Income", "FX", "Derivatives", "Commodities"]
ASSET_WEIGHTS = [0.30, 0.25, 0.20, 0.15, 0.10]
# revenue margin in basis points of trade value, by asset class
ASSET_MARGIN_BPS = {
    "Equity": 8, "Fixed Income": 5, "FX": 3, "Derivatives": 12, "Commodities": 9
}
# typical notional scale multiplier by asset class (derivatives/FX trade bigger notionals)
ASSET_VALUE_SCALE = {
    "Equity": 1.0, "Fixed Income": 1.4, "FX": 2.2, "Derivatives": 2.8, "Commodities": 1.6
}

FAILURE_REASONS = [
    "Documentation Error", "Counterparty Default", "Insufficient Funds",
    "System Error", "Regulatory Hold", "Currency Mismatch"
]

# ------------------------------------------------------------------
# 1. Calendar table
# ------------------------------------------------------------------
def build_calendar():
    dates = pd.date_range(START_DATE, CALENDAR_END, freq="D")
    df = pd.DataFrame({"Date": dates})
    df["Day_Of_Week"] = df["Date"].dt.day_name()
    df["Is_Weekend"] = df["Date"].dt.dayofweek >= 5
    df["Fiscal_Quarter"] = df["Date"].dt.quarter
    df["Fiscal_Year"] = df["Date"].dt.year

    # A simplified shared holiday calendar (~11-12 holidays/year)
    holiday_md = [
        (1, 1), (1, 15), (2, 19), (5, 27), (6, 19),
        (7, 4), (9, 2), (11, 11), (11, 27), (12, 25), (12, 26)
    ]
    holidays = set()
    for year in range(START_DATE.year, CALENDAR_END.year + 1):
        for m, d in holiday_md:
            try:
                holidays.add(pd.Timestamp(year=year, month=m, day=d))
            except ValueError:
                pass
    df["Is_Holiday"] = df["Date"].isin(holidays)
    return df


# ------------------------------------------------------------------
# 2. Employees table
# ------------------------------------------------------------------
def build_employees():
    departments = ["Trading Ops", "Settlements", "Risk", "Client Services"]
    regions = np.random.choice(REGIONS, size=N_EMPLOYEES, p=REGION_WEIGHTS)
    hire_offsets = np.random.randint(0, 365 * 10, size=N_EMPLOYEES)
    hire_dates = [pd.Timestamp("2024-12-31") - pd.Timedelta(days=int(o)) for o in hire_offsets]

    df = pd.DataFrame({
        "Employee_ID": [f"EMP{i:05d}" for i in range(1, N_EMPLOYEES + 1)],
        "Name": [fake.name() for _ in range(N_EMPLOYEES)],
        "Region": regions,
        "Department": np.random.choice(departments, size=N_EMPLOYEES, p=[0.35, 0.30, 0.15, 0.20]),
        "Hire_Date": hire_dates,
    })
    return df


# ------------------------------------------------------------------
# 3. Counterparties table
# ------------------------------------------------------------------
def build_counterparties():
    regions = np.random.choice(REGIONS, size=N_COUNTERPARTIES, p=REGION_WEIGHTS)
    types = np.random.choice(
        ["Bank", "Hedge Fund", "Asset Manager", "Corporate", "Pension Fund"],
        size=N_COUNTERPARTIES, p=[0.30, 0.20, 0.25, 0.15, 0.10]
    )
    risk = np.random.choice(["Low", "Medium", "High"], size=N_COUNTERPARTIES, p=[0.60, 0.30, 0.10])

    # Onboard_Date: mostly well before the dataset window (established relationships),
    # but a meaningful slice onboarded during the window so the "new counterparty" rule fires.
    window_days = (END_DATE - (START_DATE - pd.Timedelta(days=365 * 5))).days
    onboard_offsets = np.random.randint(0, window_days, size=N_COUNTERPARTIES)
    onboard_dates = [START_DATE - pd.Timedelta(days=365 * 5) + pd.Timedelta(days=int(o))
                     for o in onboard_offsets]

    df = pd.DataFrame({
        "Counterparty_ID": [f"CP{i:05d}" for i in range(1, N_COUNTERPARTIES + 1)],
        "Name": [fake.company() for _ in range(N_COUNTERPARTIES)],
        "Region": regions,
        "Type": types,
        "Risk_Rating": risk,
        "Onboard_Date": onboard_dates,
    })
    return df


# ------------------------------------------------------------------
# 4. Transactions table (vectorized)
# ------------------------------------------------------------------
def add_business_days(dates, n_days):
    """Add n_days business days to an array of Timestamps."""
    out = []
    for d in dates:
        out.append(np.busday_offset(d.date(), n_days, roll="forward"))
    return pd.to_datetime(out)


def build_transactions(calendar_df, employees_df, counterparties_df):
    n = N_TRANSACTIONS
    business_dates = calendar_df.loc[
        (~calendar_df["Is_Weekend"]) & (calendar_df["Date"] <= END_DATE), "Date"
    ].values
    holiday_set = set(calendar_df.loc[calendar_df["Is_Holiday"], "Date"])

    # --- Region & trade date/time ---
    region = np.random.choice(REGIONS, size=n, p=REGION_WEIGHTS)
    trade_date_idx = np.random.randint(0, len(business_dates), size=n)
    trade_date = pd.to_datetime(business_dates[trade_date_idx])

    trade_hour = np.empty(n, dtype=int)
    for r in REGIONS:
        mask = region == r
        lo, hi = REGION_HOUR_RANGE[r]
        trade_hour[mask] = np.random.randint(lo, hi, size=mask.sum())

    # --- Counterparty assignment (matched to region where possible) ---
    cp_by_region = {r: counterparties_df[counterparties_df["Region"] == r].reset_index(drop=True)
                     for r in REGIONS}
    counterparty_id = np.empty(n, dtype=object)
    counterparty_onboard = np.empty(n, dtype="datetime64[ns]")
    counterparty_risk = np.empty(n, dtype=object)
    for r in REGIONS:
        mask = region == r
        pool = cp_by_region[r]
        if len(pool) == 0:
            pool = counterparties_df
        picks = np.random.randint(0, len(pool), size=mask.sum())
        counterparty_id[mask] = pool["Counterparty_ID"].values[picks]
        counterparty_onboard[mask] = pool["Onboard_Date"].values[picks]
        counterparty_risk[mask] = pool["Risk_Rating"].values[picks]

    # --- Employee assignment (matched to region) ---
    emp_by_region = {r: employees_df[employees_df["Region"] == r].reset_index(drop=True)
                      for r in REGIONS}
    employee_id = np.empty(n, dtype=object)
    for r in REGIONS:
        mask = region == r
        pool = emp_by_region[r]
        picks = np.random.randint(0, len(pool), size=mask.sum())
        employee_id[mask] = pool["Employee_ID"].values[picks]

    # --- Asset class & currency ---
    asset_class = np.random.choice(ASSET_CLASSES, size=n, p=ASSET_WEIGHTS)
    currency = np.empty(n, dtype=object)
    for r in REGIONS:
        mask = region == r
        currency[mask] = np.random.choice(REGION_CURRENCIES[r], size=mask.sum())

    # --- Trade value (lognormal, scaled by asset class) ---
    base_value = np.random.lognormal(mean=11.0, sigma=1.1, size=n)  # ~ tens of thousands to millions
    scale = np.array([ASSET_VALUE_SCALE[a] for a in asset_class])
    trade_value = np.round(base_value * scale, 2)

    # --- Settlement date: T+2 business days ---
    settlement_date = add_business_days(trade_date, 2)
    settle_near_holiday = np.array([
        any((sd + pd.Timedelta(days=off)) in holiday_set for off in (-1, 0, 1))
        for sd in settlement_date
    ])

    # --- New counterparty flag ---
    days_since_onboard = (trade_date - pd.to_datetime(counterparty_onboard)).days
    is_new_counterparty = days_since_onboard < 90

    # --- Failure probability ---
    risk_bump = np.select(
        [counterparty_risk == "High", counterparty_risk == "Medium"],
        [0.08, 0.03], default=0.0
    )
    failure_prob = (
        0.03
        + np.where(is_new_counterparty, 0.15, 0.0)
        + np.where(settle_near_holiday, 0.10, 0.0)
        + risk_bump
    )
    failure_prob = np.clip(failure_prob, 0, 0.85)
    is_failed = np.random.random(n) < failure_prob
    status = np.where(is_failed, "Failed", "Settled")

    failure_reason = np.full(n, "", dtype=object)
    failed_idx = np.where(is_failed)[0]
    failure_reason[failed_idx] = np.random.choice(FAILURE_REASONS, size=len(failed_idx))

    # --- Processing time (minutes): larger trades take longer, failed trades take longer ---
    value_factor = np.log1p(trade_value) * 1.8          # scales with trade size
    base_time = np.random.gamma(shape=2.0, scale=4.0, size=n)
    failure_extra = np.where(is_failed, np.random.uniform(15, 45, size=n), 0.0)
    processing_time = np.round(base_time + value_factor + failure_extra, 1)
    processing_time = np.clip(processing_time, 1, 240)

    sla_met = processing_time <= 30

    # --- Operational cost: base + failure penalty ---
    base_cost = 15 + trade_value * 0.00008
    op_cost = np.where(is_failed, base_cost * np.random.uniform(1.5, 2.5, size=n), base_cost)
    op_cost = np.round(op_cost + np.random.normal(0, 3, size=n).clip(min=-10), 2)
    op_cost = np.clip(op_cost, 5, None)

    # --- Revenue: margin bps of trade value, reduced when failed ---
    margin_bps = np.array([ASSET_MARGIN_BPS[a] for a in asset_class])
    gross_revenue = trade_value * (margin_bps / 10_000.0)
    revenue = np.where(is_failed, gross_revenue * np.random.uniform(0.3, 0.7, size=n), gross_revenue)
    revenue = np.round(revenue * np.random.uniform(0.85, 1.15, size=n), 2)

    transaction_id = [f"TXN{i:08d}" for i in range(1, n + 1)]

    df = pd.DataFrame({
        "Transaction_ID": transaction_id,
        "Trade_Date": trade_date,
        "Trade_Hour": trade_hour,
        "Settlement_Date": settlement_date,
        "Asset_Class": asset_class,
        "Counterparty": counterparty_id,
        "Region": region,
        "Currency": currency,
        "Trade_Value": trade_value,
        "Revenue": revenue,
        "Operational_Cost": op_cost,
        "Processing_Time": processing_time,
        "Status": status,
        "Failure_Reason": failure_reason,
        "SLA_Met": sla_met,
        "Employee_ID": employee_id,
    })
    return df


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------
def main():
    print("Building Calendar...")
    calendar_df = build_calendar()

    print("Building Employees...")
    employees_df = build_employees()

    print("Building Counterparties...")
    counterparties_df = build_counterparties()

    print(f"Building Transactions ({N_TRANSACTIONS:,} rows)...")
    transactions_df = build_transactions(calendar_df, employees_df, counterparties_df)

    os.makedirs(OUT_DIR, exist_ok=True)
    calendar_df.to_csv(os.path.join(OUT_DIR, "Calendar.csv"), index=False)
    employees_df.to_csv(os.path.join(OUT_DIR, "Employees.csv"), index=False)
    counterparties_df.to_csv(os.path.join(OUT_DIR, "Counterparties.csv"), index=False)
    transactions_df.to_csv(os.path.join(OUT_DIR, "Transactions.csv"), index=False)

    print("\n--- Record counts ---")
    print(f"Calendar:       {len(calendar_df):,}")
    print(f"Employees:      {len(employees_df):,}")
    print(f"Counterparties: {len(counterparties_df):,}")
    print(f"Transactions:   {len(transactions_df):,}")

    print("\n--- Business rule sanity checks ---")
    fr = transactions_df.groupby(transactions_df["Status"])["Processing_Time"].mean()
    print("Avg Processing_Time by Status:\n", fr)

    corr = np.corrcoef(transactions_df["Trade_Value"], transactions_df["Processing_Time"])[0, 1]
    print(f"\nCorrelation Trade_Value vs Processing_Time: {corr:.3f}")

    fail_rate_overall = transactions_df["Status"].eq("Failed").mean()
    print(f"Overall failure rate: {fail_rate_overall:.2%}")

    region_share = transactions_df["Region"].value_counts(normalize=True)
    print("\nTransaction share by region:\n", region_share)

    sla_rate = transactions_df["SLA_Met"].mean()
    print(f"\nSLA adherence rate: {sla_rate:.2%}")


if __name__ == "__main__":
    main()
