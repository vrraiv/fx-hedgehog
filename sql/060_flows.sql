-- 060_flows.sql
-- Load the synthetic flows and define what each flow type does to exposure.
--
-- ${flows_path} is the Parquet file written by `fxrisk flows`.
--
-- The generator only produces positive amounts by flow type; the economics live here, in
-- flow_type_map. A flow type may move more than one component (a settlement both
-- extinguishes a receivable and creates cash), which is why this is a mapping table and
-- not a column on the flows: the exposure query joins to it and lets duplicate matches
-- fan out into one row per component.

CREATE OR REPLACE TABLE flows AS
SELECT
    "date"::DATE   AS flow_date,
    entity,
    ccy,
    flow_type,
    amount::DOUBLE AS amount          -- in `ccy`, positive magnitude
FROM read_parquet('${flows_path}');


CREATE OR REPLACE TABLE flow_type_map (
    flow_type  VARCHAR NOT NULL,
    component  VARCHAR NOT NULL,      -- in_flight | balance | payable | intercompany
    sign       INTEGER NOT NULL       -- +1 adds to the component, -1 reduces it
);

INSERT INTO flow_type_map VALUES
    -- a receivable is created when the customer pays, extinguished when cash settles
    ('auth',               'in_flight',    +1),
    ('settlement',         'in_flight',    -1),
    ('settlement',         'balance',      +1),
    -- merchants paid in the collected currency are a liability from authorization
    ('payable_accrual',    'payable',      -1),
    ('payout_same',        'payable',      +1),   -- liability settled ...
    ('payout_same',        'balance',      -1),   -- ... with cash
    ('payout_converted',   'balance',      -1),   -- cash sold for the functional currency
    -- refunds: cash out to the customer; merchants repay via smaller next payouts
    ('refund_paid',        'balance',      -1),
    ('refund_clawback',    'payable',      +1),   -- same-currency merchants owe it back
    -- retained fees sold monthly
    ('fee_sweep',          'balance',      -1),
    -- parent's loan to a subsidiary: asset at the parent, liability at the subsidiary
    ('interco_receivable', 'intercompany', +1),
    ('interco_payable',    'intercompany', -1);


-- Guard: every flow type the generator emits must be mapped, or exposure silently drops it.
CREATE OR REPLACE VIEW unmapped_flow_types AS
SELECT DISTINCT flow_type
FROM flows
WHERE flow_type NOT IN (SELECT flow_type FROM flow_type_map);
