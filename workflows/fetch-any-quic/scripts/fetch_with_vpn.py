#!/usr/bin/env python3
"""Usage: fetch-with-vpn [-c addr ...] [options] VERSION_CTR [URLFILE] [OUTFILE]

VERSION_CTR is A mapping from versions to repetitions.  Has the form
"v1=v1count,v2=v2count,v3=v3count" to specify the number of
repetitions per individual version.

Options:
    --gateway-node user@ipaddress
        Run the gateway on the SSH node located at ipaddress with
        the specified user.  Defaults to running as the current user
        on the localhost.

    --gateway-endpoint ip_addr
        An IPv4 address at which the gateway deploed on the
        gateway-node will be reachable.  Defaults to the ipaddress
        portion of the gateway-node.

    -c user@ipaddress, --client-node user@ipaddress
        Run a browser client on the SSH node located at ipaddress with
        the specified user.  Defaults to running as the current user
        on the localhost.  Allowed multiple times.

    --n-clients n
        Only valid when -c is provided once.  Create n clients on the
        node specified by -c [default: 1].

    --checkpoint-dir dir
        Use dir, located on this host, for checkpointing.  Data from
        the clients are saved to this directory locally, regardless of
        where they are running.  Meaningful checkpointing is disabled
        if absent.

    --n-batches n
        Split the collection for each client into n batches for
        checkpointing [default: 4].

    --snaplen len
        Truncate captured packets to len bytes.  See fetch-websites for
        default.

    --delay n
        Wait n seconds between each request for the same URL.  See
        fetch-websites for default.

    --max-attempts n
        Stop trying to collect a URL after n sequential failures
        [default: 3].

    --attempts-per-protocol
        Retry other protocols on max-attempts failures.

    --driver-path path
        Use Chromedriver binary at path.  See fetch-websites for
        default.

    --help
        Display this message and exit.
"""
# pylint: disable=too-few-public-methods
# pylint: disable=too-many-instance-attributes
# pylint: disable=too-many-arguments
import os
import uuid
import math
import time
import pathlib
import asyncio
import tempfile
import logging
import urllib.parse
import contextlib
from typing import Sequence, Optional, Dict, Iterable, IO, List, Union
from collections import Counter

import doceasy
from doceasy import Use, Or, AtLeast, And
import sh
from sh import docker  # pylint: disable=no-name-in-module
from typing_extensions import TypedDict

import wireguard
from lab.fetch_websites import filter_by_checkpoint, decode_result

_LOGGER = logging.getLogger(pathlib.Path(__file__).name)


class SSHNode:
    """A thin wrapper around SSH and docker.  Assumes that the host
    system has passwordless SSH access to the specified node.

    Calling the constructor without a node_address runs the commands on
    localhost.  Otherwise node_address in any form accepatable by ssh,
    such as user@host.
    """
    def __init__(self, node_address: Optional[str] = None):
        self.node_address = node_address

    def is_localhost(self) -> bool:
        """Return true if the node is simply the localhost, false
        otherwise.
        """
        return self.node_address is None

    @property
    def public_ip(self) -> str:
        """Return the public ip portion of the node address.  Requires
        that the node_address be in the format host@ip.
        """
        assert self.node_address is not None
        assert "@" in self.node_address
        return self.node_address.split("@")[1]

    def docker(self, *args, **kwargs):
        """Perform a docker command remotely, using SSH to access the
        remote docker daemon.
        """
        if self.is_localhost():
            return docker(*args, **kwargs)
        return docker("--host", f"ssh://{self.node_address}", *args, **kwargs)

    def get_text(self, filename: str, _iter=None):
        """Get the text from filename on the node.  The argument _iter
        is the same as in the sh library.
        """
        if self.is_localhost():
            return sh.cat(filename, _iter=_iter)
        return sh.scp(f"{self.node_address}:{filename}", "/dev/stdout",
                      _iter=_iter)

    def put_text(self, text: str, filename: str) -> str:
        """Write the text to file indicated by filename on the remote
        server.  Return filename.
        """
        with tempfile.NamedTemporaryFile(mode="w") as temp_conf:
            temp_conf.write(text)
            temp_conf.flush()
            self.put(temp_conf.name, filename)
        return filename

    def put(self, local: str, remote: str) -> str:
        """Copy local to remote on the remote host.  Return remote."""
        if self.is_localhost() and local != remote:
            sh.cp(local, remote)
        elif not self.is_localhost():
            sh.scp(local, f"{self.node_address}:{remote}")
        return remote

    def __repr__(self) -> str:
        return f"SSHNode(node_address={self.node_address!r})"


