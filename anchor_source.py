"""Bounded regular-file reads beneath an approved root without symlink traversal."""
import os
from pathlib import Path
import stat


def read_project_text(root: Path, name: str, max_bytes: int = 1024 * 1024) -> str:
    root = root.resolve()
    relative = Path(name)
    if relative.is_absolute():
        relative = relative.relative_to(root)
    if not relative.parts or ".." in relative.parts:
        raise ValueError("Path must stay beneath the project root")
    directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for component in relative.parts[:-1]:
            child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            os.close(directory)
            directory = child
        descriptor = os.open(relative.parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        with os.fdopen(descriptor, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > max_bytes:
                raise ValueError("Expected a bounded regular file")
            content = stream.read(max_bytes + 1)
            if len(content) > max_bytes:
                raise ValueError("File exceeds read limit")
            return content.decode("utf-8", errors="replace")
    finally:
        os.close(directory)
