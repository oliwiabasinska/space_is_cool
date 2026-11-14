# space_is_cool

NASA Space Apps 2026 code base: trends in NASA air-temperature data.

## Setup

```bash
pip install -r requirements.txt
```

## Run

```bash
python -m src.run         # fetch the Switzerland data and run the analysis
python -m pytest          # run the tests
```

`src.run` saves the NASA data to `data/` and the computed results to `outputs/`.
It does no plotting.

## Structure

```
src/
  fetch.py      data fetching: monthly 2 m air temperature from the NASA POWER API
  analysis.py   statistics: anomalies, seasonal Mann-Kendall test, Sen's slope
  run.py        fetch, then analyse, then save the results
  plot.py       matplotlib plot of the annual maximum temperature
tests/          tests on synthetic data with a known answer
data/           downloaded data (not in git, rebuilt by src.run)
outputs/        analysis results (not in git, rebuilt by src.run)
```

## Data and method

- **Data:** NASA POWER monthly API, variable `T2M` (temperature at 2 metres), from
  the MERRA-2 reanalysis. This is a model that assimilates observations, not a
  direct satellite measurement. It starts in January 1981 and each grid cell is
  0.5 degrees of latitude by 0.625 degrees of longitude (about 50 km).
- **Anomalies:** each month minus the 1991–2020 average for that calendar month.
- **Trend:** seasonal Mann-Kendall test for significance and seasonal Sen's slope
  for the size, in °C per decade with a 95 % confidence interval. Significance
  uses the variant that allows for correlation between months.
