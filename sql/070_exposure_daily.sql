-- 070_exposure_daily.sql
-- Net open FX exposure by (date, entity, currency), in currency units and in USD.
--
-- Exposure is a *stock*; flows are *changes*. So the core of this file is a running sum
-- of signed flows per component, evaluated on every calendar day (including days with no
-- flows, which is why a date x pair x component grid is built first).
--
-- Components (all in units of `ccy`; sign convention: positive = long the currency):
--   in_flight     receivables authorized but not yet settled          (asset,     >= 0)
--   balance       cash held in the currency                           (asset,     >= 0)
--   payable       owed to merchants who are paid in the currency       (liability, <= 0)
--   intercompany  parent/subsidiary working-capital loan              (+ at US, - at sub)
--   net           sum of the four
--   gross         sum of their absolute values (what the waterfall starts from)

CREATE OR REPLACE TABLE exposure_daily AS
WITH bounds AS (
    SELECT min(flow_date) AS first_day, max(flow_date) AS last_day FROM flows
),
calendar AS (
    -- one row per calendar day; generate_series is inclusive at both ends
    SELECT unnest(generate_series(first_day, last_day, INTERVAL 1 DAY))::DATE AS exposure_date
    FROM bounds
),
pairs AS (
    SELECT DISTINCT entity, ccy FROM flows
),
components AS (
    SELECT DISTINCT component FROM flow_type_map
),
grid AS (
    SELECT exposure_date, entity, ccy, component
    FROM calendar
    CROSS JOIN pairs
    CROSS JOIN components
),
signed AS (
    -- the join to flow_type_map fans a settlement out into two rows (in_flight -, balance +)
    SELECT
        f.flow_date,
        f.entity,
        f.ccy,
        m.component,
        sum(m.sign * f.amount) AS delta
    FROM flows AS f
    JOIN flow_type_map AS m USING (flow_type)
    GROUP BY ALL
),
running AS (
    SELECT
        g.exposure_date,
        g.entity,
        g.ccy,
        g.component,
        -- running total of changes = the position at end of day
        sum(coalesce(s.delta, 0)) OVER (
            PARTITION BY g.entity, g.ccy, g.component
            ORDER BY g.exposure_date
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS position_fcy
    FROM grid AS g
    LEFT JOIN signed AS s
      ON s.flow_date = g.exposure_date
     AND s.entity    = g.entity
     AND s.ccy       = g.ccy
     AND s.component = g.component
),
wide AS (
    -- one row per (date, entity, ccy) with a column per component
    SELECT
        exposure_date,
        entity,
        ccy,
        coalesce(sum(CASE WHEN component = 'in_flight'    THEN position_fcy END), 0) AS in_flight_fcy,
        coalesce(sum(CASE WHEN component = 'balance'      THEN position_fcy END), 0) AS balance_fcy,
        coalesce(sum(CASE WHEN component = 'payable'      THEN position_fcy END), 0) AS payable_fcy,
        coalesce(sum(CASE WHEN component = 'intercompany' THEN position_fcy END), 0) AS intercompany_fcy
    FROM running
    GROUP BY ALL
)
SELECT
    exposure_date,
    entity,
    ccy,
    in_flight_fcy,
    balance_fcy,
    payable_fcy,
    intercompany_fcy,
    in_flight_fcy + balance_fcy + payable_fcy + intercompany_fcy                    AS net_fcy,
    abs(in_flight_fcy) + abs(balance_fcy) + abs(payable_fcy) + abs(intercompany_fcy) AS gross_fcy
FROM wide
ORDER BY exposure_date, entity, ccy;


CREATE OR REPLACE VIEW exposure_daily_usd AS
-- USD translation at the latest available NY fixing on or before the exposure date.
-- ASOF JOIN picks, for each exposure row, the single FX row with the greatest obs_date
-- that satisfies obs_date <= exposure_date: a weekend exposure uses Friday's rate.
SELECT
    e.exposure_date,
    e.entity,
    e.ccy,
    CASE WHEN e.ccy = 'USD' THEN 1.0 ELSE fx.usd_per_fcy END AS usd_per_fcy,
    CASE WHEN e.ccy = 'USD' THEN e.exposure_date ELSE fx.obs_date END AS fx_date,
    e.in_flight_fcy,
    e.balance_fcy,
    e.payable_fcy,
    e.intercompany_fcy,
    e.net_fcy,
    e.gross_fcy,
    e.in_flight_fcy    * coalesce(fx.usd_per_fcy, 1.0) AS in_flight_usd,
    e.balance_fcy      * coalesce(fx.usd_per_fcy, 1.0) AS balance_usd,
    e.payable_fcy      * coalesce(fx.usd_per_fcy, 1.0) AS payable_usd,
    e.intercompany_fcy * coalesce(fx.usd_per_fcy, 1.0) AS intercompany_usd,
    e.net_fcy          * coalesce(fx.usd_per_fcy, 1.0) AS net_usd,
    e.gross_fcy        * coalesce(fx.usd_per_fcy, 1.0) AS gross_usd
FROM exposure_daily AS e
ASOF LEFT JOIN fx_usd_master_filled AS fx
    ON fx.ccy = e.ccy
   AND fx.obs_date <= e.exposure_date;
