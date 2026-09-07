"""Tests for Makefile and CI Mermaid coverage (issue #224).

Verifies that:
  - Makefile's MMD_FILES_VALIDATE find covers all of docs/
  - Makefile's mermaid-check target forwards $(MMD_FILES_VALIDATE)
  - CI lint.yml "Validate Mermaid diagrams" step uses broad 'find docs' discovery
"""

from __future__ import annotations

import re

from conftest import REPO_ROOT

MAKEFILE = REPO_ROOT / "Makefile"
RELEASE_YML = REPO_ROOT / ".github" / "workflows" / "release.yml"


class TestMakefileMermaidCoverage:
    """MMD_FILES_VALIDATE must cover all docs/, and be wired in."""

    def test_mmd_files_validate_covers_all_docs(self) -> None:
        content = MAKEFILE.read_text()
        m = re.search(r"MMD_FILES_VALIDATE\s*:=\s*\$\(shell find ([^)]*?)-name '\*\.mmd'", content)
        assert m, "Could not locate MMD_FILES_VALIDATE definition in Makefile"
        find_paths = m.group(1).strip()
        assert find_paths == "docs", (
            f"MMD_FILES_VALIDATE must search all of docs/, got: {find_paths!r}"
        )

    def test_mermaid_check_forwards_mmd_files_validate(self) -> None:
        content = MAKEFILE.read_text()
        m = re.search(r"mermaid-check:.*?validate_mermaid\.py ([^\n]*)", content, re.S)
        assert m, "Could not locate validate_mermaid.py invocation in mermaid-check target"
        invocation_args = m.group(1)
        assert "$(MD_FILES_VALIDATE)" in invocation_args
        assert "$(MMD_FILES_VALIDATE)" in invocation_args


class TestCiMermaidCoverage:
    """CI 'Validate Mermaid diagrams' step must use broad 'find docs' discovery."""

    def _step_block(self) -> str:
        content = RELEASE_YML.read_text()
        m = re.search(
            r"Validate Mermaid diagrams.*?(?=\n\s*- name:|\Z)",
            content,
            re.S,
        )
        assert m, "Could not locate 'Validate Mermaid diagrams' step in release.yml"
        return m.group(0)

    def test_md_find_covers_all_docs(self) -> None:
        block = self._step_block()
        assert "find docs" in block, (
            "CI mermaid-check must use 'find docs' (not provider-scoped paths)"
        )
        assert "docs/azure/files docs/aws/files" not in block, (
            "CI mermaid-check still uses narrow azure/aws find — must be broadened to 'find docs'"
        )

    def test_mmd_find_covers_all_docs(self) -> None:
        block = self._step_block()
        assert "find docs -name '*.mmd'" in block, (
            "CI mermaid-check must use 'find docs -name *.mmd' (not provider-scoped paths)"
        )
        assert "docs/azure/diagrams docs/aws/diagrams" not in block, (
            "CI mermaid-check still uses narrow azure/aws .mmd find —"
            " must be broadened to 'find docs'"
        )
