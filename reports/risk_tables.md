# Risk tables as of 2026-10-30

## Exposures by currency

| ccy | net (USD m) | net of hedges (USD m) |
|---|---|---|
| AUD | 7.33 | 1.18 |
| BRL | 19.58 | 6.1 |
| CAD | 32.92 | 4.78 |
| CHF | 7.33 | -1.8 |
| EUR | 62.88 | -13.84 |
| GBP | 46.93 | -8.63 |
| INR | 21.6 | 7.92 |
| JPY | 11.26 | 2.59 |
| MXN | 14.09 | 2.42 |
| SGD | 7.96 | 1.26 |

## VaR / ES, basis = net (USD m)

| label | es 1d 95% | es 1d 99% | es 10d 95% | es 10d 99% | es 21d 95% | es 21d 99% | var 1d 95% | var 1d 99% | var 10d 95% | var 10d 99% | var 21d 95% | var 21d 99% |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| historical / none | 1.74 | 2.37 | 4.19 | 5.06 | 6.02 | 6.83 | 1.23 | 1.99 | 3.55 | 4.69 | 5.21 | 6.47 |
| monte_carlo_t / ewma_0.94 | 1.56 | 2.44 | 4.59 | 6.3 | 6.58 | 8.76 | 1.06 | 1.82 | 3.52 | 5.19 | 5.18 | 7.45 |
| monte_carlo_t / ewma_0.97 | 1.53 | 2.37 | 4.53 | 6.23 | 6.48 | 8.65 | 1.05 | 1.78 | 3.48 | 5.19 | 5.08 | 7.34 |
| parametric_normal / ewma_0.94 | 1.46 | 1.89 | 4.62 | 5.96 | 6.69 | 8.64 | 1.16 | 1.65 | 3.68 | 5.21 | 5.33 | 7.54 |
| parametric_normal / ewma_0.97 | 1.43 | 1.84 | 4.51 | 5.83 | 6.53 | 8.44 | 1.14 | 1.61 | 3.6 | 5.09 | 5.21 | 7.37 |
| parametric_normal / ledoit_wolf | 1.69 | 2.18 | 5.33 | 6.89 | 7.73 | 9.98 | 1.34 | 1.9 | 4.25 | 6.01 | 6.16 | 8.71 |
| parametric_normal / sample | 1.69 | 2.19 | 5.36 | 6.92 | 7.76 | 10.03 | 1.35 | 1.91 | 4.27 | 6.04 | 6.19 | 8.76 |
| parametric_t / ewma_0.94 | 1.59 | 2.45 | 5.01 | 7.75 | 7.27 | 11.23 | 1.1 | 1.85 | 3.49 | 5.84 | 5.05 | 8.46 |
| parametric_t / ewma_0.97 | 1.55 | 2.39 | 4.9 | 7.57 | 7.1 | 10.97 | 1.08 | 1.8 | 3.41 | 5.7 | 4.94 | 8.27 |
| parametric_t / ledoit_wolf | 1.83 | 2.83 | 5.79 | 8.95 | 8.39 | 12.97 | 1.27 | 2.13 | 4.03 | 6.75 | 5.84 | 9.77 |
| parametric_t / sample | 1.84 | 2.84 | 5.82 | 9 | 8.43 | 13.04 | 1.28 | 2.14 | 4.05 | 6.78 | 5.87 | 9.82 |

## VaR / ES, basis = net_of_hedges (USD m)

