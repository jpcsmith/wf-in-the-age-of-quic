#!/usr/bin/env python3
"""Filter and sample traces for use in experiments."""
import math
import pandas as pd


def _maybe_sample(frame, *args, n=1, **kwargs):  # pylint: disable=invalid-name
    if len(frame) >= n:
        return frame.sample(*args, n=n, **kwargs)
    return pd.DataFrame()


def _sample_traces_by_region(
    traces: pd.DataFrame, n_traces: int, n_per_region: int, random_state
) -> pd.DataFrame:
    """Sample n_traces traces ensuring that there are at least
    n_per_region traces per region.  Return an empty dataframe
    if there are not enough traces.
    """
    assert "region" in traces
    return (traces.groupby("region", group_keys=False)
            .apply(_maybe_sample, n=n_per_region, random_state=random_state)
            .pipe(_maybe_sample, n=n_traces, random_state=random_state))


def select_traces(
    traces: pd.DataFrame, n_traces: int, n_classes: int, random_state
) -> pd.DataFrame:
    """Speicfying a non-positive n_classes will skip checking the
    minimum number of classes.
    """
    assert "url" in traces
    assert "region" in traces
    assert "protocol" in traces
    assert ("tcp" in traces["protocol"].array) or (
        b"tcp" in traces["protocol"].array)

    n_regions = traces["region"].nunique()
    n_protocols = traces["protocol"].nunique()

    assert n_traces % n_protocols == 0
    n_traces_per_protocol = n_traces // n_protocols

    traces = (traces.groupby(["protocol", "url"], group_keys=False)
              .apply(_sample_traces_by_region,
                     n_traces=n_traces_per_protocol,
                     n_per_region=math.ceil(n_traces / n_regions / n_protocols),
                     random_state=random_state))

    # Select only URLs that returned traces for both protocols
    url_counts = traces.groupby("url").size()
    valid_urls = url_counts[url_counts == n_traces].index.to_numpy()

    # Downsample to the requested number of URLs
    if n_classes > 0:
        if len(valid_urls) < n_classes:
            raise ValueError(
                f"Only {len(valid_urls)} of the requested {n_classes} classes "
                f"available after filtering to URLs with {n_traces} traces.")

        # Downsample to request number of URLs
        valid_urls = random_state.choice(valid_urls, n_classes, replace=False)
        assert len(valid_urls) == n_classes

    return traces[traces["url"].isin(valid_urls)].sort_index()
