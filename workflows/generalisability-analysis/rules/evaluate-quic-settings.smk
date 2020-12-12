include: "../../common/rules/split.smk"

wildcard_constraints:
    i="\d{2}",
    factor="control|bgquic|quic"


rule select_traces:
    """Select the traces to be used in the experiment."""
    input:
        monitored=config["traces"]["monitored"],
        unmonitored=config["traces"]["unmonitored"]
    output:
        "results/open-world-dataset.hdf"
    log:
        "results/logs/select-traces.log"
    shell: """\
        scripts/select-traces {input.monitored} {input.unmonitored} {output} 2> {log}
        """


def train_test_splits__params(wildcards) -> str:
    """Return params for the split traces rule."""
    if wildcards["factor"] == "bgquic":
        return "--with-quic"
    if wildcards["factor"] == "quic":
        return "--with-quic --with-monitored-quic"
    return ""


rule train_test_splits:
    """Split the traces for consistent training and test sets across the
    experiments."""
    input:
        rules.select_traces.output
    output:
        "results/splits-{factor}.json"
    params:
        extra_options=train_test_splits__params
    shell: "scripts/be-split-traces {params.extra_options} {input} {output}"


rule evaluate_setting:
    """Evaluate the classifier on a single split for a single run."""
    input:
        traces=rules.select_traces.output,
        splits="results/splits-{factor}.json.d/{i}"
    output:
        protected("results/predictions-{classifier}-{factor}-{i}.csv")
    log:
        "results/logs/predictions-{classifier}-{factor}-{i}.log"
    params:
        classifier="{classifier}"
    resources:
        gpus=1
    shell: """\
        scripts/evaluate-quic-in-bg {params.classifier} {input.traces} {input.splits} \
            {output} 2> {log}
            """


rule evaluate_setting__merge:
    """Merge the runs for each classifier."""
    input:
        lambda w: expand(
                rules.evaluate_setting.output, **w,
                i=[f"{i:02d}" for i in range(config["n_repetitions"])])
    output:
        "results/predictions-{classifier}-{factor}-all.csv"
    run:
        import pandas
        data = (pandas.concat([pandas.read_csv(filename) for filename in input],
                              keys=range(len(input)), names=["run", "sample"])
                .reset_index(level="sample", drop=True))
        data.index.astype(int, copy=False)
        data.to_csv(output[0], header=True, index=True)


ruleorder: combine_varcnn_predictions > evaluate_setting__merge
rule combine_varcnn_predictions:
    """Combine the varcnn time and sizes predictions."""
    input:
        "results/predictions-varcnn-sizes-{factor}-all.csv",
        "results/predictions-varcnn-time-{factor}-all.csv"
    output:
        "results/predictions-varcnn-{factor}-all.csv"
    run:
        import pandas as pd
        import numpy as np

        pred1, pred2 = pd.read_csv(input[0]), pd.read_csv(input[1])
        assert np.array_equal(
                pred1.columns, ["run", "y_true",] + [str(i) for i in range(-1, 100)])
        assert np.array_equal(
                pred2.columns, ["run", "y_true",] + [str(i) for i in range(-1, 100)])
        assert pred1["y_true"].equals(pred2["y_true"])
        assert pred1["run"].equals(pred2["run"])

        ((pred1 + pred2) / 2).astype({"run": int}).to_csv(
                str(output), index=False, header=True)


# -------------
# Target Rules
# -------------
rule evaluate_setting__gpu:
    """Run the experiment for all the GPU classifiers."""
    input:
        expand("results/predictions-{classifier}-{factor}-all.csv",
               classifier=GPU_CLASSIFIERS, factor=("control", "bgquic", "quic"))


rule evaluate_setting__cpu:
    """Run the experiment for all the CPU classifiers."""
    input:
        expand("results/predictions-{classifier}-{factor}-all.csv",
               classifier=CPU_CLASSIFIERS, factor=("control", "bgquic", "quic"))


# -------------
# Analyses
# -------------
rule confusion_matrix:
    """Create a confusion matrix of the varcnn classifier."""
    input:
        dataset="results/open-world-dataset.hdf",
        splits="results/splits-quic.json",
        predictions="results/predictions-varcnn-quic-all.csv"
    output:
        "results/plots/confusion-matrix.tex"
    notebook:
        "../notebooks/confusion-matrix.ipynb"


rule generalisability_box_plot:
    """Plot box-plots of the generalisability experiments."""
    input:
        expand("results/predictions-{classifier}-{factor}-all.csv",
               factor=("control", "bgquic", "quic"), classifier=config["classifiers"])
    output:
        "results/plots/score-vs-quic-presence.pgf"
    shell: "jupyter nbconvert --execute --inplace notebooks/result-analysis.ipynb"


rule generalisability_pr_curve:
    """Plot precision-recall curves of the generalisability experiments."""
    input:
        expand("results/predictions-{classifier}-{factor}-all.csv",
               factor=("control", "bgquic", "quic"), classifier=config["classifiers"])
    output:
        "results/plots/quic-presence-prcurve.pgf"
    shell: "jupyter nbconvert --execute --inplace notebooks/result-analysis-curve.ipynb"
