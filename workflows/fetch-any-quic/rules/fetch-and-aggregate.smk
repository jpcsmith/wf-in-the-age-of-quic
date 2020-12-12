# ----------------------
# Settings and functions
# ----------------------
REGIONS = list(config["gateway_nodes"].keys())

wildcard_constraints:
    groupid="\d{2}",
    repid="\d{2}",
    url_type="monitored|unmonitored",
    batch_id="\d{2}"


# Set the gateway resources programatically so that we do not forget to set them on the
# command line. We use resources to limit running multiple batches that depend on the
# same VPN gateway at the same time, since they all bind to the same port.
workflow.global_resources.update({f"gateway_{region}": 1 for region in REGIONS})
GATEWAY_RESOURCES = {
    # Bind the loop variable to reg at lambda declaration time vs runtime
    f"gateway_{region}": lambda w, reg=region: 1 if w["region"] == reg else 0
    for region in REGIONS
}


def wildcard_config(key: str, wildcard: str):
    """Returns an input/params function that gets the value for the
    wildcard provided, in the config dictionary specified by key.
    """
    return lambda wildcards: config[key][wildcards[wildcard]]


# ------------------
# Rules
# ------------------
rule sample_urls:
    """Balance and select the monitored and unmonitored URLs from the
    set of QUIC URLs.
    """
    input:
        urls=config["urls_file"],
        tlds=config["tlds_file"]
    output:
        monitored="results/url-samples/monitored.csv",
        unmonitored="results/url-samples/unmonitored.csv",
        balanced_urls=temp("results/url-samples/balanced-urls.csv")
    log:
        "results/url-samples/balanced-urls.log"
    params:
        seed=4221342,
        tail_start=config['n_monitored']+1
    shell: """
        scripts/balance-urls --shuffle --seed {params.seed} {input.tlds} {input.urls} \
                > {output.balanced_urls} 2> {log}
        head -n {config[n_monitored]} {output.balanced_urls} > {output.monitored}
        tail -n+{params.tail_start} {output.balanced_urls} > {output.unmonitored}
        """


rule configure_fetch_host:
    """We perform any transient configuration here that should be run
    before collection for the clients.  This configuration is assumed
    to be reset on reboot.
    """
    output: touch("/tmp/configure_fetch_host.done")
    shell: "sudo ethtool -K docker0 tx off sg off tso off gro off gso off ufo off lro off rx off"


def monitored_versions_string():
    result = ""
    for key, value in config["traces_per_vpn"]["monitored"].items():
        assert value % config["n_batches"]["monitored"] == 0
        value = int(value / config["n_batches"]["monitored"])
        result += f"{key}={value},"
    return result.strip(",")


rule fetch_with_vpn__monitored:
    """Fetch the traces via VPN for a given URL type and region.
    """
    input:
        urls=rules.sample_urls.output["monitored"],
        _=ancient(rules.configure_fetch_host.output)
    output:
        "results/fetch/monitored-{region}-{batch_id}.json.gz"
    log:
        "results/logs/fetch/monitored-{region}-{batch_id}.log"
    params:
        pre_gzip="results/fetch/monitored-{region}-{batch_id}.json",
        checkpoint_dir="results/fetch/checkpoints-monitored-{region}-{batch_id}",
        gateway_node=wildcard_config("gateway_nodes", "region"),
        versions=monitored_versions_string(),
    priority: 10
    threads: config["n_clients_per_vpn"] * 2
    resources:
        **GATEWAY_RESOURCES
    shell: """
        scripts/fetch-with-vpn --gateway-node {params.gateway_node} \
                --n-clients {config[n_clients_per_vpn]} --snaplen {config[snaplen]} \
                --n-batches 1 --checkpoint-dir {params.checkpoint_dir} \
                {params.versions} {input.urls} {params.pre_gzip} 2> {log}
        gzip {params.pre_gzip}
        """


rule fetch_with_vpn__unmonitored__batch_input:
    """Batch the input for fetching unmonitored traces. 

    We batch by URLs as the number of URLS >> number of samples per URL.
    """
    input:
        rules.sample_urls.output["unmonitored"]
    output:
        temp("results/fetch/unmonitored-batch-{batch_id}.csv")
    params:
        n_splits=config["n_batches"]["unmonitored"],
        split_id=lambda wild: int(wild["batch_id"]) + 1
    shell: "split --number=r/{params.split_id}/{params.n_splits} {input} > {output}"


rule fetch_with_vpn__unmonitored:
    """Fetch the traces via VPN for a given URL type and region.
    """
    input:
        urls=rules.fetch_with_vpn__unmonitored__batch_input.output,
        _=ancient(rules.configure_fetch_host.output)
    output:
        "results/fetch/unmonitored-{region}-{batch_id}.json.gz"
    log:
        "results/logs/fetch/unmonitored-{region}-{batch_id}.log"
    params:
        pre_gzip="results/fetch/unmonitored-{region}-{batch_id}.json",
        gateway_node=wildcard_config("gateway_nodes", "region"),
        checkpoint_dir="results/fetch/checkpoints-unmonitored-{region}-{batch_id}",
        versions=",".join(f"{k}={v}" for k, v 
                          in config["traces_per_vpn"]["unmonitored"].items()),
        attempts_per_protocol=("--attempts-per-protocol" 
                if ("keep_collecting_unmonitored" in config 
                    and config["keep_collecting_unmonitored"]) else "")
    threads: config["n_clients_per_vpn"] * 2
    resources:
        **GATEWAY_RESOURCES
    shell: """
        scripts/fetch-with-vpn --gateway-node {params.gateway_node} \
                --n-clients {config[n_clients_per_vpn]} --snaplen {config[snaplen]} \
                --n-batches 1 {params.attempts_per_protocol} \
                --checkpoint-dir {params.checkpoint_dir} \
                {params.versions} {input.urls} {params.pre_gzip} 2> {log}
        gzip {params.pre_gzip}
        """
