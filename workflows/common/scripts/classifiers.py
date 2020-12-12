"""Factory classes for creating the various classifiers and extracting
their features.

The base class is "ClassifierFactory".  An appropriate factory can be
retrieved using get_classifier_factory()
"""
import pathlib
import logging
import dataclasses
import hashlib
import tempfile

from typing_extensions import Literal
import numpy as np

from lab.classifiers import dfnet, varcnn, p1fp, kfingerprinting
from lab.feature_extraction.trace import (
    ensure_non_ragged, extract_metadata, Metadata, extract_interarrival_times
)
from lab.third_party import li2018measuring


@dataclasses.dataclass
class ClassifierFactory:
    """Base factory for classifiers used in the experiment."""
    # Number of features to use after dropping small packets
    n_features_hint: int = 5000

    # Number of classes in the experiment
    n_classes: int = 101

    # Flag indicating whether the classifier uses validation data
    requires_validation_set: bool = False

    # Whether to use verbose output verbose
    verbose: int = 2

    @property
    def tag(self) -> str:
        """Return a tag for the classifier"""
        raise NotImplementedError()

    def create(self, random_state: np.random.RandomState = None):
        """Create a new classifier instance."""
        raise NotImplementedError()

    def extract_features(  # pylint: disable=unused-argument
        self, sizes: np.ndarray, timestamps: np.ndarray
    ) -> np.ndarray:
        """Extract size features for training and testing the classifier.

        Override in a subclass to change the features used.
        """
        return ensure_non_ragged(sizes, dimension=self.n_features_hint)

    def load_features(self, h5group) -> np.ndarray:
        """Load the features from the provided hdf5 group."""
        return np.asarray(h5group[self.tag])


@dataclasses.dataclass
class DeepFingerprintingFactory(ClassifierFactory):
    """Create DeepFingerprinting classifiers for an experiment.
    """
    epochs: int = 30

    @property
    def tag(self):
        return "dfnet"

    def create(self, random_state=None):
        return dfnet.DeepFingerprintingClassifier(
            n_features=self.n_features_hint, n_classes=self.n_classes,
            epochs=self.epochs, verbose=self.verbose)


@dataclasses.dataclass
class P1FPFactory(ClassifierFactory):
    """Create p1-FP(C) classifiers for an experiment."""
    epochs: int = 40

    @property
    def tag(self):
        return "p1fp"

    def create(self, random_state=None):
        return p1fp.KerasP1FPClassifierC(
            n_features=self.n_features_hint, n_classes=self.n_classes,
            epochs=self.epochs, verbose=self.verbose)


@dataclasses.dataclass
class VarCNNFactory(ClassifierFactory):
    """Configure the experiment using the Var-CNN classifier."""
    n_meta_features: int = 12

    # Var-CNN uses early stopping in their paper (and here), and so this defines
    # the maximum number of epochs
    epochs: int = 150

    # Whether the classifier should use size or timestamp features
    feature_type: Literal["time", "sizes"] = "sizes"

    # VarCNN uses a validation split
    requires_validation_set: bool = True

    @property
    def tag(self):
        return f"varcnn-{self.feature_type}"

    def create(self, random_state=None):
        return varcnn.VarCNNClassifier(
            n_classes=self.n_classes, n_packet_features=self.n_features_hint,
            n_meta_features=self.n_meta_features,
            callbacks=varcnn.default_callbacks(), epochs=self.epochs,
            tag=f"varcnn-{self.feature_type}", verbose=self.verbose)

    def extract_features(
        self, sizes: np.ndarray, timestamps: np.ndarray
    ) -> np.ndarray:
        metadata = (Metadata.COUNT_METADATA | Metadata.TIME_METADATA
                    | Metadata.SIZE_METADATA)
        meta_features = extract_metadata(
            sizes=sizes, timestamps=timestamps, metadata=metadata,
            batch_size=5_000
        )

        if self.n_meta_features != meta_features.shape[1]:
            raise ValueError(
                f"The number of metadata features, {meta_features.shape[1]}, "
                f"does not match the amount specified: {self.n_meta_features}.")

        if self.feature_type == "sizes":
            features = ensure_non_ragged(sizes, dimension=self.n_features_hint)
        else:
            assert self.feature_type == "time"
            features = extract_interarrival_times(
                timestamps, dimension=self.n_features_hint)

        return np.hstack((features, meta_features))


