# Risk tables as of 2026-10-30

## Exposures by currency

| ccy | net (USD m) | net of hedges (USD m) |
|---|---|---|
| AUD | 7.17 | -2.12 |
| BRL | 20.09 | 20.09 |
| CAD | 33.65 | -8.22 |
| CHF | 7.29 | -12.86 |
| EUR | 63.92 | -104.23 |
| GBP | 48.04 | -73.77 |
| INR | 21.18 | 21.18 |
| JPY | 11.18 | -2.04 |
| MXN | 14.42 | 13.73 |
| SGD | 7.93 | -2.01 |

## VaR / ES, basis = net (USD m)

| label | es 1d 95% | es 1d 99% | es 10d 95% | es 10d 99% | es 21d 95% | es 21d 99% | var 1d 95% | var 1d 99% | var 10d 95% | var 10d 99% | var 21d 95% | var 21d 99% |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| historical / none | 1.76 | 2.41 | 4.26 | 5.14 | 6.1 | 6.93 | 1.24 | 2.01 | 3.61 | 4.75 | 5.28 | 6.55 |
| monte_carlo_t / ewma_0.94 | 1.59 | 2.48 | 4.68 | 6.41 | 6.7 | 8.92 | 1.08 | 1.86 | 3.59 | 5.28 | 5.27 | 7.58 |
| monte_carlo_t / ewma_0.97 | 1.55 | 2.41 | 4.61 | 6.34 | 6.59 | 8.79 | 1.06 | 1.81 | 3.54 | 5.28 | 5.17 | 7.46 |
| parametric_normal / ewma_0.94 | 1.49 | 1.92 | 4.7 | 6.07 | 6.81 | 8.8 | 1.19 | 1.68 | 3.75 | 5.3 | 5.43 | 7.68 |
| parametric_normal / ewma_0.97 | 1.45 | 1.87 | 4.59 | 5.93 | 6.65 | 8.59 | 1.16 | 1.64 | 3.66 | 5.17 | 5.3 | 7.5 |
| parametric_normal / ledoit_wolf | 1.71 | 2.21 | 5.41 | 6.99 | 7.84 | 10.14 | 1.36 | 1.93 | 4.32 | 6.1 | 6.25 | 8.85 |
| parametric_normal / sample | 1.72 | 2.22 | 5.44 | 7.03 | 7.88 | 10.19 | 1.37 | 1.94 | 4.34 | 6.14 | 6.29 | 8.89 |
| parametric_t / ewma_0.94 | 1.61 | 2.5 | 5.11 | 7.89 | 7.4 | 11.43 | 1.12 | 1.88 | 3.55 | 5.95 | 5.15 | 8.62 |
| parametric_t / ewma_0.97 | 1.58 | 2.43 | 4.98 | 7.7 | 7.22 | 11.16 | 1.1 | 1.84 | 3.47 | 5.8 | 5.02 | 8.41 |
| parametric_t / ledoit_wolf | 1.86 | 2.87 | 5.88 | 9.08 | 8.52 | 13.17 | 1.29 | 2.17 | 4.09 | 6.85 | 5.93 | 9.92 |
| parametric_t / sample | 1.87 | 2.89 | 5.91 | 9.13 | 8.56 | 13.23 | 1.3 | 2.18 | 4.11 | 6.88 | 5.96 | 9.97 |

## VaR / ES, basis = net_of_hedges (USD m)

