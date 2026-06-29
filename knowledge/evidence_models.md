# Evidence & Finding Models

## Finding record (analysis layer)

Minimum fields for interchange inside ANCHOR:

```json
{
  "tool": "slither",
  "rule_id": "reentrancy-eth",
  "level": "warning",
  "message": "Reentrancy in withdraw()",
  "file_path": "src/Vault.sol",
  "start_line": 42,
  "snippet": "...",
  "dedup_key": "sha256:...",
  "cluster_id": "c-0192",
  "validation": {
    "status": "review",
    "confidence": 0.62,
    "reasons": ["code_flow present", "economic context medium"]
  }
}
```

## Outcome ledger event (promotion layer)

Append-only JSONL at `outcomes/ledger.jsonl`:

```json
{
  "timestamp": "2026-06-29T12:00:00Z",
  "type": "finding",
  "status": "accepted",
  "title": "Unprotected withdrawal",
  "links": {
    "benchmark": "run-id",
    "artifact": "benchmarks/.../benchmark.json"
  },
  "lesson": "Access control missing on external call path"
}
```

Supported `type`: benchmark, pr, issue, finding.  
Supported `status`: open, published, triaged, accepted, rejected, patched, merged.

## Promotion ladder

```text
DETECTED -> CORRELATED -> REPRODUCED_REAL
```

Server constant `LADDER` in `anchor_server.py` — do not promote verbally beyond the stored validation state.

## Evidence bundle (export)

From `anchor_storage.py`:

- `storage.json` manifest
- artifact paths (SARIF, logs, benchmark.json)
- optional Ed25519 signature via `anchor_signing_key.pem`

## Schema rules

1. Hypothesis fields (`future_state`, economic scores) are **annotations**, not ledger facts.
2. Only Forge-verified reproduction elevates to `REPRODUCED_REAL`.
3. Council rejection must write a ledger row with `status: rejected` and a reason string.
4. Never mutate ledger history; append corrections as new events.
