"""Download Vancouver CityBikes monthly archives and extract the Mobi UBC stations."""

import hashlib
import json
import re
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

INDEX = "https://data.citybik.es/dumps/by-network/"
DATA = Path(__file__).resolve().parents[1] / "data"
RAW = DATA / "raw"
PROCESSED = DATA / "processed"
MANIFEST = PROCESSED / "sources.json"

# Current locations listed at https://www.mobibikes.ca/en/ubc, matched by Mobi ID.
UBC_IDS = [
    "2112", "2114", "2116", "2117", "2127", "2131", "2132", "2134", "2136",
    "2142", "2143", "2154", "2156", "2157", "2167", "2252", "2255",
]
CURL = ["curl", "--fail", "--location", "--silent", "--show-error", "--retry", "2",
        "--connect-timeout", "15", "--max-time", "120"]


def listings():
    def entries(url):
        return json.loads(subprocess.check_output([*CURL, url]))

    sources = []
    for year in entries(INDEX):
        if year["type"] != "directory" or not re.fullmatch(r"\d{4}", year["name"]):
            continue
        url = INDEX + year["name"] + "/"
        for item in entries(url):
            if re.fullmatch(year["name"] + r"\d{2}-mobibikes-stats\.parquet", item["name"]):
                sources.append({"name": item["name"], "url": url + item["name"],
                                "bytes": item["size"], "modified": item["mtime"]})
    if not sources:
        raise RuntimeError(f"No monthly Mobi files listed at {INDEX}")
    return sorted(sources, key=lambda source: source["name"])


def cache_archive(source, previous):
    path = RAW / source["name"]
    if path.exists() and path.stat().st_size == source["bytes"]:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if not previous or (digest == previous["sha256"] and source["modified"] == previous["modified"]):
            return path, digest
    with TemporaryDirectory(dir=RAW) as tmp:
        download = Path(tmp) / path.name
        subprocess.run([*CURL, "--output", str(download), source["url"]], check=True)
        if download.stat().st_size != source["bytes"]:
            raise ValueError(f"Incomplete archive: {source['url']}")
        digest = hashlib.sha256(download.read_bytes()).hexdigest()
        download.replace(path)
    return path, digest


def campus_changes(path):
    frame = pd.read_parquet(
        path, columns=["nuid", "name", "timestamp", "latitude", "longitude", "bikes", "free", "extra"],
        filters=[("nuid", "in", UBC_IDS)],
    ).rename(columns={"nuid": "station_id", "name": "station_name", "timestamp": "observed_at",
                      "bikes": "total_bikes", "free": "free_docks"})
    # A missing type count is unknown, even when the source issued a total.
    metadata = pd.DataFrame(
        [json.loads(raw) if raw else {} for raw in frame.pop("extra")], index=frame.index,
    )
    for key, name in [("ebikes", "ebikes"), ("normal_bikes", "classic_bikes"), ("slots", "capacity"),
                      ("renting", "is_renting"), ("returning", "is_returning")]:
        dtype = "boolean" if key in ("renting", "returning") else "Int32"
        frame[name] = metadata.reindex(columns=[key])[key].astype(dtype)
    frame[["total_bikes", "free_docks"]] = frame[["total_bikes", "free_docks"]].astype("Int32")
    frame["station_id"] = frame["station_id"].astype("string")
    frame["observed_at"] = pd.to_datetime(frame["observed_at"], utc=True).astype("datetime64[ns, UTC]")
    return frame


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    previous = json.loads(MANIFEST.read_text())["archives"] if MANIFEST.exists() else []
    previous = {source["name"]: source for source in previous}
    sources = listings()
    campuses, network_times = [], []
    for source in sources:
        path, source["sha256"] = cache_archive(source, previous.get(source["name"]))
        campus = campus_changes(path)
        # Each timestamp is evidence of at least one change somewhere in Vancouver.
        observed = pd.read_parquet(path, columns=["timestamp"])["timestamp"].drop_duplicates()
        campuses.append(campus)
        network_times.append(pd.to_datetime(observed, utc=True).astype("datetime64[ns, UTC]"))
        source.update(ubc_rows=len(campus), ebikes_known=int(campus["ebikes"].count()))

    inventory = pd.concat(campuses, ignore_index=True).sort_values(["station_id", "observed_at"])
    if inventory.duplicated(["station_id", "observed_at"]).any() or inventory["observed_at"].isna().any():
        raise ValueError("The archive contains ambiguous campus observation times")
    network = pd.concat(network_times, ignore_index=True).drop_duplicates().sort_values().rename("observed_at")
    if not inventory["observed_at"].isin(network).all():
        raise ValueError("Campus timestamps are missing from the network observation index")

    manifest = {"attribution": "Bike-share data by CityBikes contributors and available from https://data.citybik.es.",
                "license": "ODbL-1.0", "terms": "https://data.citybik.es/",
                "station_list": "https://www.mobibikes.ca/en/ubc", "archives": sources}
    with TemporaryDirectory(dir=PROCESSED) as tmp:
        stage = Path(tmp)
        inventory.to_parquet(stage / "ubc_inventory.parquet", index=False)
        network.to_frame().to_parquet(stage / "network_observations.parquet", index=False)
        (stage / MANIFEST.name).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        for name in ("ubc_inventory.parquet", "network_observations.parquet", MANIFEST.name):
            (stage / name).replace(PROCESSED / name)
    print(f"{len(sources)} monthly archives, {len(inventory):,} UBC changes at "
          f"{inventory['station_id'].nunique()} stations, {int(inventory['ebikes'].count()):,} known e-bike counts")


if __name__ == "__main__":
    main()
