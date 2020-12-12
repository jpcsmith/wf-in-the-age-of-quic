rule evaluate_distinguisher:
    """Evaluate the distinguisher on a specified number of training URLS,
    with 1 sample per URL-protocol pair."""
    input:
        config["features_dataset"]
    output:
        predictions="results/distinguisher/predictions-{train_size}.csv",
        importances="results/distinguisher/importances-{train_size}.csv"
    log:
        "results/logs/distinguisher/evaluate-distinguisher-{train_size}.log"
    params:
        train_size="{train_size}"
    wildcard_constraints:
        train_size="\d+"
    threads: 4
    shell: """\
        scripts/evaluate-distinguisher \
            --n-jobs {threads} --train-size {params.train_size} \
            --importances {output.importances} {input} {output.predictions} 2> {log}
        """

rule evaluate_distinguisher__all:
    """Run evaluate_distinguisher for each of the train sizes defined in
    train_sizes in the config."""
    input:
        expand(rules.evaluate_distinguisher.output, train_size=config["train_sizes"])


rule distinguisher_plot:
    """Plot the top feature importances for and performance of the
    distinguisher."""
    input:
        expand(rules.evaluate_distinguisher.output, train_size=config["train_sizes"])
    output:
        "results/plots/distinguisher-importance.pgf",
        "results/plots/distinguisher-performance.pgf"
    shell: """\
        jupyter nbconvert --execute --inplace notebooks/distinguisher-performance.ipynb
        """
