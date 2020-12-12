# 6. Distinguish Protocol

This workflow defines and evaluates the *distinguisher* for differentiating between QUIC and TCP traces, as well as the *Split ensemble* for joint classification of QUIC and TCP traces.


## Data Availability Statements

The pre-extracted features used to support the findings of this workflow are taken from the [Single and Mixed Analyses] workflow.
Additionally, as this workflow creates a combined plot for QUIC, TCP, the Mixed classifier, and the Split ensemble, it requires the predictions for the classifiers from the [Single and Mixed Analyses] workflow.

### Dataset List

| Data file                                                    | Source                      | Notes                                                                    | Provided |
|--------------------------------------------------------------|-----------------------------|--------------------------------------------------------------------------|----------|
| `../single-and-mixed-analyses/results/extracted-dataset.hdf` | [Single and Mixed Analyses] | The dataset of extracted features with the additional features for QUIC. | no       |
| `../single-and-mixed-analyses/results/dataset-performance/*` | [Single and Mixed Analyses] | The predictions in the TCP, QUIC, and Mixed settings.                    | no       |



## Computational Requirements

### Description of Programs

- `scripts/`:
  - `evaluate-distinguisher`: Evaluates the distinguisher on 1 trace pair per URL from the dataset, for a specified number of URLs.
  - `split-distinguish`: Trains the distinguisher on the provided dataset and split and creates predictions.
  - `split-classify`: Trains a classifier on a single protocol from the train samples and creates predictions for all test samples.
- `notebooks/`:
  - `distinguisher-performance.ipynb`: Plots feature importance for the distinguisher and its distinguisher's accuracy.
  - `split-classify.ipynb`: Creates plots for Split (this workflow) and the [Single and Mixed Analyses] settings.
- `Snakefile`, `rules/`: Orchestrates running the above scripts and notebooks.

Additionally, this workflow uses symlinks to the following programs, described in their respective workflows:

- `../common/scripts/classifiers.py`
- `../single-and-mixed-analyses/scripts/split_samples.py`

### Memory and Runtime Requirements

Evaluates deep-learning models.
Each of the 200 train-test splits takes around 15&ndash;45 minutes for a sequential runtime of around 50&ndash;150 hours.
See the main [README](../../README.md) for details on resources.


## Instructions

#### 1. Configure the workflow

Update `config/config.yaml` to point to the datasets from the previous workflow if different.
The predictions for QUIC, TCP, and Mixed must be in their original location `../single-and-mixed-analyses/results/dataset-performance/*`.

#### 2. Run the workflow

```bash
# Perform a dry-run
snakemake -n -j
# Make all targets in the workflow
snakemake -j
```

Depending on the dataset files that are already available and their timestamps, some or all of the workflow will be run.
Use `snakemake -F -j` to force running all of the rules, or see `snakemake --help` for other run options.

<!-- Links -->
[Single and Mixed Analyses]: ../single-and-mixed-analyses
