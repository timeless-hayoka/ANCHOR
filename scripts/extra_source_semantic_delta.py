"""Conservative Solidity token comparison for source-version triage.

Whitespace and comments are ignored; strings, identifiers and symbols remain.
Token equality does not establish compiler or deployed-bytecode equivalence.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import re
from typing import Any

_TOKEN = re.compile(
    r'(?P<space>\s+)'
    r'|(?P<line>//[^\n]*)'
    r'|(?P<block>/\*[\s\S]*?\*/)'
    r'|(?P<string>"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\')'
    r'|(?P<identifier>[A-Za-z_$][A-Za-z0-9_$]*)'
    r'|(?P<number>0[xX][0-9a-fA-F_]+|[0-9][0-9_]*)'
    r'|(?P<operator>\S)',
)


def solidity_tokens(source: str) -> list[str]:
    """Lex tokens while preserving quoted strings and detecting malformed input."""
    tokens: list[str] = []
    pos = 0
    while pos < len(source):
        match = _TOKEN.match(source, pos)
        if not match:
            raise ValueError(f"Unrecognized source near offset {pos}")
        kind = match.lastgroup
        if kind == "operator" and match.group() in {'"', "'"}:
            raise ValueError(f"Unterminated string near offset {pos}")
        if kind == "operator" and source[pos:pos + 2] == "/*":
            raise ValueError(f"Unterminated block comment near offset {pos}")
        if kind not in {"space", "line", "block"}:
            tokens.append(match.group())
        pos = match.end()
    return tokens


def compare_solidity_source(local: str, verified: str) -> dict[str, Any]:
    """Return bounded token-difference metadata without source or security claims."""
    try:
        left = solidity_tokens(local)
        right = solidity_tokens(verified)
    except ValueError as exc:
        return {"classification": "INDETERMINATE", "reason": str(exc)}
    same = left == right
    output: dict[str, Any] = {
        "classification": "TOKEN_EQUIVALENT" if same else "TOKEN_DIFFERENT",
        "local_token_count": len(left),
        "verified_token_count": len(right),
        "local_token_sha256": hashlib.sha256(json.dumps(left, separators=(",", ":")).encode()).hexdigest(),
        "verified_token_sha256": hashlib.sha256(json.dumps(right, separators=(",", ":")).encode()).hexdigest(),
        "security_conclusion": "NONE",
    }
    if not same:
        hunks = [
            item for item in difflib.SequenceMatcher(None, left, right, autojunk=False).get_opcodes()
            if item[0] != "equal"
        ]
        output["token_hunk_count"] = len(hunks)
        output["token_hunks_first_12"] = [
            {"kind": kind, "local_token_range": [a + 1, b], "verified_token_range": [c + 1, d]}
            for kind, a, b, c, d in hunks[:12]
        ]
    return output