def _make_counter(versions: Sequence[str], repetitions: int) -> Counter:
    """Create a counter from a possibly repeating sequence of keys.
    The resulting counter will have repetitions counts per non-unique
    value in versions.
    """
    counter: Counter = Counter()
    for version in versions:
        counter[version] += repetitions
    return counter


def batch(remaining: Dict[str, Counter], n_batches: int) -> Counter:
    """We cannot specify fine-grained collection, so we assume that
    domains were in parallel and identify the least number across
    each version that we can collect.  If this minimum number for a
    version is zero, that version is dropped from the collection.
    """
    counter: Counter = Counter()
    for version_ctr in remaining.values():
        # Update counter to max(counter[ver], version_ctr[ver])
        counter |= version_ctr

    # Remove zero and negative counts
    counter = +counter

    return Counter({
        key: math.ceil(value / n_batches)
        for key, value in counter.items()
    })


class FetchOptions(TypedDict):
    """Options that can be forwarded onto the fetch-websites script.
    May be used within this script.
    """
    driver_path: str
    delay: float
    max_attempts: int
    snaplen: Optional[int]
    version_ctr: Counter
    attempts_per_protocol: bool


def _filter_urls(urls: Iterable[str]) -> Iterable[str]:
    for url in urls:
        if urllib.parse.urlparse(url).port is None:
            yield url
        else:
            _LOGGER.warning("Dropping %s as it has a port.", url)


