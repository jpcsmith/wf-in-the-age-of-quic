wildcard_constraints:
    frac="\d(\.\d+)?",
    rep="\d{2}"


rule extracted_dataset:
    """Create a dataset with features already extracted."""
    input:
        "results/open-world-dataset.hdf"
    output:
        "results/extracted-dataset.hdf"
    shell: "scripts/extract-features {input} {output}"


rule quic_deployment_splits:
    """Split the traces for the specified fraction of URLs supporting
    QUIC."""
    input:
        "results/extracted-dataset.hdf"
    output:
        "results/vary-deployment/splits-{frac}-deployed.json"
    params:
        frac="{frac}"
    shell: """\
        scripts/be-split-traces --with-quic --with-monitored-quic \
            --quic-frac {params.frac} {input} {output}
        """


rule evaluate_deployment:
    """Evaluate the classifier in the presence of partial deployment."""
    input:
        features="results/extracted-dataset.hdf",
        splits=rules.quic_deployment_splits.output
    output:
        "results/vary-deployment/{classifier}/predictions-{frac}-{rep}.csv"
    log:
        "results/vary-deployment/{classifier}/predictions-{frac}-{rep}.log"
    params:
        lineno=lambda w: int(w["rep"]) + 1,
        classifier="{classifier}"
    threads: lambda w: 4 if w["classifier"] == "kfp" else 2
    resources:
        gpu=lambda w: 2 if w["classifier"] != "kfp" else 0,
        time=lambda w: config["classifier_time"][w["classifier"]]
    shell: """\
        scripts/evaluate-classifier {params.classifier} --classifier-args n_jobs={threads} \
            {input.features} <(sed -n '{params.lineno}p' {input.splits}) {output} 2> {log}
        """


rule evaluate_deployment__cpu:
    """Evaluate CPU classifiers in the presence of partial deployment of
    QUIC for the levels speccfied in "quic_deployment_levels" config key."""
    input:
        expand("results/vary-deployment/kfp/predictions-{frac:.1f}-{rep:02d}.csv",
               frac=config["quic_deployment_levels"], rep=range(config["n_repetitions"]))


rule evaluate_deployment__gpu:
    """Evaluate GPU classifiers in the presence of partial deployment of
    QUIC for the levels speccfied in "quic_deployment_levels" config key."""
    input:
        expand("results/vary-deployment/{classifier}/predictions-{frac:.1f}-{rep:02d}.csv",
               frac=config["quic_deployment_levels"], rep=range(config["n_repetitions"]),
               classifier=["dfnet"])


# -------------
# Analyses
# -------------
rule deployment_plots:
    """Plot the results of the deployment experiments."""
    input:
        expand("results/vary-deployment/{classifier}/predictions-{frac:.1f}-{rep:02d}.csv",
               frac=config["quic_deployment_levels"], rep=range(config["n_repetitions"]),
               classifier=["dfnet", "kfp"])
    output:
        "results/plots/vary-deployment.pgf"
    shell: "jupyter nbconvert --execute --inplace notebooks/vary-deploy.ipynb"
