"""Initialize the file-backed secrets described by the core Compose config."""

import json
import re
import secrets
import sys
from pathlib import Path

LENGTHS = {
    "postgres_password": 24,
    "tracking_db_password": 24,
    "artifact_key": 10,
    "artifact_secret": 20,
}

try:
    config = json.load(sys.stdin)
    files = {name: Path(config["secrets"][name]["file"]) for name in LENGTHS}
    directories = {path.parent for path in files.values()}
    if len(directories) != 1 or any(path.name != name for name, path in files.items()):
        raise ValueError("Core secrets must use the generated filenames in one private directory")

    directory = directories.pop()
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    if directory.is_symlink() or directory.stat().st_mode & 0o077:
        raise ValueError(f"Set directory permissions to 0700 for {directory}")

    for name, size in LENGTHS.items():
        path = files[name]
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise ValueError(f"Secret {name} must be a regular non-symlink file")
        try:
            with path.open("x") as handle:
                handle.write(secrets.token_hex(size) + "\n")
        except FileExistsError:
            if not re.fullmatch(rf"[0-9a-f]{{{2 * size}}}\n?", path.read_text()):
                raise ValueError(f"Secret {name} has an invalid format. Restore the original file for existing data.")
        # Compose bind-mounts files for different container users. The host directory
        # protects the files while each container sees only its own mounts.
        path.chmod(0o444)
    print(f"Core secret files initialized in {directory}")
except (OSError, ValueError, KeyError) as error:
    sys.exit(f"Secret initialization failed: {error}")
