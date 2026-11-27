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

## Reading the experiment

The pilot uses 23 available monthly files from November 2024 through October 2026. June 2025 is missing. Each example represents a potential walk starting when a station's most recent report was at most ten minutes old and showed at least one e-bike. The outcome is reported availability at arrival. Quiet stations can carry forward their last known counts. Riders' unlock attempts are outside the archive.

The [executed notebook](notebooks/availability.ipynb) starts with a real Brock Commons inventory change and shows how it becomes a labeled walk. It compares raw counts and station identity with local time, five- and fifteen-minute inventory changes, report activity, and time spent at the current count. Each comparison uses forward validation on July, August and September 2026. Compact result tables follow each experiment.

The notebook makes two selections. One asks which walks to flag across campus. The other asks when to warn a rider who repeatedly sees one bike at the same hub. Both use a budget of 20 warnings per 100 eligible walks. October was already examined during the original pilot, so its results are a retrospective benchmark.

At Brock Commons, 120 of 521 one-bike walks in October had an empty ten-minute arrival. Per 100 warnings, the count-only rule identified 23.0 empty arrivals, logistic regression with local time identified 36.5, and a shallow tree using current counts, station and local time identified 38.5. The notebook shows the uncertainty on those gains and how results change across all 17 hubs.

The [station and school-year experiment](notebooks/station_seasons.ipynb) ranks all 17 docks by observed e-bike movement, tests calendar features across eight months, and checks seasonal demand with one full year of rider departures. Run `python scripts/prepare_trip_counts.py` before rerunning this notebook. Only monthly station totals are cached. The [official Mobi trip files](https://www.mobibikes.ca/en/system-data) are the source for rider departures.

## Data sources

Bike-share data by CityBikes contributors and available from https://data.citybik.es. The archive records changes in total bikes or free docks, so some exchanges between e-bikes and regular bikes are invisible. [Archive and ODbL terms](https://data.citybik.es/) · [CityBikes collector](https://github.com/citybikes/analytics/blob/master/collect.py) · [Mobi's UBC station list](https://www.mobibikes.ca/en/ubc)
