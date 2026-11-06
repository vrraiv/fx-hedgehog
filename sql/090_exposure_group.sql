-- 090_exposure_group.sql
-- Group net exposure by currency on the FX (NY business-day) calendar: the input to the
-- risk engine and the hedge optimizer. Exposure exists every calendar day; risk is
-- measured on trading days, so each FX date simply picks that day's exposure (an exact
-- match, no as-of needed). Hedges include entity-level and group-level positions.

CREATE OR REPLACE TABLE exposure_group_fx AS
SELECT
    fx.obs_date,
    fx.ccy,
    fx.usd_per_fcy,
    w.net_fcy,
    w.net_usd,
    w.net_of_hedges_fcy,
    w.net_of_hedges_usd,
    w.gross_usd
FROM fx_usd_master_filled        AS fx
JOIN exposure_waterfall_by_ccy   AS w
  ON w.exposure_date = fx.obs_date
 AND w.ccy           = fx.ccy
ORDER BY fx.obs_date, fx.ccy;
