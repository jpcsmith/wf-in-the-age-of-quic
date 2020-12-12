wildcard_constraints:
    rep="\d{2}",
    protocol="quic|tcp"


rule create_mixed_split:
    """Create the splits that will be used for evaluation."""
    input:
        config["features_dataset"]
    output:
        "results/evaluate-split/split-mixed.json"
    log:
        "results/evaluate-split/split-mixed.log"
    shell: """\
        scripts/split-samples --protocol mixed --seed 3796 --n-repeats 2 \
            {input} {output} 2> {log}
        """


rule split_distinguish:
    """Perform the distinguishing phase of the split-distinguish
    classifier."""
    input:
        dataset=config["features_dataset"],
        splits=rules.create_mixed_split.output
    output:
        "results/evaluate-split/distinguisher-predictions-{rep}.csv"
    log:
        "results/logs/evaluate-split/distinguisher-predictions-{rep}.log"
    params:
        lineno=lambda w: int(w["rep"]) + 1
    wildcard_constraints:
        i="\d{2}"
    threads: 4
    shell: """\
        scripts/split-distinguish --n-jobs {threads} \
            {input.dataset} <(cat {input.splits} | sed -n '{params.lineno}p') \
            {output} 2> {log}
        """


rule split_distinguish__all:
    """Run the split_distinguish rule for each of n_repetitions repetitions."""
    input:
        expand("results/evaluate-split/distinguisher-predictions-{rep:02d}.csv",
               rep=range(config["n_repetitions"]))


def split_classify_kfp_args(wildcards, threads=1):
    arg_dict = {"n_jobs": threads}

    if wildcards["protocol"] == "tcp":
        arg_dict["feature_set"] = "kfp"
    elif wildcards["protocol"] == "quic":
        arg_dict["feature_set"] = "kfp-ext"
        arg_dict["n_features_hint"] = config["n_quic_features"]
    else:
        raise ValueError(f"Unrecognised protocol: {wildcards['protocol']!r}")

    return "--classifier-args {}".format(
            ",".join([f"{k}={v}" for k, v in arg_dict.items()]))


rule split_classify_kfp:
    """Perform classification for kfp for a single split."""
    input:
        dataset=config["features_dataset"],
        splits=rules.create_mixed_split.output
    output:
        "results/evaluate-split/kfp-predictions-{protocol}-{rep}.csv"
    log:
        "results/logs/evaluate-split/kfp-predictions-{protocol}-{rep}.log"
    params:
        protocol="{protocol}",
        lineno=lambda w: int(w["rep"]) + 1,
        classifier_args=split_classify_kfp_args
    threads: 4
    shell: """\
        scripts/split-classify kfp --protocol {params.protocol} {params.classifier_args}\
            {input.dataset} <(cat {input.splits} | sed -n '{params.lineno}p') \
            {output} 2> {log}
        """


rule split_classify_kfp__all:
    """Perform classification for kfp for a all splits."""
    input:
        expand("results/evaluate-split/kfp-predictions-{protocol}-{rep:02d}.csv",
               rep=range(config["n_repetitions"]), protocol=("quic", "tcp"))


rule split_classify:
    """Evaluate a GPU classifier on a split."""
    input:
        dataset=config["features_dataset"],
        splits=rules.create_mixed_split.output
    output:
        "results/evaluate-split/{classifier}-predictions-{protocol}-{rep}.csv"
    log:
        "results/logs/evaluate-split/{classifier}-predictions-{protocol}-{rep}.log"
    params:
        classifier="{classifier}",
        protocol="{protocol}",
        lineno=lambda w: int(w["rep"]) + 1,
    threads: 2
    resources:
        gpus=lambda w: 2 if w["classifier"] != "p1fp" else 1
    wildcard_constraints:
        classifier="|".join(config["gpu_classifiers"])
    shell: """\
        scripts/split-classify {params.classifier} --protocol {params.protocol} \
            {input.dataset} <(cat {input.splits} | sed -n '{params.lineno}p') \
            {output} 2> {log}
        """


rule split_classify__gpu:
    """Evaluate all GPU classifiers on all splits."""
    input:
        expand("results/evaluate-split/{classifier}-predictions-{protocol}-{rep:02d}.csv",
               rep=range(config["n_repetitions"]), protocol=("quic", "tcp"),
               classifier=config["gpu_classifiers"])


rule split_mixed_plots:
    """Create the plots for the results of Split, Mixed, TCP, and QUIC."""
    input:
        expand(["results/evaluate-split/{classifier}-predictions-{protocol}-{rep:02d}.csv",
                "results/evaluate-split/distinguisher-predictions-{rep:02d}.csv"],
               rep=range(config["n_repetitions"]), protocol=("quic", "tcp"),
               classifier=config["gpu_classifiers"] + ["kfp"]),
        expand("../single-and-mixed-analyses/results/dataset-performance/{classifier}/predictions-{proto}-{rep:02d}.csv",
               classifier=("varcnn-time", "varcnn-sizes", "p1fp", "kfp", "dfnet"),
               rep=range(20), proto=("quic", "tcp", "mixed"))
    output:
        "results/plots/split-classify-prcurve.pgf",
        "results/plots/split-classify.pgf"
    shell: """\
        jupyter nbconvert --execute --inplace notebooks/split-classify.ipynb \
            --ExecutePreprocessor.timeout=600
        """
