"""Download the pre-built ris-mcp SQLite corpus from HuggingFace."""
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Any

from huggingface_hub import hf_hub_download
from huggingface_hub.utils import RepositoryNotFoundError

from .store import default_db_path


class DatasetNotPublishedError(RuntimeError):
    """Raised when the HF dataset repo does not exist yet."""


def import_from_hf(
    *,
    repo: str = "voilaj/austrian-caselaw",
    revision: str = "main",
    force: bool = False,
) -> dict[str, Any]:
    target = default_db_path()
    if target.exists() and not force:
        raise FileExistsError(
            f"{target} already exists; pass force=True to overwrite"
        )

    try:
        db_src = Path(hf_hub_download(
            repo_id=repo, filename="ris.db",
            revision=revision, repo_type="dataset",
        ))
        sha_src = Path(hf_hub_download(
            repo_id=repo, filename="ris.db.sha256",
            revision=revision, repo_type="dataset",
        ))
    except RepositoryNotFoundError as e:
        raise DatasetNotPublishedError(
            f"HuggingFace dataset {repo} not published yet. "
            "See https://jonashertner.github.io/ris-mcp for status."
        ) from e

    expected = sha_src.read_text().strip().split()[0]
    actual = hashlib.sha256(db_src.read_bytes()).hexdigest()
    if actual != expected:
        raise ValueError(
            f"sha256 mismatch: expected {expected}, got {actual}. "
            f"Downloaded file not moved to {target}."
        )

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(db_src), str(target))

    size = target.stat().st_size
    return {"path": str(target), "bytes": size, "sha256": actual}
