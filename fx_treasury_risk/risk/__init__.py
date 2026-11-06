"""Risk engine: returns, covariance estimators, VaR / Expected Shortfall, stress tests.

Conventions (docs/methodology.md section 5):

* Inputs are **USD exposures by currency** (positive = long the currency) and daily
  **log returns of usd_per_fcy**.
* P&L over a horizon is ``sum_c exposure_usd_c * (exp(r_c) - 1)``; loss is ``-P&L``.
* VaR and ES are reported as **positive USD loss amounts** at confidence ``alpha``:
  VaR is the ``alpha`` quantile of loss, ES the mean loss beyond VaR.
* Every function returns tidy frames with ``method`` and parameter columns so that
  results from different estimators can be stacked and compared.
"""