@dataclasses.dataclass
class KFingerprintingFactory(ClassifierFactory):
    """Factory to create k-FP classifiers for the experiment."""
    # Initial value taken from sirinam2018deep section 5.7
    n_neighbours: int = 6

    n_features_hint: int = -1

    # The feature set to use for classification
    feature_set: Literal["kfp", "kfp-ext", "kfp-mixed"] = "kfp"

    # Whether to cache and reuse the extracted features.
    # The cache is derived from te lengths of the samples
    cache_features: bool = True

    # Specify the number of jobs to use, -1 means all cores
    n_jobs: int = -1

    def __post_init__(self):
        if self.n_features_hint <= 0:
            # TODO: Is this the best default?
            if self.feature_set in ("kfp", "kfp-mixed"):
                self.n_features_hint = len(kfingerprinting.ALL_DEFAULT_FEATURES)
            elif self.feature_set == "kfp-ext":
                self.n_features_hint = len(li2018measuring.FEATURE_NAMES)
            else:
                raise ValueError(f"Unknown feature-set: {self.feature_set}")

    @property
    def tag(self):
        return self.feature_set

    def create(self, random_state=None):
        return kfingerprinting.KFingerprintingClassifier(
            n_neighbours=self.n_neighbours, unknown_label=-1,
            random_state=random_state, n_jobs=self.n_jobs)

    def load_features(self, h5group) -> np.ndarray:
        """Load the features from the provided hdf5 group."""
        if self.tag == "kfp-mixed":
            features = np.hstack((
                h5group["kfp"][:],
                h5group["kfp-ext"][:, :self.n_features_hint]
            ))
        else:
            features = np.asarray(h5group[self.tag][:, :self.n_features_hint])

        logging.info("%s features with shape %s.", self.tag, features.shape)
        return features

    def extract_features(
        self, sizes: np.ndarray, timestamps: np.ndarray
    ) -> np.ndarray:
        path = self._get_cache_file(sizes)
        features = (self._load_features(path) if self.cache_features
                    else None)

        if features is None:
            features = kfingerprinting.extract_features_sequence(
                sizes=sizes, timestamps=timestamps, n_jobs=None)

        if self.cache_features:
            self._save_features(path, features)

        return features

    @staticmethod
    def _get_cache_file(sizes: np.ndarray) -> str:
        """Returns a sorta-unique hex string representing the features."""
        data = np.fromiter((len(row) for row in sizes), int).tobytes()
        cache_id = hashlib.blake2b(data, digest_size=8).hexdigest()
        directory = tempfile.gettempdir()
        return f"{directory}/kfp-features-{cache_id}.npy"

    def _save_features(self, filename: str, features: np.ndarray):
        assert self.cache_features
        if pathlib.Path(filename).is_file():
            logging.info("Skipping save as features already exist.")
        else:
            np.save(filename, features)

    def _load_features(self, filename: str):
        assert self.cache_features
        try:
            logging.info("Attempting to load features from %r.", filename)
            return np.load(filename)
        except IOError as err:
            logging.info("Failed to load features %s.", err)
            return None


def get_classifier_factory(tag: str, **kwargs):
    """Return a factory for creating the classifier identified by "tag".
    """
    if tag != "kfp" and "n_jobs" in kwargs:
        logging.info("Ignoring 'n_jobs' for non-k-FP classifier %r.", tag)
        del kwargs["n_jobs"]

    if tag == "dfnet":
        return DeepFingerprintingFactory(**kwargs)
    if tag == "p1fp":
        return P1FPFactory(**kwargs)
    if tag == "kfp":
        return KFingerprintingFactory(**kwargs)
    if tag == "varcnn-time":
        return VarCNNFactory(feature_type="time", **kwargs)
    if tag == "varcnn-sizes":
        return VarCNNFactory(feature_type="sizes", **kwargs)
    raise ValueError(f"Unknown classifier factory {tag!r}")
