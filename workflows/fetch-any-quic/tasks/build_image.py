"""Tasks for building docker images."""
from invoke import task


@task(name="client")
def build_client(ctx, tag="fetch-client", build_context="./docker/client"):
    """Build the client image."""
    ctx.run(f"docker build --tag {tag} {build_context}", echo=True)


@task(name="wg-gateway")
def build_wg_gateway(ctx, tag="wg-gateway", build_context="./docker/wg-gateway",
                     machine_name=""):
    """Build the wireguard gateway image."""
    prefix = (f'eval "$(docker-machine env {machine_name})" && ' if machine_name
              else "")
    ctx.run(prefix + f"docker build --tag {tag} {build_context}", echo=True)