| label | es 1d 95% | es 1d 99% | es 10d 95% | es 10d 99% | es 21d 95% | es 21d 99% | var 1d 95% | var 1d 99% | var 10d 95% | var 10d 99% | var 21d 95% | var 21d 99% |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| historical / none | 1.95 | 2.85 | 6.5 | 9.38 | 9.35 | 12.83 | 1.38 | 2.35 | 4.53 | 8.06 | 6.73 | 11.09 |
| monte_carlo_t / ewma_0.94 | 1.47 | 2.25 | 4.44 | 5.97 | 6.36 | 8.41 | 1.02 | 1.71 | 3.42 | 5.06 | 4.98 | 7.2 |
| monte_carlo_t / ewma_0.97 | 1.39 | 2.14 | 4.22 | 5.69 | 6.06 | 8.03 | 0.97 | 1.64 | 3.24 | 4.81 | 4.75 | 6.89 |
| parametric_normal / ewma_0.94 | 1.38 | 1.78 | 4.37 | 5.64 | 6.33 | 8.17 | 1.1 | 1.56 | 3.48 | 4.92 | 5.04 | 7.14 |
| parametric_normal / ewma_0.97 | 1.3 | 1.68 | 4.12 | 5.32 | 5.97 | 7.71 | 1.04 | 1.47 | 3.28 | 4.64 | 4.76 | 6.73 |
| parametric_normal / ledoit_wolf | 1.65 | 2.13 | 5.2 | 6.72 | 7.54 | 9.74 | 1.31 | 1.86 | 4.15 | 5.87 | 6.01 | 8.5 |
| parametric_normal / sample | 1.65 | 2.13 | 5.21 | 6.74 | 7.56 | 9.76 | 1.31 | 1.86 | 4.16 | 5.88 | 6.02 | 8.52 |
| parametric_t / ewma_0.94 | 1.5 | 2.3 | 4.73 | 7.26 | 6.86 | 10.52 | 1.05 | 1.74 | 3.31 | 5.51 | 4.8 | 7.98 |
| parametric_t / ewma_0.97 | 1.41 | 2.17 | 4.46 | 6.85 | 6.47 | 9.92 | 0.99 | 1.64 | 3.12 | 5.19 | 4.52 | 7.53 |
| parametric_t / ledoit_wolf | 1.78 | 2.74 | 5.64 | 8.65 | 8.17 | 12.54 | 1.25 | 2.08 | 3.95 | 6.56 | 5.72 | 9.51 |
| parametric_t / sample | 1.79 | 2.74 | 5.65 | 8.67 | 8.19 | 12.57 | 1.25 | 2.08 | 3.95 | 6.58 | 5.73 | 9.53 |

## Stress, basis = net

| scenario | kind | window | propagated | largest_move | P&L (USD m) | note |
|---|---|---|---|---|---|---|
| chf_depeg_2015 | historical | 2015-01-14 to 2015-01-16 | no | CHF +18.1% | -0.54 | SNB removes the EUR/CHF floor, 15 Jan 2015 |
| brexit_2016 | historical | 2016-06-23 to 2016-06-27 | no | GBP -11.3% | -9.18 | UK referendum result, 24-27 Jun 2016 |
| covid_2020 | historical | 2020-03-06 to 2020-03-20 | no | MXN -17.5% | -16.86 | dash for dollars, March 2020 |
| usd_surge_2022 | historical | 2022-08-01 to 2022-09-27 | no | GBP -13.3% | -16.03 | Fed hiking cycle, DXY peak 27 Sep 2022 |
| taper_tantrum_2013 | historical | 2013-05-22 to 2013-08-30 | no | INR -16.7% | -4.56 | EM selloff after Bernanke's taper remarks (BRL, INR) |
| usd_up_10 | hypothetical |  | no | EUR -10.0% | -22.35 | every exposure currency weakens 10% against USD, no propagation needed |
| em_selloff_15 | hypothetical |  | yes | MXN -15.0% | -14.02 | EM selloff; majors follow conditionally |
| em_selloff_15 | hypothetical |  | no | MXN -15.0% | -6.82 | EM selloff; majors follow conditionally |
| eur_down_10 | hypothetical |  | yes | EUR -10.0% | -16.75 | euro-specific shock; others follow conditionally |
| eur_down_10 | hypothetical |  | no | EUR -10.0% | -6.08 | euro-specific shock; others follow conditionally |
| jpy_up_10 | hypothetical |  | yes | BRL +11.0% | 10.42 | yen safe-haven rally; others follow conditionally |
| jpy_up_10 | hypothetical |  | no | JPY +10.0% | 1.18 | yen safe-haven rally; others follow conditionally |
