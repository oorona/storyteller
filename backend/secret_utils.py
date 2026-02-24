import os
from typing import Optional


def read_secret(
    env_var_name: str,
    file_env_var_name: str,
    default_file_path: Optional[str] = None,
) -> Optional[str]:
    """Read a secret from an env var first, then a file path env var/default path."""
    direct_value = os.getenv(env_var_name)
    if direct_value:
        value = direct_value.strip()
        if value:
            return value

    file_path = os.getenv(file_env_var_name) or default_file_path
    if not file_path:
        return None

    try:
        with open(file_path, "r", encoding="utf-8") as secret_file:
            content = secret_file.read()
            if not content:
                return None

            # Support Docker secret style files and tolerate accidental comments.
            # First non-empty, non-comment line wins.
            for line in content.splitlines():
                candidate = line.strip()
                if not candidate or candidate.startswith("#"):
                    continue
                return candidate

            # Fallback for single-line secrets without newlines.
            value = content.strip()
            return value if value and not value.startswith("#") else None
    except FileNotFoundError:
        return None
    except OSError:
        return None
