"""Tests for the wireguard module."""
from wireguard import GatewayConfig, ClientConfig


def test_gateway_config_no_peers():
    """It should correctly create the gateway configuration with no
    peers.
    """
    config = GatewayConfig(endpoint="localhost", private_key="privkey",
                           public_key="pubkey")
    assert config.to_string() == "\n".join([
        "[Interface]",
        "PrivateKey = privkey",
        "Address = 10.0.0.1/24",
        "ListenPort = 51888",
        "PostUp = iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE",
        "PostDown = iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE",
        ""
    ])


def test_gateway_config_peers():
    """It should correctly create the gateway config with peers.
    """
    config = GatewayConfig(endpoint="localhost", private_key="privkey",
                           public_key="pubkey")
    config.set_clients([
        ClientConfig(address="10.0.0.2", private_key="client1_privkey",
                     public_key="client1_pubkey"),
        ClientConfig(address="10.0.0.3", private_key="client2_privkey",
                     public_key="client2_pubkey")
    ])
    assert config.to_string() == "\n".join([
        "[Interface]",
        "PrivateKey = privkey",
        "Address = 10.0.0.1/24",
        "ListenPort = 51888",
        "PostUp = iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE",
        "PostDown = iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE",
        "",
        "[Peer]",
        "PublicKey = client1_pubkey",
        "AllowedIPs = 10.0.0.2/32",
        "",
        "[Peer]",
        "PublicKey = client2_pubkey",
        "AllowedIPs = 10.0.0.3/32",
        "",
    ])


def test_client_config():
    """Should create correct configs for the clients."""
    config = GatewayConfig(endpoint="localhost", private_key="privkey",
                           public_key="pubkey")
    client_configs = [
        ClientConfig(address="10.0.0.2", private_key="client1_privkey",
                     public_key="client1_pubkey"),
        ClientConfig(address="10.0.0.3", private_key="client2_privkey",
                     public_key="client2_pubkey")
    ]
    config.set_clients(client_configs)

    assert client_configs[0].to_string() == "\n".join([
        "[Interface]",
        f"PrivateKey = client1_privkey",
        "Address = 10.0.0.2/32",
        "",
        "[Peer]",
        "PublicKey = pubkey",
        "Endpoint = localhost:51888",
        "AllowedIPs = 0.0.0.0/0",
        ""
    ])
    assert client_configs[1].to_string() == "\n".join([
        "[Interface]",
        f"PrivateKey = client2_privkey",
        "Address = 10.0.0.3/32",
        "",
        "[Peer]",
        "PublicKey = pubkey",
        "Endpoint = localhost:51888",
        "AllowedIPs = 0.0.0.0/0",
        ""
    ])
