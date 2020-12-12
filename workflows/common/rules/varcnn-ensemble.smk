rule varcnn_predictions:
    """Combine the predictions of the varcnn-sizes and varcnn-time
    ensembles.
    """
    input:
        "{prefix}varcnn-sizes{suffix}.csv",
        "{prefix}varcnn-time{suffix}.csv"
    output:
        "{prefix}varcnn{suffix}.csv"
    run:
        from lab.classifiers.varcnn import combine_predictions_as_frame
        combine_predictions_as_frame(
            pd.read_csv(input[0]), pd.read_csv(input[1])
        ).to_csv(output, index=False, header=True)
