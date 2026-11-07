"""Bounded trusted-helper execution. Resource limits do not sandbox target code."""
from __future__ import annotations

import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile

MAX_OUTPUT_BYTES = 1024 * 1024
COMMAND_TIMEOUT = 120


def execution_env() -> dict[str, str]:
    """Do not inherit credentials, provider keys, Python hooks or RPC settings."""
    return {key: value for key, value in os.environ.items()
            if key in {"PATH", "LANG", "LC_ALL", "SYSTEMROOT", "TMPDIR"}}


def limited_command(command: list[str], timeout: int = COMMAND_TIMEOUT) -> list[str]:
    if os.name != "posix":
        raise RuntimeError("Bounded helper execution requires POSIX")
    return [sys.executable, str(Path(__file__).with_name("anchor_exec_worker.py")),
            str(max(1, timeout)), str(2 * 1024**3), str(MAX_OUTPUT_BYTES), *command]


def kill_process_group(pid: int) -> None:
    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def run_bounded(command: list[str], *, cwd: Path | None = None,
                env: dict[str, str] | None = None, timeout: int = COMMAND_TIMEOUT) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        proc = subprocess.Popen(
            limited_command(command, timeout), cwd=cwd,
            env=execution_env() if env is None else env,
            stdout=stdout, stderr=stderr, start_new_session=True,
        )
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            kill_process_group(proc.pid)
            proc.wait()
            raise
        finally:
            # Kill descendants even when the direct child exited successfully.
            kill_process_group(proc.pid)
        stdout.seek(0)
        stderr.seek(0)
        out = stdout.read(MAX_OUTPUT_BYTES + 1)
        err = stderr.read(MAX_OUTPUT_BYTES + 1)
        if len(out) >= MAX_OUTPUT_BYTES or len(err) >= MAX_OUTPUT_BYTES:
            raise ValueError("Command output limit reached")
        return subprocess.CompletedProcess(command, proc.returncode,
            out.decode(errors="replace"), err.decode(errors="replace"))
