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

## VaR / ES, basis = net (USD m)

| label | es 1d 95% | es 1d 99% | es 10d 95% | es 10d 99% | es 21d 95% | es 21d 99% | var 1d 95% | var 1d 99% | var 10d 95% | var 10d 99% | var 21d 95% | var 21d 99% |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| historical / none | 0.9 | 1.28 | 2.27 | 2.7 | 3.15 | 3.68 | 0.64 | 1 | 1.9 | 2.52 | 2.75 | 3.37 |
| monte_carlo_t / ewma_0.94 | 1.07 | 1.68 | 3.11 | 4.2 | 4.42 | 5.81 | 0.73 | 1.26 | 2.4 | 3.49 | 3.48 | 5.03 |
| monte_carlo_t / ewma_0.97 | 0.97 | 1.53 | 2.85 | 3.89 | 4.07 | 5.39 | 0.66 | 1.14 | 2.2 | 3.24 | 3.18 | 4.6 |
| parametric_normal / ewma_0.94 | 1.01 | 1.3 | 3.19 | 4.12 | 4.62 | 5.97 | 0.8 | 1.14 | 2.54 | 3.6 | 3.69 | 5.21 |
| parametric_normal / ewma_0.97 | 0.91 | 1.18 | 2.88 | 3.72 | 4.17 | 5.39 | 0.73 | 1.03 | 2.3 | 3.25 | 3.33 | 4.71 |
| parametric_normal / ledoit_wolf | 0.86 | 1.11 | 2.71 | 3.5 | 3.92 | 5.07 | 0.68 | 0.97 | 2.16 | 3.05 | 3.13 | 4.42 |
| parametric_normal / sample | 0.86 | 1.11 | 2.72 | 3.52 | 3.94 | 5.09 | 0.69 | 0.97 | 2.17 | 3.07 | 3.14 | 4.45 |
| parametric_t / ewma_0.94 | 1.09 | 1.69 | 3.46 | 5.33 | 5.02 | 7.73 | 0.76 | 1.27 | 2.41 | 4.03 | 3.5 | 5.84 |
| parametric_t / ewma_0.97 | 0.99 | 1.52 | 3.12 | 4.81 | 4.53 | 6.98 | 0.69 | 1.15 | 2.18 | 3.64 | 3.16 | 5.27 |
| parametric_t / ledoit_wolf | 0.93 | 1.43 | 2.94 | 4.52 | 4.26 | 6.56 | 0.65 | 1.08 | 2.05 | 3.42 | 2.97 | 4.95 |
| parametric_t / sample | 0.93 | 1.44 | 2.95 | 4.55 | 4.28 | 6.59 | 0.65 | 1.09 | 2.06 | 3.44 | 2.98 | 4.98 |

## VaR / ES, basis = net_of_hedges (USD m)

