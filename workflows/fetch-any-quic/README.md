# 2. Fetch QUIC Traces

This workflow fetches web-pages using the QUIC and TCP protocols, converts these fetches to vectors of sizes and timestamps, and counts the number of resources fetched with each protocol.

This is likely the most complicated workflow in the entire project as it orchestrates multiple browser instances and gateways in docker containers.

## Data Availability Statements

### Dataset List

This workflow requires a list of URLs to request and the TLDs as created by the [Identify QUIC Sites] workflow.

| Data file                                                                 | Source                | Notes                         | Provided       |
|---------------------------------------------------------------------------|-----------------------|-------------------------------|----------------|
| `../identify-quic-sites/results/profile-domains/urls-with-version.csv`    | [Identify QUIC Sites] | List of QUIC-supporting URLs  | no             |
| `../identify-quic-sites/results/all-domains/tlds-alpha-by-domain.txt`     | [Identify QUIC Sites] | List of top-level domains     | yes            |
| `results/fetch/monitored-{blr1,fra1,nyc3}-{00..07}.json.gz`               | This workflow         | Raw monitored fetch data      | no<sup>1</sup> |
| `results/fetch/unmonitored-{blr1,fra1,nyc3}-{00..49}.json.gz`             | This workflow         | Raw unmonitored fetch data    | no<sup>1</sup> |

1. These raw traces are around 30 GB in size. They are therefore provided separately. See the main [README](../../README.md) for more details.


## Computational Requirements

### Software Requirements

If running the trace collection, Docker and Wireguard must be installed on the hosts serving as the client and gateways.
Additionally, the Digital Ocean invoke tasks founds in `tasks/` requires docker-machine.
A binary for docker-machine can be found in `../../tools` bust must be added to the executable path.

### Description of Programs

- `docker/{client, server}`: Docker build contexts for the clients and Wireguard gateways.
- `tasks/`: A set of `pyinvoke` tasks (see `inv --list`) for building the above docker images and provisioning digital ocean gateways.
- `scripts/:`
  - `balance-urls`: Removes domains such as "blogspot.com" from the input URL list that are very frequent.
  - `docker-fetch-websites`: Creates and runs a docker container to fetch websites.
  - `docker-wg-gateway`: Creates and runs a docker container with the Wireguard gateway.
  - `fetch_with_vpn.py:` Orchestrates a remote Wireguard gateway and multiple docker containers to fetch websites.
  - `pcap-to-trace`: Extracts vectors of packet sizes and times from the output of `fetch_with_vpn.py`
  - `trace-to-hdf`: Combines the above trace files to a single HDF file.
- `Snakefile`, `rules/`: Orchestrates running the above scripts and notebook.

### Memory and Runtime Requirements

The collection of the traces was last run on a 32-core, 20 GB server with 15 docker containers simultaneously collecting traces.
In this setting the collection required around 4 days.

## Instructions

#### 1. Install dependencies

Follow the instructions in the main [README](../../README.md) to install the dependencies.

#### 2. Create Docker images

```bash
# Build the client docker image
docker build --tag fetch-client ./docker/client
# Build the gateway docker image
docker build --tag wg-gateway ./docker/wg-gateway
```

#### 3. Configure the Wireguard gateway servers

Ensure that the Wireguard gateway servers have Wireguard and Docker installed, and export the wg-gateway docker images to the servers.
If using the Digital Ocean tasks to provision the machines and build the images remotely (see `inv -l`), an API key and SSH key path must be specified in `tasks/digital_ocean.py`.

#### 4. Configure the workflow

Update `config/config.yaml` to point to the URLs and TLDs files from the previous workflow (see the Dataset List above), and with the SSH ids for each of the gateway nodes.

#### 5. Run the workflow

```bash
# Perform a dry-run
snakemake -n -j
# Make all targets in the workflow
snakemake -j
```

Depending on the dataset files that are already available and their timestamps, some or all of the workflow will be run.
Use `snakemake -F -j` to force running all of the rules, or see `snakemake --help` for other run options.


<!-- Links -->
[Identify QUIC Sites]: ../identify-quic-sites
