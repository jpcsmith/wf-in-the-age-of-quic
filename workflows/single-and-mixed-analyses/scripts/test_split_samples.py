import h5py
import pytest
import numpy as np
import pandas as pd

from split_samples import Splitter


@pytest.fixture(name="labels", params=["results/open-world-dataset.hdf"])
def fixture_labels(request) -> pd.DataFrame:
    """Return a labels dataframe."""
    with h5py.File(request.param, mode="r") as h5in:
        return (pd.DataFrame.from_records(np.asarray(h5in["labels"]))
                .transform(lambda col: col.str.decode("ascii")
                           if col.name in ("url", "region", "protocol")
                           else col))


@pytest.mark.parametrize("protocol", ["quic", "tcp", "mixed"])
def test_split_monitored(labels, protocol):
    """Test properties specific to the monitored split."""
    splitter = Splitter(
        n_splits=10, n_repeats=1, protocol=protocol, validation_split=.1,
        random_state=42
    )
    exp_protocols = ["quic", "tcp"] if protocol == "mixed" else [protocol]

    for (train, val, test) in splitter.split_monitored(labels):
        assert sorted(labels.iloc[train]["protocol"].unique()) == exp_protocols
        assert sorted(labels.iloc[test]["protocol"].unique()) == exp_protocols
        assert sorted(labels.iloc[val]["protocol"].unique()) == exp_protocols


@pytest.mark.parametrize("protocol", ["quic", "tcp", "mixed"])
def test_split_unmonitored(labels, protocol):
    """Groups should be unique across splits."""
    splitter = Splitter(
        n_splits=10, n_repeats=1, protocol=protocol, validation_split=.1,
        random_state=42
    )

    groups = labels["group"].values

    for (train, val, test) in splitter.split_unmonitored(labels):
        assert np.intersect1d(groups[train], groups[val]).size == 0
        assert np.intersect1d(groups[train], groups[test]).size == 0
        assert np.intersect1d(groups[test], groups[val]).size == 0


def test_split_mixed(labels):
    """Test mixed splits."""
    splitter = Splitter(
        n_splits=10, n_repeats=1, protocol="mixed", validation_split=.1,
        random_state=42
    )

    for (train, val, test) in splitter.split(labels):
        # Each class should contain an even number of QUIC and TCP
        for idx in (train, val, test):
            counts = labels.iloc[idx].groupby(["class", "protocol"]).size()
            for class_ in labels["class"].unique():
                n_quic = counts.xs([class_, "quic"])
                n_tcp = counts.xs([class_, "tcp"])
                if class_ != -1:
                    assert n_quic == pytest.approx(n_tcp, abs=1)
                else:
                    # Will be on average the same number of QUIC and TCP samples
                    # assert n_quic == pytest.approx(n_tcp, abs=3)
                    pass


@pytest.mark.parametrize("protocol", ["quic", "tcp", "mixed"])
def test_split(labels, protocol):
    """Test general split properties."""
    splitter = Splitter(
        n_splits=10, n_repeats=1, protocol=protocol, validation_split=.1,
        random_state=42
    )
    n_samples = (len(labels) // 2 if protocol == "mixed"
                 else sum(labels["protocol"] == protocol))

    for (train, val, test) in splitter.split(labels):
        # Test that the number of splits result in the corect number of set
        # sizes
        assert len(test) / n_samples == pytest.approx(1/10, rel=1e-3)
        assert (len(train) + len(val)) / n_samples == pytest.approx(
            9/10, rel=1e-3)

        # The validation set should be .1 of the train_val set
        assert len(val) / (len(train) + len(val)) == pytest.approx(.1, rel=1e-3)
