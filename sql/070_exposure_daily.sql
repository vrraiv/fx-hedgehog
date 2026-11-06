-- 070_exposure_daily.sql
-- Net open FX exposure by (date, entity, currency), in currency units and in USD.
--
-- ============================================================================
-- WHAT THIS FILE PRODUCES
-- ============================================================================
--
--   exposure_daily      TABLE  one row per (exposure_date, entity, ccy) for EVERY
--                              calendar day between the first and last flow, holding
--                              the end-of-day position of each exposure component in
--                              units of the foreign currency ("_fcy").
--
--   exposure_daily_usd  VIEW   the same rows translated into USD ("_usd") at the
--                              latest New York fixing on or before the exposure date.
--
-- ============================================================================
-- INPUTS (built by earlier scripts)
-- ============================================================================
--
--   flows                 (060) one row per cash-flow event:
--                               flow_date, entity, ccy, flow_type, amount (> 0, in ccy)
--   flow_type_map         (060) economics of each flow_type: which exposure component
--                               it moves and in which direction (sign = +1 / -1).
--                               One flow_type may map to SEVERAL components.
--   fx_usd_master_filled  (050) USD per 1 unit of foreign currency, one row per
--                               (NY business day, ccy), gaps forward-filled.
--
-- ============================================================================
-- CORE IDEA: EXPOSURE IS A STOCK, FLOWS ARE CHANGES
-- ============================================================================
--
-- A flow tells you how much a position CHANGED on a given day. The position itself
-- (what we are actually exposed to) is the cumulative sum of all changes up to and
-- including that day. So the heart of this file is a running sum of signed flows per
-- component, evaluated on every calendar day.
--
-- "Every calendar day" matters: a position does not disappear on a day with no flows.
-- If we only produced rows on days with activity, a quiet weekend would have no row at
-- all, and any consumer would read that as zero exposure. To avoid that we first build a
-- complete date x pair x component grid and
-- left-join the flows onto it, so days without flows contribute a delta of 0 and simply
-- carry the previous day's position forward.
--
-- ============================================================================
-- COMPONENTS
-- ============================================================================
--
-- All components are in units of `ccy`. Sign convention: positive = LONG the currency
-- (we gain if the currency strengthens), negative = SHORT (we lose if it strengthens).
--
--   in_flight     receivables authorized but not yet settled          (asset,     >= 0)
--                 The customer has paid, but the card scheme / acquiring bank has not
--                 yet settled the cash to us (we are the payments company).
--   balance       cash held in the currency                           (asset,     >= 0)
--   payable       owed to merchants who are paid in the currency       (liability, <= 0)
--                 We collected in EUR and must pay the merchant in EUR: a short EUR.
--   intercompany  parent/subsidiary working-capital loan              (+ at US, - at sub)
--                 The same loan is an asset at the lender and a liability at the
--                 borrower, so it nets to zero at group level but not per entity.
--   net           sum of the four. The economic exposure a hedge should offset.
--   gross         sum of their absolute values. The starting point of the exposure
--                 waterfall (080): it shows how much natural offsetting happens before
--                 any hedge is applied.
--
-- ============================================================================
-- OBJECT 1: exposure_daily (TABLE)
-- ============================================================================
--
-- Materialized as a TABLE rather than a VIEW because the window function over the full
-- grid is one of the more expensive steps in the SQL layer and several downstream
-- objects (075_hedges, 080_exposure_waterfall, 090_exposure_group) read it repeatedly.
-- The risk engine itself reads exposure_group_fx (090), not this table.
--
-- The query is a chain of CTEs (common table expressions, the `WITH ... AS` blocks).
-- Each one is a named intermediate result that the next one builds on. Read them
-- top to bottom; the data flow is:
--
--   bounds -> calendar -\
--   pairs ---------------+-> grid -\
--   components ---------/           +-> running -> wide -> final SELECT
--   flows x flow_type_map -> signed /

