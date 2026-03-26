from __future__ import annotations

import os
import subprocess
from functools import lru_cache
from pathlib import Path


def _assistant_root() -> Path:
    return Path(__file__).resolve().parent.parent


@lru_cache(maxsize=1)
def _git_sha_fallback() -> str:
    repo_root = _assistant_root().parent
    try:
        return (
            subprocess.check_output(
                ["git", "-C", str(repo_root), "rev-parse", "--short=12", "HEAD"],
                stderr=subprocess.DEVNULL,
                text=True,
            )
            .strip()
        )
    except Exception:
        return ""


def get_release_info() -> dict[str, str]:
    build_sha = str(os.getenv("ASSISTANT_BUILD_SHA", "")).strip() or _git_sha_fallback()
    release_version = str(os.getenv("ASSISTANT_RELEASE_VERSION", "")).strip() or build_sha or "dev"
    build_timestamp = str(os.getenv("ASSISTANT_BUILD_TIMESTAMP", "")).strip()
    return {
        "release_version": release_version,
        "build_sha": build_sha,
        "build_timestamp": build_timestamp,
        "runtime": "nextjs-fastapi",
    }
