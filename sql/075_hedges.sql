-- 075_hedges.sql
-- Hedge positions and the stylized legacy hedging programme.
--
-- hedge_positions is the table the policy backtest writes the optimizer's monthly
-- positions to. For months it has not written, the "existing hedges" shown in the
-- waterfall come from hedges_legacy: a simple rule a treasury might have run by hand
-- before any optimization:
--
--     on the first day of each month, sell forward 50% of last month's average net
--     exposure in each non-USD currency, one-month tenor.
--
-- Sign convention: notional_fcy < 0 means the currency was SOLD forward (the usual hedge
-- of a long exposure); net_of_hedges = net + notional.
--
-- The table is recreated empty on every exposure build, so the exposure stage's output
-- never depends on what a previous run left behind. `fxrisk backtest` then writes the
-- optimizer's positions and rebuilds exposure_group_fx (090), so every later stage sees
-- them. A fresh clone and a second run therefore produce the same tables.

CREATE OR REPLACE TABLE hedge_positions (
    trade_date    DATE    NOT NULL,
    maturity_date DATE    NOT NULL,   -- position is active on trade_date <= d < maturity_date
    entity        VARCHAR NOT NULL,
    ccy           VARCHAR NOT NULL,
    notional_fcy  DOUBLE  NOT NULL,
    source        VARCHAR NOT NULL    -- 'legacy' | 'optimizer' | ...
);


CREATE OR REPLACE VIEW hedges_legacy AS
WITH monthly AS (
    -- average net exposure per calendar month
    SELECT
        date_trunc('month', exposure_date)::DATE AS month_start,
        entity,
        ccy,
        avg(net_fcy) AS avg_net_fcy
    FROM exposure_daily
    WHERE ccy <> 'USD'
    GROUP BY ALL
)
SELECT
    -- each month's average decides the hedge dealt on the first of the NEXT month, so the
    -- last month of data also yields the programme's next trade (the policy backtest and
    -- the hedge stage read their legacy benchmark from this view; the first month of
    -- data has no history and therefore no hedge)
    (month_start + INTERVAL 1 MONTH)::DATE               AS trade_date,
    (month_start + INTERVAL 2 MONTH)::DATE               AS maturity_date,
    entity,
    ccy,
    -0.5 * avg_net_fcy                                   AS notional_fcy,  -- a sale
    'legacy'                                             AS source
FROM monthly;


CREATE OR REPLACE VIEW hedges_all AS
-- Positions from every source. Legacy rows are used only for months where the optimizer
-- has written nothing, so the optimizer takes over month by month.
SELECT trade_date, maturity_date, entity, ccy, notional_fcy, source FROM hedge_positions
UNION ALL
SELECT l.trade_date, l.maturity_date, l.entity, l.ccy, l.notional_fcy, l.source
FROM hedges_legacy AS l
WHERE NOT EXISTS (
    -- an optimizer position for the same currency and month (any entity, including the
    -- group-level 'GROUP' rows) replaces the legacy rule for that month
    SELECT 1 FROM hedge_positions AS p
    WHERE p.ccy = l.ccy
      AND date_trunc('month', p.trade_date) = date_trunc('month', l.trade_date)
);
