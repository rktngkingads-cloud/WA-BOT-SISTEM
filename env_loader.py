from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv


def load_local_env() -> bool:
    """Load .env from the repository directory when it exists."""
    env_path = Path(__file__).with_name(".env")
    return load_dotenv(dotenv_path=env_path, override=False)