| label | es 1d 95% | es 1d 99% | es 10d 95% | es 10d 99% | es 21d 95% | es 21d 99% | var 1d 95% | var 1d 99% | var 10d 95% | var 10d 99% | var 21d 95% | var 21d 99% |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| historical / none | 0.2 | 0.3 | 0.69 | 0.98 | 0.9 | 1.37 | 0.13 | 0.24 | 0.45 | 0.86 | 0.65 | 1.06 |
| monte_carlo_t / ewma_0.94 | 0.29 | 0.44 | 0.84 | 1.12 | 1.2 | 1.56 | 0.2 | 0.33 | 0.66 | 0.96 | 0.95 | 1.36 |
| monte_carlo_t / ewma_0.97 | 0.24 | 0.37 | 0.71 | 0.95 | 1.01 | 1.33 | 0.17 | 0.28 | 0.55 | 0.81 | 0.79 | 1.14 |
| parametric_normal / ewma_0.94 | 0.27 | 0.36 | 0.87 | 1.12 | 1.26 | 1.63 | 0.22 | 0.31 | 0.69 | 0.98 | 1 | 1.42 |
| parametric_normal / ewma_0.97 | 0.23 | 0.29 | 0.72 | 0.93 | 1.04 | 1.34 | 0.18 | 0.26 | 0.57 | 0.81 | 0.83 | 1.17 |
| parametric_normal / ledoit_wolf | 0.17 | 0.22 | 0.54 | 0.7 | 0.78 | 1.01 | 0.14 | 0.19 | 0.43 | 0.61 | 0.62 | 0.88 |
| parametric_normal / sample | 0.17 | 0.22 | 0.54 | 0.7 | 0.78 | 1.01 | 0.14 | 0.19 | 0.43 | 0.61 | 0.62 | 0.88 |
| parametric_t / ewma_0.94 | 0.3 | 0.47 | 0.95 | 1.47 | 1.37 | 2.14 | 0.21 | 0.35 | 0.65 | 1.1 | 0.95 | 1.6 |
| parametric_t / ewma_0.97 | 0.25 | 0.39 | 0.78 | 1.22 | 1.13 | 1.77 | 0.17 | 0.29 | 0.54 | 0.91 | 0.78 | 1.32 |
| parametric_t / ledoit_wolf | 0.19 | 0.29 | 0.59 | 0.92 | 0.85 | 1.33 | 0.13 | 0.22 | 0.41 | 0.69 | 0.59 | 0.99 |
| parametric_t / sample | 0.19 | 0.29 | 0.59 | 0.91 | 0.85 | 1.32 | 0.13 | 0.22 | 0.4 | 0.68 | 0.59 | 0.99 |

## Stress, basis = net

| scenario | kind | window | propagated | largest_move | P&L (USD m) | note |
|---|---|---|---|---|---|---|
| chf_depeg_2015 | historical | 2015-01-14 to 2015-01-16 | no | CHF +18.1% | -0.49 | SNB removes the EUR/CHF floor, 15 Jan 2015 |
| brexit_2016 | historical | 2016-06-23 to 2016-06-27 | no | GBP -11.3% | -9 | UK referendum result, 24-27 Jun 2016 |
| covid_2020 | historical | 2020-03-06 to 2020-03-20 | no | MXN -17.5% | -16.59 | dash for dollars, March 2020 |
| usd_surge_2022 | historical | 2022-08-01 to 2022-09-27 | no | GBP -13.3% | -15.8 | Fed hiking cycle, DXY peak 27 Sep 2022 |
| taper_tantrum_2013 | historical | 2013-05-22 to 2013-08-30 | no | INR -16.7% | -4.58 | EM selloff after Bernanke's taper remarks (BRL, INR) |
| usd_up_10 | hypothetical |  | no | EUR -10.0% | -22.07 | every exposure currency weakens 10% against USD, no propagation needed |
| em_selloff_15 | hypothetical |  | yes | MXN -15.0% | -13.83 | EM selloff; majors follow conditionally |
| em_selloff_15 | hypothetical |  | no | MXN -15.0% | -6.75 | EM selloff; majors follow conditionally |
| eur_down_10 | hypothetical |  | yes | EUR -10.0% | -16.48 | euro-specific shock; others follow conditionally |
| eur_down_10 | hypothetical |  | no | EUR -10.0% | -5.98 | euro-specific shock; others follow conditionally |
| jpy_up_10 | hypothetical |  | yes | BRL +11.0% | 10.26 | yen safe-haven rally; others follow conditionally |
| jpy_up_10 | hypothetical |  | no | JPY +10.0% | 1.18 | yen safe-haven rally; others follow conditionally |
