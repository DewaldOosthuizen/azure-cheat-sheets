"""Tests for issue #203 — pip-audit CI step and dev-dependency declaration.

Covers:
  - pyproject.toml declares pip-audit>=2.7,<3 in [project.optional-dependencies] dev
  - .github/workflows/release.yml python-lint job has an "Audit Python dependencies" step
    that runs `pip-audit` with no continue-on-error flag
  - CONTRIBUTING.md section 6 documents pip-audit after the "Run tests" block
"""

import re

from conftest import REPO_ROOT
from packaging.requirements import Requirement
from packaging.version import Version

PYPROJECT = REPO_ROOT / "pyproject.toml"
RELEASE_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "release.yml"
CONTRIBUTING = REPO_ROOT / "CONTRIBUTING.md"


# ---------------------------------------------------------------------------
# pyproject.toml
# ---------------------------------------------------------------------------


class TestPyprojectPipAudit:
    """pip-audit is declared in [project.optional-dependencies] dev."""

    def _dev_section(self) -> str:
        text = PYPROJECT.read_text()
        # Extract the dev = [...] block
        m = re.search(r"\[project\.optional-dependencies\].*?dev\s*=\s*\[(.*?)\]", text, re.S)
        assert m, "Could not locate dev extras in pyproject.toml"
        return m.group(1)

    def _dev_requirements(self) -> list[Requirement]:
        entries = re.findall(r'"([^"]+)"', self._dev_section())
        return [Requirement(entry) for entry in entries]

    def _requirement(self, name: str) -> Requirement:
        for req in self._dev_requirements():
            if req.name == name:
                return req
        raise AssertionError(f"{name} must be listed under [project.optional-dependencies] dev")

    def test_pip_audit_present_in_dev_extras(self):
        self._requirement("pip-audit")

    def test_pip_audit_has_lower_bound(self):
        req = self._requirement("pip-audit")
        lower_bounds = [
            Version(spec.version) for spec in req.specifier if spec.operator in {">", ">="}
        ]
        assert lower_bounds, "pip-audit must define a lower bound"
        assert max(lower_bounds) >= Version("2.7"), "pip-audit lower bound must be >=2.7"

    def test_pip_audit_has_upper_bound(self):
        req = self._requirement("pip-audit")
        assert any(
            spec.operator == "<" and Version(spec.version) == Version("3") for spec in req.specifier
        ), "pip-audit upper bound must be <3"


# ---------------------------------------------------------------------------
# .github/workflows/release.yml
# ---------------------------------------------------------------------------


class TestCIAuditStep:
    """python-lint job has an Audit Python dependencies step running pip-audit."""

    def _workflow_text(self) -> str:
        return RELEASE_WORKFLOW.read_text()

    def test_audit_step_name_present(self):
        assert "Audit Python dependencies" in self._workflow_text(), (
            "python-lint job must have a step named 'Audit Python dependencies'"
        )

    def test_audit_step_runs_pip_audit(self):
        text = self._workflow_text()
        # Step must declare: run: pip-audit
        assert re.search(r"run:\s*pip-audit", text), "Audit step must run 'pip-audit'"

    def test_audit_step_has_no_continue_on_error(self):
        text = self._workflow_text()
        # Find the audit step block and confirm continue-on-error is absent from it
        m = re.search(
            r"- name: Audit Python dependencies(.*?)(?=\n      - name:|\Z)",
            text,
            re.S,
        )
        assert m, "Audit Python dependencies step not found"
        step_block = m.group(1)
        assert "continue-on-error" not in step_block, (
            "Audit step must NOT have continue-on-error — it must fail CI on CVEs"
        )

    def test_audit_step_appears_after_format_check(self):
        text = self._workflow_text()
        format_pos = text.find("Ruff format check")
        audit_pos = text.find("Audit Python dependencies")
        assert format_pos != -1, "Ruff format check step not found"
        assert audit_pos != -1, "Audit Python dependencies step not found"
        assert audit_pos > format_pos, "Audit step must appear after Ruff format check step"

    def test_audit_step_inside_python_lint_job(self):
        text = self._workflow_text()
        # python-lint job block starts at "python-lint:" and runs until the next top-level job
        m = re.search(r"python-lint:.*?(?=\n  \w[\w-]*:|\Z)", text, re.S)
        assert m, "python-lint job not found"
        assert "Audit Python dependencies" in m.group(0), (
            "Audit step must be inside the python-lint job, not another job"
        )


# ---------------------------------------------------------------------------
# CONTRIBUTING.md
# ---------------------------------------------------------------------------


class TestContributingPipAudit:
    """Section 6 documents pip-audit after the Run tests block."""

    def _section6(self) -> str:
        text = CONTRIBUTING.read_text()
        # Extract section 6 content up to the next ## heading
        m = re.search(r"## 6\. Running Checks Locally(.*?)(?=\n## |\Z)", text, re.S)
        assert m, "Section 6 'Running Checks Locally' not found in CONTRIBUTING.md"
        return m.group(1)

    def test_pip_audit_command_present(self):
        assert "make python-audit" in self._section6(), (
            "CONTRIBUTING.md section 6 must document the 'make python-audit' command"
        )

    def test_pip_audit_appears_after_pytest(self):
        section = self._section6()
        pytest_pos = section.find("make python-test")
        audit_pos = section.find("make python-audit")
        assert pytest_pos != -1, "'make python-test' not found in section 6"
        assert audit_pos != -1, "'make python-audit' not found in section 6"
        assert audit_pos > pytest_pos, (
            "pip-audit block must appear after the pytest block in section 6"
        )

    def test_pip_audit_appears_before_all_commands_must_exit(self):
        section = self._section6()
        audit_pos = section.find("make python-audit")
        closing_pos = section.find("All checks must exit")
        assert audit_pos != -1, "'make python-audit' not found in section 6"
        assert closing_pos != -1, "'All checks must exit' sentence not found"
        assert audit_pos < closing_pos, "pip-audit block must appear before the closing sentence"

    def test_pip_audit_in_code_fence(self):
        section = self._section6()
        # make python-audit must appear inside a ```bash ... ``` block
        fenced = re.findall(r"```bash(.*?)```", section, re.S)
        assert any("python-audit" in block for block in fenced), (
            "pip-audit must be documented inside a ```bash code fence via make python-audit"
        )

    def test_audit_description_present(self):
        section = self._section6()
        assert "known CVEs" in section or "CVE" in section, (
            "Section 6 pip-audit block should mention CVE scanning purpose"
        )
