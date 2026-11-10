-- 070_exposure_daily.sql
-- Net open FX exposure by (date, entity, currency), in currency units and in USD.
--
-- Exposure is a stock; flows are changes to it. Each component's end-of-day position is
-- the running sum of its signed flows, evaluated on EVERY calendar day so that a day
-- without flows carries the previous position rather than reading as zero.
--
-- Components (all in units of `ccy`; positive = long the currency):
--   in_flight     receivables authorized but not yet settled          (asset,  >= 0)
--   balance       cash held in the currency                           (asset,  >= 0)
--   payable       owed to merchants paid in the currency               (liability, <= 0)
--   intercompany  parent's working-capital loan: + at US, - at the subsidiary; nets to
--                 zero at group level
--   net           sum of the four: the exposure a hedge offsets
--   gross         sum of absolute values: the top of the waterfall (080), showing how
--                 much natural offsetting happens before any hedge
--
-- exposure_daily is a TABLE because the window over the full date x pair x component
-- grid is the most expensive step in the SQL layer and 075-090 read it repeatedly.

CREATE OR REPLACE TABLE exposure_daily AS
WITH bounds AS (
    -- the horizon follows whatever range the flow generator was run with
    SELECT min(flow_date) AS first_day, max(flow_date) AS last_day FROM flows
),
calendar AS (
    -- every calendar day, weekends included
    SELECT unnest(generate_series(first_day, last_day, INTERVAL 1 DAY))::DATE AS exposure_date
    FROM bounds
),
pairs AS (
    -- only (entity, currency) pairs that ever transact get rows
    SELECT DISTINCT entity, ccy FROM flows
),
components AS (
    -- read from the mapping so a new component in 060 flows through automatically
    SELECT DISTINCT component FROM flow_type_map
),
grid AS (
    -- day x pair x component: about 0.5m rows on the default configuration
    SELECT exposure_date, entity, ccy, component
    FROM calendar
    CROSS JOIN pairs
    CROSS JOIN components
),
signed AS (
    -- daily change per component. A flow type mapped to two components (a settlement
    -- moves in_flight -1 and balance +1) fans out into two rows through the join.
    -- Unmapped flow types would be dropped here; build.py rejects them before this runs.
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
    -- end-of-day position = running sum of changes; days without flows add zero
    SELECT
        g.exposure_date,
        g.entity,
        g.ccy,
        g.component,
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
    -- one row per (date, entity, ccy), one column per component
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
-- USD translation at the latest NY fixing on or before the exposure date: a weekend or
-- holiday uses the previous business day's rate, the only rate that existed then.
-- USD rows translate at 1.0. A non-USD row with no fixing yet (the first calendar days of
-- the sample, before the FX master starts) gets NULL USD values rather than an
-- untranslated amount; 090 joins on FX dates only, so nothing downstream reads them.
WITH translated AS (
    SELECT
        e.*,
        CASE WHEN e.ccy = 'USD' THEN 1.0 ELSE fx.usd_per_fcy END AS rate,
        CASE WHEN e.ccy = 'USD' THEN e.exposure_date ELSE fx.obs_date END AS fx_date
    FROM exposure_daily AS e
    ASOF LEFT JOIN fx_usd_master_filled AS fx
        ON fx.ccy = e.ccy
       AND fx.obs_date <= e.exposure_date
)
SELECT
    exposure_date,
    entity,
    ccy,
    rate                    AS usd_per_fcy,
    fx_date,
    in_flight_fcy,
    balance_fcy,
    payable_fcy,
    intercompany_fcy,
    net_fcy,
    gross_fcy,
    in_flight_fcy    * rate AS in_flight_usd,
    balance_fcy      * rate AS balance_usd,
    payable_fcy      * rate AS payable_usd,
    intercompany_fcy * rate AS intercompany_usd,
    net_fcy          * rate AS net_usd,
    gross_fcy        * rate AS gross_usd
FROM translated;