| label | es 1d 95% | es 1d 99% | es 10d 95% | es 10d 99% | es 21d 95% | es 21d 99% | var 1d 95% | var 1d 99% | var 10d 95% | var 10d 99% | var 21d 95% | var 21d 99% |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| historical / none | 0.58 | 0.93 | 2.1 | 2.82 | 2.56 | 3.41 | 0.39 | 0.69 | 1.5 | 2.55 | 2.01 | 2.69 |
| monte_carlo_t / ewma_0.94 | 0.87 | 1.33 | 2.54 | 3.37 | 3.6 | 4.66 | 0.62 | 1.01 | 1.98 | 2.88 | 2.85 | 4.07 |
| monte_carlo_t / ewma_0.97 | 0.72 | 1.1 | 2.11 | 2.83 | 3.01 | 3.94 | 0.51 | 0.84 | 1.64 | 2.4 | 2.39 | 3.4 |
| parametric_normal / ewma_0.94 | 0.83 | 1.08 | 2.63 | 3.4 | 3.81 | 4.93 | 0.66 | 0.94 | 2.1 | 2.97 | 3.04 | 4.3 |
| parametric_normal / ewma_0.97 | 0.68 | 0.88 | 2.16 | 2.79 | 3.13 | 4.05 | 0.55 | 0.77 | 1.72 | 2.44 | 2.5 | 3.53 |
| parametric_normal / ledoit_wolf | 0.49 | 0.63 | 1.55 | 2.01 | 2.25 | 2.91 | 0.39 | 0.55 | 1.24 | 1.75 | 1.79 | 2.54 |
| parametric_normal / sample | 0.49 | 0.64 | 1.55 | 2.01 | 2.25 | 2.91 | 0.39 | 0.55 | 1.24 | 1.75 | 1.8 | 2.54 |
| parametric_t / ewma_0.94 | 0.91 | 1.42 | 2.87 | 4.5 | 4.16 | 6.52 | 0.62 | 1.06 | 1.97 | 3.35 | 2.86 | 4.85 |
| parametric_t / ewma_0.97 | 0.75 | 1.17 | 2.36 | 3.7 | 3.42 | 5.36 | 0.51 | 0.87 | 1.62 | 2.75 | 2.35 | 3.98 |
| parametric_t / ledoit_wolf | 0.54 | 0.84 | 1.69 | 2.65 | 2.45 | 3.84 | 0.37 | 0.62 | 1.16 | 1.97 | 1.69 | 2.86 |
| parametric_t / sample | 0.54 | 0.84 | 1.7 | 2.66 | 2.46 | 3.85 | 0.37 | 0.63 | 1.17 | 1.98 | 1.69 | 2.87 |

## Stress, basis = net

| scenario | kind | window | propagated | largest_move | implied_moves | P&L (USD m) | note |
|---|---|---|---|---|---|---|---|
| chf_depeg_2015 | historical | 2015-01-14 to 2015-01-16 | no | CHF +18.1% |  | 1.05 | SNB removes the EUR/CHF floor, 15 Jan 2015 |
| brexit_2016 | historical | 2016-06-23 to 2016-06-27 | no | GBP -11.3% |  | -2.92 | UK referendum result, 24-27 Jun 2016 |
| covid_2020 | historical | 2020-03-06 to 2020-03-20 | no | MXN -17.5% |  | -8.66 | dash for dollars, March 2020 |
| usd_surge_2022 | historical | 2022-08-01 to 2022-09-27 | no | GBP -13.3% |  | -6.42 | Fed hiking cycle, DXY peak 27 Sep 2022 |
| taper_tantrum_2013 | historical | 2013-05-22 to 2013-08-30 | no | INR -16.7% |  | -6.5 | EM selloff after Bernanke's taper remarks (BRL, INR) |
| usd_up_10 | hypothetical |  | no | EUR -10.0% |  | -11.51 | every exposure currency weakens 10% against USD, no propagation needed |
| em_selloff_15 | hypothetical |  | yes | MXN -15.0% | AUD -10.8%, EUR -7.3%, GBP -7.2% | -11.02 | EM selloff; majors follow conditionally |
| em_selloff_15 | hypothetical |  | no | MXN -15.0% |  | -6.82 | EM selloff; majors follow conditionally |
| eur_down_10 | hypothetical |  | yes | EUR -10.0% | AUD -9.4%, CHF -8.9%, GBP -8.7% | -7.15 | euro-specific shock; others follow conditionally |
| eur_down_10 | hypothetical |  | no | EUR -10.0% |  | -1.12 | euro-specific shock; others follow conditionally |
| jpy_up_10 | hypothetical |  | yes | JPY +10.0% | CHF +4.6%, AUD +3.9%, GBP +3.6% | 3.68 | yen +10% against USD; others follow conditionally, which mostly means broad USD weakness rather than an EM risk-off |
| jpy_up_10 | hypothetical |  | no | JPY +10.0% |  | 1.18 | yen +10% against USD; others follow conditionally, which mostly means broad USD weakness rather than an EM risk-off |
