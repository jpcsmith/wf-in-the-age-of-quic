wildcard_constraints:
    url_type="monitored|unmonitored",
    batch_id="\d{2}",
    region="\w+"


REGIONS = list(config["gateway_nodes"].keys())


rule create_traces:
    """Filter the results from the fetches and create simple packet traces.
    """
    input:
        "results/fetch/{url_type}-{region}-{batch_id}.json.gz"
    output:
        "results/traces/{url_type}-{region}-{batch_id}.json"
    log:
        "results/logs/traces/{url_type}-{region}-{batch_id}.log"
    params:
        client_subnet=config["client_subnet"]
    shell: """\
        zcat {input} | scripts/pcap-to-trace -Y wg {params.client_subnet} \
            2> {log} > {output}
           """


rule region_trace:
    """Create a temporary trace file consisting of all the files from
    the region and annotated with the region.
    """
    input:
        lambda w: expand("results/traces/{url_type}-{region}-{batch_id:02d}.json",
                         batch_id=range(config["n_batches"][w["url_type"]]), **w),
    output:
        temp("results/traces/{url_type}-{region}.json")
    shell: "cat {input} | jq -c '.region = \"{wildcards.region}\"' > {output}"


rule all_monitored_traces:
    """Traces for monitored samples for TCP and QUIC.
    """
    input:
        expand(rules.region_trace.output, region=REGIONS, url_type="monitored")
    output:
        "results/traces/monitored-traces.hdf"
    log:
        "results/logs/traces/monitored-traces.log"
    threads: len(REGIONS)
    shell: "scripts/trace-to-hdf {output} {input} 2> {log}"


rule all_unmonitored_traces:
    """Traces for unmonitored samples for TCP and QUIC.
    """
    input:
        expand(rules.region_trace.output, region=REGIONS, url_type="unmonitored")
    output:
        "results/traces/unmonitored-traces.hdf"
    log:
        "results/logs/traces/unmonitored-traces.log"
    threads: len(REGIONS)
    shell: "scripts/trace-to-hdf {output} {input} 2> {log}"


rule all_traces:
    """Traces for monitored and unmonitored samples for TCP and QUIC.
    """
    input:
        rules.all_monitored_traces.output,
        rules.all_unmonitored_traces.output
