"""Shared test setup.

Keep tests independent of locally downloaded data: `make demo-stops` writes a real VBB
network to data/vbb/, which would otherwise change commute results on machines that have
run it. Tests that need a network pass one in explicitly (see tests/gtfs_fixture.py).
"""

import pytest

import enrich.commute as commute


@pytest.fixture(autouse=True)
def no_local_transit_network(monkeypatch):
    monkeypatch.setattr(commute, "get_network", lambda: None)
