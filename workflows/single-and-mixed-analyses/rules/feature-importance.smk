rule extract_extended_features:
    """Extract the 3000+ extended features from the dataset."""
    input:
        config["open_world_dataset"]
    output:
        "results/extended-features.npy"
    log:
        "results/logs/extended-features.log"
    shell: "scripts/extract-extended-features {input} {output} 2> >(tee {log} >&2)"


rule compute_tree_importances:
    """Compute importances and predictions using the random forest
    classifier underpinning k-FP."""
    input:
        labels=config["open_world_dataset"],
        features=rules.extract_extended_features.output,
        splits="results/tree-importance/split-{protocol}-4791.json"
    output:
        importances="results/tree-importance/importances-{protocol}.csv",
        predictions="results/tree-importance/predictions-{protocol}.csv"
    log:
        "results/logs/compute-tree-importances-{protocol}.log"
    threads: 99
    shell: """\
        scripts/compute-tree-importance --pred-output {output.predictions} \
            {input.labels} {input.features} {input.splits} {output.importances} \
            2> >(tee {log} >&2)
        """


rule compute_tree_importances__all:
    """Run compute_tree_importances for tcp, quic, and mixed datasets."""
    input:
        expand("results/tree-importance/importances-{protocol}.csv",
               protocol=("tcp", "quic", "mixed"))


rule feature_comparison_plot:
    """Plot the feature rank comparisons."""
    input:
        expand("results/tree-importance/importances-{protocol}.csv",
               protocol=("tcp", "quic", "mixed"))
    output:
        "results/plots/feature-rank-comparison.pgf",
        "results/tree-importance/quic-feature-ranks.csv"
    shell: "jupyter nbconvert --execute --inplace notebooks/feature-analysis.ipynb"
