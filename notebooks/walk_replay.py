"""Point-in-time lookups and paired summaries for the two-dock replay."""
import numpy as np
import pandas as pd


def observed_drops(reports, network, grid):
    """Count published decreases from comparable reports in two trailing time windows."""
    reports = reports.sort_values("observed_at")
    t = pd.DatetimeIndex(reports.observed_at)
    count = reports.ebikes.where(reports.is_renting.ne(False).fillna(True))
    delta = count.diff()
    segment = network.reindex(t).to_numpy()
    fresh = reports.observed_at.diff().le(pd.Timedelta(minutes=15)).to_numpy()
    valid = delta.notna().to_numpy() & fresh & np.r_[False, segment[1:] == segment[:-1]]
    drops = (-delta).clip(lower=0).fillna(0).to_numpy(dtype=float)
    sums = np.r_[0.0, np.cumsum(np.where(valid, drops, 0))]
    pairs = np.r_[0, np.cumsum(valid)]
    result = {}
    for tag, end_min, start_min in (("recent", 0, 15), ("prior", 15, 30)):
        left = t.searchsorted(grid - pd.Timedelta(minutes=start_min), side="right")
        right = t.searchsorted(grid - pd.Timedelta(minutes=end_min), side="right")
        result[tag] = sums[right] - sums[left]
        result[tag + "_seen"] = pairs[right] > pairs[left]
    return pd.DataFrame(result, index=grid)


def empty_at(reports, arrivals):
    """Latest archived state by the exact ETA; explicit closures count as empty."""
    times = pd.DatetimeIndex(reports.observed_at)
    i = times.searchsorted(arrivals, side="right") - 1
    counts = reports.ebikes.to_numpy(dtype=float, na_value=np.nan)[i]
    closed = reports.is_renting.eq(False).fillna(False).to_numpy(dtype=bool)[i]
    known = (i >= 0) & (np.isfinite(counts) | closed)
    y = np.where(known, (counts == 0) | closed, np.nan)
    return y, times.take(i)


def risk_at(frame, suffix, minutes, anchors):
    """Linear interpolation between out-of-time risk forecasts at adjacent horizons."""
    if minutes < anchors[0] or minutes > anchors[-1]:
        raise ValueError(f"ETA outside trained horizons: {minutes}")
    upper = max(1, np.searchsorted(anchors, minutes, side="left"))
    lo, hi = anchors[upper-1:upper+1]
    share = (minutes - lo) / (hi - lo)
    return frame[f"risk_{lo}_{suffix}"] * (1 - share) + frame[f"risk_{hi}_{suffix}"] * share


def backup_metrics(frame):
    """All arrival outcomes are paired, including walks on which both docks were empty."""
    suggested = frame.loc[frame.redirect]
    n = len(suggested)
    if n == 0:
        return pd.Series({"opportunities": len(frame), "suggestions": 0})
    near, far = suggested.near_empty, suggested.far_empty
    saved = near & ~far
    spoiled = ~near & far
    extra = suggested.far_min - suggested.near_min
    recovered = ~near | ~suggested.recovery_empty
    return pd.Series({
        "opportunities": len(frame), "suggestions": n, "suggested_pct": 100*n/len(frame),
        "saved_per_100": 100*saved.mean(), "spoiled_per_100": 100*spoiled.mean(),
        "near_had_bike_per_100": 100*(~near).mean(), "both_empty_per_100": 100*(near & far).mean(),
        "net_saved_per_100": 100*(saved.sum()-spoiled.sum())/n,
        "net_saved_per_100_opportunities": 100*(saved.sum()-spoiled.sum())/len(frame),
        "extra_walk_min_per_100": 100*extra.mean(),
        "net_pickups_vs_fallback_per_100": 100*((~far).sum()-recovered.sum())/n,
        "extra_min_vs_fallback_per_100": 100*(extra-near*suggested.link_min).mean(),
    })


def weekly_ratio_ci(weeks, numerator, denominator, scale=100, second=None):
    """Resample weeks jointly, recalculating one ratio or a paired difference of ratios."""
    frame = pd.DataFrame({"week": np.asarray(weeks), "a": np.asarray(numerator),
                          "b": np.asarray(denominator)})
    if second is not None:
        frame["c"], frame["d"] = map(np.asarray, second)
    totals = frame.groupby("week").sum().to_numpy()
    def statistic(x):
        result = x[..., 0] / x[..., 1]
        if second is not None:
            result = result - x[..., 2] / x[..., 3]
        return scale * result

    denominators = totals[:, [1]] if second is None else totals[:, [1, 3]]
    active_weeks = (denominators > 0).sum(axis=0)
    if active_weeks.min() == 0:
        return np.nan, np.nan, np.nan
    estimate = statistic(totals.sum(axis=0))
    if active_weeks.min() < 5:
        return estimate, np.nan, np.nan
    rng = np.random.default_rng(42)
    sample = totals[rng.integers(len(totals), size=(2000, len(totals)))].sum(axis=1)
    sample = sample[sample[:, 1] > 0]
    if second is not None:
        sample = sample[sample[:, 3] > 0]
    return (estimate, *np.quantile(statistic(sample), [.025, .975]))
