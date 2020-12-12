rule extract_protocol_counts:
    """Extract aggregate statistics of the number of resources returned
    with different protocols.
    """
    input: 
        "results/fetch/{prefix}.json.gz"
    output:
        temp("results/resource-protocol-counts/{prefix}.count.json")
    shell: """\
            zcat {input} | jq  --compact-output '{{url: .url, req_proto: .protocol}} \
                + (select(.status == "success").http_trace \
                    | [.[] | select(.message.message.method == "Network.responseReceived" \
                                    and .message.message.params.response.status == 200)] \
                    | select(length > 0) \
                    | map(.message.message.params.response.protocol) | group_by(.) \
                    | map({{(.[0]): length}}) | add)' \
                > {output}
        """

rule gather_protocol_counts:
    """Merge the the protocol counts into a single file.
    """
    input:
        lambda w: expand(
            "results/resource-protocol-counts/{url_type}-{region}-{batch_id:02d}.count.json", 
            url_type=w["url_type"], region=config["gateway_nodes"].keys(), 
            batch_id=range(config["n_batches"][w["url_type"]])),
    output:
        "results/resource-protocol-counts/{url_type}-counts.json"
    shell: "cat {input} > {output}"
