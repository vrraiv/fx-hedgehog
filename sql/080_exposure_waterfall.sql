-- 080_exposure_waterfall.sql
-- The same exposure three ways: gross -> net -> net of existing hedges.
--
--   gross            sum of absolute component positions; what a naive "how much FX do
--                    we touch" count would show
--   net              assets minus liabilities in the currency; what actually moves P&L
--   net_of_hedges    net plus active forward positions; the residual a treasurer owns
--
-- The gap gross -> net is natural offset (receivables vs merchant payables, parent loan
-- vs subsidiary loan); the gap net -> net_of_hedges is the hedging programme.

CREATE OR REPLACE VIEW exposure_waterfall AS
WITH active_hedges AS (
    -- hedge notional active on each exposure date; a date x hedge range join
    SELECT
        e.exposure_date,
        e.entity,
        e.ccy,
        sum(h.notional_fcy) AS hedge_fcy
    FROM exposure_daily AS e
    JOIN hedges_all AS h
      ON h.entity = e.entity
     AND h.ccy    = e.ccy
     AND e.exposure_date >= h.trade_date
     AND e.exposure_date <  h.maturity_date
    GROUP BY ALL
)
SELECT
    e.exposure_date,
    e.entity,
    e.ccy,
    e.usd_per_fcy,
    e.gross_fcy,
    e.net_fcy,
    coalesce(a.hedge_fcy, 0)                                 AS hedge_fcy,
    e.net_fcy + coalesce(a.hedge_fcy, 0)                     AS net_of_hedges_fcy,
    e.gross_usd,
    e.net_usd,
    coalesce(a.hedge_fcy, 0) * e.usd_per_fcy                 AS hedge_usd,
    (e.net_fcy + coalesce(a.hedge_fcy, 0)) * e.usd_per_fcy   AS net_of_hedges_usd
FROM exposure_daily_usd AS e
LEFT JOIN active_hedges AS a USING (exposure_date, entity, ccy);


CREATE OR REPLACE VIEW exposure_waterfall_by_ccy AS
-- Group view: one row per (date, ccy), entities summed. USD is excluded because it is
-- the reporting currency and carries no translation risk.
SELECT
    exposure_date,
    ccy,
    sum(gross_usd)          AS gross_usd,
    sum(net_usd)            AS net_usd,
    sum(hedge_usd)          AS hedge_usd,
    sum(net_of_hedges_usd)  AS net_of_hedges_usd
FROM exposure_waterfall
WHERE ccy <> 'USD'
GROUP BY ALL;
