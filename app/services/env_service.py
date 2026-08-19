"""
Persisting settings back to the .env file.

Only used for values an admin is expected to change at runtime — currently the
embedding API key. Everything else stays a deploy-time concern.
"""

import logging
import os
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"


def update_env_var(name: str, value: str, env_path: Path | None = None) -> bool:
    """
    Replace (or append) a single variable in .env, leaving the rest untouched.

    Written to a temporary file in the same directory and then moved into place,
    so an interrupted write cannot leave a half-truncated .env — which would
    take the database URL down with it.

    Returns True if the file was updated, False if it could not be written.
    The value is never logged.
    """
    path = env_path or ENV_PATH

    try:
        lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []

        replaced = False
        for i, line in enumerate(lines):
            # Match assignments only, so a comment mentioning the name is safe
            if line.lstrip().startswith(f"{name}="):
                lines[i] = f"{name}={value}"
                replaced = True
                break

        if not replaced:
            lines.append(f"{name}={value}")

        fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".env.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("\n".join(lines) + "\n")
            os.replace(tmp_name, path)
        except Exception:
            # Never leave the temp file behind holding a secret
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise

        logger.info(f"{name} updated in {path.name} ({'replaced' if replaced else 'appended'}).")
        return True

    except Exception as e:
        logger.error(f"Could not persist {name} to {path}: {e}")
        return False
