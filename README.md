# Website Fingerprinting in the Age of QUIC

This repository contains the code for the paper "Website Fingerprinting in the Age of QUIC" (PETS 2021).

The code is divided into "workflows" with each workflow responsible for one or a few related experiments.
Each workflow contains the scripts for collecting and processing data, performing machine learning classification, and generating plots for the paper.


## Data Availability Statements

The data used to support this paper are provided in two sets:

- [**quic-wf-core.tgz (831 MB)**](https://polybox.ethz.ch/index.php/s/u10mAN6NCcDP39U):
  - The domains used for scanning and the scan results in CSV format with headers.
  - The open-world-dataset in HDF5 format, with class labels, arrays of sizes and timestamps, and packets below 175 bytes removed.
- **quic-wf-raw.tar (28 GB)**:
  - The raw fetch QUIC and TCP traces and their associated metadata.
  - Each file is a JSON stream of objects with the following, possible null-valued, keys:
    - *url, final_url*: requested and final redirected URLs
    - *status*: HTTP status code of the fetch
    - *protocol*: protocol used to request the main page, "quic" or "tcp"
    - *packets*: base64 encoded PCAP for the request
    - *http_trace*: Chromium DevTools performance log ([reference](https://chromedevtools.github.io/devtools-protocol/tot/Network/))
  - Due to the size, this is only available upon request.


## Computational Requirements

### Software Requirements

- Bash
- Git and Git-LFS 2.17
- Python 3.7
  - Dependencies listed in `requirements.txt`
  - The [**wf-tools**](https://github.com/jpcsmith/wf-tools) library
- Optional:
  - Docker 19.03.12
  - Wireguard v1.0.20200513
  - docker-machine v0.16.2

### Memory and Runtime Requirements

The code was last run on a computing cluster with each experiment running on 2&ndash;4 cores (each 2.4 GHz), 6 GB main memory per core.
Machine learning training and testing used an additional 0&ndash;2 GPUs based on the classifier.
These jobs were run in parallel to reduce runtime, with each train-test split requiring 1&ndash;3 hours.

**Note:** The current `requirements.txt` specifies tensorflow-cpu. If you have access to a GPU then install tensorflow-gpu instead.

## Getting Started

#### 1. Clone the repository and change to the directory.

```bash
# Clone the repository
git clone https://github.com/jpcsmith/wf-in-the-age-of-quic.git
# Change to the code directory
cd wf-in-the-age-of-quic/
# Download the git LFS files
git lfs pull
```

#### 2. Create and activate a virtual environment

```bash
python3 -m venv env
source env/bin/activate
```

#### 3. Install the Python requirements
```bash
# Ensure that pip is the latest version
python3 -m pip install --upgrade pip

# Install the requirements using pip
python3 -m pip install --no-cache-dir -r requirements.txt
```

If the installation fails, ensure that the Python development libraries are installed and retry the above.
On Ubuntu 18.04, this would be the `python3.7-dev` and `python3-venv` packages.

#### 4. (Optional) Download and extract the data

```bash
wget https://polybox.ethz.ch/index.php/s/u10mAN6NCcDP39U/download -O quic-wf-core.tgz
tar -xzvf quic-wf-core.tgz
```

#### 5. (Optional) Install Docker and Wireguard
If planning to run trace-collection, i.e. from the [Fetch QUIC Traces] workflow, install docker (19.03.12) and Wireguard (v1.0.20200513).

#### 6. Run the desired workflow
Change to the desired workflow's directory and follow the instructions for running the workflow.

## Mapping of Paper Sections to Workflows
The workflows responsible for the various sections of the paper are mapped below.

| Paper Section | Workflows | Directories |
|-------------------------------|----------|-----------|
| 4. Combined QUIC-TCP Dataset  | Identify QUIC Sites<br>Fetch QUIC Traces | [**workflows/identify-quic-sites**](workflows/identify-quic-sites)<br>[**workflows/fetch-any-quic**](workflows/fetch-any-quic) |
| 6. From TCP to QUIC           | Generalisability Analysis<br>Single and Mixed Analyses | [**workflows/generalisability-analysis**](workflows/generalisability-analysis)<br>[**workflows/single-and-mixed-analyses**](workflows/single-and-mixed-analyses) |
| 7. Joint Classification of QUIC and TCP | Single and Mixed Analyses<br>Distinguish Protocol | [**workflows/single-and-mixed-analyses**](workflows/single-and-mixed-analyses)<br>[**workflows/distinguish-protocol**](workflows/distinguish-protocol) |
| 8. Remove Control Packets | Removing Control Packets | [**workflows/removing-control-packets**](workflows/removing-control-packets) |


## List of Tables and Programs

The following table lists the programs and files responsible for the various tables and figures found in the paper.
Notebooks are located in the `notebooks/` directory and outputs in the `results/plots` directory **relative to the associated workflow**.

| Figure/Table   | Workflow                    | Notebook                                 | Output file                            |
|----------------|-----------------------------|------------------------------------------|----------------------------------------|
| Table 2        | [Generalisability Analysis] | [**confusion-matrix.ipynb**]             | `confusion-matrix.tex`                 |
| Figure 2       | [Generalisability Analysis] | [**result-analysis.ipynb**]              | `score-vs-quic-presence.pgf`           |
| Figure 3       | [Single and Mixed Analyses] | [**feature-analysis.ipynb**]             | `feature-rank-comparison.pgf`          |
| Figure 4       | [Single and Mixed Analyses] | [**determine-num-quic-features.ipynb**]  | `quic-feature-scores.pgf`              |
| Figure 5       | [Distinguish Protocol]      | [**split-classify.ipynb**]               | `split-classify.pgf`                   |
| Figure 6       | [Distinguish Protocol]      | [**distinguisher-performance.ipynb**]    | `distinguisher-performance.pgf`        |
| Figure 7       | [Distinguish Protocol]      | [**distinguisher-performance.ipynb**]    | `distinguisher-importance.pgf`         |
| Figure 8       | [Removing Control Packets]  | [**min-size-analysis.ipynb**]            | `packet-size-ecdf.pgf`                 |
| Table 3        | [Removing Control Packets]  | [**min-size-analysis.ipynb**]            | embedded in notebook                   |
| Figure 9       | [Fetch QUIC Traces]         | [**resource-distribution.ipynb**]        | `quic-resource-dist.pgf`               |
| Figure 10      | [Generalisability Analysis] | [**vary-deploy.ipynb**]                  | `vary-deployment.pgf`                  |
| Figure 11a     | [Generalisability Analysis] | [**result-analysis-curve.ipynb**]        | `quic-presence-prcurve.pgf`            |
| Figure 11b     | [Distinguish Protocol]      | [**split-classify.ipynb**]               | `split-classify-prcurve.pgf`           |
| Figure 11c     | [Removing Control Packets]  | [**min-size-analysis-curve.ipynb**]      | `score-vs-min-packet-size-prcurve.pgf` |


[Generalisability Analysis]: ./workflows/generalisability-analysis
[Single and Mixed Analyses]: ./workflow/single-and-mixed-analyses
[Distinguish Protocol]: ./workflows/distinguish-protocol
[Removing Control Packets]: ./workflows/removing-control-packets
[Fetch QUIC Traces]: ./workflows/fetch-any-quic

[**confusion-matrix.ipynb**]: workflows/generalisability-analysis/notebooks/confusion-matrix.ipynb
[**result-analysis.ipynb**]: workflows/generalisability-analysis/notebooks/result-analysis.ipynb
[**feature-analysis.ipynb**]: workflows/single-and-mixed-analyses/notebooks/feature-analysis.ipynb
[**determine-num-quic-features.ipynb**]: workflows/single-and-mixed-analyses/notebooks/determine-num-quic-features.ipynb
[**split-classify.ipynb**]: workflows/distinguish-protocol/notebooks/split-classify.ipynb
[**distinguisher-performance.ipynb**]: workflows/distinguish-protocol/notebooks/distinguisher-performance.ipynb
[**min-size-analysis.ipynb**]: workflows/removing-control-packets/notebooks/min-size-analysis.ipynb
[**resource-distribution.ipynb**]: workflows/fetch-any-quic/notebooks/resource-distribution.ipynb
[**vary-deploy.ipynb**]: workflows/generalisability-analysis/notebooks/vary-deploy.ipynb
[**result-analysis-curve.ipynb**]: workflows/generalisability-analysis/notebooks/result-analysis-curve.ipynb
[**min-size-analysis-curve.ipynb**]: workflows/removing-control-packets/notebooks/min-size-analysis-curve.ipynb

## Licence

The code and associated data is released under an MIT licence as found in the [LICENCE](./LICENCE) file.
