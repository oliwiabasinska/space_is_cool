# Space Is Cool

An interactive climate-trend explorer created for the NASA Space Apps Challenge.
The app is called **Earth System Trend Detective**.

## What the app does

- Opens with a dark world-map landing page and an interactive Paris example.
- Lets you draw a region on the map or enter its latitude and longitude bounds.
- Fetches monthly climate data from the NASA POWER API for average temperature,
  maximum temperature, and precipitation.
- Compares the available variables and initially selects the one with the
  strongest statistical evidence. You can use the variable selector to explore
  the others.
- Lets you choose the analysis period and displays monthly anomalies, an
  estimated trend per decade, statistical evidence, and a confidence interval.

The trend analysis uses a seasonal Mann-Kendall test and seasonal Sen's slope.
The evidence test accounts for autocorrelation between neighboring months.
Anomalies are calculated relative to the 1991–2020 average for each calendar
month. The data are NASA POWER MERRA-2 reanalysis, which combines a weather
model with observations; they are not direct satellite measurements.

## Run from the terminal

Open a terminal in the project folder (the folder containing `requirements.txt`),
then install the dependencies and start Streamlit:

```bash
python -m pip install -r requirements.txt
streamlit run app/app.py
```

Streamlit will print a local URL to open in your browser. Stop the app with
`Ctrl+C` in the terminal.

## AI-assisted development

AI assistants helped with product conception and implementation:

- **Claude** helped combine product features with the statistical analysis and
  NASA API integration.
- **ChatGPT** inspired the Paris example on the landing page and the UI/data
  analytics presentation.
- **Copilot (GPT-Luna)** was used in VS Code to refine individual features.
