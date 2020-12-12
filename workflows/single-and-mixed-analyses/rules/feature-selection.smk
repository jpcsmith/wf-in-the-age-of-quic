rule extracted_dataset_with_extended_features:
    """Add the extended k-FP features to the extracted dataset in the
    order of the rankings for QUIC."""
    input:
        dataset="results/extracted-dataset.hdf",
        extended_features="results/extended-features.npy",
        ranks="results/tree-importance/quic-feature-ranks.csv"
    output:
        touch("results/.extracted-dataset-extended")
    shell: """\
        scripts/add-extended-features {input.extended_features} {input.ranks} \
            {input.dataset}
        """


rule evaluate_quic_features:
    """Evaluate the k-FP classifier on the extended feature set for QUIC,
    while truncating to a specified number of features."""
    input:
        dataset="results/extracted-dataset.hdf",
        split="results/tree-importance/split-quic-{i}-25797.json",
        _=rules.extracted_dataset_with_extended_features.output
    output:
        "results/tree-importance/kfp-ext-quic-{n_features}-{i}.csv"
    log:
        "results/logs/tree-importance/kfp-ext-quic-{n_features}-{i}.log"
    params:
        n_features="{n_features}"
    wildcard_constraints:
        n_features="\d+"
    threads: 4
    shell: """\
        scripts/evaluate-classifier kfp \
            --classifier-args feature_set=kfp-ext,n_features_hint={params.n_features},n_jobs={threads} \
            {input.dataset} {input.split} {output} 2> {log}
        """


rule evaluate_quic_features__all:
    """Run the evaluate_quic_features experiment for n_repetitions,
    using the feature sizes in quic_feature_steps."""
    input:
        expand("results/tree-importance/kfp-ext-quic-{n_features}-{i:02d}.csv",
               n_features=config["quic_feature_steps"], i=range(10))


rule quic_feature_scores_plot:
    """Plot the performance scores for QUIC with various numbers of top
    features."""
    input:
        expand("results/tree-importance/kfp-ext-quic-{n_features}-{i:02d}.csv",
               n_features=config["quic_feature_steps"], i=range(10))
    output:
        "results/plots/quic-feature-scores.pgf",
        "results/plots/quic-feature-scores.png"
    shell: """\
        jupyter nbconvert --execute --inplace notebooks/determine-num-quic-features.ipynb
        """
