"""Aggregate official monthly rider departures for a full UBC school year and summer."""
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from prepare_data import DATA, UBC_IDS

# Public CSVs linked by month at https://www.mobibikes.ca/en/system-data
FILES = {
    "2025-09": "1J7C5G5vNSmDkqfoUTsQ_LnQVaR-X737J",
    "2025-10": "1yohvHSSBqxxaN-cvTFfK-h5OFCBfmzIi",
    "2025-11": "1up0ysRQylyweDN1SRsaCrZesBs_gaGPc",
    "2025-12": "1oE3m-KLr_7SyvQopEGCvkMnZ_jlv-9FP",
    "2026-01": "10jnaOurjlVRfZUQQBby_pNNvhMvRE57Z",
    "2026-02": "12TDQat06FaacqWvY3oSpLYb8VexQACYC",
    "2026-03": "1juChYWJMOe6tibuMeIERMHi5KQB-AQR0",
    "2026-04": "1SgVj92gqvFwPtwY5E-M8QnN_rgiSazsU",
    "2026-05": "1Jhn1Rr3KQjALu886PcqmMY5WQYkqr9vD",
    "2026-06": "138WOueWybVMe1eY6IkrJF0R9vroKo2Ak",
    "2026-07": "18qIV_Zzb0hdf7dr3Zajwx6s8y5Brgpbq",
    "2026-08": "1RJBjRoAg7piiCbmgkVrkcnh5VSnTbYF-",
}


def count_month(path):
    trips = pd.read_csv(path, usecols=["Departure station", "Electric bike"],
                        dtype="string", encoding="utf-8-sig")
    trips["station_id"] = trips["Departure station"].str.extract(r"^\s*(\d+)\b", expand=False)
    campus = trips.loc[trips.station_id.isin(UBC_IDS)].copy()
    electric = campus["Electric bike"].str.strip().str.lower()
    if campus.empty or not electric.isin(["true", "false"]).all():
        raise ValueError(f"Check campus stations and electric flags in {path.name}")
    campus["electric"] = electric.eq("true")
    return campus.groupby("station_id").agg(departures=("electric", "size"), ebike_departures=("electric", "sum"))


def main():
    cache = DATA / "trip_counts"
    cache.mkdir(parents=True, exist_ok=True)
    for month, file_id in FILES.items():
        output = cache / f"{month}.csv"
        if output.exists():
            continue
        with TemporaryDirectory(dir=cache) as folder:
            raw = Path(folder) / "trips.csv"
            url = f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm=t"
            subprocess.run(["curl", "--fail", "--location", "--silent", "--show-error", "--retry", "2",
                            "--connect-timeout", "15", "--max-time", "120", "--output", str(raw), url], check=True)
            counts = count_month(raw).reindex(UBC_IDS, fill_value=0)
            staged = Path(folder) / "counts.csv"
            counts.to_csv(staged)
            staged.replace(output)
            print(f"{month}: {counts.departures.sum():,} campus departures", flush=True)


if __name__ == "__main__":
    main()
