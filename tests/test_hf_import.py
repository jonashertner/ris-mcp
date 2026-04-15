import hashlib
from pathlib import Path
from unittest.mock import patch

import pytest

from ris_mcp.hf_import import DatasetNotPublishedError, import_from_hf


def _write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def test_import_from_hf_writes_db(tmp_path, monkeypatch):
    monkeypatch.setenv("RIS_MCP_DATA_DIR", str(tmp_path))
    db_bytes = b"SQLite format 3\x00" + b"\x00" * 100
    sha = hashlib.sha256(db_bytes).hexdigest()
    sha_file = f"{sha}  ris.db\n"

    def fake_download(*, repo_id: str, filename: str, **kwargs) -> str:
        staging = tmp_path / "_staging"
        staging.mkdir(exist_ok=True)
        p = staging / filename
        if filename == "ris.db":
            _write(p, db_bytes)
        elif filename == "ris.db.sha256":
            p.write_text(sha_file)
        else:
            raise ValueError(filename)
        return str(p)

    with patch("ris_mcp.hf_import.hf_hub_download", side_effect=fake_download):
        result = import_from_hf(repo="voilaj/austrian-caselaw")

    target = tmp_path / "ris.db"
    assert target.exists()
    assert target.read_bytes() == db_bytes
    assert result["path"] == str(target)
    assert result["bytes"] == len(db_bytes)


def test_import_from_hf_refuses_existing_without_force(tmp_path, monkeypatch):
    monkeypatch.setenv("RIS_MCP_DATA_DIR", str(tmp_path))
    (tmp_path / "ris.db").write_bytes(b"existing")
    with pytest.raises(FileExistsError):
        import_from_hf(repo="voilaj/austrian-caselaw")


def test_import_from_hf_raises_dataset_not_published(tmp_path, monkeypatch):
    monkeypatch.setenv("RIS_MCP_DATA_DIR", str(tmp_path))
    import httpx
    from huggingface_hub.utils import RepositoryNotFoundError
    response = httpx.Response(404, request=httpx.Request("GET", "https://hf.co"))
    err = RepositoryNotFoundError("no such repo", response=response)
    with patch("ris_mcp.hf_import.hf_hub_download", side_effect=err), \
            pytest.raises(DatasetNotPublishedError):
        import_from_hf(repo="voilaj/austrian-caselaw")


def test_import_from_hf_verifies_sha256(tmp_path, monkeypatch):
    monkeypatch.setenv("RIS_MCP_DATA_DIR", str(tmp_path))
    db_bytes = b"content"
    wrong_sha = "0" * 64

    def fake_download(*, repo_id: str, filename: str, **kwargs) -> str:
        staging = tmp_path / "_staging"
        staging.mkdir(exist_ok=True)
        p = staging / filename
        if filename == "ris.db":
            _write(p, db_bytes)
        elif filename == "ris.db.sha256":
            p.write_text(f"{wrong_sha}  ris.db\n")
        return str(p)

    with patch("ris_mcp.hf_import.hf_hub_download", side_effect=fake_download), \
            pytest.raises(ValueError, match="sha256 mismatch"):
        import_from_hf(repo="voilaj/austrian-caselaw")
    assert not (tmp_path / "ris.db").exists()
