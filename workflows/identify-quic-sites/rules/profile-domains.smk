"""Perform profiling on the top domain lists, identifying whether the
support the QUIC protocols, and which versions they support.
"""
wildcard_constraints:
    partid="\d{2}"

rule create_domain_batch:
    """Batch the domains into n_profile_parts as defined in the config."""
    input:
        "results/all-domains/unique-top-list.csv"
    output:
        temp("results/all-domains/unique-top-list-{partid}.csv")
    params:
        part=lambda w: int(w.partid) + 1,
        n_parts=config['n_profile_parts']
    shell: "split --number=r/{params.part}/{params.n_parts} {input} > {output}"


rule profile_domains__part:
    """Profile a portion of the the domains after splitting the top list
    into parts, to allow resumption on failure."""
    input:
        rules.create_domain_batch.output
    output:
        protected("results/profile-domains/profile-results-{partid}.csv")
    log:
        "results/logs/profile-domains/profile-results-{partid}.log"
    params:
        part=lambda w: int(w.partid) + 1,
        n_parts=config['n_profile_parts']
    threads: 999  # Prevent this being parallelized
    shell: 
        "scripts/profile-domains {input} > {output} 2> {log}"

rule profile_domains:
    """Profile all the domains."""
    input:
        expand("results/profile-domains/profile-results-{partid:02d}.csv",
               partid=range(config['n_profile_parts']))
    output:
        "results/profile-domains/profile-results.csv.gz"
    run:
        import pandas
        pandas.concat(
            pandas.read_csv(infile) for infile in input
        ).to_csv(output[0], header=True, index=False, compression="gzip")


rule profile_domains__analysis:
    """Analyse the results of the profile_domains run."""
    input:
        profiled_dataset=rules.profile_domains.output[0]
    output:
        # Output for reports:
        error_plot=report("results/report/profile-domains/error-plot.png",
                          category="Profile Analysis"),
        http_status_plot=report("results/report/profile-domains/http-status-plot.png",
                                category="Profile Analysis"),
        rankings_plot=report("results/report/profile-domains/rankings-plot.png",
                             category="Profile Analysis"),
        # Output for further processing:
        urls_with_version="results/profile-domains/urls-with-version.csv"
    notebook: "../notebooks/profile-domain-inspection.ipynb"
