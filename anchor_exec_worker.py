"""POSIX resource limits before exec; this is not a filesystem/network sandbox."""
from __future__ import annotations

import os
import resource
import sys


def main() -> None:
    cpu, memory, file_bytes = map(int, sys.argv[1:4])
    resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))
    resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
    resource.setrlimit(resource.RLIMIT_FSIZE, (file_bytes, file_bytes))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_NOFILE, (128, 128))
    command = sys.argv[4:]
    os.execvpe(command[0], command, os.environ)


if __name__ == "__main__":
    main()
