"""Retreieve the most recent versions of the website lists."""
import datetime

_TODAY = datetime.datetime.today().date()

rule download_tlds:
    """Download the list of top-level domains."""
    output:
        link="results/all-domains/tlds-alpha-by-domain.txt",
        real=f"results/all-domains/tlds-alpha-by-domain-{_TODAY}.txt"
    shell: """
        wget -q {config[tld-url]} --output-document={output.real}
        ln --symbolic --relative {output.real} {output.link}
        """

rule download_top_list:
    """Download a top 1-million list."""
    output:
        link="results/all-domains/{list}.csv",
        real=f"results/all-domains/{{list}}-{_TODAY}.csv"
    params:
        url=lambda wild: config['top-lists'][wild.list]
    wildcard_constraints:
        list="(umbrella-1m|alexa-1m)"
    shell: """
        wget -q {params.url} --output-document=/dev/stdout | zcat - > {output.real}
        ln --symbolic --relative {output.real} {output.link}
        """


rule download_majestic_top_list:
    """Download the majestic top 1-million list."""
    output:
        link="results/all-domains/majestic-1m.csv",
        real=f"results/all-domains/majestic-1m-{_TODAY}.csv"
    params:
        url=lambda wild: config['top-lists']['majestic-1m']
    shell: """
        wget -q {params.url} --output-document={output.real}
        ln --symbolic --relative {output.real} {output.link}
        """


rule merge_top_lists:
    """Identify the 'unique' domains in the top lists."""
    input:
        majestic="results/all-domains/majestic-1m.csv",
        alexa="results/all-domains/alexa-1m.csv",
        umbrella="results/all-domains/umbrella-1m.csv",
        tlds="results/all-domains/tlds-alpha-by-domain.txt"
    output:
        "results/all-domains/unique-top-list.csv"
    shell: """
        awk -F, 'BEGIN {{OFS=","}} NR != 1 {{print $1,$3}}' {input.majestic} \
            | awk -F, '{{print $2}}' - {input.alexa} {input.umbrella} \
            | tr -d '\r' \
            | sort | uniq -u | shuf \
            | scripts/filter-domain-list --tlds={input.tlds} > {output}
        """
