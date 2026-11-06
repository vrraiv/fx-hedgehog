-- 050_fx_usd_master.sql
-- The one FX table everything downstream uses: USD per 1 FCY, one row per (date, ccy).
--
-- Calendar  : New York business days = every date on which FRED published an H.10 rate.
--             Other sources trade on days NY is closed; those days are dropped so that
--             daily returns always span one NY trading day.
-- Precedence: FRED, then BoC, then ECB. `source_used` records which one filled the cell
--             so a report can state exactly where each number came from.
-- Gaps      : if no source has a value the row is kept with usd_per_fcy = NULL; the
--             quality check counts those. `fx_usd_master_filled` forward-fills them.

CREATE OR REPLACE TABLE fx_usd_master AS
WITH calendar AS (
    SELECT DISTINCT obs_date
    FROM fx_usd_per_fcy
    WHERE source = 'fred'
),
ccys AS (
    SELECT DISTINCT ccy
    FROM fx_usd_per_fcy
    WHERE ccy <> 'USD'
),
grid AS (
    -- the full (date x currency) rectangle, so that gaps become visible as NULLs
    SELECT obs_date, ccy
    FROM calendar
    CROSS JOIN ccys
),
wide AS (
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
    g.obs_date,
    g.ccy,
    coalesce(w.fred, w.boc, w.ecb) AS usd_per_fcy,     -- first non-NULL wins
    CASE
        WHEN w.fred IS NOT NULL THEN 'fred'
        WHEN w.boc  IS NOT NULL THEN 'boc'
        WHEN w.ecb  IS NOT NULL THEN 'ecb'
    END AS source_used
FROM grid AS g
LEFT JOIN wide AS w USING (obs_date, ccy)
ORDER BY g.obs_date, g.ccy;


CREATE OR REPLACE VIEW fx_usd_master_filled AS
-- Forward-filled version. `last_value(... IGNORE NULLS)` over an unbounded-preceding
-- window carries the most recent non-NULL value forward within each currency.
-- `is_filled` marks the carried values so a return computed over them can be excluded.
SELECT
    obs_date,
    ccy,
    last_value(usd_per_fcy IGNORE NULLS) OVER (
        PARTITION BY ccy
        ORDER BY obs_date
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS usd_per_fcy,
    usd_per_fcy IS NULL AS is_filled,
    source_used
FROM fx_usd_master;