class BrowserPeer:
    """A client for collecting traces.

    Multiple BrowserPeers can coexist on the same SSHNode.
    """
    class _LogAdapter(logging.LoggerAdapter):
        def process(self, msg, kwargs):
            return "[%s] %s" % (self.extra["tag"], msg), kwargs

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        wg_conf: wireguard.ClientConfig,
        urls: Iterable[str],
        checkpoint_dir: Union[str, pathlib.Path],
        node: Optional[SSHNode] = None,
        n_batches: int = 1,
        **kwargs
    ):
        super().__init__()
        self._uuid = uuid.uuid4()
        self._logger = self._LogAdapter(
            _LOGGER, {"tag": f"Client@{wg_conf.address}"})
        self.wg_conf = wg_conf
        self._logger.info("Using wireguard config: %s", self.wg_conf)
        self.node = node or SSHNode()
        self._logger.info("Assigned to node %s", self.node)
        self.checkpoint_path = pathlib.Path(
            checkpoint_dir, self.slug).with_suffix(".state")
        self._logger.info("Writing state to '%s'", self.checkpoint_path)
        self._filenames = {
            "checkpoint": str(self.checkpoint_path),
            "bulk-log": str(pathlib.Path(checkpoint_dir, self.slug)
                            .with_suffix(".log")),
            "remote-config": f"/tmp/{self.slug}-{self._uuid.hex}-wg0.conf"
        }
        self._logger.info("Using the following files: %s", self._filenames)

        self.urls = list(_filter_urls(urls))
        self._fetch_options: FetchOptions = kwargs  # type: ignore
        self.n_batches = n_batches

    @property
    def slug(self) -> str:
        """Return a slug for this peer that is suitable for use as a
        filename.  Should be persistent across multiple rules with the
        same input.
        """
        filesafe_ip = self.wg_conf.address.replace(".", "_")
        return f"peer-{filesafe_ip}"

    def _recover_from_checkpoint(self) -> Dict[str, Counter]:
        if self.checkpoint_path.is_file():
            with self.checkpoint_path.open(mode="r") as checkpoint_file:
                checkpoint = [decode_result(line, full_decode=False)
                              for line in checkpoint_file]
            self._logger.info("Loaded %d entries from checkpoint file '%s'",
                              len(checkpoint), self.checkpoint_path)
        else:
            self._logger.info("Checkpoint file '%s' does not exist. Skipping "
                              "checkpoint usage.", self.checkpoint_path)
            checkpoint = []

        result = filter_by_checkpoint(
            self.urls, checkpoint, self._fetch_options["version_ctr"],
            max_attempts=self._fetch_options["max_attempts"])
        self._logger.info("%d URLs remaining to be collected.", len(result))
        return result

    async def run(self) -> pathlib.Path:
        """Collect traces of the URLs and return a path to the
        checkpoint file containing the results.
        """
        # Determine the URLs still left to collected
        remaining = self._recover_from_checkpoint()

        # Batch the collection. We batch the collection even with checkpointing
        # because creating new docker containers from time to time helps to
        # prevent leakage of chrome browser or state across collections.
        batch_ctr = batch(remaining, self.n_batches)
        if not batch_ctr:
            return self.checkpoint_path

        self.node.put_text(
            self.wg_conf.to_string(), self._filenames["remote-config"])

        urls = list(remaining.keys())
        for _ in range(self.n_batches):
            await self._collect_batch(urls, batch_ctr)
        return self.checkpoint_path

    def _fetch_args(self, batch_ctr: Counter):
        args = ["--wireguard", self._filenames["remote-config"],
                "--version-ctr", doceasy.Mapping.to_string(batch_ctr),
                "--iface", "eth0",
                "--no-html"]
        for key in ("driver_path", "delay", "max_attempts", "snaplen"):
            if self._fetch_options[key] is not None:  # type: ignore
                arg = "--" + key.replace("_", "-")
                args += [arg, self._fetch_options[key]]  # type: ignore
        return args

    async def _collect_batch(self, urls: Sequence[str], batch_ctr: Counter):
        """Collect a single batch of the URLs.  Traces are written
        immediately to the state file.
        """
        with open(self.checkpoint_path, mode="a") as checkpoint_file:
            docker_fetch_websites = sh.Command("scripts/docker-fetch-websites")

            env = None
            if not self.node.is_localhost():
                env = os.environ.copy()
                env["DOCKER_HOST"] = f"ssh://{self.node.node_address}"

            self._logger.info("Collecting batch of %d urls, %s times.",
                              len(urls), batch_ctr)

            process = docker_fetch_websites(
                *self._fetch_args(batch_ctr),
                # Urls as input
                _in="\n".join(urls),
                # Append the output directly to the checkpoint file
                _out=checkpoint_file,
                # Write stderr, otherwise we lose the logs due to their length
                _err=self._filenames["bulk-log"],
                # Potentially override the environment for running remotely
                _env=env,
                # Run in the background, and dont print exceptions in the
                # background thread.
                _bg=True, _bg_exc=False)

            try:
                # Sleep for a short duration initially to allow the process to
                # immediately exit
                await asyncio.sleep(2)

                while process.is_alive():
                    # Check in on the process occasionally. This runs for a long
                    # time, usually > 30 mins, so an extra 30s is nothing.
                    await asyncio.sleep(30)
                process.wait()
            except asyncio.CancelledError:
                self._logger.info("Received CancelledError. Cleaning up.")

                if process.is_alive():
                    self._logger.info("Terminating the subprocess.")
                    process.terminate()

                with contextlib.suppress(sh.ErrorReturnCode):
                    self._logger.info("Waiting for the subprocess to exit.")
                    process.wait()

                raise
            self._logger.info("Batch collection complete.")

    def clear_checkpoint(self):
        """Remove the checkpoint file."""
        self.checkpoint_path.unlink()


class WireguardGateway:
    """A wireguard gateway.

    Assumes that it is the sole gateway running on the SSHNode.
    """
    start_delay: int = 3

    def __init__(
        self, wg_conf: wireguard.GatewayConfig, node: Optional[SSHNode] = None,
    ):
        super().__init__()
        self.wg_conf = wg_conf
        self.node = node or SSHNode()
        self._container_id: Optional[str] = None
        self._logger = _LOGGER

    async def start(self) -> "WireguardGateway":
        """Start the VPN gateway."""
        docker_wg_gateway = sh.Command("./scripts/docker-wg-gateway")
        if not self.node.is_localhost():
            docker_wg_gateway = docker_wg_gateway.bake(_env={
                "DOCKER_HOST": f"ssh://{self.node.node_address}",
                **os.environ
            })

        remote_conf_path = self.node.put_text(
            self.wg_conf.to_string(), "/tmp/wg0.conf")
        self._container_id = docker_wg_gateway("start", remote_conf_path)
        assert self._container_id is not None
        self._container_id = self._container_id.strip()

        self._logger.info("Waiting for the gateway to start.")
        await asyncio.sleep(self.start_delay)
        assert bool(self.node.docker(
            "container", "inspect", "--format", "{{ .State.Running }}",
            self._container_id
        ))

        return self

    async def stop(self) -> None:
        """Stop the VPN server if it is running."""
        if self._container_id is not None:
            self.node.docker("stop", self._container_id)
            self.node.docker("rm", self._container_id)
            self._container_id = None

    async def __aenter__(self) -> "WireguardGateway":
        return await self.start()

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.stop()


