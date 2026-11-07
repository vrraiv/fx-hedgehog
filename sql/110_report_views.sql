-- 110_report_views.sql
-- Small views the decision report reads. Everything here is a re-cut of tables that
-- earlier stages already built; the report stage computes nothing new, it only presents.
--
-- Three views:
--   report_waterfall_latest   gross -> net -> hedge -> net of hedges by currency, last date
--   report_entity_latest      component breakdown by (entity, ccy), last date, USD m
--   report_exposure_monthly   group gross and |net| exposure, monthly averages, USD m (history figure)

CREATE OR REPLACE VIEW report_waterfall_latest AS
-- One row per currency on the last FX date, plus a GROUP total row so the report can
-- print the waterfall as "sum of absolutes": gross is already an absolute, net and
-- net-of-hedges are signed per currency, so the group row takes abs() before summing.
-- "Last FX date" rather than "last calendar date" so the waterfall is dated the same as
-- the risk and hedge tables (the exposure grid runs to the end of the flows' month, which
-- can be a weekend).
WITH last_day AS (
    SELECT max(obs_date) AS d FROM exposure_group_fx
),
by_ccy AS (
    SELECT
        w.exposure_date,
        w.ccy,
        w.gross_usd          / 1e6 AS gross_usd_m,
        w.net_usd            / 1e6 AS net_usd_m,
        w.hedge_usd          / 1e6 AS hedge_usd_m,
        w.net_of_hedges_usd  / 1e6 AS net_of_hedges_usd_m
    FROM exposure_waterfall_by_ccy AS w
    JOIN last_day ON w.exposure_date = last_day.d
)
SELECT exposure_date, ccy, gross_usd_m, net_usd_m, hedge_usd_m, net_of_hedges_usd_m,
       0 AS sort_key
FROM by_ccy
UNION ALL
SELECT
    max(exposure_date),
    'TOTAL (abs)',
    sum(gross_usd_m),
    sum(abs(net_usd_m)),
    sum(abs(hedge_usd_m)),
    sum(abs(net_of_hedges_usd_m)),
    1
FROM by_ccy
ORDER BY sort_key, abs(net_usd_m) DESC;


CREATE OR REPLACE VIEW report_entity_latest AS
SELECT
    entity,
    ccy,
    in_flight_usd    / 1e6 AS in_flight_m,
    balance_usd      / 1e6 AS balance_m,
    payable_usd      / 1e6 AS payable_m,
    intercompany_usd / 1e6 AS intercompany_m,
    net_usd          / 1e6 AS net_m
FROM exposure_daily_usd
WHERE exposure_date = (SELECT max(obs_date) FROM exposure_group_fx)
ORDER BY entity, ccy;


CREATE OR REPLACE VIEW report_exposure_monthly AS
-- Monthly average of the group book: total gross and the sum of absolute net positions
-- across the ten currencies, in USD millions. An average rather than a month-end
-- snapshot because exposure dips on the last day of every month (fee sweep, payouts), so
-- month-end values would show the book at its monthly low. Two steps: sum across
-- currencies per day, then average the daily totals within the month.
WITH daily AS (
    SELECT
        obs_date,
        sum(gross_usd)              AS gross_usd,
        sum(abs(net_usd))           AS net_abs_usd,
        sum(abs(net_of_hedges_usd)) AS net_of_hedges_abs_usd
    FROM exposure_group_fx
    GROUP BY obs_date
)
SELECT
    date_trunc('month', obs_date)::DATE AS month,
    avg(gross_usd)              / 1e6 AS gross_usd_m,
    avg(net_abs_usd)            / 1e6 AS net_abs_usd_m,
    avg(net_of_hedges_abs_usd)  / 1e6 AS net_of_hedges_abs_usd_m,
    count(*)                          AS n_days
FROM daily
GROUP BY ALL
ORDER BY month;
