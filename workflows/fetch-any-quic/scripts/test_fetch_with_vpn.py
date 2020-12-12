"""Tests for fetch_with_vpn.py"""
import logging
from collections import Counter

import wireguard
from fetch_with_vpn import batch, BrowserPeer, SSHNode


def test_batch():
    """It should divide the remaining sets into the smallest sized
    batches that will collect everything.
    """
    counters = {
        "a.com": Counter({"Q043": 40, "Q046": 10, "tcp": 100}),
        "b.com": Counter({"Q043": 30, "Q046": 40, "tcp": 110}),
        "c.com": Counter({"Q043": 20, "Q046": 30, "tcp": 90}),
    }
    assert batch(counters, n_batches=1) == Counter(
        {"Q043": 40, "Q046": 40, "tcp": 110})
    assert batch(counters, n_batches=2) == Counter(
        {"Q043": 20, "Q046": 20, "tcp": 55})
    assert batch(counters, n_batches=4) == Counter(
        {"Q043": 10, "Q046": 10, "tcp": 28})


def test_batch_min_count():
    """Each batch should collect at least 1 sample for any version that
    is not zero.
    """
    assert batch({
        "a.com": Counter({"Q043": 5, "Q046": 3, "tcp": 1}),
    }, n_batches=4) == Counter({"Q043": 2, "Q046": 1, "tcp": 1})


def test_batch_empty():
    """It should skip batching if there are none remaining."""
    assert batch({
        "a.com": Counter({"Q043": 0, "Q046": 0, "tcp": 0}),
        "b.com": Counter({"Q043": 0, "Q046": 0, "tcp": 0}),
    }, n_batches=4) == Counter()


def test_browser_peer_sanity(caplog):
    """Sanity check that it can be constructed."""
    caplog.set_level(logging.INFO)
    BrowserPeer(wireguard.ClientConfig("10.0.0.1"), [], "/tmp")
