# 5. Single and Mixed Analyses

This workflow evaluates the classifiers when trained and tested on TCP only, QUIC only, and on a mixture of QUIC and TCP traces.
It also is responsible for comparing features when used with QUIC as opposed to TCP, as well as extracting these features and adding them to the dataset.


## Data Availability Statements

The dataset of sampled monitored and unmonitored packet sizes and times used to support the findings of this workflow are taken from the [Generalisability Analysis] workflow.
The used path is specified in `config/config.yaml`.

### Dataset List

| Data file                                                     | Source                      | Notes                                                 | Provided |
|---------------------------------------------------------------|-----------------------------|-------------------------------------------------------|----------|
| `../generalisability-analysis/results/open-world-dataset.hdf` | [Generalisability Analysis] | Open world dataset.                                   | yes      |
| `results/tree-importance/quic-feature-ranks.csv`              | This workflow               | The ranks of the features for use with QUIC and k-FP. | yes      |

[Generalisability Analysis]: ../generalisability-analysis


## Computational Requirements

### Description of Programs

- `scripts/`:
  - `split-samples`: Splits the traces into train, test, and validation sets.
  - `extract-extended-features`: Extracts the set of 3000+ manual features.
  - `compute-tree-importance`: Calculates MDI over the above set of features for QUIC/TCP.
  - `add-extended-features`: Adds the extended features to the dataset for use in subsequent experiments.
- `notebooks/`:
  - `feature-analysis.ipynb`: Plots the feature ranks in QUIC vs TCP.
  - `determine-num-quic-features.ipynb`: Plots k-FP performance on QUIC as the number of included top-ranking manual features increases.
  - `dataset-performance.ipynb`: Creates exploratory box-plots of the performance of the QUIC, TCP, and Mixed settings.
- `Snakefile`, `rules/`: Orchestrates running the above scripts and notebooks.

Additionally, this workflow uses symlinks to the following programs, described in their respective workflows:

- `../common/scripts/{classifiers.py,evaluate-classifier,extract-features}`

### Memory and Runtime Requirements

Evaluates deep-learning models.
Each of the 400 train-test splits takes around 30&ndash;60 minutes for a sequential runtime of around 150&ndash;300 hours.
See the main [README](../../README.md) for details on resources.


## Instructions

#### 1. Configure the workflow

Update `config/config.yaml` to point to the datasets from the previous workflow if different.

#### 2. (Option A) Run the workflow

This uses the final packet size threshold already configured in `config/config.yaml`.

```bash
# Perform a dry-run
snakemake -n -j
# Make all targets in the workflow
snakemake -j
```

Depending on the dataset files that are already available and their timestamps, some or all of the workflow will be run.
Use `snakemake -F -j` to force running all of the rules, or see `snakemake --help` for other run options.

#### 2. (Option B) Run with a different threshold

Run feature analyses, adjust the number of features to use for QUIC, then run the single, QUIC, and mixed experiments:

##### 2.B.1. Run feature analyses

```bash
# Perform a dry-run
snakemake -j -n -- feature_comparison_plot quic_feature_scores_plot
# Make the targets
snakemake -j -- feature_comparison_plot quic_feature_scores_plot
```

##### 2.B.2. Update threshold

Inspect `results/plots/quic-feature-scores.png` and update the desired number of additional QUIC features in `config/config.yaml`.

##### 2.B.3. Run remaining experiments

```bash
# Perform a dry-run
snakemake -j -n -- classifier_protocol_evaluation__cpu classifier_protocol_evaluation__gpu
# Make the targets
snakemake -j -- classifier_protocol_evaluation__cpu classifier_protocol_evaluation__gpu
```
