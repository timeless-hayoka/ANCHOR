"""Resolve and validate archive-capable mainnet RPC URLs for fork benchmarks."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

PUPPET_V3_FORK_BLOCK = 15450164
CURVY_PUPPET_FORK_BLOCK = 20190356
DEFAULT_PROBE_BLOCK = PUPPET_V3_FORK_BLOCK
PUBLICNODE_DEFAULT = "https://ethereum.publicnode.com"
ARCHIVE_TOKEN_HINT = "Archive requests require a personal token"
ENV_KEY = "MAINNET_FORKING_URL"


def parse_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            values[key] = value
    return values


def resolve_mainnet_fork_url(
    *,
    dvd_root: Path | None = None,
    anchor_root: Path | None = None,
    environ: dict[str, str] | None = None,
) -> tuple[str | None, str]:
    """Return (url, source_label). Never log the full URL with secrets."""
    env = dict(os.environ if environ is None else environ)
    if env.get(ENV_KEY):
        return env[ENV_KEY], "environment"

    anchor_root = anchor_root or Path(__file__).resolve().parent
    dvd_root = dvd_root or Path(os.environ.get("ANCHOR_DVD_ROOT", "/home/crexs/damn-vulnerable-defi"))

    for path, label in (
        (anchor_root / ".env.local", "anchor .env.local"),
        (anchor_root / "benchmarks" / "damn-vulnerable-defi" / ".env", "anchor dvd benchmark .env"),
        (dvd_root / ".env", "dvd .env"),
    ):
        values = parse_dotenv(path)
        if values.get(ENV_KEY):
            return values[ENV_KEY], label

    return None, "unset"


def fork_url_is_publicnode_without_token(url: str | None) -> bool:
    if not url:
        return True
    normalized = url.rstrip("/")
    return normalized == PUBLICNODE_DEFAULT or normalized.endswith(".publicnode.com")


def classify_fork_log(text: str) -> str | None:
    blob = text or ""
    if ARCHIVE_TOKEN_HINT in blob:
        return "archive_token_required"
    if "HTTP error 403" in blob and "publicnode" in blob.lower():
        return "archive_token_required"
    if "MAINNET_FORKING_URL" in blob and "environment variable" in blob.lower():
        return "missing_fork_url"
    if "failed to get account" in blob.lower() or "database error" in blob.lower():
        return "rpc_state_unavailable"
    return None


def probe_archive_rpc(url: str, block_number: int = DEFAULT_PROBE_BLOCK, timeout_sec: float = 15.0) -> dict[str, object]:
    """Check that historical state is readable at ``block_number``."""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "eth_getCode",
        "params": ["0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2", hex(block_number)],
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "anchor-fork-rpc-probe/1.0"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_sec) as response:
            body = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace") if exc.fp else str(exc)
        kind = "archive_token_required" if ARCHIVE_TOKEN_HINT in detail else "http_error"
        return {"ok": False, "error_kind": kind, "detail": detail[:500]}
    except urllib.error.URLError as exc:
        return {"ok": False, "error_kind": "connection_error", "detail": str(exc.reason)[:500]}

    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        return {"ok": False, "error_kind": "invalid_response", "detail": body[:500]}

    if parsed.get("error"):
        message = str(parsed["error"].get("message", parsed["error"]))
        kind = "archive_token_required" if ARCHIVE_TOKEN_HINT in message else "rpc_error"
        return {"ok": False, "error_kind": kind, "detail": message[:500]}

    code = parsed.get("result")
    if not isinstance(code, str) or code in {"0x", "0x0"}:
        return {"ok": False, "error_kind": "empty_contract_code", "detail": "WETH code missing at fork block"}
    return {"ok": True, "error_kind": None, "detail": "archive state readable"}


def rpc_setup_instructions(*, using_default_publicnode: bool) -> list[str]:
    lines = [
        f"Set `{ENV_KEY}` to an archive-capable Ethereum mainnet HTTPS endpoint.",
        f"Copy `benchmarks/damn-vulnerable-defi/env.example` to `{os.environ.get('ANCHOR_DVD_ROOT', '/home/crexs/damn-vulnerable-defi')}/.env` and fill in the URL.",
        "PublicNode free endpoint requires a personal token: https://www.allnodes.com/publicnode",
        "URL format: https://ethereum.publicnode.com/YOUR_TOKEN",
        "Verify with: ./anchor env fork-check",
    ]
    if using_default_publicnode:
        lines.insert(0, "Forge is falling back to foundry.toml `ethereum.publicnode.com` without a token.")
    return lines


def mask_rpc_url(url: str | None) -> str:
    if not url:
        return "(unset)"
    if re.search(r"/[A-Za-z0-9_-]{8,}$", url):
        return re.sub(r"/[A-Za-z0-9_-]{8,}$", "/***", url)
    return url.split("?", 1)[0]
