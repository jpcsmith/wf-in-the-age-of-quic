#!/usr/bin/env python3
"""Usage: split-samples [options] INFILE [OUTFILE]

Split the traces in INFILE into training, testing, and validation
datasets for the background experiment.  This would normally be done at
experiment time, however VarCNN requires the same exact dataset for the
time and sizes variants so that they can be combined later. This
approach ensures they are identical.

OUTFILE is a json stream with each line containing a dict with the keys
"train", "test", "val", and "train-val" the latter which contains a
combined permutationof "train" and "val".

Options:
    --n-splits k
        Split the data into k folds [default: 10]

    --n-repeats n
        Repeat the k-folds n times [default: 2]

    --validation-split frac
        Set aside frac fraction of the training set for validation
        [default: 0.1].

    --protocol proto
        Return samples for proto where proto can be one of "quic",
        "tcp", or "mixed". Regardless of the protoocl, the same
        number of samples are returned [default: mixed]

    --seed value
        Seed the random number generation with value [default: 16248].
"""
import json
import time
import logging
from collections import namedtuple
from typing import Iterator, IO

import h5py
import doceasy
import pandas as pd
import numpy as np
from numpy.random import RandomState
import sklearn
from sklearn.model_selection import (
    GroupShuffleSplit, RepeatedStratifiedKFold, train_test_split
)

Split = namedtuple("Split", ["train", "val", "test"])
_LOGGER = logging.getLogger("be-split-traces")


def decode_column(
    column: pd.Series, names=("url", "region", "protocol"),
    encoding: str = "ascii"
):
    """Decode the column if it has one of the names in column_names.
    """
    if column.name in names:
        return column.str.decode(encoding)
    return column


class _IndexTransformer:
    def __init__(self, mask):
        self.mask = mask

    def fit_transform(self, *args):
        """Transform the arguments with the specified mask."""
        if len(args) == 1:
            return args[0][self.mask]
        return tuple([arg[self.mask] for arg in args])

    def inverse_transform(self, *seq_of_indices):
        """Convert the indices back to the original space."""
        original_indices = np.arange(len(self.mask))[self.mask]

        if len(seq_of_indices) == 1:
            return original_indices[seq_of_indices[0]]
        return tuple([original_indices[idx] for idx in seq_of_indices])


