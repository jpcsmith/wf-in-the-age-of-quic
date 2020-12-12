"""Utilities for working with wireguard."""
# pylint: disable=too-few-public-methods
from typing import Optional, List, Sequence

import sh
from typing_extensions import Final


DEFAULT_ENDPOINT_PORT: Final = 51888


class BasicConfig:
    """Basic configuration for a wireguard peer."""
    def __init__(
        self,
        address: str,
        private_key: Optional[str] = None,
        public_key: Optional[str] = None,
        endpoint: Optional[str] = None
    ):
        if private_key is None:
            self.private_key = sh.wg("genkey").strip()
            self.public_key = sh.wg("pubkey", _in=self.private_key).strip()
        else:
            self.private_key = private_key
            assert public_key is not None
            self.public_key = public_key
        self.address = address
        self.endpoint = endpoint


class ClientConfig(BasicConfig):
    """Configuration for the client."""
    def __init__(
        self, *args, gateway: Optional["GatewayConfig"] = None, **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.gateway = gateway

    def to_string(self) -> str:
        """Create and return the config for the client with the current
        gateway.
        """
        assert self.gateway and self.gateway.endpoint and self.address
        config_lines = [
            "[Interface]",
            f"PrivateKey = {self.private_key}",
            f"Address = {self.address}/32",
            "",
            "[Peer]",
            f"PublicKey = {self.gateway.public_key}",
            f"Endpoint = {self.gateway.endpoint}:{DEFAULT_ENDPOINT_PORT}",
            "AllowedIPs = 0.0.0.0/0",
            ""
        ]
        return "\n".join(config_lines)

    def __repr__(self) -> str:
        return (f"ClientConfig(address={self.address!r},"
                f"public_key={self.public_key!r},endpoint={self.endpoint!r},"
                f"gateway={self.gateway!r})")


class GatewayConfig(BasicConfig):
    """Configuration for the gateway."""
    def __init__(
        self,
        endpoint: str,
        clients: Optional[List[ClientConfig]] = None,
        **kwargs
    ):
        super().__init__("10.0.0.1", endpoint=endpoint, **kwargs)
        self.clients: List[ClientConfig] = []
        self.set_clients(clients or [])

    def set_clients(self, clients: Sequence[ClientConfig]):
        """Set the clients to this gateway, assigning them an address in
        the range managed by the gateway.
        """
        self.clients.clear()
        for client in clients:
            client.gateway = self
            self.clients.append(client)

    def to_string(self) -> str:
        """Create and return the config for the gateway with the current
        set of clients.
        """
        config_lines = [
            "[Interface]",
            f"PrivateKey = {self.private_key}",
            f"Address = {self.address}/24",
            "ListenPort = 51888",
            "PostUp = iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE",
            "PostDown = iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE",
            ""
        ]
        for client in self.clients:
            config_lines.extend([
                "[Peer]",
                f"PublicKey = {client.public_key}",
                f"AllowedIPs = {client.address}/32",
                ""
            ])
        return "\n".join(config_lines)
