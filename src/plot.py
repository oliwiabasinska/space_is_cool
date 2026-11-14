from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from fetch import get_series

SWITZERLAND = (45.8, 47.8, 5.9, 10.5)
FIRST_YEAR = 1981
OUTPUT_FILE = Path(__file__).resolve().parent.parent / "max_temp.png"

if __name__ == "__main__":
    this_year = pd.Timestamp.now().year
    maximum = get_series(*SWITZERLAND, FIRST_YEAR, this_year, how="max")

    if maximum.empty:
        raise ValueError("No maximum temperature measurements are available to plot.")

    annual_maximum = maximum.resample("YS").mean()
    elapsed_years = (annual_maximum.index - maximum.index[0]).days / 365.2425
    plt.plot(elapsed_years, annual_maximum.values, marker="o")
    plt.xlabel("Time since first measurement (years)")
    plt.ylabel("Annual average of monthly maximum temperatures (°C)")
    plt.title("Annual average maximum temperature in Switzerland")
    plt.tight_layout()
    plt.savefig(OUTPUT_FILE, dpi=150)
    plt.close()

    print(f"Plot saved to {OUTPUT_FILE}")
