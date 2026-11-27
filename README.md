# Will there still be a Mobi e-bike when you get there?

A UBC rider sees one e-bike at a dock five minutes away. Would a forecast help them decide whether to walk there or try another dock?

**The pilot is complete. I’d leave ML out of the first version.** Keep the nearest dock with an e-bike first. When only one remains, mark it “One e-bike left · at risk” and show the closest backup.

## What I learned

I replayed five- and ten-minute walks at 17 UBC stations, training on earlier months and testing on later ones. In the October ten-minute replay, when exactly one e-bike was showing, a model using station, bike counts and local time identified **22 empty arrivals per 100 warnings**, compared with **17** using the e-bike count alone. Both could warn on 20% of those walks at each station. E-bike departures rose during school months, but adding the school calendar barely changed warning precision. [Walk-time forecasts](notebooks/availability.ipynb) · [Station and school-year comparisons](notebooks/station_seasons.ipynb)

I tested the walking advice from eight origins around two dock pairs (UBC Bookstore / War Memorial Gym and Totem Park / Orchard Commons). At an assumed 80 metres per minute, the forecast suggested walking straight to the farther dock **1,019 times**. In about **88%** of those cases, the nearer dock still showed an e-bike at arrival.

Going straight to the backup yielded 9–10 more first-attempt pickups per 100 suggestions than trying the nearer dock. If the rider was willing to try both, starting at the nearer dock yielded about **two more eventual pickups per 100 suggestions** and saved **1.3–2.0 minutes of walking per suggestion**. [Backup-walk replay](notebooks/backup_walks.ipynb)

## Limits of the archive

I used 23 months of inventory from November 2024 through October 2026, with June 2025 missing. The archive records changes in total bikes or free docks, so an e-bike and a regular bike can trade places without triggering a report. In the initial replay, only 16% of five-minute walks had a newer station report by arrival. The remaining walks carried the last count forward.

Every pickup above is inferred from inventory. The archive has no record of whether a rider could unlock the bike. A field trial could test whether a forecast warning helps riders more than “one bike left.”

## Next product step

Build a mobile page that uses the rider’s location to list stations with their preferred bike type in walking-distance order. Show the current count and walking time beside each option. Someone walking to the last e-bike should already know where to go if it’s gone.

## Reproduce the experiments

The linked notebooks include their outputs. To rerun them locally, use Python 3.12 and curl from the repository root.

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python scripts/prepare_data.py
python scripts/prepare_trip_counts.py  # only needed for the school-year comparison
python -m jupyterlab notebooks/
```

Select the environment’s Python kernel and run a notebook from top to bottom. The preparation scripts cache the data under `data/`. Once prepared, the notebooks run offline.

Bike-share data by CityBikes contributors and available from https://data.citybik.es. [Archive and ODbL terms](https://data.citybik.es/) · [Collector](https://github.com/citybikes/analytics/blob/master/collect.py) · [Mobi rider trip data](https://www.mobibikes.ca/en/system-data) · [UBC station list](https://www.mobibikes.ca/en/ubc)
