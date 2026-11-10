# Risk tables as of 2026-10-30

## Exposures by currency

| ccy | net (USD m) | net of hedges (USD m) |
|---|---|---|
| AUD | 7.17 | -2.12 |
| BRL | 20.09 | 20.09 |
| CAD | 10.01 | -2.07 |
| CHF | 7.29 | -12.86 |
| EUR | 11.74 | -14.56 |
| GBP | 9.97 | -13.91 |
| INR | 21.18 | 21.18 |
| JPY | 11.18 | -2.04 |
| MXN | 14.42 | 14.42 |
| SGD | 7.93 | -2.01 |

## VaR / ES, net exposure (USD m)

| method | ES 1d 95% | ES 1d 99% | ES 10d 95% | ES 10d 99% | ES 21d 95% | ES 21d 99% | VaR 1d 95% | VaR 1d 99% | VaR 10d 95% | VaR 10d 99% | VaR 21d 95% | VaR 21d 99% |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| historical simulation | 0.9 | 1.28 | 2.27 | 2.7 | 3.15 | 3.68 | 0.64 | 1 | 1.9 | 2.52 | 2.75 | 3.37 |
| Monte Carlo, t copula, EWMA 0.94 | 1.07 | 1.68 | 3.11 | 4.2 | 4.42 | 5.81 | 0.73 | 1.26 | 2.4 | 3.49 | 3.48 | 5.03 |
| Monte Carlo, t copula, EWMA 0.97 | 0.97 | 1.53 | 2.85 | 3.89 | 4.07 | 5.39 | 0.66 | 1.14 | 2.2 | 3.24 | 3.18 | 4.6 |
| normal, EWMA 0.94 | 1.01 | 1.3 | 3.19 | 4.12 | 4.62 | 5.97 | 0.8 | 1.14 | 2.54 | 3.6 | 3.69 | 5.21 |
| normal, EWMA 0.97 | 0.91 | 1.18 | 2.88 | 3.72 | 4.17 | 5.39 | 0.73 | 1.03 | 2.3 | 3.25 | 3.33 | 4.71 |
| normal, Ledoit-Wolf | 0.86 | 1.11 | 2.71 | 3.5 | 3.92 | 5.07 | 0.68 | 0.97 | 2.16 | 3.05 | 3.13 | 4.42 |
| normal, sample covariance | 0.86 | 1.11 | 2.72 | 3.52 | 3.94 | 5.09 | 0.69 | 0.97 | 2.17 | 3.07 | 3.14 | 4.45 |
| Student-t, EWMA 0.94 | 1.09 | 1.69 | 3.46 | 5.33 | 5.02 | 7.73 | 0.76 | 1.27 | 2.41 | 4.03 | 3.5 | 5.84 |
| Student-t, EWMA 0.97 | 0.99 | 1.52 | 3.12 | 4.81 | 4.53 | 6.98 | 0.69 | 1.15 | 2.18 | 3.64 | 3.16 | 5.27 |
| Student-t, Ledoit-Wolf | 0.93 | 1.43 | 2.94 | 4.52 | 4.26 | 6.56 | 0.65 | 1.08 | 2.05 | 3.42 | 2.97 | 4.95 |
| Student-t, sample covariance | 0.93 | 1.44 | 2.95 | 4.55 | 4.28 | 6.59 | 0.65 | 1.09 | 2.06 | 3.44 | 2.98 | 4.98 |

## VaR / ES, net of hedges exposure (USD m)

