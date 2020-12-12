rule split_line:
    """Extract a single line from the input file."""
    input: "{prefix}"
    output: "{prefix}.d/{line}"
    params:
        lineno=lambda w: int(w["line"]) + 1
    shell: "sed -n '{params.lineno}p' {input} > {output}"
