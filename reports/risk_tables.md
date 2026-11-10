# Risk tables as of 2026-11-06

## Exposures by currency

| ccy | net (USD m) | net of hedges (USD m) |
|---|---|---|
| AUD | 8.56 | 1.56 |
| BRL | 21.1 | 12.31 |
| CAD | 14.87 | 4.97 |
| CHF | 9.22 | 1.9 |
| EUR | 22.39 | 10.66 |
| GBP | 17.12 | 7.16 |
| INR | 22.62 | 22.62 |
| JPY | 12.89 | 1.77 |
| MXN | 17.27 | 17.27 |
| SGD | 8.85 | 0.95 |

## VaR / ES, net exposure (USD m)

| method | ES 1d 95% | ES 1d 99% | ES 10d 95% | ES 10d 99% | ES 21d 95% | ES 21d 99% | VaR 1d 95% | VaR 1d 99% | VaR 10d 95% | VaR 10d 99% | VaR 21d 95% | VaR 21d 99% |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| historical simulation | 1.14 | 1.59 | 2.87 | 3.4 | 4 | 4.68 | 0.81 | 1.35 | 2.41 | 3.18 | 3.5 | 4.33 |
| Monte Carlo, t copula, EWMA 0.94 | 1.17 | 1.84 | 3.39 | 4.51 | 4.87 | 6.36 | 0.81 | 1.37 | 2.65 | 3.88 | 3.84 | 5.54 |
| Monte Carlo, t copula, EWMA 0.97 | 1.13 | 1.78 | 3.26 | 4.34 | 4.69 | 6.16 | 0.77 | 1.31 | 2.55 | 3.72 | 3.71 | 5.34 |
| normal, EWMA 0.94 | 1.1 | 1.42 | 3.48 | 4.5 | 5.04 | 6.51 | 0.88 | 1.24 | 2.77 | 3.92 | 4.02 | 5.69 |
| normal, EWMA 0.97 | 1.06 | 1.36 | 3.34 | 4.31 | 4.84 | 6.25 | 0.84 | 1.19 | 2.66 | 3.76 | 3.86 | 5.45 |
| normal, Ledoit-Wolf | 1.09 | 1.41 | 3.45 | 4.46 | 5.01 | 6.47 | 0.87 | 1.23 | 2.76 | 3.9 | 3.99 | 5.65 |
| normal, sample covariance | 1.1 | 1.42 | 3.47 | 4.49 | 5.04 | 6.51 | 0.88 | 1.24 | 2.77 | 3.92 | 4.02 | 5.68 |
| Student-t, EWMA 0.94 | 1.19 | 1.83 | 3.77 | 5.8 | 5.47 | 8.4 | 0.83 | 1.39 | 2.64 | 4.39 | 3.82 | 6.36 |
| Student-t, EWMA 0.97 | 1.14 | 1.76 | 3.62 | 5.56 | 5.24 | 8.05 | 0.8 | 1.33 | 2.53 | 4.21 | 3.66 | 6.1 |
| Student-t, Ledoit-Wolf | 1.18 | 1.82 | 3.75 | 5.75 | 5.43 | 8.34 | 0.83 | 1.38 | 2.62 | 4.36 | 3.79 | 6.32 |
| Student-t, sample covariance | 1.19 | 1.83 | 3.77 | 5.79 | 5.46 | 8.39 | 0.83 | 1.39 | 2.63 | 4.39 | 3.82 | 6.36 |

## VaR / ES, net of hedges exposure (USD m)

