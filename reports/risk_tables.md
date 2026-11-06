# Risk tables as of 2026-10-30

## Exposures by currency

| ccy | net (USD m) | net of hedges (USD m) |
|---|---|---|
| AUD | 7.33 | -1.61 |
| BRL | 19.58 | 19.58 |
| CAD | 32.92 | -9.57 |
| CHF | 7.33 | -12.7 |
| EUR | 62.88 | -104.3 |
| GBP | 46.93 | -75.77 |
| INR | 21.6 | 21.6 |
| JPY | 11.26 | -1.96 |
| MXN | 14.09 | 12.68 |
| SGD | 7.96 | -1.9 |

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
| historical / none | 1.98 | 2.89 | 6.56 | 9.46 | 9.44 | 12.94 | 1.41 | 2.34 | 4.57 | 8.22 | 6.79 | 11.15 |
| monte_carlo_t / ewma_0.94 | 1.48 | 2.27 | 4.47 | 6.01 | 6.41 | 8.47 | 1.03 | 1.73 | 3.44 | 5.09 | 5.02 | 7.24 |
| monte_carlo_t / ewma_0.97 | 1.41 | 2.16 | 4.26 | 5.76 | 6.12 | 8.11 | 0.98 | 1.65 | 3.28 | 4.86 | 4.8 | 6.96 |
| parametric_normal / ewma_0.94 | 1.39 | 1.79 | 4.39 | 5.67 | 6.36 | 8.22 | 1.11 | 1.57 | 3.5 | 4.95 | 5.07 | 7.17 |
| parametric_normal / ewma_0.97 | 1.31 | 1.7 | 4.16 | 5.37 | 6.02 | 7.78 | 1.05 | 1.48 | 3.31 | 4.69 | 4.8 | 6.79 |
| parametric_normal / ledoit_wolf | 1.67 | 2.15 | 5.27 | 6.81 | 7.64 | 9.87 | 1.33 | 1.88 | 4.2 | 5.94 | 6.09 | 8.61 |
| parametric_normal / sample | 1.67 | 2.16 | 5.28 | 6.82 | 7.65 | 9.89 | 1.33 | 1.88 | 4.21 | 5.96 | 6.1 | 8.63 |
| parametric_t / ewma_0.94 | 1.5 | 2.31 | 4.76 | 7.29 | 6.89 | 10.57 | 1.05 | 1.75 | 3.33 | 5.53 | 4.82 | 8.02 |
| parametric_t / ewma_0.97 | 1.42 | 2.18 | 4.5 | 6.9 | 6.53 | 10.01 | 1 | 1.66 | 3.15 | 5.24 | 4.57 | 7.59 |
| parametric_t / ledoit_wolf | 1.81 | 2.77 | 5.71 | 8.76 | 8.28 | 12.69 | 1.26 | 2.1 | 4 | 6.65 | 5.79 | 9.63 |
| parametric_t / sample | 1.81 | 2.78 | 5.72 | 8.78 | 8.3 | 12.72 | 1.27 | 2.11 | 4.01 | 6.66 | 5.81 | 9.65 |

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
