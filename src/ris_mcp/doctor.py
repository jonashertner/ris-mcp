"""Diagnostics for ris-mcp: tell users why their install isn't working."""
from __future__ import annotations

import shutil
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from . import __version__
from .store import default_db_path, open_db

Status = Literal["ok", "warn", "fail"]


@dataclass
class Check:
    name: str
    status: Status
    detail: str
    hint: str = ""


def check_python() -> Check:
    major, minor = sys.version_info[:2]
    version = f"{major}.{minor}"
    if (major, minor) >= (3, 11):
        return Check("Python version", "ok", version)
    return Check(
        "Python version", "fail",
        f"{version} — ris-mcp requires Python 3.11 or newer",
        hint="Install a newer Python via uv, pyenv, or python.org.",
    )


def check_uvx() -> Check:
    path = shutil.which("uvx")
    if path:
        return Check(
            "uvx on PATH", "ok", path,
            hint="Use this exact path in Claude Desktop config on macOS "
                 "(Claude Desktop does not inherit your shell PATH).",
        )
    return Check(
        "uvx on PATH", "fail",
        "uvx not found on PATH",
        hint="Install uv: curl -LsSf https://astral.sh/uv/install.sh | sh "
             "(then restart your terminal).",
    )


def check_db_file(db_path: Path | None = None) -> Check:
    p = db_path if db_path is not None else default_db_path()
    if not p.exists():
        return Check(
            "Database file", "fail",
            f"not found at {p}",
            hint="Run: ris-ingest import-from-hf "
                 "(or ris-ingest --full to build from scratch, 2–3 days).",
        )
    size = p.stat().st_size
    size_mb = size / (1024 * 1024)
    if size < 10_000:
        return Check(
            "Database file", "warn",
            f"{p} exists but is very small ({size_mb:.2f} MB) — probably empty",
            hint="Run: ris-ingest import-from-hf",
        )
    return Check("Database file", "ok", f"{p} ({size_mb:.0f} MB)")


def check_db_contents(db_path: Path | None = None) -> Check:
    p = db_path if db_path is not None else default_db_path()
    if not p.exists():
        return Check("Database contents", "fail", "no database to inspect")
    try:
        conn = open_db(p)
        total = conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
        laws = conn.execute("SELECT COUNT(*) FROM laws").fetchone()[0]
        conn.close()
    except sqlite3.DatabaseError as e:
        return Check(
            "Database contents", "fail",
            f"corrupt or unreadable: {e}",
            hint="Delete the file and re-run ris-ingest import-from-hf.",
        )
    if total == 0 and laws == 0:
        return Check(
            "Database contents", "warn",
            "no decisions or laws indexed yet",
            hint="Run: ris-ingest import-from-hf (or ris-ingest --full).",
        )
    return Check(
        "Database contents", "ok",
        f"{total:,} decisions, {laws:,} law articles",
    )


def run_diagnostics() -> list[Check]:
    return [
        Check("ris-mcp version", "ok", __version__),
        check_python(),
        check_uvx(),
        check_db_file(),
        check_db_contents(),
    ]


def format_report(checks: list[Check]) -> str:
    icon = {"ok": "✅", "warn": "⚠️ ", "fail": "❌"}
    lines: list[str] = ["ris-mcp doctor", "─" * 40]
    for c in checks:
        lines.append(f"{icon[c.status]} {c.name}: {c.detail}")
        if c.hint and c.status != "ok":
            lines.append(f"   → {c.hint}")
    lines.append("")
    any_fail = any(c.status == "fail" for c in checks)
    any_warn = any(c.status == "warn" for c in checks)
    if any_fail:
        lines.append("Status: something needs attention (see ❌ above).")
    elif any_warn:
        lines.append("Status: mostly working but incomplete (see ⚠️ above).")
    else:
        lines.append("Status: all good — Claude can query Austrian law.")
    return "\n".join(lines)