| method | ES 1d 95% | ES 1d 99% | ES 10d 95% | ES 10d 99% | ES 21d 95% | ES 21d 99% | VaR 1d 95% | VaR 1d 99% | VaR 10d 95% | VaR 10d 99% | VaR 21d 95% | VaR 21d 99% |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| historical simulation | 0.6 | 0.86 | 1.64 | 2.09 | 2.19 | 2.6 | 0.45 | 0.71 | 1.33 | 1.8 | 1.87 | 2.41 |
| Monte Carlo, t copula, EWMA 0.94 | 0.65 | 1.05 | 1.92 | 2.62 | 2.76 | 3.65 | 0.45 | 0.77 | 1.49 | 2.18 | 2.16 | 3.14 |
| Monte Carlo, t copula, EWMA 0.97 | 0.62 | 1 | 1.82 | 2.48 | 2.62 | 3.47 | 0.42 | 0.74 | 1.4 | 2.06 | 2.06 | 3.02 |
| normal, EWMA 0.94 | 0.62 | 0.8 | 1.96 | 2.53 | 2.83 | 3.66 | 0.49 | 0.7 | 1.56 | 2.21 | 2.26 | 3.2 |
| normal, EWMA 0.97 | 0.59 | 0.76 | 1.85 | 2.39 | 2.69 | 3.47 | 0.47 | 0.66 | 1.48 | 2.09 | 2.14 | 3.03 |
| normal, Ledoit-Wolf | 0.56 | 0.72 | 1.77 | 2.29 | 2.57 | 3.32 | 0.45 | 0.63 | 1.41 | 2 | 2.05 | 2.9 |
| normal, sample covariance | 0.56 | 0.73 | 1.78 | 2.3 | 2.58 | 3.34 | 0.45 | 0.64 | 1.42 | 2.01 | 2.06 | 2.91 |
| Student-t, EWMA 0.94 | 0.67 | 1 | 2.1 | 3.15 | 3.05 | 4.57 | 0.47 | 0.77 | 1.5 | 2.44 | 2.17 | 3.54 |
| Student-t, EWMA 0.97 | 0.63 | 0.94 | 1.99 | 2.99 | 2.89 | 4.33 | 0.45 | 0.73 | 1.42 | 2.31 | 2.06 | 3.35 |
| Student-t, Ledoit-Wolf | 0.6 | 0.9 | 1.91 | 2.86 | 2.77 | 4.14 | 0.43 | 0.7 | 1.36 | 2.21 | 1.97 | 3.21 |
| Student-t, sample covariance | 0.61 | 0.91 | 1.92 | 2.87 | 2.78 | 4.16 | 0.43 | 0.7 | 1.37 | 2.22 | 1.98 | 3.22 |

## Stress, net exposure

| scenario | kind | window | others propagated | largest move | largest implied moves | P&L (USD m) | note |
|---|---|---|---|---|---|---|---|
| CHF floor removed, Jan 2015 | historical | 2015-01-14 to 2015-01-16 | no | CHF +18.1% |  | 1.11 | SNB removes the EUR/CHF floor, 15 Jan 2015 |
| Brexit vote, Jun 2016 | historical | 2016-06-23 to 2016-06-27 | no | GBP -11.3% |  | -4.32 | UK referendum result, 24-27 Jun 2016 |
| Dash for dollars, Mar 2020 | historical | 2020-03-06 to 2020-03-20 | no | MXN -17.5% |  | -11.24 | dash for dollars, March 2020 |
| USD surge, Aug-Sep 2022 | historical | 2022-08-01 to 2022-09-27 | no | GBP -13.3% |  | -8.79 | Fed hiking cycle, DXY peak 27 Sep 2022 |
| Taper tantrum, May-Aug 2013 | historical | 2013-05-22 to 2013-08-30 | no | INR -16.7% |  | -6.63 | EM selloff after Bernanke's taper remarks (BRL, INR) |
| USD +10% against all | hypothetical |  | no | EUR -10.0% |  | -14.74 | every exposure currency weakens 10% against USD, no propagation needed |
| EM selloff (BRL, MXN -15%, INR -10%) | hypothetical |  | yes | MXN -15.0% | AUD -10.5%, GBP -7.1%, EUR -7.1% | -13.44 | EM selloff; majors follow conditionally |
| EM selloff (BRL, MXN -15%, INR -10%) | hypothetical |  | no | MXN -15.0% |  | -7.5 | EM selloff; majors follow conditionally |
| EUR -10% | hypothetical |  | yes | EUR -10.0% | AUD -9.3%, CHF -8.9%, GBP -8.6% | -9.71 | euro-specific shock; others follow conditionally |
| EUR -10% | hypothetical |  | no | EUR -10.0% |  | -2.13 | euro-specific shock; others follow conditionally |
| JPY +10% | hypothetical |  | yes | JPY +10.0% | CHF +4.6%, AUD +3.8%, EUR +3.6% | 4.81 | yen +10% against USD; others follow conditionally, which mostly means broad USD weakness rather than an EM risk-off |
| JPY +10% | hypothetical |  | no | JPY +10.0% |  | 1.36 | yen +10% against USD; others follow conditionally, which mostly means broad USD weakness rather than an EM risk-off |