CREATE OR REPLACE TABLE exposure_daily AS
WITH bounds AS (
    -- CTE `bounds`: the date range the exposure series must cover.
    -- A single row: first_day = earliest flow, last_day = latest flow.
    -- Taken from the data rather than hard-coded so the pipeline follows whatever
    -- horizon the flow generator was run with.
    SELECT min(flow_date) AS first_day, max(flow_date) AS last_day FROM flows
),
calendar AS (
    -- CTE `calendar`: one row per calendar day between first_day and last_day.
    --
    --   generate_series(start, stop, step)  DuckDB function returning a LIST of values
    --                                        from start to stop, inclusive at BOTH ends,
    --                                        stepping by `step` (here INTERVAL 1 DAY).
    --   unnest(list)                         explodes that list into one row per element.
    --   ::DATE                               casts each element (a TIMESTAMP, because the
    --                                        step is an INTERVAL) back to a plain DATE.
    --
    -- This is a full calendar, weekends and holidays included, by design (see the
    -- "stock vs. flows" note above).
    SELECT unnest(generate_series(first_day, last_day, INTERVAL 1 DAY))::DATE AS exposure_date
    FROM bounds
),
pairs AS (
    -- CTE `pairs`: every (entity, currency) combination that appears in the flows.
    -- An entity that never transacts in a currency is not given rows of zeros; it
    -- simply does not appear for that currency.
    SELECT DISTINCT entity, ccy FROM flows
),
components AS (
    -- CTE `components`: the set of exposure components, read from flow_type_map rather
    -- than hard-coded, so adding a new component in 060 automatically flows through
    -- to the grid here. (Currently: in_flight, balance, payable, intercompany.)
    SELECT DISTINCT component FROM flow_type_map
),
grid AS (
    -- CTE `grid`: the complete rectangle  calendar x pairs x components.
    --
    -- CROSS JOIN produces every combination of rows from both sides (a Cartesian
    -- product). Two cross joins give us one row for every
    --   (day, entity, currency, component)
    -- whether or not anything happened that day. Row count is
    --   n_days * n_pairs * n_components,
    -- about 17 years x 21 pairs x 4 components = 0.5m rows on the default config, which
    -- DuckDB handles in well under a second and is what lets the running sum below carry
    -- positions across inactive days. (The final table is a quarter of that: one row per
    -- date and pair, 110k rows.)
    SELECT exposure_date, entity, ccy, component
    FROM calendar
    CROSS JOIN pairs
    CROSS JOIN components
),
signed AS (
    -- CTE `signed`: the net CHANGE (delta) to each component on each day, with signs
    -- applied. This is where the raw, always-positive flow amounts acquire economic
    -- meaning.
    --
    -- JOIN flow_type_map USING (flow_type)
    --   `USING (col)` is shorthand for `ON f.flow_type = m.flow_type` and also
    --   collapses the two flow_type columns into one in the output.
    --   Because flow_type_map can hold more than one row per flow_type, the join
    --   FANS OUT: a single 'settlement' flow of 100 becomes two rows,
    --     (in_flight, -1 * 100)  the receivable is extinguished
    --     (balance,   +1 * 100)  and the cash arrives.
    --   This is the intended mechanism for "one event moves two components".
    --
    -- sum(m.sign * f.amount) AS delta
    --   m.sign is +1 or -1; multiplying turns the positive magnitude into a signed
    --   change. Summing collapses all flows of the same (day, entity, ccy, component)
    --   into one delta, e.g. three auths and one settlement on the same day.
    --
    -- GROUP BY ALL
    --   DuckDB syntax (a few other engines have it too): group by every non-aggregated
    --   column in the SELECT list,
    --   i.e. flow_date, entity, ccy, component. Equivalent to listing them explicitly
    --   but immune to drift if a column is added or renamed.
    --
    -- Note the inner JOIN: a flow_type absent from flow_type_map is silently dropped
    -- here. The `unmapped_flow_types` view in 060 and the guard in
    -- fx_treasury_risk/exposure/build.py exist precisely to catch that.
    SELECT
        f.flow_date,
        f.entity,
        f.ccy,
        m.component,
        sum(m.sign * f.amount) AS delta
    FROM flows AS f
    JOIN flow_type_map AS m USING (flow_type)
    GROUP BY ALL
),
running AS (
    -- CTE `running`: turn daily deltas into end-of-day POSITIONS via a running sum.
    --
    -- LEFT JOIN signed ON (all four keys)
    --   Keeps every grid row. Days with no flows for that (entity, ccy, component)
    --   get NULL for s.delta, which coalesce(..., 0) turns into a zero change.
    --   The join is written with explicit `ON` conditions (not USING) because the
    --   date column is named differently on each side (exposure_date vs flow_date).
    --
    -- sum(...) OVER (...)  a WINDOW function, not a GROUP BY aggregate:
    --   it returns one value per input row instead of collapsing rows.
    --
    --   PARTITION BY g.entity, g.ccy, g.component
    --     Restart the running total for each separate series. EA/EUR/balance never
    --     mixes with EA/GBP/balance or with EA/EUR/payable.
    --   ORDER BY g.exposure_date
    --     Accumulate in calendar order.
    --   ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    --     The window frame: from the first row of the partition up to and including
    --     this row. That is exactly "sum of all changes so far" = the position at
    --     end of day. (Stated explicitly rather than relying on the default frame,
    --     whose RANGE semantics would be the same here but are easy to misread.)
    --
    -- Result column `position_fcy`: the end-of-day stock of that component, in ccy.
    SELECT
        g.exposure_date,
        g.entity,
        g.ccy,
        g.component,
        -- running total of changes = the position at end of day
        sum(coalesce(s.delta, 0)) OVER (
            PARTITION BY g.entity, g.ccy, g.component
            ORDER BY g.exposure_date
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS position_fcy
    FROM grid AS g
    LEFT JOIN signed AS s
      ON s.flow_date = g.exposure_date
     AND s.entity    = g.entity
     AND s.ccy       = g.ccy
     AND s.component = g.component
),
wide AS (
    -- CTE `wide`: PIVOT from long to wide.
    --
    -- `running` is "long": one row per (date, entity, ccy, component). Downstream
    -- consumers want "wide": one row per (date, entity, ccy) with a column per
    -- component, so that net and gross can be computed across columns and the table
    -- reads naturally.
    --
    -- The pivot idiom:
    --   sum(CASE WHEN component = 'x' THEN position_fcy END)
    --     The CASE yields position_fcy for the matching component row and NULL for
    --     every other row; sum() ignores NULLs, so within a (date, entity, ccy) group
    --     it picks out exactly the one matching value. (max() would work equally
    --     well; sum() is conventional for this pattern.)
    --   coalesce(..., 0)
    --     Defensive: if a component had no row at all the result would be NULL.
    --     With the full grid above this cannot happen, but a 0 is the correct
    --     economic value for "no position" and keeps net/gross arithmetic NULL-safe.
    --
    -- GROUP BY ALL groups on exposure_date, entity, ccy.
    SELECT
        exposure_date,
        entity,
        ccy,
        coalesce(sum(CASE WHEN component = 'in_flight'    THEN position_fcy END), 0) AS in_flight_fcy,
        coalesce(sum(CASE WHEN component = 'balance'      THEN position_fcy END), 0) AS balance_fcy,
        coalesce(sum(CASE WHEN component = 'payable'      THEN position_fcy END), 0) AS payable_fcy,
        coalesce(sum(CASE WHEN component = 'intercompany' THEN position_fcy END), 0) AS intercompany_fcy
    FROM running
    GROUP BY ALL
)
-- Final SELECT: add the two derived totals and fix the row order.
--
--   net_fcy    plain sum of the four components. Because each carries its economic
--              sign, assets and liabilities offset: a 100 EUR balance and a -60 EUR
--              payable net to +40 EUR long.
--   gross_fcy  sum of absolute values: 100 + 60 = 160 in the example above. This is
--              the exposure you would see if nothing offset anything, and is the top
--              bar of the gross -> net -> net-of-hedges waterfall in 080.
--
-- ORDER BY is applied so the materialized table is stored in a predictable order;
-- it is not relied upon for correctness.
SELECT
    exposure_date,
    entity,
    ccy,
    in_flight_fcy,
    balance_fcy,
    payable_fcy,
    intercompany_fcy,
    in_flight_fcy + balance_fcy + payable_fcy + intercompany_fcy                    AS net_fcy,
    abs(in_flight_fcy) + abs(balance_fcy) + abs(payable_fcy) + abs(intercompany_fcy) AS gross_fcy
FROM wide
ORDER BY exposure_date, entity, ccy;


-- ============================================================================
-- OBJECT 2: exposure_daily_usd (VIEW)
-- ============================================================================
--
-- Translate every exposure row into USD so that positions in different currencies can
-- be compared, summed at group level (090), and fed to the VaR engine, which works in
-- the reporting currency.
--
-- Defined as a VIEW (not a table) because it is cheap: one lookup per row against the
-- FX master, no window functions. Keeping it a view also means a refreshed FX table is
-- reflected immediately without rebuilding exposure.
--
-- Rate convention: `usd_per_fcy` = US dollars per 1 unit of foreign currency, so
--   amount_usd = amount_fcy * usd_per_fcy
-- for every column, with no division anywhere.
--
-- WHICH RATE? The latest New York fixing ON OR BEFORE the exposure date.
--   exposure_daily has a row for every calendar day; fx_usd_master_filled has a row
--   only for NY business days. A Saturday or holiday exposure is therefore valued at
--   the previous business day's close, which is the standard treasury convention and
--   the only rate that actually existed at the time.

CREATE OR REPLACE VIEW exposure_daily_usd AS
-- USD translation at the latest available NY fixing on or before the exposure date.
-- ASOF JOIN picks, for each exposure row, the single FX row with the greatest obs_date
-- that satisfies obs_date <= exposure_date: a weekend exposure uses Friday's rate.
--
-- ASOF LEFT JOIN  (DuckDB)
--   A specialised join for "most recent value as of a point in time". For each row on
--   the left it finds AT MOST ONE row on the right: among the right rows that satisfy
--   the equality conditions (fx.ccy = e.ccy) and the single inequality condition
--   (fx.obs_date <= e.exposure_date), it keeps the one with the largest obs_date.
--   Doing this with an ordinary join would need a correlated subquery or a window
--   function to deduplicate; ASOF does it in one pass.
--   The LEFT keeps exposure rows that have no FX row at all: USD, which is not in the
--   FX master, and the first calendar days of the sample, which precede the first NY
--   fixing (flows start 2010-01-01, the FX master on 2010-01-04); fx.* is NULL there.
--
-- Output columns
--   usd_per_fcy   the rate used. For USD rows there is no FX row, so the rate is 1.0
--                 by definition (1 USD = 1 USD). For a non-USD row with no fixing
--                 (the first three calendar days of the sample) it is NULL.
--   fx_date       the obs_date of the fixing actually used. Reported so a user can see
--                 that a Sunday row is valued at Friday's rate. For USD it is simply
--                 the exposure date, since no fixing is involved.
--   *_fcy         passed through unchanged from exposure_daily.
--   *_usd         each fcy column multiplied by `rate` (the usd_per_fcy expression
--                 above). A non-USD row with no fixing therefore gets NULL USD values
--                 rather than a silently untranslated amount; nothing downstream reads
--                 those few rows (090 joins on FX dates only), and a NULL is the honest
--                 value for "no rate existed".
WITH translated AS (
    SELECT
        e.*,
        CASE WHEN e.ccy = 'USD' THEN 1.0 ELSE fx.usd_per_fcy END AS rate,
        CASE WHEN e.ccy = 'USD' THEN e.exposure_date ELSE fx.obs_date END AS fx_date
    FROM exposure_daily AS e
    ASOF LEFT JOIN fx_usd_master_filled AS fx
        ON fx.ccy = e.ccy
       AND fx.obs_date <= e.exposure_date
)
SELECT
    exposure_date,
    entity,
    ccy,
    rate                    AS usd_per_fcy,
    fx_date,
    in_flight_fcy,
    balance_fcy,
    payable_fcy,
    intercompany_fcy,
    net_fcy,
    gross_fcy,
    in_flight_fcy    * rate AS in_flight_usd,
    balance_fcy      * rate AS balance_usd,
    payable_fcy      * rate AS payable_usd,
    intercompany_fcy * rate AS intercompany_usd,
    net_fcy          * rate AS net_usd,
    gross_fcy        * rate AS gross_usd
FROM translated;
