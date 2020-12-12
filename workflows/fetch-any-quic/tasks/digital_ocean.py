"""Tasks for managing droplets on digital ocean."""
import re
from invoke import task

from . import build_image

REGIONS = ('fra1', 'nyc3', 'blr1')
SSH_PUBKEY = "TO_BE_ADDED"
DEFAULT_DROPLET_PREFIX = "wg-gateway"
API_TOKEN = "TO_BE_ADDED"


@task
def rm_gateways(ctx, gateway_prefix=DEFAULT_DROPLET_PREFIX):
    """Remove all machines with a gateway prefix."""
    ctx.run(
        'docker-machine rm $('
        'docker-machine ls --filter "name=%s" --format "{{ .Name }}"'
        ')' % gateway_prefix, echo=True)


@task
def list_ips(ctx, gateway_prefix=DEFAULT_DROPLET_PREFIX):
    """List the public IP addresses of each of the gateways."""
    result = ctx.run('docker-machine ls --filter "name=%s" '
                     '--format "{{ .Name }}: {{ .URL }}"' % gateway_prefix,
                     hide="stdout")
    result = result.stdout.replace("tcp://", "")
    print(re.compile(r":\d+$", re.MULTILINE).sub("", result).strip())


def _get_gateways(ctx, gateway_prefix):
    return ctx.run(
        'docker-machine ls --filter "name=%s" --format "{{ .Name }}"'
        % gateway_prefix, hide="stdout"
    ).stdout.strip().split("\n")


@task
def ls_containers(ctx, gateway_prefix=DEFAULT_DROPLET_PREFIX):
    """List all containers running on each droplet."""
    machines = _get_gateways(ctx, gateway_prefix)
    for machine_name in machines:
        ctx.run(f"eval $(docker-machine env {machine_name}) "
                "&& docker container ls --all", echo=True)
        print("")


@task
def create_droplet(ctx, name, region, size="s-1vcpu-1gb"):
    """Create a digital ocean droplet."""
    options = {
        "image": "ubuntu-20-04-x64", "region": region,
        "access-token": API_TOKEN, "size": size, "tags": "jsmith"
    }
    args = ["docker-machine create --driver digitalocean"]
    for key, value in options.items():
        args += ["--digitalocean-" + key, value]
    args += [name]

    ctx.run(" ".join(args))


@task
def create_gateway_droplets(
    ctx, regions=REGIONS, gateway_prefix=DEFAULT_DROPLET_PREFIX
):
    """Create a digital ocean droplet for each gateway region."""
    existing = set(_get_gateways(ctx, gateway_prefix))
    for region in regions:
        name = f"{gateway_prefix}-{region}"
        if name not in existing:
            create_droplet(ctx, name, region)


@task
def build_images(ctx, gateway_prefix=DEFAULT_DROPLET_PREFIX):
    """Build the gateway images on all remote machines."""
    gateways = _get_gateways(ctx, gateway_prefix)
    for gateway in gateways:
        build_image.build_wg_gateway(ctx, machine_name=gateway)


@task
def clean(ctx, gateway_prefix=DEFAULT_DROPLET_PREFIX):
    """Stop and remove all running containers."""
    machines = _get_gateways(ctx, gateway_prefix)
    for machine_name in machines:
        ctx.run(f"eval $(docker-machine env {machine_name}) "
                "&& docker stop $(docker ps -aq) && docker rm $(docker ps -aq)",
                echo=True, hide="stderr", warn=True)
        print("")


@task
def provision(ctx, gateway_prefix=DEFAULT_DROPLET_PREFIX):
    """Create, provision, and build the docker images on remote
    gateways.
    """
    for gateway in _get_gateways(ctx, gateway_prefix):
        ctx.run(f"docker-machine ssh {gateway} "
                f"'bash -c \"cat - >> ~/.ssh/authorized_keys\"' < {SSH_PUBKEY}",
                echo=True)
        build_image.build_wg_gateway(ctx, machine_name=gateway)
