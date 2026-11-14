# space_is_cool

NASA Space Apps 2026 code base: trends in NASA air-temperature data.

## Setup

```bash
pip install -r requirements.txt
```

## Run

```bash
python -m src.fetch       # download the Switzerland data into data/
python -m src.analysis    # run the trend analysis, results go to outputs/
python -m pytest          # run the tests
```

Open the `.html` files in `outputs/` in a browser to see the figures.

## Structure

```
src/
  fetch.py      download monthly 2 m air temperature from the NASA POWER API
  trends.py     anomalies, seasonal Mann-Kendall test, Sen's slope
  plotly_plots.py  Plotly figures: trend line, year-by-month heatmap, trend map
  analysis.py   runs everything for Switzerland and saves the results
tests/          tests on synthetic data with a known answer
data/           downloaded data (not in git, rebuilt by src.fetch)
outputs/        results and figures (not in git, rebuilt by src.analysis)
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
