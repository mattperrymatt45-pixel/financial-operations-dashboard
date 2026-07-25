-- ============================================================
-- Phase 3: SQL Analytics Views
-- Financial Operations KPI Dashboard
-- These views are the data source for Phase 4 (ETL) and
-- Phase 5 (Power BI).
-- ============================================================

-- ------------------------------------------------------------
-- 1. Daily transaction volume (overall + by region)
-- ------------------------------------------------------------
DROP VIEW IF EXISTS vw_daily_transaction_volume;
CREATE VIEW vw_daily_transaction_volume AS
SELECT
    t.trade_date,
    c.fiscal_quarter,
    c.fiscal_year,
    c.is_holiday,
    t.region,
    COUNT(*)                              AS transaction_count,
    SUM(t.trade_value)                    AS total_trade_value,
    ROUND(AVG(t.trade_value), 2)          AS avg_trade_value
FROM transactions t
JOIN calendar c ON c.cal_date = t.trade_date
GROUP BY t.trade_date, c.fiscal_quarter, c.fiscal_year, c.is_holiday, t.region;


-- ------------------------------------------------------------
-- 2. Settlement success rate (daily, by region)
-- ------------------------------------------------------------
DROP VIEW IF EXISTS vw_settlement_success_rate;
CREATE VIEW vw_settlement_success_rate AS
SELECT
    t.trade_date,
    t.region,
    COUNT(*)                                                        AS total_trades,
    COUNT(*) FILTER (WHERE t.status = 'Settled')                    AS settled_trades,
    COUNT(*) FILTER (WHERE t.status = 'Failed')                     AS failed_trades,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE t.status = 'Settled') / NULLIF(COUNT(*), 0), 2
    )                                                                AS settlement_success_pct
FROM transactions t
GROUP BY t.trade_date, t.region;


-- ------------------------------------------------------------
-- 3. Failed trades by region (with failure reason breakdown)
-- ------------------------------------------------------------
DROP VIEW IF EXISTS vw_failed_trades_by_region;
CREATE VIEW vw_failed_trades_by_region AS
SELECT
    t.region,
    t.failure_reason,
    COUNT(*)                                       AS failed_trade_count,
    ROUND(AVG(t.trade_value), 2)                   AS avg_failed_trade_value,
    ROUND(AVG(t.processing_time), 1)               AS avg_processing_time,
    ROUND(
        100.0 * COUNT(*) / NULLIF(
            SUM(COUNT(*)) OVER (PARTITION BY t.region), 0
        ), 2
    )                                               AS pct_of_region_failures
FROM transactions t
WHERE t.status = 'Failed'
GROUP BY t.region, t.failure_reason;


-- ------------------------------------------------------------
-- 4. Revenue trends (daily, by region and asset class)
-- ------------------------------------------------------------
DROP VIEW IF EXISTS vw_revenue_trends;
CREATE VIEW vw_revenue_trends AS
SELECT
    t.trade_date,
    c.fiscal_quarter,
    c.fiscal_year,
    t.region,
    t.asset_class,
    COUNT(*)                        AS transaction_count,
    SUM(t.revenue)                  AS total_revenue,
    SUM(t.operational_cost)         AS total_operational_cost,
    SUM(t.revenue - t.operational_cost) AS net_profit
FROM transactions t
JOIN calendar c ON c.cal_date = t.trade_date
GROUP BY t.trade_date, c.fiscal_quarter, c.fiscal_year, t.region, t.asset_class;


-- ------------------------------------------------------------
-- 5. Top counterparties (revenue contribution, failure rate, processing time)
-- ------------------------------------------------------------
DROP VIEW IF EXISTS vw_top_counterparties;
CREATE VIEW vw_top_counterparties AS
SELECT
    cp.counterparty_id,
    cp.name,
    cp.region,
    cp.type,
    cp.risk_rating,
    COUNT(*)                                                     AS total_trades,
    SUM(t.revenue)                                                AS total_revenue,
    ROUND(AVG(t.processing_time), 1)                              AS avg_processing_time,
    COUNT(*) FILTER (WHERE t.status = 'Failed')                   AS failed_trades,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE t.status = 'Failed') / NULLIF(COUNT(*), 0), 2
    )                                                              AS failure_rate_pct,
    RANK() OVER (ORDER BY SUM(t.revenue) DESC)                    AS revenue_rank
FROM transactions t
JOIN counterparties cp ON cp.counterparty_id = t.counterparty_id
GROUP BY cp.counterparty_id, cp.name, cp.region, cp.type, cp.risk_rating;


-- ------------------------------------------------------------
-- 6. SLA adherence (daily, by region and asset class)
-- ------------------------------------------------------------
DROP VIEW IF EXISTS vw_sla_adherence;
CREATE VIEW vw_sla_adherence AS
SELECT
    t.trade_date,
    t.region,
    t.asset_class,
    COUNT(*)                                              AS total_trades,
    COUNT(*) FILTER (WHERE t.sla_met)                     AS sla_met_count,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE t.sla_met) / NULLIF(COUNT(*), 0), 2
    )                                                      AS sla_adherence_pct,
    ROUND(AVG(t.processing_time), 1)                       AS avg_processing_time
FROM transactions t
GROUP BY t.trade_date, t.region, t.asset_class;


-- ------------------------------------------------------------
-- 7. Operational cost analysis (by region, asset class, status)
-- ------------------------------------------------------------
DROP VIEW IF EXISTS vw_operational_cost_analysis;
CREATE VIEW vw_operational_cost_analysis AS
SELECT
    t.region,
    t.asset_class,
    t.status,
    COUNT(*)                                AS trade_count,
    SUM(t.operational_cost)                 AS total_operational_cost,
    ROUND(AVG(t.operational_cost), 2)       AS avg_operational_cost,
    ROUND(
        SUM(t.operational_cost) / NULLIF(SUM(t.trade_value), 0) * 100, 4
    )                                        AS cost_pct_of_trade_value
FROM transactions t
GROUP BY t.region, t.asset_class, t.status;


-- ------------------------------------------------------------
-- 8. Employee productivity (bonus view - feeds the Operations dashboard)
-- ------------------------------------------------------------
DROP VIEW IF EXISTS vw_employee_productivity;
CREATE VIEW vw_employee_productivity AS
SELECT
    e.employee_id,
    e.name,
    e.region,
    e.department,
    COUNT(*)                                                      AS trades_handled,
    ROUND(AVG(t.processing_time), 1)                              AS avg_processing_time,
    COUNT(*) FILTER (WHERE t.status = 'Failed')                   AS failed_trades,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE t.sla_met) / NULLIF(COUNT(*), 0), 2
    )                                                              AS sla_adherence_pct
FROM transactions t
JOIN employees e ON e.employee_id = t.employee_id
GROUP BY e.employee_id, e.name, e.region, e.department;
