-- 040_fx_reconciliation.sql
-- Cross-source reconciliation of the USD-per-FCY rates.
--
-- FRED is the reference (longest history, NY noon fixing). For each day and currency we
-- compute the log difference of the other sources against it; a log difference is
-- approximately a percentage difference and is symmetric (A vs B = -(B vs A)).
--
-- Expected disagreement is *not* zero because the fixings happen at different times:
--   FRED H.10   noon New York
--   BoC         average over the trading day (current series) / noon (legacy series)
--   ECB         14:15 Central European Time, about five hours before NY noon
-- The quality step compares the summary below with tolerances derived from the observed
-- distribution (see docs/decisions/0005-reconciliation-tolerances.md).

CREATE OR REPLACE VIEW fx_reconciliation_daily AS
WITH wide AS (
    -- conditional aggregation turns the long (date, ccy, source) table into one row per
    -- (date, ccy) with a column per source. (DuckDB also has a PIVOT statement that does
    -- this; the CASE form is used here because it is portable and explicit.)
    SELECT
        obs_date,
        ccy,
        max(CASE WHEN source = 'fred' THEN usd_per_fcy END) AS fred,
        max(CASE WHEN source = 'boc'  THEN usd_per_fcy END) AS boc,
        max(CASE WHEN source = 'ecb'  THEN usd_per_fcy END) AS ecb
    FROM fx_usd_per_fcy
    GROUP BY obs_date, ccy
)
SELECT
    obs_date,
    ccy,
    fred,
    boc,
    ecb,
    ln(boc) - ln(fred) AS boc_vs_fred,
    ln(ecb) - ln(fred) AS ecb_vs_fred
FROM wide;


CREATE OR REPLACE VIEW fx_reconciliation_summary AS
-- One row per (ccy, comparison) with the statistics the quality check thresholds.
-- Units: basis points of log difference (1 bp = 0.01%).
WITH long AS (
    SELECT obs_date, ccy, 'boc' AS source, boc_vs_fred AS diff FROM fx_reconciliation_daily
    UNION ALL
    SELECT obs_date, ccy, 'ecb' AS source, ecb_vs_fred AS diff FROM fx_reconciliation_daily
)
SELECT
    ccy,
    source,
    count(diff)                                        AS n_days,
    min(obs_date) FILTER (WHERE diff IS NOT NULL)      AS first_date,
    max(obs_date) FILTER (WHERE diff IS NOT NULL)      AS last_date,
    1e4 * median(abs(diff))                            AS median_abs_bp,
    1e4 * quantile_cont(abs(diff), 0.99)               AS p99_abs_bp,
    1e4 * max(abs(diff))                               AS max_abs_bp,
    1e4 * avg(diff)                                    AS mean_bp,
    avg(CASE WHEN abs(diff) > 0.01 THEN 1.0 ELSE 0.0 END) AS share_gt_100bp
FROM long
WHERE diff IS NOT NULL
GROUP BY ccy, source
ORDER BY source, ccy;
