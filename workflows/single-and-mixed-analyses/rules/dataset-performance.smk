# ----------------------
# Settings and functions
# ----------------------
GPU_CLASSIFIERS = [c for c in config["classifiers"] if c != "kfp"]
CPU_CLASSIFIERS = [c for c in config["classifiers"] if c not in GPU_CLASSIFIERS]

# Set the GPU resource to one so that multiple runs do not compete for a single GPU.
# Can be overridden at the command line if more gpus are available
workflow.global_resources.setdefault("gpus", 1)


# ------------------
# Rules
# ------------------
def get_classifier_args(wildcards, threads=1) -> str:
    if wildcards["classifier"] != "kfp":
        return ""

    arg_dict = {"n_jobs": threads}
    if wildcards["protocol"] == "tcp":
        arg_dict["feature_set"] = "kfp"
    elif wildcards["protocol"] == "quic":
        arg_dict["feature_set"] = "kfp-ext"
        arg_dict["n_features_hint"] = config["n_quic_features"]
    elif wildcards["protocol"] == "mixed":
        arg_dict["feature_set"] = "kfp-mixed"
        arg_dict["n_features_hint"] = config["n_quic_features"]
    else:
        raise ValueError(f"Unrecognised protocol: {wildcards['protocol']!r}")

    return "--classifier-args {}".format(
            ",".join([f"{k}={v}" for k, v in arg_dict.items()]))


def get_evaluation_inputs(wildcards):
    inputs = {
        "dataset": rules.extracted_dataset.output,
        "splits": "results/dataset-performance/split-{protocol}-{i}-1271.json",
    }

    if wildcards["classifier"] == "kfp":
        inputs["extended_dataset"] = "results/.extracted-dataset-extended"

    return inputs


def required_gpu_for_classifier(wildcards):
    if wildcards["classifier"] == "p1fp":
        return 1
    if wildcards["classifier"] == "kfp":
        return 0
    return 2


rule classifier_protocol_evaluation:
    """Evaluate the classifier on the protocol"""
    input:
        unpack(get_evaluation_inputs)
    output:
        "results/dataset-performance/{classifier}/predictions-{protocol}-{i}.csv"
    log:
        "results/logs/dataset-performance/{classifier}/predictions-{protocol}-{i}.log"
    params:
        classifier="{classifier}",
        classifier_args=get_classifier_args
    threads: lambda w: 2 if w["classifier"] != "kfp" else 4
    resources:
        gpus=required_gpu_for_classifier
    shell: """\
        scripts/evaluate-classifier {params.classifier_args} {params.classifier} \
            {input.dataset} {input.splits} {output} 2> {log}
        """

rule classifier_protocol_evaluation__gpu:
    """Run the experiment for all the GPU classifiers."""
    input:
        expand("results/dataset-performance/{classifier}/predictions-{protocol}-{i:02d}.csv",
               classifier=GPU_CLASSIFIERS, i=range(config["n_repetitions"]),
               protocol=("tcp", "quic", "mixed"))


rule classifier_protocol_evaluation__cpu:
    """Run the experiment for all the CPU classifiers."""
    input:
        expand("results/dataset-performance/{classifier}/predictions-{protocol}-{i:02d}.csv",
               classifier=CPU_CLASSIFIERS, i=range(config["n_repetitions"]),
               protocol=("tcp", "quic", "mixed"))
