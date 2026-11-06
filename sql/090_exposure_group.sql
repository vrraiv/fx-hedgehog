-- 090_exposure_group.sql
-- Group net exposure by currency on the FX (NY business-day) calendar: the input to the
-- risk engine. Exposure exists every calendar day; risk is measured on trading days, so
-- each FX date simply picks that day's exposure (an exact match, no as-of needed).

CREATE OR REPLACE TABLE exposure_group_fx AS
SELECT
    fx.obs_date,
    fx.ccy,
    fx.usd_per_fcy,
    sum(w.net_fcy)             AS net_fcy,
    sum(w.net_usd)             AS net_usd,
    sum(w.net_of_hedges_fcy)   AS net_of_hedges_fcy,
    sum(w.net_of_hedges_usd)   AS net_of_hedges_usd,
    sum(w.gross_usd)           AS gross_usd
FROM fx_usd_master_filled AS fx
JOIN exposure_waterfall   AS w
  ON w.exposure_date = fx.obs_date
 AND w.ccy           = fx.ccy
GROUP BY ALL
ORDER BY fx.obs_date, fx.ccy;
