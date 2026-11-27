# Mobi e-bike availability at UBC

If a station shows an e-bike now, how likely is it to be empty after a five- or ten-minute walk? This offline pilot uses archived inventory from 17 UBC stations, including Brock Commons.

## Run the experiment

Use Python 3.12 and curl. From the project root, run

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python scripts/prepare_data.py
python -m jupyterlab notebooks/availability.ipynb
```

Select the project Python kernel and run all cells. The preparation script downloads the monthly Vancouver files to `data/raw/` and reuses its cache on later runs. It writes campus inventory changes, a citywide timestamp index for detecting archive gaps, and a source manifest with URLs and checksums to `data/processed/`. Once these files exist, the notebook runs offline.

## First experiment

The pilot uses 23 available monthly files from November 2024 through October 2026. June 2025 is missing. Each example represents a potential walk starting when a station's most recent report was at most ten minutes old and showed at least one e-bike. The outcome is reported availability at arrival. Quiet stations can carry forward their last known counts. Riders' unlock attempts are outside the archive.

The notebook compares a count-only baseline, two logistic regressions and a shallow boosted tree. It selects a model on July–September 2026, then measures it on October at the same warning budget of 20 warnings per 100 eligible walks. Logistic regression using station, time and inventory earned the selection at both horizons. In October it identified 13.4 empty arrivals per 100 warnings at five minutes and 21.0 at ten minutes. The count-only baseline identified 10.0 and 16.5 respectively.

## Data sources

Bike-share data by CityBikes contributors and available from https://data.citybik.es. The archive records changes in total bikes or free docks, so some exchanges between e-bikes and regular bikes are invisible. [Archive and ODbL terms](https://data.citybik.es/) · [CityBikes collector](https://github.com/citybikes/analytics/blob/master/collect.py) · [Mobi's UBC station list](https://www.mobibikes.ca/en/ubc)
