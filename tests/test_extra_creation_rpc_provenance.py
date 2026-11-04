"""Offline deterministic coverage of the read-only creation provenance probe."""
import importlib.util
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "extra_creation_rpc_provenance", ROOT / "scripts/extra_creation_rpc_provenance.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _fixture(url, method, params, request_id):
    tx = {
        "blockNumber": hex(MODULE.CREATE_BLOCK),
        "from": MODULE.SENDER, "to": MODULE.FACTORY,
        "input": "0xf18efb45" + "00" * 448,
    }
    receipt = {"blockNumber": hex(MODULE.CREATE_BLOCK), "status": "0x1",
               "to": MODULE.FACTORY}
    data = {"eth_chainId": "0xa",
            "eth_getTransactionByHash": tx, "eth_getTransactionReceipt": receipt}
    if method == "eth_getCode":
        result = "0x" + ("60" * 8 if params[0] == MODULE.FACTORY else "61" * 8)
    elif method == "debug_traceTransaction":
        result = {
            "type": "CALL", "from": MODULE.SENDER, "to": MODULE.FACTORY,
            "calls": [{"type": "CREATE2", "from": MODULE.FACTORY,
                       "to": MODULE.VAULT, "input": "0x6000"}],
        }
    else:
        result = data[method]
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def test_probe_has_no_mainnet_write_method_or_storage_override():
    source = (ROOT / "scripts/extra_creation_rpc_provenance.py").read_text()
    assert 'read("eth_getTransactionByHash"' in source
    assert 'read("eth_getTransactionReceipt"' in source
    assert 'read("eth_getCode"' in source
    assert '"debug_traceTransaction"' in source
    assert 'eth_sendRawTransaction' not in source
    assert 'eth_sendTransaction' not in source
    assert '"eth_call"' in source
    assert "stateOverrides" not in source


def test_mocked_historical_trace_and_code_fingerprints_are_reproducible():
    with patch.object(MODULE, "rpc", side_effect=_fixture), patch.object(
        MODULE.shutil, "which", return_value=None
    ), patch.object(MODULE, "readonly_registry_observations", return_value={"status": "UNKNOWN"}):
        evidence = MODULE.collect("https://example.invalid")
    assert evidence["chain_id"] == 10
    assert evidence["factory_runtime_equal_across_blocks"] is True
    assert evidence["vault_runtime_equal_across_blocks"] is True
    assert evidence["trace"]["status"] == "AVAILABLE"
    types = [node["type"] for node in evidence["trace"]["summary"]["nodes"]]
    assert types == ["CALL", "CREATE2"]
    assert evidence["source_equivalence"] == "UNKNOWN"
    assert evidence["liquidation_eligibility"] == "UNKNOWN"


def test_wrong_chain_fails_closed():
    def wrong_chain(url, method, params, request_id):
        response = _fixture(url, method, params, request_id)
        if method == "eth_chainId":
            response["result"] = "0x1"
        return response
    with patch.object(MODULE, "rpc", side_effect=wrong_chain):
        try:
            MODULE.collect("https://example.invalid")
        except MODULE.ProvenanceError as exc:
            assert "not Optimism" in str(exc)
        else:
            raise AssertionError("must reject wrong chain")


def test_trace_unavailable_not_interpreted_as_no_delegation():
    def missing_trace(url, method, params, request_id):
        response = _fixture(url, method, params, request_id)
        if method == "debug_traceTransaction":
            return {"jsonrpc": "2.0", "id": request_id,
                    "error": {"code": -32601, "message": "method not found"}}
        return response
    with patch.object(MODULE, "rpc", side_effect=missing_trace), patch.object(
        MODULE.shutil, "which", return_value=None
    ), patch.object(MODULE, "readonly_registry_observations", return_value={"status": "UNKNOWN"}):
        evidence = MODULE.collect("https://example.invalid")
    assert evidence["trace"]["status"] == "UNAVAILABLE"
    assert evidence["source_equivalence"] == "UNKNOWN"


def test_trace_node_budget_and_full_input_redaction():
    huge = {"type": "CALL", "input": "0x" + "be" * 10000,
            "calls": [{"type": "DELEGATECALL", "input": "0xabcdef01"}] * 200}
    result = MODULE.trace_summary(huge)
    assert result["truncated"]
    assert len(result["nodes"]) == MODULE.MAX_TRACE_NODES
    assert "input" not in result["nodes"][0]
    assert "input_sha256" in result["nodes"][0]


def test_static_opcode_inventory_skips_immediate_bytes_and_flags_unverified_selectors():
    # PUSH4, then a real DELEGATECALL opcode; PUSH1 0xf4 data must be skipped.
    raw = "0x63f18efb4560f4f4" + "73" + "11" * 20 + "f5"
    inv = MODULE.opcode_inventory(raw)
    assert "0xf18efb45" in inv["push4_literals"]
    assert "0x" + "11" * 20 in inv["push20_literals"]
    assert inv["opcode_counts"]["DELEGATECALL"] == 1
    assert inv["opcode_counts"]["CREATE2"] == 1
    assert "do not prove" in inv["note"]


def test_archived_registry_snapshot_flags_absent_getters_unknown():
    with patch.object(MODULE, "method_selector", return_value="0xb93f9b0a"), patch.object(
        MODULE, "rpc", return_value={
            "jsonrpc": "2.0", "id": 10, "error": {"code": -32601, "message": "unavailable"}
        }
    ):
        result = MODULE.readonly_registry_observations(
            "https://example.invalid", MODULE.FACTORY, MODULE.CREATE_BLOCK, 10
        )
    assert result["status"] == "UNKNOWN"
    assert result["entries"] == {}
