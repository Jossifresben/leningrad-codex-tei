"""Tests for the vendor-seed stage."""

from __future__ import annotations

import hashlib
import json

import pytest

from leningrad_codex_tei.stages.vendor_seed import vendor_seed


def _bad_seed(payload: bytes):
    return lambda url: (
        json.dumps({"sha": SHA}).encode() if "api.github.com" in url else payload
    )


SHA = "0123456789abcdef0123456789abcdef01234567"


def _fetcher(seed_fixture: dict, calls: list[str] | None = None):
    def fetcher(url: str) -> bytes:
        if calls is not None:
            calls.append(url)
        if url.startswith("https://api.github.com/"):
            return json.dumps({"sha": SHA}).encode()
        return json.dumps(seed_fixture).encode()

    return fetcher


def test_vendor_seed_writes_pinned_seed(config, seed_fixture: dict) -> None:
    calls: list[str] = []
    fetcher = _fetcher(seed_fixture, calls)

    info = vendor_seed(config, fetcher=fetcher)

    assert config.paths.seed.exists()
    assert json.loads(config.paths.seed.read_text(encoding="utf-8")) == seed_fixture
    expected = hashlib.sha256(json.dumps(seed_fixture).encode()).hexdigest()
    assert info["sha256"] == expected
    assert info["records"] == 1

    assert info["ref"] == "deadbee"
    assert info["commit"] == SHA

    assert len(calls) == 2
    assert calls[0].endswith("/repos/example/codex-index-leningrad/commits/deadbee")
    assert SHA in calls[1]
    assert calls[1].endswith("/UXLC-utils-sparse/data/lci_recs.json")


def test_vendor_seed_skips_resolving_a_full_sha(config, seed_fixture: dict) -> None:
    config.seed.commit = SHA
    calls: list[str] = []
    info = vendor_seed(config, fetcher=_fetcher(seed_fixture, calls))
    assert info["commit"] == SHA
    assert len(calls) == 1
    assert "api.github.com" not in calls[0]


def test_vendor_seed_rejects_unresolvable_ref(config) -> None:
    with pytest.raises(ValueError, match="cannot resolve"):
        vendor_seed(config, fetcher=lambda url: b'{"message": "Not Found"}')


def test_vendor_seed_creates_parent_directories(config, seed_fixture: dict) -> None:
    info = vendor_seed(config, fetcher=_fetcher(seed_fixture))
    assert config.paths.seed.parent.exists()


def test_vendor_seed_rejects_invalid_json(config) -> None:
    with pytest.raises(ValueError):
        vendor_seed(config, fetcher=_bad_seed(b"{not json"))


def test_vendor_seed_rejects_missing_body(config) -> None:
    with pytest.raises(ValueError):
        vendor_seed(config, fetcher=_bad_seed(b'{"header": {}}'))