class TraceCollectionExperiment:
    """Collect traffic traces of the specified URLs."""
    def __init__(
        self,
        gateway_node: SSHNode,
        client_nodes: Sequence[SSHNode],
        urls: Sequence[str],
        checkpoint_dir: Optional[pathlib.Path],
        n_batches: int,
        gateway_endpoint: str = "",
        **fetch_options,
    ):
        checkpoint_dir = checkpoint_dir or pathlib.Path(
            "/tmp/checkpoints-{:d}".format(time.perf_counter_ns()))
        checkpoint_dir.mkdir(parents=True, exist_ok=True)

        self.gateway = WireguardGateway(
            wireguard.GatewayConfig(gateway_endpoint), gateway_node)
        self.clients = [
            BrowserPeer(
                wireguard.ClientConfig(address=f"10.0.0.{i+2}"),
                urls[i::len(client_nodes)],
                checkpoint_dir,
                node=node,
                n_batches=n_batches,
                **fetch_options
            ) for i, node in enumerate(client_nodes)
        ]
        # TODO: Make this less error prone
        self.gateway.wg_conf.set_clients([c.wg_conf for c in self.clients])

    async def run(self) -> List[str]:
        """Perform the experiment and return a list of the files
        that can be combined for the full results.
        """
        async with self.gateway:
            tasks = [asyncio.create_task(c.run()) for c in self.clients]
            try:
                gathered_tasks = asyncio.gather(*tasks)
                client_checkpoints = await gathered_tasks
            except Exception:
                gathered_tasks.cancel()

                # We will need to re-run due to the failure. Any completed
                # tasks will persist until the next run due to the
                # checkpointing
                await asyncio.gather(*tasks, return_exceptions=True)
                raise

        _LOGGER.info("Clients sucessfully ran, returning their output.")
        return [str(checkpoint) for checkpoint in client_checkpoints]

    def clear_checkpoint(self) -> None:
        """Remove the checkpoints."""
        for client in self.clients:
            client.clear_checkpoint()


async def main(
    urlfile,
    outfile: IO[str],
    gateway_node: SSHNode,
    client_node: Sequence[SSHNode],
    n_clients: int,
    checkpoint_dir: Optional[pathlib.Path],
    gateway_endpoint: Optional[str],
    **kwargs
):
    """Script entry pooint."""
    logging.basicConfig(
        format='[%(asctime)s] %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO)
    _LOGGER.info("Running script.")

    # Either we have a 1 repetiton per node, or multiple client nodes
    client_node = list(client_node) or [SSHNode(), ]
    assert n_clients == 1 or len(client_node) == 1
    if len(client_node) == 1 and n_clients > 1:
        for _ in range(n_clients - 1):
            client_node.append(SSHNode(client_node[0].node_address))

    urls = [url for (url, ) in urlfile]

    gateway_endpoint = gateway_endpoint or gateway_node.public_ip
    experiment = TraceCollectionExperiment(
        gateway_node, client_node, urls, checkpoint_dir=checkpoint_dir,
        gateway_endpoint=gateway_endpoint, **kwargs,
    )

    checkpoint_filenames = await experiment.run()
    sh.cat(checkpoint_filenames, _out=outfile)

    experiment.clear_checkpoint()


if __name__ == "__main__":
    asyncio.run(
        main(**doceasy.doceasy(__doc__, doceasy.Schema({
            "URLFILE": doceasy.CsvFile(mode="r", default="-"),
            "OUTFILE": doceasy.File(mode="w", default="-"),
            "VERSION_CTR": And(doceasy.Mapping(int), Use(Counter)),
            "--gateway-node": Use(SSHNode),
            "--gateway-endpoint": Or(None, str),
            "--client-node": list((Use(SSHNode), )),
            "--n-clients": And(Use(int), AtLeast(1)),
            "--checkpoint-dir": Or(None, Use(pathlib.Path)),
            "--driver-path": Or(None, str),
            "--delay": Or(None, Use(float)),
            "--max-attempts": Use(int),
            "--attempts-per-protocol": bool,
            "--snaplen": Or(None, Use(int)),
            "--n-batches": Use(int),
        }, ignore_extra_keys=True)))
    )
