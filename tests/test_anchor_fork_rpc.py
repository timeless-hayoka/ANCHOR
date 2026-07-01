from __future__ import annotations

from pathlib import Path

import anchor_fork_rpc as fork_rpc


def test_resolve_mainnet_fork_url_prefers_environment(monkeypatch, tmp_path: Path):
    dvd_root = tmp_path / "dvd"
    dvd_root.mkdir()
    (dvd_root / ".env").write_text("MAINNET_FORKING_URL=https://dvd.example/rpc\n", encoding="utf-8")
    monkeypatch.setenv("MAINNET_FORKING_URL", "https://env.example/rpc")
    url, source = fork_rpc.resolve_mainnet_fork_url(dvd_root=dvd_root, anchor_root=tmp_path)
    assert url == "https://env.example/rpc"
    assert source == "environment"


def test_classify_fork_log_detects_publicnode_archive_block():
    sample = 'Archive requests require a personal token. Get one at: https://www.allnodes.com/publicnode'
    assert fork_rpc.classify_fork_log(sample) == "archive_token_required"


def test_mask_rpc_url_redacts_token_suffix():
    masked = fork_rpc.mask_rpc_url("https://ethereum.publicnode.com/secret-token-value")
    assert masked == "https://ethereum.publicnode.com/***"


def test_fork_url_is_publicnode_without_token():
    assert fork_rpc.fork_url_is_publicnode_without_token("https://ethereum.publicnode.com") is True
    assert fork_rpc.fork_url_is_publicnode_without_token("https://ethereum.publicnode.com/token123") is False
