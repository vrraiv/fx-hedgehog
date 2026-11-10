-- 100_rates_short.sql
-- One short rate per (NY business day, currency) for covered-interest-parity pricing.
--
-- Every currency is priced off its central bank's policy rate (ADR-0015): one family of
-- daily series, so the rate differential that sets carry compares like with like, and no
-- rate is stale or published after the date it describes. The euro area uses the ECB
-- deposit facility rate, which has anchored euro money-market rates since 2014; the BIS
-- euro-area series (the main refinancing rate) is its fallback. Singapore has no policy
-- rate (the MAS targets the exchange rate), so SGD is proxied by the USD rate and
-- flagged is_proxy = true.
--
-- Each rate is carried forward to every business day with an ASOF JOIN (a policy rate
-- holds until it is changed). A fallback is used only when the primary series is more
-- than 120 days stale.

CREATE OR REPLACE TABLE rate_sources (
    ccy          VARCHAR NOT NULL,
    rank         INTEGER NOT NULL,   -- 1 = primary, 2 = fallback
    source       VARCHAR NOT NULL,
    series_id    VARCHAR NOT NULL,
    day_count    INTEGER NOT NULL    -- 360 or 365, the money-market convention
);

INSERT INTO rate_sources VALUES
    ('USD', 1, 'bis', 'D.US',                      360),
    ('EUR', 1, 'ecb', 'FM.D.U2.EUR.4F.KR.DFR.LEV', 360),
    ('EUR', 2, 'bis', 'D.XM',                      360),
    ('GBP', 1, 'bis', 'D.GB',                      365),
    ('CAD', 1, 'bis', 'D.CA',                      365),
    ('JPY', 1, 'bis', 'D.JP',                      360),
    ('AUD', 1, 'bis', 'D.AU',                      365),
    ('CHF', 1, 'bis', 'D.CH',                      360),
    ('MXN', 1, 'bis', 'D.MX',                      360),
    ('BRL', 1, 'bis', 'D.BR',                      365),
    ('INR', 1, 'bis', 'D.IN',                      365);


CREATE OR REPLACE TABLE rates_short AS
WITH calendar AS (
    SELECT DISTINCT obs_date FROM fx_usd_master
),
obs AS (
    -- every observation of every candidate series, with its metadata attached
    SELECT
        r.ccy, r.rank, r.source, r.series_id, r.day_count,
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
    -- the rate in force on each date, per currency and rank
    SELECT
        g.obs_date, g.ccy, g.rank,
        o.source, o.series_id, o.day_count,
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
    obs_date, ccy, rate_pct, source, series_id, rate_date, days_stale, day_count,
    false        AS is_proxy,
    rank = 2     AS is_fallback
FROM chosen

UNION ALL

-- SGD: no policy rate; use the USD rate and say so
SELECT
    obs_date, 'SGD' AS ccy, rate_pct, 'proxy:USD' AS source, series_id, rate_date, days_stale,
    day_count,           -- same day count as USD so the proxy carry is exactly zero
    true         AS is_proxy,
    rank = 2     AS is_fallback
FROM chosen
WHERE ccy = 'USD'
ORDER BY obs_date, ccy;
