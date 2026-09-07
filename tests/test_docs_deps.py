"""Tests for issue #294 — documentation dependency resolution is unified and locked.

The authoritative source for documentation build dependencies is the `docs`
optional dependency group in pyproject.toml. requirements-docs.txt is
generated from uv.lock via `uv export --extra docs --no-dev` and must match
the committed file.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS_DOCS = REPO_ROOT / "requirements-docs.txt"


def _uv_available() -> bool:
    """Check whether `uv` is on PATH."""
    try:
        subprocess.run(
            ["uv", "--version"],
            capture_output=True,
            timeout=10,
            check=True,
        )
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def _uv_export(path: Path) -> None:
    """Run `uv export --format requirements.txt --output-file <path> --extra docs
    --no-dev --no-header` using the active interpreter."""
    subprocess.run(
        [
            "uv",
            "export",
            "--format",
            "requirements.txt",
            "--output-file",
            str(path),
            "--extra",
            "docs",
            "--no-dev",
            "--no-header",
        ],
        cwd=REPO_ROOT,
        check=True,
        timeout=120,
    )


def _normalize(req_text: str) -> list[str]:
    """Strip comment-only lines and blank lines, return remaining non-empty lines."""
    lines = []
    for line in req_text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            lines.append(stripped)
    return lines


def test_docs_deps_match_uv_export(tmp_path: Path):
    """requirements-docs.txt must match `uv export --extra docs --no-dev` output line-for-line."""
    if not _uv_available():
        pytest.skip("uv not on PATH — cannot verify docs dependency lock")

    generated_path = tmp_path / "requirements-docs-generated.txt"
    _uv_export(generated_path)

    committed = REQUIREMENTS_DOCS.read_text()
    generated = generated_path.read_text()

    committed_lines = _normalize(committed)
    generated_lines = _normalize(generated)

    assert committed_lines == generated_lines, (
        "requirements-docs.txt does not match `uv export --extra docs --no-dev` output.\n"
        "Regenerate with: uv export --format requirements.txt --output-file "
        "requirements-docs.txt --extra docs --no-dev --no-header\n"
        "Then run `make check-docs-deps` before committing."
    )
