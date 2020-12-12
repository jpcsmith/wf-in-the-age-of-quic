# 3. Removing Control Packets

This workflow analyses the impact of small packets on trace classification (Section 8) and handles the filtering of small packets from the traces for the other workflows.


## Data Availability Statements

The monitored and unmonitored web-page trace data used to support the findings of this workflow are taken from the [Fetch QUIC Traces] workflow.
The exact paths are specified in `config/config.yaml`.

### Dataset List

| Data file                                                  | Source              | Notes                                    | Provided |
|------------------------------------------------------------|---------------------|------------------------------------------|----------|
| `../fetch-any-quic/results/traces/monitored-traces.hdf`    | [Fetch QUIC Traces] | Monitored traces with *all* packets      | no       |
| `../fetch-any-quic/results/traces/unmonitored-traces.hdf`  | [Fetch QUIC Traces] | Unmonitored traces with *all* packets    | no       |


## Computational Requirements

### Description of Programs

- `notebooks/`
  - `min-size-analysis.ipynb`: Plots packet sizes and creates the precision and recall scores table.
  - `min-size-analysis-curve.ipynb`: Plots the precision recall curve.
- `scripts/`
  - `select-traces`: Selects web-pages from the input datasets that have sufficient training and testing samples.
  - `remove-small-packets`: Filters packets below the specified size threshold.
  - `split-traces`: Creates the train-test splits.
- `Snakefile`: Orchestrates running the above scripts and notebooks.

Additionally, this workflow uses symlinks to the following programs, described in their respective workflows:

- `../common/scripts/{classifiers.py,evaluate-classifier,extract-features}`


### Memory and Runtime Requirements

Evaluates deep-learning models.
Each of the 150 train-test splits takes around 30&ndash;60 minutes for a sequential runtime of around 75&ndash;150 hours.
See the main [README](../../README.md) for details on resources.

## Instructions

#### 1. Configure the workflow

Update `config/config.yaml` to point to the datasets from the previous workflow if different.

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
[Fetch QUIC Traces]: ../fetch-any-quic
