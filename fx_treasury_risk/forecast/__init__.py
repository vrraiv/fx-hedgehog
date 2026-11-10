"""Exposure forecasting 1-63 trading days ahead with prediction intervals.

Two models (docs/methodology.md section 6, ADR-0011):

* ``seasonal_naive`` - the value on the same weekday four weeks earlier, repeated;
  intervals from the empirical distribution of its own past errors at each horizon.
* ``calendar_ar1`` - a structural regression of log exposure on calendar features
  (weekday, distance to month end, first days of the month, month of year, trend) with
  AR(1) errors; intervals from its own standardised in-sample errors on the log scale.

Both produce quantiles of the exposure in currency units (``net_fcy``). Evaluation is
rolling-origin: pinball loss and central-interval coverage at 50/80/95 per currency.
"""
