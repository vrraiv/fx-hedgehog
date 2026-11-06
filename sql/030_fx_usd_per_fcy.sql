-- 030_fx_usd_per_fcy.sql
-- Convert every FX observation to the house convention: USD per 1 unit of foreign
-- currency, one row per (obs_date, ccy, source). Three sources, three conventions:
--
--   FRED  quotes some pairs as USD per FCY (DEXUSEU) and others as FCY per USD (DEXJPUS)
--   BoC   quotes everything as CAD per FCY, so USD/FCY = (CAD per FCY) / (CAD per USD)
--   ECB   quotes everything as FCY per EUR, so USD/FCY = (USD per EUR) / (FCY per EUR)
--
-- Each CTE below handles one source; the final SELECT stacks them. Keeping all three
-- side by side is what makes the reconciliation check (040) possible.

CREATE OR REPLACE VIEW fx_usd_per_fcy AS
WITH obs AS (
    -- attach the metadata we need: currency, quote convention and (for BoC) vintage
    SELECT
        o.obs_date,
        o.source,
        o.value,
        c.ccy,
        c.quote,
        c.vintage
    FROM raw_observations AS o
    JOIN series_catalog   AS c USING (source, series_id)
    WHERE c.category = 'fx'
),

-- ---------------------------------------------------------------- FRED -----------------
fred AS (
    SELECT
        obs_date,
        ccy,
        'fred' AS source,
        CASE quote
            WHEN 'USD_PER_FCY' THEN value
            WHEN 'FCY_PER_USD' THEN 1.0 / value
        END AS usd_per_fcy
    FROM obs
    WHERE source = 'fred'
),

-- ---------------------------------------------------------------- BoC ------------------
-- The USD/CAD series is the bridge: every other cross is divided by it. The join is on
-- date AND vintage so that a legacy noon cross is only ever divided by the legacy noon
-- USD/CAD, never by the (later-introduced) daily-average series.
boc_usdcad AS (
    SELECT obs_date, vintage, value AS cad_per_usd
    FROM obs
    WHERE source = 'boc' AND ccy = 'USD'
),
boc_all_vintages AS (
    SELECT
        x.obs_date,
        x.ccy,
        x.vintage,
        x.value / u.cad_per_usd AS usd_per_fcy      -- (CAD/FCY) / (CAD/USD) = USD/FCY
    FROM obs AS x
    JOIN boc_usdcad AS u
      ON u.obs_date = x.obs_date AND u.vintage = x.vintage
    WHERE x.source = 'boc' AND x.ccy <> 'USD'

    UNION ALL

    -- CAD itself: USD per CAD is just the reciprocal of CAD per USD
    SELECT obs_date, 'CAD' AS ccy, vintage, 1.0 / cad_per_usd AS usd_per_fcy
    FROM boc_usdcad
),
boc AS (
    -- Jan-Apr 2017 is covered by both vintages; keep the current (daily average) one.
    -- QUALIFY filters on a window function without a nested sub-query.
    SELECT obs_date, ccy, 'boc' AS source, usd_per_fcy
    FROM boc_all_vintages
    QUALIFY row_number() OVER (
        PARTITION BY obs_date, ccy
        ORDER BY (vintage = 'current') DESC
    ) = 1
),

-- ---------------------------------------------------------------- ECB ------------------
ecb_usdeur AS (
    SELECT obs_date, value AS usd_per_eur
    FROM obs
    WHERE source = 'ecb' AND ccy = 'USD'
),
ecb AS (
    SELECT
        x.obs_date,
        x.ccy,
        'ecb' AS source,
        e.usd_per_eur / x.value AS usd_per_fcy     -- (USD/EUR) / (FCY/EUR) = USD/FCY
    FROM obs AS x
    JOIN ecb_usdeur AS e USING (obs_date)
    WHERE x.source = 'ecb' AND x.ccy <> 'USD'

    UNION ALL

    SELECT obs_date, 'EUR' AS ccy, 'ecb' AS source, usd_per_eur
    FROM ecb_usdeur
)

SELECT obs_date, ccy, source, usd_per_fcy FROM fred
UNION ALL
SELECT obs_date, ccy, source, usd_per_fcy FROM boc
UNION ALL
SELECT obs_date, ccy, source, usd_per_fcy FROM ecb;
