"""Hedging: short rates, forward pricing by covered interest parity, carry, the optimizer.

Sign conventions (docs/hedging-primer.md):

* ``notional_fcy < 0`` means the currency was sold forward (the hedge of a long exposure).
* ``hedge_cost_rate`` is the annualized cost, as a fraction of notional, of hedging a
  *long* exposure: ``(S - F) / S * 365 / days``. Positive means hedging costs carry
  (the forward sells the currency below spot, which happens when ``r_fcy > r_usd``).
"""
