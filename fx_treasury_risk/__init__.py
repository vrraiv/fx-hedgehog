"""fx_treasury_risk: FX treasury risk system for a stylized multi-currency payments business.

Conventions used throughout the package (see docs/methodology.md):

* Reporting currency is USD.
* Every FX rate stored in the master table is **USD per one unit of foreign currency**
  (``usd_per_fcy``). A rising number means the foreign currency strengthened.
* Exposure sign: positive = long the foreign currency (an asset the business will
  receive or holds), negative = short (a liability it must pay).
* Interest rates are annualized simple rates in percent unless the docstring says otherwise.
"""

__version__ = "0.1.0"
