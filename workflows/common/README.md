# 0. Common

This workflow exists as a place to keep common code and rules for other workflows.
There's nothing to do here.

## Description of Programs

- `scripts/`
  - `extract-features`: Creates an HDF with the standard features for the classifiers, extracted from the dataset.
  - `evaluate-classifier`: Evaluates a single classifier on a single split of the extracted features.
  - `classifiers.py`: Interface for the classifiers used in the workflows
