-- 020_series_catalog.sql
-- Materialise the Python series registry (fx_treasury_risk/data/registry.py) as a table so
-- that SQL can join observations to their metadata (currency, quote convention, vintage).
--
-- `catalog_df` is a pandas DataFrame registered on the connection by Python just before
-- this file runs; DuckDB lets you query a registered DataFrame as if it were a table.

CREATE OR REPLACE TABLE series_catalog AS
SELECT
    source,
    series_id,
    category,          -- fx | rate | policy_rate | eer | retail
    ccy,
    quote,             -- USD_PER_FCY | FCY_PER_USD | CAD_PER_FCY | FCY_PER_EUR | NULL
    frequency,         -- daily | monthly
    vintage,           -- current | legacy (Bank of Canada FX series only)
    tenor_months,
    unit,
    description
FROM catalog_df;
