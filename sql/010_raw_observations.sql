-- 010_raw_observations.sql
-- Load every cached CSV into one long ("tidy") table: one row per (source, series_id, date).
--
-- Why long rather than wide? Each source has its own calendar and its own quote
-- convention, and a long table lets SQL join on the series catalogue to normalise them
-- instead of hard-coding column names. Wide matrices are built later as views.
--
-- This file is a Python string.Template: ${cache_glob} is substituted at run time and
-- expands to <data_dir>/cache/*/*.csv. A literal dollar sign is written as two ($$).

CREATE OR REPLACE TABLE raw_observations AS
WITH files AS (
    SELECT
        -- read_csv(..., filename = true) adds a column with the path each row came from;
        -- Windows paths use backslashes, so normalise them before pattern-matching.
        replace(filename, '\', '/')        AS path,
        "date"                             AS obs_date,
        value                              AS value
    FROM read_csv(
        '${cache_glob}',
        header   = true,
        filename = true,
        columns  = {'date': 'DATE', 'value': 'DOUBLE'}
    )
)
SELECT
    -- the cache layout is  <source>/<series_id>.csv ; recover both from the path
    regexp_extract(path, '([^/]+)/([^/]+)\.csv$$', 1) AS source,
    regexp_extract(path, '([^/]+)/([^/]+)\.csv$$', 2) AS series_id,
    obs_date,
    value
FROM files
ORDER BY source, series_id, obs_date;
