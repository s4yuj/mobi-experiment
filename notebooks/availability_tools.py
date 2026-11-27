"""Time alignment and shared scoring for the UBC availability experiment."""

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.metrics import average_precision_score, brier_score_loss
from threadpoolctl import threadpool_limits


def covered_times(network, interval_min, history_min, arrival_min, max_gap_min):
    """Sample the clock only inside uninterrupted runs of citywide archive activity."""
    gap = network.to_series().diff().gt(pd.Timedelta(minutes=max_gap_min))
    segments = network.to_series().groupby(gap.cumsum()).agg(["first", "last"])
    windows = []
    frequency = f"{interval_min}min"
    for start, end in segments.itertuples(index=False):
        first = (start + pd.Timedelta(minutes=history_min)).ceil(frequency)
        last = (end - pd.Timedelta(minutes=arrival_min)).floor(frequency)
        if first <= last:
            windows.append(pd.DataFrame({
                "time": pd.date_range(first, last, freq=frequency), "coverage_start": start,
            }))
    return pd.concat(windows, ignore_index=True).sort_values("time")


def station_decisions(reports, grid, horizons, freshness_min):
    """Align one station's reports at decision, lag and arrival times using backward lookups."""
    reports = reports.sort_values("observed_at").reset_index(drop=True)
    report_clock = pd.DatetimeIndex(reports.observed_at)
    decisions = pd.DatetimeIndex(grid.time)
    current = report_clock.searchsorted(decisions, side="right") - 1
    age = (decisions - report_clock.take(current)).total_seconds() / 60
    # A missing rental flag is unknown. Only an explicit closure rules out a decision.
    permitted = ~reports.is_renting.eq(False).fillna(False).to_numpy(dtype=bool)
    counts = reports.ebikes.to_numpy(dtype=float, na_value=np.nan)
    eligible = (current >= 0) & (age <= freshness_min) & (counts[current] > 0) & permitted[current]
    idx = current[eligible]
    times = decisions[eligible]
    state = reports.iloc[idx].reset_index(drop=True).copy()
    state.insert(0, "time", times)
    state["age_min"] = age[eligible]
    coverage_start = pd.DatetimeIndex(grid.loc[eligible, "coverage_start"])

    for lag in (5, 15):
        as_of = times - pd.Timedelta(minutes=lag)
        past = report_clock.searchsorted(as_of, side="right") - 1
        last_report = report_clock.take(past)
        usable = ((past >= 0) & (as_of - last_report <= pd.Timedelta(minutes=freshness_min))
                  & (last_report >= coverage_start) & permitted[past])
        state[f"ebikes_{lag}m_ago"] = np.where(usable, counts[past], np.nan)
    state["reports_15"] = idx + 1 - report_clock.searchsorted(times - pd.Timedelta(minutes=15), side="right")

    for h in horizons:
        arrival = times + pd.Timedelta(minutes=h)
        at_arrival = report_clock.searchsorted(arrival, side="right") - 1
        state[f"arrival_report_{h}"] = report_clock.take(at_arrival)
        state[f"arrival_ebikes_{h}"] = counts[at_arrival]
        state[f"arrival_closed_{h}"] = ~permitted[at_arrival]
    return state


def forward_split(examples, month, max_walk):
    """Purge walks whose outcomes touch the next calendar block."""
    arrival = examples.time + pd.Timedelta(minutes=max_walk)
    end = month + pd.offsets.MonthBegin(1)
    train = examples.loc[arrival < month]
    evaluation = examples.loc[(examples.time >= month) & (arrival < end)]
    if train.empty or evaluation.empty:
        raise ValueError(f"Missing training or evaluation data for {month:%Y-%m}")
    return train, evaluation


def warning_weights(scores, rate):
    """Fractional credit at the cutoff gives tied scores the same chance of a warning."""
    scores = np.asarray(scores, dtype=float)
    if not (0 < rate <= 1 and len(scores) and np.isfinite(scores).all()):
        raise ValueError("A valid warning rate and finite scores are required.")
    budget = rate * len(scores)
    position = len(scores) - int(np.ceil(budget))
    cutoff = np.partition(scores, position)[position]
    above, tied = scores > cutoff, scores == cutoff
    return above.astype(float) + tied * (budget - above.sum()) / tied.sum()


def metrics(y, scores, rate):
    y = np.asarray(y, dtype=int)
    warnings = warning_weights(scores, rate)
    hits = np.dot(warnings, y)
    return dict(walks=len(y), empty_arrivals=int(y.sum()), empty_rate=y.mean(),
                precision=hits / warnings.sum(), recall=hits / y.sum() if y.any() else np.nan,
                average_precision=average_precision_score(y, scores) if y.any() else np.nan,
                brier=brier_score_loss(y, scores))


def predict(model, features, train, evaluation, horizon):
    y = train[f"empty_{horizon}"].astype(int)
    if model is None:
        bucket = train.ebikes.clip(upper=5)
        rates = y.groupby(bucket).agg(["sum", "count"])
        smoothed = (rates["sum"] + 10 * y.mean()) / (rates["count"] + 10)
        return evaluation.ebikes.clip(upper=5).map(smoothed).fillna(y.mean()).to_numpy(dtype=float)
    with threadpool_limits(limits=2):
        fitted = clone(model).fit(train[features], y)
        return fitted.predict_proba(evaluation[features])[:, 1]


def paired_precision_interval(y, scores, baseline, days, rate, seed=42):
    """Resample whole local days, retaining both models' original warning assignments."""
    y = np.asarray(y, dtype=int)
    w, b = warning_weights(scores, rate), warning_weights(baseline, rate)
    daily = pd.DataFrame(dict(w=w, hits=w*y, base=b, base_hits=b*y, day=days)).groupby("day").sum()
    draws = np.random.default_rng(seed).integers(len(daily), size=(1000, len(daily)))
    totals = daily.to_numpy()[draws].sum(axis=1)
    totals = totals[(totals[:, 0] > 0) & (totals[:, 2] > 0)]
    gain = totals[:, 1] / totals[:, 0] - totals[:, 3] / totals[:, 2]
    return np.quantile(gain, [.025, .975]) if len(gain) else (np.nan, np.nan)


def precision_within_stations(y, scores, stations, rate):
    """Allocate the warning budget independently at each station, then pool the warnings."""
    y = np.asarray(y, dtype=int)
    scores = np.asarray(scores, dtype=float)
    weights = np.empty(len(y))
    for positions in pd.Series(stations).groupby(stations).indices.values():
        weights[positions] = warning_weights(scores[positions], rate)
    return np.average(y, weights=weights)
