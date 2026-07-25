-- ============================================================
-- Phase 2: PostgreSQL Schema
-- Financial Operations KPI Dashboard
-- ============================================================

DROP TABLE IF EXISTS transactions CASCADE;
DROP TABLE IF EXISTS counterparties CASCADE;
DROP TABLE IF EXISTS employees CASCADE;
DROP TABLE IF EXISTS calendar CASCADE;

-- ------------------------------------------------------------
-- Calendar: dimension table for dates, holidays, fiscal periods
-- ------------------------------------------------------------
CREATE TABLE calendar (
    cal_date        DATE PRIMARY KEY,
    day_of_week     VARCHAR(10)  NOT NULL,
    is_weekend      BOOLEAN      NOT NULL,
    fiscal_quarter  SMALLINT     NOT NULL,
    fiscal_year     SMALLINT     NOT NULL,
    is_holiday      BOOLEAN      NOT NULL
);

-- ------------------------------------------------------------
-- Employees
-- ------------------------------------------------------------
CREATE TABLE employees (
    employee_id     VARCHAR(10)  PRIMARY KEY,
    name            VARCHAR(100) NOT NULL,
    region          VARCHAR(10)  NOT NULL,
    department      VARCHAR(50)  NOT NULL,
    hire_date       DATE         NOT NULL
);

-- ------------------------------------------------------------
-- Counterparties
-- ------------------------------------------------------------
CREATE TABLE counterparties (
    counterparty_id VARCHAR(10)  PRIMARY KEY,
    name            VARCHAR(150) NOT NULL,
    region          VARCHAR(10)  NOT NULL,
    type            VARCHAR(30)  NOT NULL,
    risk_rating     VARCHAR(10)  NOT NULL,
    onboard_date    DATE         NOT NULL
);

-- ------------------------------------------------------------
-- Transactions: fact table
-- ------------------------------------------------------------
CREATE TABLE transactions (
    transaction_id    VARCHAR(15)   PRIMARY KEY,
    trade_date        DATE          NOT NULL REFERENCES calendar(cal_date),
    trade_hour        SMALLINT      NOT NULL CHECK (trade_hour BETWEEN 0 AND 23),
    settlement_date   DATE          NOT NULL REFERENCES calendar(cal_date),
    asset_class       VARCHAR(20)   NOT NULL,
    counterparty_id   VARCHAR(10)   NOT NULL REFERENCES counterparties(counterparty_id),
    region            VARCHAR(10)   NOT NULL,
    currency          VARCHAR(5)    NOT NULL,
    trade_value       NUMERIC(18,2) NOT NULL,
    revenue           NUMERIC(18,2) NOT NULL,
    operational_cost  NUMERIC(18,2) NOT NULL,
    processing_time   NUMERIC(6,1)  NOT NULL,
    status            VARCHAR(10)   NOT NULL,
    failure_reason    VARCHAR(50),
    sla_met           BOOLEAN       NOT NULL,
    employee_id       VARCHAR(10)   NOT NULL REFERENCES employees(employee_id)
);

-- ------------------------------------------------------------
-- Indexes to support the Phase 3 analytics queries
-- ------------------------------------------------------------
CREATE INDEX idx_txn_trade_date        ON transactions(trade_date);
CREATE INDEX idx_txn_settlement_date   ON transactions(settlement_date);
CREATE INDEX idx_txn_region            ON transactions(region);
CREATE INDEX idx_txn_status            ON transactions(status);
CREATE INDEX idx_txn_counterparty_id   ON transactions(counterparty_id);
CREATE INDEX idx_txn_employee_id       ON transactions(employee_id);
CREATE INDEX idx_txn_asset_class       ON transactions(asset_class);
CREATE INDEX idx_txn_region_date       ON transactions(region, trade_date);

CREATE INDEX idx_cp_region             ON counterparties(region);
CREATE INDEX idx_emp_region            ON employees(region);