class Splitter:
    """Split a dataset in train and test instances.
    """
    def __init__(
        self, n_splits: int = 10, n_repeats: int = 1,
        validation_split: float = 0.1,
        protocol: str = "mixed", random_state: np.random.RandomState = None
    ):
        assert protocol in ("quic", "tcp", "mixed")
        self.protocol = protocol
        self.n_splits = n_splits
        self.n_repeats = n_repeats
        self.validation_split = validation_split
        self.random_state = sklearn.utils.check_random_state(random_state)

    def split_monitored(self, labels) -> Iterator[Split]:
        """Yield indicies of the monitored samples to be used for
        training, validation, and testing
        """
        idx_transformer = _IndexTransformer(
            (labels["class"] != -1) if self.protocol == "mixed" else
            ((labels["class"] != -1) & (labels["protocol"] == self.protocol)))
        labels = idx_transformer.fit_transform(labels)

        stratify = labels[["class", "protocol"]].copy()
        stratify["protocol"] = stratify["protocol"].astype("category").cat.codes
        # Encode as 1d values
        stratify = np.unique(stratify.values, axis=0, return_inverse=True)[1]

        splitter = RepeatedStratifiedKFold(
            n_splits=self.n_splits, n_repeats=self.n_repeats,
            random_state=self.random_state)
        for train_val_idx, test_idx in splitter.split(
            np.zeros((len(labels), 1)), stratify
        ):
            if self.protocol == "mixed":
                train_val_idx = (labels.iloc[train_val_idx]
                                 .assign(idx=train_val_idx)
                                 .groupby(
                                     ["class", "protocol"], group_keys=False)
                                 .apply(pd.DataFrame.sample, frac=.5,
                                        random_state=self.random_state)
                                 .loc[:, "idx"].values)
                test_idx = (labels.iloc[test_idx]
                            .assign(idx=test_idx)
                            .groupby(["class", "protocol"], group_keys=False)
                            .apply(pd.DataFrame.sample, frac=.5,
                                   random_state=self.random_state)
                            .loc[:, "idx"].values)

            if self.validation_split > 0:
                train_idx, val_idx = train_test_split(
                    train_val_idx, test_size=self.validation_split,
                    random_state=self.random_state,
                    stratify=stratify[train_val_idx])
            else:
                train_idx, val_idx = train_val_idx, np.array([], dtype=int)

            yield Split(*idx_transformer.inverse_transform(
                train_idx, val_idx, test_idx))

    def split_unmonitored(self, labels) -> Iterator[Split]:
        """Split the unmonitored set, ensuring that no label is common
        across different groups.
        """
        idx_transformer = _IndexTransformer(
            (labels["class"] == -1) if self.protocol == "mixed" else
            ((labels["class"] == -1) & (labels["protocol"] == self.protocol)))
        labels = idx_transformer.fit_transform(labels)
        X = np.zeros((len(labels), 1))

        # Get the total number of splits since we use a shuffle split
        n_splits = self.n_splits * self.n_repeats
        # Convert a "fold" to a ratio for the test set
        test_size = 1 / self.n_splits

        groups = labels["group"].values

        splitter = GroupShuffleSplit(n_splits=n_splits, test_size=test_size,
                                     random_state=self.random_state)
        for train_val_idx, test_idx in splitter.split(X, groups=groups):
            if self.protocol == "mixed":
                unique_groups = np.unique(groups)
                tcp_groups = self.random_state.choice(
                    unique_groups, size=(len(unique_groups) // 2),
                    replace=False)
                filter_idx = np.concatenate((
                    np.nonzero((labels["group"].isin(tcp_groups)
                               & (labels["protocol"] == "tcp")).values)[0],
                    np.nonzero((~labels["group"].isin(tcp_groups)
                               & (labels["protocol"] != "tcp")).values)[0]
                ))
                train_val_idx = np.intersect1d(filter_idx, train_val_idx)
                test_idx = np.intersect1d(filter_idx, test_idx)

            if self.validation_split > 0:
                train_idx, val_idx = self._split_unmonitored_validation_set(
                    train_val_idx, labels)
            else:
                train_idx, val_idx = train_val_idx, np.array([], dtype=int)

            yield Split(*idx_transformer.inverse_transform(
                train_idx, val_idx, test_idx))

    def _split_unmonitored_validation_set(self, indices, labels):
        protocols = ([self.protocol] if self.protocol != "mixed"
                     else ["quic", "tcp"])
        mask = np.zeros(len(labels), dtype=bool)
        mask[indices] = True

        idx_transformer = _IndexTransformer(mask)
        labels = idx_transformer.fit_transform(labels)

        train_result = []
        val_result = []
        for proto in protocols:
            train, val = self._split_unmon_val_protocol(proto, labels)
            train_result.append(idx_transformer.inverse_transform(train))
            val_result.append(idx_transformer.inverse_transform(val))

        return np.concatenate(train_result), np.concatenate(val_result)

    def _split_unmon_val_protocol(self, protocol, labels):
        idx_transformer = _IndexTransformer(labels["protocol"] == protocol)
        labels = idx_transformer.fit_transform(labels)
        groups = labels["group"].values

        train_idx, val_idx = next(GroupShuffleSplit(
            n_splits=1, test_size=self.validation_split,
            random_state=self.random_state
        ).split(labels, groups=groups))

        # Get the real indices, the above indices are indices into the
        # train_val_idx
        return (idx_transformer.inverse_transform(train_idx),
                idx_transformer.inverse_transform(val_idx))

    def split(self, labels: pd.DataFrame) -> Iterator[Split]:
        """Split the dataset into train, validation, and test indices,
        ensuring that each class is represented in all three sets.

        Labels should contain groups for the unmonitored set,
        unmonitored classes labelled as -1 and which protocol each
        is associated with.

        Each URL in the unmonitored set should have at least 1 sample
        for each of QUIC and TCP.
        """
        for monitored_indices, unmonitored_indices in zip(
            self.split_monitored(labels), self.split_unmonitored(labels)
        ):
            train_idx = np.concatenate((
                monitored_indices.train, unmonitored_indices.train))
            self.random_state.shuffle(train_idx)

            val_idx = np.concatenate((
                monitored_indices.val, unmonitored_indices.val))
            self.random_state.shuffle(val_idx)

            test_idx = np.concatenate((
                monitored_indices.test, unmonitored_indices.test))
            self.random_state.shuffle(test_idx)

            yield Split(train_idx, val_idx, test_idx)


def main(infile: str, outfile: IO, **splitter_kw):
    """Script entry point."""
    logging.basicConfig(
        format='[%(asctime)s] [%(levelname)s] %(name)s - %(message)s',
        level=logging.INFO)

    start = time.perf_counter()

    with h5py.File(infile, mode="r") as h5in:
        _LOGGER.info("Reading labels from %r...", infile)
        labels = (pd.DataFrame.from_records(np.asarray(h5in["labels"]))
                  .transform(decode_column))

    _LOGGER.info("Creating splitter with args %s", splitter_kw)
    random_state = RandomState(splitter_kw.pop("seed"))
    splitter = Splitter(**splitter_kw, random_state=random_state)  # type:ignore

    for indices in splitter.split(labels):
        permutation = random_state.permutation(
            len(indices.train) + len(indices.val))

        json.dump({
            "train": indices.train.tolist(),
            "val": indices.val.tolist(),
            "test": indices.test.tolist(),
            "train-val": np.concatenate(
                (indices.train, indices.val))[permutation].tolist()
        }, outfile, indent=None, separators=(",", ":"))
        outfile.write("\n")

    _LOGGER.info("Script complete in %.2fs", (time.perf_counter() - start))


if __name__ == "__main__":
    main(**doceasy.doceasy(__doc__, {
        "INFILE": str,
        "OUTFILE": doceasy.File(mode="w", default="-"),
        "--n-splits": doceasy.Use(int),
        "--n-repeats": doceasy.Use(int),
        "--validation-split": doceasy.Use(float),
        "--seed": doceasy.Use(int),
        "--protocol": str,
    }))
