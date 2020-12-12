# 1. Identify QUIC Sites

This workflow downloads and sanitises the TLD list and popular domain lists, queries domains for their support for QUIC, and selects URLs that support common QUIC versions.


## Data Availability Statements

The URL lists and list of top-level domains used to support the findings of this workflow are available online.
We provide them, in addition to the results of the QUIC support scan, as they require interaction with external websites.

### Dataset List

| Data file                                                 | Source        | Notes                 | Provided |
|-----------------------------------------------------------|---------------|-----------------------|----------|
| `results/all-domains/alexa-1m-2020-06-22.csv`             | [Alexa 1M]    | Popular domains       | yes      |
| `results/all-domains/majestic-1m-2020-06-22.csv`          | [Majestic 1M] | Popular domains       | yes      |
| `results/all-domains/umbrella-1m-2020-06-22.csv`          | [Umbrella 1M] | Popular domains       | yes      |
| `results/all-domains/tlds-alpha-by-domain-2020-06-22.txt` | [IANA]        | Top-level domain list | yes      |
| `results/profile-domains/profile-results.csv.gz`          | This workflow | Raw QUIC scan results | yes      |


## Computational Requirements

### Description of Programs

- `scripts/filter-domain-list`: Filters invalid, similar, or duplicate entries from the domain list.
- `scripts/profile-domains`: Queries web-servers for their QUIC support.
- `notebooks/profile-domain-inspection.ipynb`: Calculates summary statistics from the scan results.
- `Snakefile`, `rules/`: Orchestrates running the above scripts and notebook.

### Memory and Runtime Requirements

Scanning occurs asynchronously on a single core and takes ~17 hours.


## Instructions

Follow the instructions in the main [README](../../README.md), then run the workflow with:

```bash
# Perform a dry-run
snakemake -n -j
# Make all targets in the workflow
snakemake -j
```

Since the raw QUIC scan results are already provided, this will create the final URLs from the scan results.
Use `snakemake -F -j` to force running all of the rules, or see `snakemake --help` for other run options.


<!-- Links -->
[Alexa 1M]: http://s3.amazonaws.com/alexa-static/top-1m.csv.zip
[Majestic 1M]: http://downloads.majestic.com/majestic_million.csv
[Umbrella 1M]: http://s3-us-west-1.amazonaws.com/umbrella-static/top-1m.csv.zip
[IANA]: https://data.iana.org/TLD/tlds-alpha-by-domain.txt
