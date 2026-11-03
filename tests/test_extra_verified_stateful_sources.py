"""Fail-closed controls for materializing Sourcify verified sources."""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "extra_verified_stateful_sources", ROOT / "scripts/extra_verified_stateful_sources.py"
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

POOL = "contracts/lendingpool/LendingPool.sol"


def test_rejects_wrong_target_and_compiler():
    bad = {
        "chainId": "10",
        "address": mod.ADDRESS,
        "runtimeMatch": "match",
        "compilation": {"language": "Solidity", "compilerVersion": "0.8.20"},
        "stdJsonInput": {"language": "Solidity", "sources": {}},
        "runtimeBytecode": {"recompiledBytecode": "0x6000"},
    }
    with pytest.raises(ValueError):
        mod.prepare_files(bad)


def test_write_never_replaces_existing_tree(tmp_path):
    dest = tmp_path / "sources"
    names = {POOL: "contract LendingPool {}"}
    report = mod.write_sources(dest, names)
    assert report["state"] == "VERIFIED_SOURCE_TREE_MATERIALIZED"
    assert report["file_count"] == 1
    assert (dest / POOL).read_text() == names[POOL]
    with pytest.raises(ValueError):
        mod.write_sources(dest, names)


def test_bad_deployment_refuses_materialization(tmp_path, capsys):
    bad = tmp_path / "source.json"
    outdir = tmp_path / "verified"
    bad.write_text(json.dumps({"chainId": "8453"}))
    assert mod.main(["--snapshot", str(bad), "--outdir", str(outdir)]) == 2
    assert not outdir.exists()
    assert "NOT_MATERIALIZED" in capsys.readouterr().out
