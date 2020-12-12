rule gzip:
    """Generate a gzipped file from arbitrary input.
    """ 
    input: "{prefix}"
    output: "{prefix}.gz"
    shell: "gzip {input}"
