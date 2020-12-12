#!/usr/bin/env python3
"""Usage: split-dataset [options] DATASET [OUTFILE]

Select TCP indices from DATASET to be used for k-fold cross validation,
and write them as a json stream to OUTFILE.
"""
import math
import time
import json
import logging
from typing import IO, Optional
from dataclasses import dataclass

import h5py
import doceasy
import sklearn
import numpy as np
import pandas as pd
from typing_extensions import Final
from sklearn.model_selection import (
    StratifiedKFold, train_test_split, GroupKFold, GroupShuffleSplit,
)

#: The number of folds to use in the k-fold split
N_SPLITS: Final[int] = 10
#: The fraction of samples to set-aside for validation
VALIDATION_SIZE: Final[float] = 0.1
#: The seed for the random number generator
RNG_SEED: Final[int] = 32514

_LOGGER = logging.getLogger(__name__)


@dataclass
class ExperimentSplitter:
    """Splits the TCP-only dataset for the experiment using stratified
    k-fold.
    """
    n_splits: int = 5
    validation_size: float = 0.10
    random_state: Optional[np.random.RandomState] = None

    def _check_postconditions(self, labels, train_idx, val_idx, test_idx):
        all_idx = np.concatenate([train_idx, val_idx, test_idx])
        n_train_val = len(train_idx) + len(val_idx)
        n_tcp_labels = len(labels)

        # Ensure that there are only TCP samples
        assert sum(~labels.iloc[all_idx]["protocol"].isin([b"tcp", "tcp"])) == 0
        # Ensure that the number of train+val samples is correct
        assert math.isclose(n_train_val / n_tcp_labels, 1 - (1 / self.n_splits),
                            abs_tol=0.02)
        # Ensure that the number of validation samples is correct
        assert math.isclose(len(val_idx) / n_train_val, self.validation_size,
                            abs_tol=0.02)
        # Ensure that the number of test samples is correct
        assert math.isclose(len(test_idx) / n_tcp_labels, 1 / self.n_splits,
                            abs_tol=0.02)

        # Ensure that none of the indices overlap
        assert len(np.intersect1d(train_idx, val_idx)) == 0
        assert len(np.intersect1d(train_idx, test_idx)) == 0
        assert len(np.intersect1d(val_idx, test_idx)) == 0

    def split(self, labels: pd.DataFrame):
        """Split the labels based on their region and class.
        """
        assert "protocol" in labels
        assert labels["protocol"].isin(["tcp", b"tcp"]).all()

        random_state = sklearn.utils.check_random_state(self.random_state)

        for mon_splits, unmon_splits in zip(
            self._split_monitored(labels, random_state),
            self._split_unmonitored(labels, random_state)
        ):
            train_idx = np.concatenate([mon_splits[0], unmon_splits[0]])
            random_state.shuffle(train_idx)

            val_idx = np.concatenate([mon_splits[1], unmon_splits[1]])
            random_state.shuffle(val_idx)

            test_idx = np.concatenate([mon_splits[2], unmon_splits[2]])
            random_state.shuffle(test_idx)

            self._check_postconditions(labels, train_idx, val_idx, test_idx)

            yield (train_idx, val_idx, test_idx)

    def _split_monitored(self, labels: pd.DataFrame, random_state):
        assert "class" in labels
        assert "region" in labels

        mask = (labels["class"] != -1)
        labels = labels[mask]
        indices = np.arange(len(mask))[mask]

        splitter = StratifiedKFold(n_splits=self.n_splits, shuffle=False)

        stratify_on = labels[["class", "region"]].to_records(index=False)
        for train_val_idx, test_idx in splitter.split(indices, stratify_on):
            train_idx, val_idx = train_test_split(
                train_val_idx, test_size=self.validation_size,
                random_state=random_state, stratify=stratify_on[train_val_idx])

            yield (indices[train_idx], indices[val_idx], indices[test_idx])

    def _split_unmonitored(self, labels: pd.DataFrame, random_state):
        assert "class" in labels
        assert "group" in labels

        mask = (labels["class"] == -1)
        labels = labels[mask]
        indices = np.arange(len(mask))[mask]

        splitter = GroupKFold(self.n_splits)
        for train_val_idx, test_idx in splitter.split(
            indices, groups=labels["group"]
        ):
            val_splitter = GroupShuffleSplit(
                n_splits=1, test_size=self.validation_size,
                random_state=random_state)

            # pylint: disable=stop-iteration-return
            train_val_idx__train_idx, train_val_idx__val_idx = next(
                val_splitter.split(
                    train_val_idx, groups=labels["group"].iloc[train_val_idx])
            )
            train_idx = train_val_idx[train_val_idx__train_idx]
            val_idx = train_val_idx[train_val_idx__val_idx]

            yield (indices[train_idx], indices[val_idx], indices[test_idx])


def main(dataset: str, outfile: IO[str]):
    """Load the dataset, create the splits and write them to outfile
    as a json stream.
    """
    logging.basicConfig(
        format='[%(asctime)s] [%(levelname)s] %(name)s - %(message)s',
        level=logging.INFO)
    start = time.perf_counter()

    _LOGGER.info("Loading dataset from %r...", dataset)
    with h5py.File(dataset, mode="r") as h5in:
        labels = pd.DataFrame.from_records(np.asarray(h5in["labels"]))

    splitter = ExperimentSplitter(
        n_splits=N_SPLITS, validation_size=VALIDATION_SIZE,
        random_state=RNG_SEED)

    _LOGGER.info("Splitting dataset using %s...", splitter)
    for train_idx, val_idx, test_idx in ExperimentSplitter(
        n_splits=N_SPLITS, validation_size=VALIDATION_SIZE,
        random_state=RNG_SEED
    ).split(labels):
        json.dump({
            "train": train_idx.tolist(),
            "val": val_idx.tolist(),
            "test": test_idx.tolist(),
            "train-val": np.concatenate([train_idx, val_idx]).tolist()
        }, outfile, indent=None, separators=(",", ":"))
        outfile.write("\n")

    _LOGGER.info("Splitting complete in %.2fs.", time.perf_counter() - start)


if __name__ == "__main__":
    main(**doceasy.doceasy(__doc__, {
        "DATASET": str,
        "OUTFILE": doceasy.File(mode="w", default="-")
    }))
