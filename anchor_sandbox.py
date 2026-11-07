"""Fail-closed Linux filesystem and network isolation for target tools."""
from pathlib import Path
import shutil


def sandbox_command(command: list[str], workspace: Path) -> list[str]:
    bwrap = shutil.which("bwrap")
    binary = shutil.which(command[0])
    if not bwrap or not binary:
        raise RuntimeError("Target execution requires bubblewrap and the selected tool")
    argv = [bwrap, "--unshare-all", "--die-with-parent", "--new-session",
            "--cap-drop", "ALL"]
    for name in ("/usr", "/lib", "/lib64"):
        if Path(name).exists():
            argv += ["--ro-bind", name, name]
    argv += ["--symlink", "usr/bin", "/bin", "--symlink", "usr/sbin", "/sbin",
             "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp",
             "--dir", "/home", "--dir", "/home/anchor",
             "--bind", str(workspace.resolve()), "/work", "--chdir", "/work",
             "--setenv", "HOME", "/home/anchor", "--setenv", "PATH", "/tools:/usr/bin:/bin"]
    resolved = Path(binary).resolve()
    executable = str(resolved)
    if not resolved.is_relative_to("/usr"):
        argv += ["--dir", "/tools", "--ro-bind", str(resolved), "/tools/" + resolved.name]
        executable = "/tools/" + resolved.name
    return [*argv, "--", executable, *command[1:]]