| method | ES 1d 95% | ES 1d 99% | ES 10d 95% | ES 10d 99% | ES 21d 95% | ES 21d 99% | VaR 1d 95% | VaR 1d 99% | VaR 10d 95% | VaR 10d 99% | VaR 21d 95% | VaR 21d 99% |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| historical simulation | 0.58 | 0.93 | 2.1 | 2.82 | 2.56 | 3.41 | 0.39 | 0.69 | 1.5 | 2.55 | 2.01 | 2.69 |
| Monte Carlo, t copula, EWMA 0.94 | 0.87 | 1.33 | 2.54 | 3.37 | 3.6 | 4.66 | 0.62 | 1.01 | 1.98 | 2.88 | 2.85 | 4.07 |
| Monte Carlo, t copula, EWMA 0.97 | 0.72 | 1.1 | 2.11 | 2.83 | 3.01 | 3.94 | 0.51 | 0.84 | 1.64 | 2.4 | 2.39 | 3.4 |
| normal, EWMA 0.94 | 0.83 | 1.08 | 2.63 | 3.4 | 3.81 | 4.93 | 0.66 | 0.94 | 2.1 | 2.97 | 3.04 | 4.3 |
| normal, EWMA 0.97 | 0.68 | 0.88 | 2.16 | 2.79 | 3.13 | 4.05 | 0.55 | 0.77 | 1.72 | 2.44 | 2.5 | 3.53 |
| normal, Ledoit-Wolf | 0.49 | 0.63 | 1.55 | 2.01 | 2.25 | 2.91 | 0.39 | 0.55 | 1.24 | 1.75 | 1.79 | 2.54 |
| normal, sample covariance | 0.49 | 0.64 | 1.55 | 2.01 | 2.25 | 2.91 | 0.39 | 0.55 | 1.24 | 1.75 | 1.8 | 2.54 |
| Student-t, EWMA 0.94 | 0.91 | 1.42 | 2.87 | 4.5 | 4.16 | 6.52 | 0.62 | 1.06 | 1.97 | 3.35 | 2.86 | 4.85 |
| Student-t, EWMA 0.97 | 0.75 | 1.17 | 2.36 | 3.7 | 3.42 | 5.36 | 0.51 | 0.87 | 1.62 | 2.75 | 2.35 | 3.98 |
| Student-t, Ledoit-Wolf | 0.54 | 0.84 | 1.69 | 2.65 | 2.45 | 3.84 | 0.37 | 0.62 | 1.16 | 1.97 | 1.69 | 2.86 |
| Student-t, sample covariance | 0.54 | 0.84 | 1.7 | 2.66 | 2.46 | 3.85 | 0.37 | 0.63 | 1.17 | 1.98 | 1.69 | 2.87 |

## Stress, net exposure

| scenario | kind | window | others propagated | largest move | largest implied moves | P&L (USD m) | note |
|---|---|---|---|---|---|---|---|
| CHF floor removed, Jan 2015 | historical | 2015-01-14 to 2015-01-16 | no | CHF +18.1% |  | 1.05 | SNB removes the EUR/CHF floor, 15 Jan 2015 |
| Brexit vote, Jun 2016 | historical | 2016-06-23 to 2016-06-27 | no | GBP -11.3% |  | -2.92 | UK referendum result, 24-27 Jun 2016 |
| Dash for dollars, Mar 2020 | historical | 2020-03-06 to 2020-03-20 | no | MXN -17.5% |  | -8.66 | dash for dollars, March 2020 |
| USD surge, Aug-Sep 2022 | historical | 2022-08-01 to 2022-09-27 | no | GBP -13.3% |  | -6.42 | Fed hiking cycle, DXY peak 27 Sep 2022 |
| Taper tantrum, May-Aug 2013 | historical | 2013-05-22 to 2013-08-30 | no | INR -16.7% |  | -6.5 | EM selloff after Bernanke's taper remarks (BRL, INR) |
| USD +10% against all | hypothetical |  | no | EUR -10.0% |  | -11.51 | every exposure currency weakens 10% against USD, no propagation needed |
| EM selloff (BRL, MXN -15%, INR -10%) | hypothetical |  | yes | MXN -15.0% | AUD -10.8%, EUR -7.3%, GBP -7.2% | -11.02 | EM selloff; majors follow conditionally |
| EM selloff (BRL, MXN -15%, INR -10%) | hypothetical |  | no | MXN -15.0% |  | -6.82 | EM selloff; majors follow conditionally |
| EUR -10% | hypothetical |  | yes | EUR -10.0% | AUD -9.4%, CHF -8.9%, GBP -8.7% | -7.15 | euro-specific shock; others follow conditionally |
| EUR -10% | hypothetical |  | no | EUR -10.0% |  | -1.12 | euro-specific shock; others follow conditionally |
| JPY +10% | hypothetical |  | yes | JPY +10.0% | CHF +4.6%, AUD +3.9%, GBP +3.6% | 3.68 | yen +10% against USD; others follow conditionally, which mostly means broad USD weakness rather than an EM risk-off |
| JPY +10% | hypothetical |  | no | JPY +10.0% |  | 1.18 | yen +10% against USD; others follow conditionally, which mostly means broad USD weakness rather than an EM risk-off |
