# Phase 5: Power BI Dashboard Build Guide

This is a build-ready spec for the 5 dashboards. Power BI Desktop can't be generated
by Claude directly, so this document gives you everything to build it yourself in
under an hour per dashboard: the connection, the data model, every DAX measure,
and the exact visuals/layout for each page.

---

## 1. Connect Power BI to PostgreSQL

1. Power BI Desktop → **Get Data** → **More** → **Database** → **PostgreSQL database**.
2. Server: `localhost` (or your DB host), Database: `financial_ops`.
3. Data Connectivity mode: **DirectQuery** if you want live/near-real-time dashboards,
   or **Import** for faster visuals (recommended given the row counts here — 300k
   transactions is small enough to import comfortably).
4. Requires the [Npgsql PostgreSQL driver](https://www.npgsql.org/) installed locally,
   and (for scheduled refresh in the Power BI Service) an **On-premises Data Gateway**
   if the DB isn't cloud-hosted.
5. Import these objects (not the raw `transactions` table directly for reporting — use
   the Phase 3 views + Phase 4 KPI tables so DAX stays simple):
   - `daily_kpi`
   - `monthly_kpi`
   - `region_kpi`
   - `vw_top_counterparties`
   - `vw_failed_trades_by_region`
   - `vw_employee_productivity`
   - `calendar` (needed as the model's date table)
   - `counterparties`, `employees` (for slicers/attributes, e.g. Risk_Rating, Department)

---

## 2. Data Model (star schema)

```
                    ┌───────────────┐
                    │   calendar    │  (mark as Date Table on cal_date)
                    └───────┬───────┘
                            │ 1
              ┌─────────────┼──────────────┐
              │ *            │ *             │ *
      ┌───────▼──────┐ ┌────▼─────────┐ ┌───▼──────────────┐
      │  daily_kpi   │ │ monthly_kpi  │ │ vw_failed_trades  │
      │ (date+region)│ │ (year_month) │ │   _by_region      │
      └──────────────┘ └──────────────┘ └───────────────────┘

      ┌───────────────────┐        ┌────────────────────┐
      │ region_kpi        │        │ vw_top_counterparties│──┐
      │ (region grain)    │        │ (counterparty grain) │  │ *
      └───────────────────┘        └──────────┬────────────┘  │
                                               │ 1              │
                                       ┌───────▼───────┐        │
                                       │ counterparties │◄──────┘
                                       └────────────────┘

      ┌──────────────────────┐        ┌────────────┐
      │ vw_employee_          │───────►│ employees  │
      │  productivity         │  1:1   └────────────┘
      └──────────────────────┘
```

Notes:
- Relationships from `calendar` to `daily_kpi`/`monthly_kpi` use `cal_date` ↔ `trade_date`
  (for monthly_kpi, relate via a `year_month` column added to calendar, or better: build
  monthly relationships off `daily_kpi` and let Power BI auto-aggregate to month using
  the calendar hierarchy instead of relying on `monthly_kpi` for time intelligence).
- `region_kpi` has no date column — use it only for the single full-period regional
  scorecards, not for time-series visuals.
- Set `calendar[cal_date]` as the official **Date Table** (Modeling → Mark as Date Table)
  so Power BI's time intelligence functions (`TOTALYTD`, `SAMEPERIODLASTYEAR`, etc.) work.

---

## 3. DAX Measures

Create a dedicated **Measures** table (New Table → blank) to keep these organized.

```dax
-- Core KPIs (build off daily_kpi for full drill-down flexibility)
Total Transactions      = SUM(daily_kpi[transaction_count])
Total Trade Value (USD) = SUM(daily_kpi[total_trade_value_usd])
Total Revenue (USD)     = SUM(daily_kpi[total_revenue_usd])
Total Op Cost (USD)     = SUM(daily_kpi[total_operational_cost_usd])
Total Profit (USD)      = SUM(daily_kpi[profit_usd])

Profit Margin %         = DIVIDE([Total Profit (USD)], [Total Revenue (USD)])

-- Weighted averages (don't just AVERAGE the pre-aggregated daily rates - weight by volume)
Settlement Success % =
VAR FailedTx = SUMX(daily_kpi, daily_kpi[transaction_count] * daily_kpi[failure_rate_pct] / 100)
RETURN 1 - DIVIDE(FailedTx, [Total Transactions])

SLA Adherence % =
VAR MetTx = SUMX(daily_kpi, daily_kpi[transaction_count] * daily_kpi[sla_adherence_pct] / 100)
RETURN DIVIDE(MetTx, [Total Transactions])

Avg Processing Time (min) =
DIVIDE(
    SUMX(daily_kpi, daily_kpi[transaction_count] * daily_kpi[avg_processing_time]),
    [Total Transactions]
)

Avg Settlement Delay (days) =
DIVIDE(
    SUMX(daily_kpi, daily_kpi[transaction_count] * daily_kpi[avg_settlement_delay_days]),
    [Total Transactions]
)

Failed Trades = SUMX(daily_kpi, daily_kpi[transaction_count] * daily_kpi[failure_rate_pct] / 100)

-- Time intelligence (requires calendar marked as Date Table)
Revenue MoM % =
VAR PrevMonth = CALCULATE([Total Revenue (USD)], DATEADD(calendar[cal_date], -1, MONTH))
RETURN DIVIDE([Total Revenue (USD)] - PrevMonth, PrevMonth)

Revenue YTD = TOTALYTD([Total Revenue (USD)], calendar[cal_date])

-- Counterparty dashboard (from vw_top_counterparties, already pre-aggregated per counterparty)
CP Revenue Contribution % =
DIVIDE(SUM(vw_top_counterparties[total_revenue]), CALCULATE(SUM(vw_top_counterparties[total_revenue]), ALL(vw_top_counterparties)))

-- Operations dashboard (from vw_employee_productivity)
Employee SLA % = AVERAGE(vw_employee_productivity[sla_adherence_pct])
```

---

## 4. Dashboard Pages

### Page 1 — Executive Dashboard
**Purpose:** single-glance health check for leadership.

| Visual | Fields |
|---|---|
| 6 KPI cards (top row) | Total Transactions, Total Revenue (USD), Settlement Success %, Failed Trades, SLA Adherence %, Avg Processing Time |
| Line chart (large, center) | `calendar[cal_date]` (month drill) on X, `[Total Revenue (USD)]` and `[Total Profit (USD)]` on Y — dual-line |
| Donut chart | Transactions by Region |
| Bar chart | Revenue by Asset Class (from daily source, needs asset_class — pull from `vw_revenue_trends` if added, or extend `daily_kpi` grain) |
| KPI trend sparkline | Settlement Success % over time |

**Features:** Set the line chart's date field to a hierarchy (Year → Quarter → Month → Day) so users can drill down by clicking. Add a **Region** slicer at the top that cross-filters every visual on the page.

### Page 2 — Regional Dashboard
| Visual | Fields |
|---|---|
| Map or column chart | Revenue by Region (`region_kpi`) |
| Clustered bar | Transaction Volume by Region over time (`daily_kpi`, Region as legend) |
| Line chart | Failure Rate % by Region over time |
| Table | Region, Total Trades, Revenue, Profit, Failure Rate %, SLA % (from `region_kpi`) |

**Features:** Add a Region slicer; enable **cross-filtering** (Format → Edit Interactions) so clicking a region in the map filters the volume/failure charts.

### Page 3 — Counterparty Dashboard
| Visual | Fields |
|---|---|
| Table/matrix | Counterparty Name, Region, Type, Risk Rating, Total Revenue, Failure Rate %, Avg Processing Time, Revenue Rank (`vw_top_counterparties`) |
| Bar chart | Top 15 Counterparties by Revenue |
| Scatter plot | X = Failure Rate %, Y = Total Revenue, size = Total Trades, color = Risk Rating — flags high-revenue/high-risk counterparties at a glance |

**Features:** Add tooltips showing Risk_Rating and Type on hover (Format → Tooltips → set fields). Add a Risk_Rating slicer.

### Page 4 — Operations Dashboard
| Visual | Fields |
|---|---|
| Table | Employee Name, Department, Region, Trades Handled, Avg Processing Time, Failed Trades, SLA % (`vw_employee_productivity`) |
| Bar chart | Trades Handled by Department |
| Pie chart | Exception/Failure Type share (`vw_failed_trades_by_region`, Failure_Reason) |
| Line chart | Operational Cost trend over time (`daily_kpi[total_operational_cost_usd]`) |

**Features:** Drill-down hierarchy Department → Employee on the bar chart (right-click → Drill Down).

### Page 5 — Forecast Dashboard
| Visual | Fields |
|---|---|
| Line chart w/ forecast | `calendar[cal_date]` (Month) × `[Total Revenue (USD)]` |
| Line chart w/ forecast | `calendar[cal_date]` (Month) × `[Total Transactions]` |
| Line chart w/ forecast | `calendar[cal_date]` (Month) × Failure Rate % |

**How to add native Power BI forecasting:**
1. Click the line chart → **Analytics pane** (magnifying-glass-with-chart icon in Visualizations).
2. Click **Forecast** → **Add**.
3. Set *Forecast length* (e.g. 3-6 months), *Confidence interval* (95% default), *Seasonality* (set to 12 if monthly data with yearly seasonality, or leave Auto).
4. Power BI uses exponential smoothing under the hood — good enough for exec-level trend projection.

**For a more rigorous ARIMA/Prophet forecast:** run it in Python (see note below) and load
the forecasted values as a separate table (`revenue_forecast`) with a `Is_Forecast` flag,
then plot actuals + forecast as two series in the same chart. I can build that Python
forecasting script now if you want it — it's arguably part of Phase 5 too since the
project plan lists "ARIMA / Prophet" as an alternative to Power BI's built-in forecasting.

---

## 5. Cross-cutting features (apply to all pages)

- **Filters/Slicers:** put a shared **Date Range** slicer and **Region** slicer in a
  bookmark-controlled filter panel, or replicate on every page for consistency.
- **Cross-filtering:** default behavior is fine for most visuals; disable it on KPI
  cards (Format → Edit Interactions → set to "None") so a click elsewhere doesn't
  zero out the top-line numbers.
- **Tooltips:** for the map/region visuals, add a tooltip page showing a mini trend
  sparkline — Insert → New Page → set Page type to "Tooltip" in Page settings, then
  set it as the custom tooltip on the region visual.
- **Automatic refresh:** In Power BI Service, Dataset Settings → Scheduled Refresh
  (up to 8x/day on Pro). Since this connects to PostgreSQL, you'll need the
  On-premises Data Gateway installed and pointed at the DB.

---

## 6. Suggested next step

Since I can't produce the actual `.pbix` binary from this environment, the fastest
path is: open Power BI Desktop → follow Section 1 to connect → paste the DAX from
Section 3 → build pages per Section 4. If you get stuck on a specific visual or DAX
error, paste it back to me and I'll debug it.
