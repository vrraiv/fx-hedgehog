-- 100_rates_short.sql
-- One short rate per (NY business day, currency) for covered-interest-parity pricing.
--
-- Source precedence per currency (ADR-0006): a primary market rate (3-month where FRED
-- carries one), falling back to the BIS daily policy rate when the primary is more than
-- 120 days stale. Monthly series are carried forward to daily with an ASOF JOIN: for each
-- calendar date take the latest observation on or before it. SGD has no public rate and
-- is proxied by the USD rate, flagged is_proxy = true.
--
-- Rates are in percent per annum as published; `basis` says how to read them
-- ('discount' for US T-bills, which Python converts to a simple yield; see the primer).

CREATE OR REPLACE TABLE rate_sources (
    ccy          VARCHAR NOT NULL,
    rank         INTEGER NOT NULL,   -- 1 = primary, 2 = fallback
    source       VARCHAR NOT NULL,
    series_id    VARCHAR NOT NULL,
    tenor_months INTEGER NOT NULL,   -- 0 = overnight / policy
    day_count    INTEGER NOT NULL,   -- 360 or 365
    basis        VARCHAR NOT NULL    -- 'simple' | 'discount'
);

INSERT INTO rate_sources VALUES
    ('USD', 1, 'fred', 'DTB3',            3, 360, 'discount'),
    ('USD', 2, 'fred', 'SOFR',            0, 360, 'simple'),
    ('CAD', 1, 'boc',  'TB.CDN.90D.MID',  3, 365, 'simple'),
    ('CAD', 2, 'bis',  'D.CA',            0, 365, 'simple'),
    ('EUR', 1, 'fred', 'IR3TIB01EZM156N', 3, 360, 'simple'),
    ('EUR', 2, 'bis',  'D.XM',            0, 360, 'simple'),
    ('GBP', 1, 'fred', 'IR3TIB01GBM156N', 3, 365, 'simple'),
    ('GBP', 2, 'bis',  'D.GB',            0, 365, 'simple'),
    ('JPY', 1, 'fred', 'IR3TIB01JPM156N', 3, 360, 'simple'),
    ('JPY', 2, 'bis',  'D.JP',            0, 360, 'simple'),
    ('AUD', 1, 'fred', 'IR3TIB01AUM156N', 3, 365, 'simple'),
    ('AUD', 2, 'bis',  'D.AU',            0, 365, 'simple'),
    ('CHF', 1, 'fred', 'IR3TIB01CHM156N', 3, 360, 'simple'),
    ('CHF', 2, 'bis',  'D.CH',            0, 360, 'simple'),
    ('MXN', 1, 'fred', 'IR3TIB01MXM156N', 3, 360, 'simple'),
    ('MXN', 2, 'bis',  'D.MX',            0, 360, 'simple'),
    ('BRL', 1, 'fred', 'IRSTCI01BRM156N', 0, 365, 'simple'),
    ('BRL', 2, 'bis',  'D.BR',            0, 365, 'simple'),
    ('INR', 1, 'fred', 'IRSTCI01INM156N', 0, 365, 'simple'),
    ('INR', 2, 'bis',  'D.IN',            0, 365, 'simple');


CREATE OR REPLACE TABLE rates_short AS
WITH calendar AS (
    SELECT DISTINCT obs_date FROM fx_usd_master
),
obs AS (
    -- every observation of every candidate series, with its metadata attached
    SELECT
        r.ccy, r.rank, r.source, r.series_id, r.tenor_months, r.day_count, r.basis,
        o.obs_date AS rate_date,
        o.value    AS rate_pct
    FROM rate_sources     AS r
    JOIN raw_observations AS o USING (source, series_id)
),
grid AS (
    -- one row per (date, ccy, rank): the ASOF JOIN below needs the partition keys on
    -- its left side so that each currency/rank pair is matched independently
    SELECT c.obs_date, r.ccy, r.rank
    FROM calendar AS c
    CROSS JOIN (SELECT DISTINCT ccy, rank FROM rate_sources) AS r
),
latest AS (
    -- latest observation on or before each date, per currency and rank
    SELECT
        g.obs_date, g.ccy, g.rank,
        o.source, o.series_id, o.tenor_months, o.day_count, o.basis,
        o.rate_date, o.rate_pct,
        g.obs_date - o.rate_date AS days_stale
    FROM grid AS g
    ASOF LEFT JOIN obs AS o
      ON o.ccy = g.ccy
     AND o.rank = g.rank
     AND o.rate_date <= g.obs_date
),
chosen AS (
    -- precedence: fresh primary, then fallback, then a stale primary rather than nothing
    SELECT *
    FROM latest
    WHERE rate_pct IS NOT NULL
    QUALIFY row_number() OVER (
        PARTITION BY obs_date, ccy
        ORDER BY CASE
            WHEN rank = 1 AND days_stale <= 120 THEN 0
            WHEN rank = 2                       THEN 1
            ELSE 2
        END
    ) = 1
)
SELECT
    obs_date, ccy, rate_pct, source, series_id, rate_date, days_stale,
    tenor_months, day_count, basis,
    false        AS is_proxy,
    rank = 2     AS is_fallback
FROM chosen

UNION ALL

-- SGD: no public short rate; use the USD rate and say so
SELECT
    obs_date, 'SGD' AS ccy, rate_pct, 'proxy:USD' AS source, series_id, rate_date, days_stale,
    tenor_months, day_count, basis,      -- same day count as USD so the proxy carry is exactly zero
    true         AS is_proxy,
    rank = 2     AS is_fallback
FROM chosen
WHERE ccy = 'USD'
ORDER BY obs_date, ccy;
