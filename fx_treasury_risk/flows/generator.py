"""Deterministic synthetic merchant flows for a stylized multi-entity payments business.

For every configured (entity, currency) pair the generator produces daily amounts, in the
collected currency, for a fixed set of flow types. The *economics* of each flow (which
exposure component it moves, and with what sign) are not decided here: that mapping lives
in ``sql/060_flows.sql`` (table ``flow_type_map``) so the exposure logic stays in SQL.

Life of an authorized amount ``A`` on calendar day ``t`` (see docs/methodology.md s.3):

* ``auth``            day t: the receivable is created (in-flight).
* ``payable_accrual`` day t: the share of merchants paid in the same currency becomes a
                      payable immediately, ``A * (1 - take) * s``.
* ``settlement``      day t + L business days: cash arrives, receivable extinguished.
* ``payout_same``     next payout date after settlement: merchants paid in currency.
* ``payout_converted`` same date: the rest is sold for the functional currency.
* ``refund_paid``     day t + R calendar days: a share of A refunded to the customer
                      out of the currency balance.
* ``refund_clawback`` same date: merchants paid in the same currency owe the refund back
                      net of the fee, so the payable to them falls by ``(1-take) * R * s``;
                      the next payout is reduced by the same amount. Merchants paid in the
                      functional currency are clawed back there, so the next converted
                      payout is smaller by ``(1-take) * R * (1-s)``.
* ``fee_sweep``       last business day of the month: fees earned on settlements, less
                      fees given back on refunds, sold for the functional currency.

Conservation: for every authorized A the balance, payable and in-flight components all
return to zero once A is settled, paid out, refunded and swept; nothing accumulates
except the intercompany loan, which is a stock by design.
* ``interco_receivable`` / ``interco_payable``: working-capital loans from the US parent.

Amounts are positive magnitudes; ``flow_type_map`` applies the signs.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from fx_treasury_risk.flows.config import FlowConfig

FLOW_TYPES: tuple[str, ...] = (
    "auth",
    "payable_accrual",
    "settlement",
    "payout_same",
    "payout_converted",
    "refund_paid",
    "refund_clawback",
    "fee_sweep",
    "interco_receivable",
    "interco_payable",
)


def _pair_rng(seed: int, entity: str, ccy: str) -> np.random.Generator:
    """A generator whose stream depends only on (seed, entity, ccy).

    Adding or removing another pair in the config therefore never changes this pair's
    flows, which keeps backtests comparable across config edits.
    """
    return np.random.default_rng([seed, *(ord(ch) for ch in f"{entity}:{ccy}")])


def _ar1_noise(rng: np.random.Generator, n: int, sigma: float, rho: float) -> np.ndarray:
    """Mean-one lognormal multiplier with AR(1) log-noise of stationary s.d. ``sigma``.

    The starting value is drawn before the innovations so that the first ``m`` values do
    not depend on ``n``: extending the horizon appends to the path without rewriting it.
    """
    e0 = rng.standard_normal() * sigma
    eps = rng.standard_normal(n) * sigma * np.sqrt(1 - rho**2)
    e = np.empty(n)
    e[0] = e0
    for t in range(1, n):  # short loop; n ~ 6,000
        e[t] = rho * e[t - 1] + eps[t]
    return np.exp(e - 0.5 * sigma**2)


def _regime_multiplier(cfg: FlowConfig, days: pd.DatetimeIndex) -> np.ndarray:
    m = np.ones(len(days))
    for r in cfg.regimes:
        mask = (days >= pd.Timestamp(r.start)) & (days <= pd.Timestamp(r.end))
        m[mask] *= r.multiplier
    return m


def _refund_lag_probs(mean: int, max_lag: int) -> np.ndarray:
    """Truncated geometric distribution over lags 1..max_lag with mean about ``mean``."""
    p = 1.0 / mean
    lags = np.arange(1, max_lag + 1)
    q = (1 - p) ** (lags - 1) * p
    return q / q.sum()


def _add_shifted(target: np.ndarray, src: np.ndarray, shift_pos: np.ndarray, weight: float) -> None:
    """``target[shift_pos[i]] += weight * src[i]`` for destinations inside the array."""
    ok = (shift_pos >= 0) & (shift_pos < len(target))
    np.add.at(target, shift_pos[ok], weight * src[ok])


def _payout_positions(days: pd.DatetimeIndex, schedule: str) -> np.ndarray:
    if schedule == "daily":
        return np.flatnonzero(days.day_of_week < 5)
    if schedule == "weekly":
        return np.flatnonzero(days.day_of_week == 4)  # Friday
    raise ValueError(f"unknown payout schedule {schedule!r}")


def _month_end_business_positions(days: pd.DatetimeIndex) -> np.ndarray:
    bdays = days[days.day_of_week < 5]
    last = bdays.to_series().groupby([bdays.year, bdays.month]).max()
    return days.get_indexer(pd.DatetimeIndex(last.to_numpy()))


def _window_sums(cum: np.ndarray, positions: np.ndarray) -> np.ndarray:
    """Differences of a cumulative sum at ``positions``: sum over (prev position, position]."""
    at = cum[positions]
    return np.diff(np.concatenate([[0.0], at]))


def generate_pair(
    cfg: FlowConfig, entity: str, ccy: str, annual: np.ndarray, days: pd.DatetimeIndex
) -> pd.DataFrame:
    """Daily flows for one (entity, currency) pair, long format."""
    rng = _pair_rng(cfg.seed, entity, ccy)
    n = len(days)
    years = (days - days[0]).days.to_numpy() / 365.25
    volume = cfg.entities[entity].volumes_per_day[ccy]

    weekly = np.asarray(cfg.weekly_seasonality)[days.day_of_week.to_numpy()]
    monthly = annual[days.month.to_numpy() - 1]
    growth = np.exp(cfg.growth_annual_rate * years)
    noise = _ar1_noise(rng, n, cfg.noise_daily_sigma, cfg.noise_ar1)
    auth = volume * growth * weekly * monthly * _regime_multiplier(cfg, days) * noise

    take, s = cfg.take_rate, cfg.same_ccy_share(ccy)
    payable_accrual = auth * (1 - take) * s

    # settlement: spread each day's authorizations over business-day lags
    days_d = days.to_numpy().astype("datetime64[D]")
    settlement = np.zeros(n)
    for lag, prob in cfg.settlement_lag(ccy).items():
        dest = np.busday_offset(days_d, lag, roll="forward")
        pos = (dest - days_d[0]).astype(int)
        _add_shifted(settlement, auth, pos, prob)

    # refunds: calendar-day lags with a truncated geometric distribution
    refund_paid = np.zeros(n)
    probs = _refund_lag_probs(cfg.refund_mean_lag_days, cfg.refund_max_lag_days)
    base_pos = np.arange(n)
    for lag, prob in enumerate(probs, start=1):
        _add_shifted(refund_paid, auth * cfg.refund_rate, base_pos + lag, prob)
    refund_clawback = refund_paid * (1 - take) * s
    clawback_converted = refund_paid * (1 - take) * (1 - s)

    # merchant payouts on the schedule, covering settlements up to the previous day,
    # net of refunds clawed back from the merchants over the same window
    due_same = settlement * (1 - take) * s - refund_clawback
    due_conv = settlement * (1 - take) * (1 - s) - clawback_converted
    cum_same_prev = np.concatenate([[0.0], np.cumsum(due_same)[:-1]])
    cum_conv_prev = np.concatenate([[0.0], np.cumsum(due_conv)[:-1]])
    pay_pos = _payout_positions(days, cfg.payout_schedule_by_entity[entity])
    payout_same = np.zeros(n)
    payout_conv = np.zeros(n)
    payout_same[pay_pos] = _window_sums(cum_same_prev, pay_pos)
    payout_conv[pay_pos] = _window_sums(cum_conv_prev, pay_pos)

    # fee sweep: fees on the month's settlements, less fees returned on refunds, sold at
    # month end (always non-negative because refunds are a fraction of authorizations)
    fee_net = settlement * take - refund_paid * take
    sweep_pos = _month_end_business_positions(days)
    fee_sweep = np.zeros(n)
    fee_sweep[sweep_pos] = np.maximum(_window_sums(np.cumsum(fee_net), sweep_pos), 0.0)

    columns = {
        "auth": auth,
        "payable_accrual": payable_accrual,
        "settlement": settlement,
        "payout_same": payout_same,
        "payout_converted": payout_conv,
        "refund_paid": refund_paid,
        "refund_clawback": refund_clawback,
        "fee_sweep": fee_sweep,
    }
    wide = pd.DataFrame(columns, index=days)
    wide.index.name = "date"
    long = wide.melt(ignore_index=False, var_name="flow_type", value_name="amount").reset_index()
    long = long[long["amount"] > 0]
    long.insert(1, "entity", entity)
    long.insert(2, "ccy", ccy)
    return long


def generate_intercompany(cfg: FlowConfig, days: pd.DatetimeIndex) -> pd.DataFrame:
    """Quarterly top-ups of the parent's working-capital loans, in the borrower's currency.

    The outstanding balance tracks the growth trend; each quarter emits the *change* so
    that cumulative sums in SQL give the balance. A receivable row at the US parent and a
    payable row at the subsidiary are emitted for every top-up.
    """
    quarter_starts = pd.date_range(days[0], days[-1], freq="QS")
    quarter_starts = quarter_starts[quarter_starts >= days[0]]
    bday = pd.DatetimeIndex(
        np.busday_offset(quarter_starts.to_numpy().astype("datetime64[D]"), 0, roll="forward")
    )
    years = (bday - days[0]).days.to_numpy() / 365.25
    rows = []
    for sub, notional in cfg.interco_loans_from_us.items():
        ccy = cfg.entities[sub].functional
        outstanding = notional * np.exp(cfg.growth_annual_rate * years)
        change = np.diff(np.concatenate([[0.0], outstanding]))
        for d, amt in zip(bday, change, strict=True):
            rows.append((d, "US", ccy, "interco_receivable", amt))
            rows.append((d, sub, ccy, "interco_payable", amt))
    return pd.DataFrame(rows, columns=["date", "entity", "ccy", "flow_type", "amount"])


def generate(cfg: FlowConfig, annual_profiles: dict[str, np.ndarray]) -> pd.DataFrame:
    """All flows for all pairs plus intercompany, sorted, long format.

    Columns: ``date`` (calendar day), ``entity``, ``ccy``, ``flow_type``, ``amount`` (in
    ``ccy``, positive magnitude). ``cfg.end`` must be resolved (see
    :func:`fx_treasury_risk.flows.pipeline.resolve_end`). Flows on any date depend only on
    earlier dates, so a later ``end`` appends flows without changing earlier ones.
    """
    if cfg.end is None:
        raise ValueError("flow config end date is unresolved ('auto'); call resolve_end first")
    days = pd.date_range(cfg.start, cfg.end, freq="D")
    frames = [
        generate_pair(cfg, e, c, annual_profiles[cfg.annual_profile_by_entity[e]], days)
        for e, c in cfg.pairs
    ]
    frames.append(generate_intercompany(cfg, days))
    out = pd.concat(frames, ignore_index=True)
    out["date"] = pd.to_datetime(out["date"])
    return out.sort_values(["date", "entity", "ccy", "flow_type"]).reset_index(drop=True)
