# 4. Generalisability Analysis

This workflow selects URLs that have a common number of samples in the monitored and unmonitored sets across the protocols.
The first evaluates classifier performance for classifiers trained on TCP but evaluated on test samples with QUIC in the unmonitored set or monitored and unmonitored sets.
The second evaluates classifier performance as we adjust the fraction of samples in the test set that are QUIC or TCP.


## Data Availability Statements

The *filtered* monitored and unmonitored trace data used to support the findings of this workflow are taken from the [Removing Control Packets] workflow.
The used paths are specified in `config/config.yaml`.

### Dataset List

| Data file                                                             | Source                     | Notes                                                                    | Provided |
|-----------------------------------------------------------------------|----------------------------|--------------------------------------------------------------------------|----------|
| `../removing-control-packets/results/filtered/monitored-traces.hdf`   | [Removing Control Packets] | *Filtered* monitored traces                                              | no       |
| `../removing-control-packets/results/filtered/unmonitored-traces.hdf` | [Removing Control Packets] | *Filtered* monitored traces                                              | no       |
| `results/open-world-dataset.hdf`                                      | This workflow              | Filtered and selected traces, used for this and subsequent evaluations.  | yes      |

[Removing Control Packets]: ../removing-control-packets


## Computational Requirements

### Description of Programs

- `scripts/`
  - `select-traces`: Selects the URLs from the monitored and unmonitored traces that have sufficient numbers of samples.
  - `be-split-traces`: Splits the traces into train, test, and validation sets.
  - `evaluate-quic-in-bg`: Extracts features from the dataset and evaluates a single classifier on a split of the dataset (legacy).
- `notebooks/`
  - `confusion-matrix.ipynb`: Creates a confusion matrix for the experiment with QUIC in the monitored and unmonitored sets.
  - `result-analysis.ipynb`: Creates box plots of the results of the various QUIC settings.
  - `result-analysis-curve.ipynb`: Creates PR curves for the results of the various QUIC settings.
  - `vary-deploy.ipynb`: Creates line-plots for the experiment that varies the fraction of QUIC to TCP samples.
- `Snakefile`, `rules/`: Orchestrates running the above scripts.

Additionally, this workflow uses symlinks to the following programs, described in their respective workflows:

- `../common/scripts/{classifiers.py,evaluate-classifier,extract-features}`

### Memory and Runtime Requirements

Evaluates deep-learning models.
Each of the 330 train-test splits takes around 30&ndash;60 minutes for a sequential runtime of around 165&ndash;330 hours.
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
