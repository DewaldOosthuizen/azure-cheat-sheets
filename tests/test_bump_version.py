"""Tests for scripts/bump_version.py"""

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent.parent / "scripts" / "bump_version.py"


def _run_bump(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=cwd or SCRIPT.parent.parent,
        capture_output=True,
        text=True,
    )


class TestBumpVersionCLI:
    """Test CLI behavior and exit codes."""

    def test_help_exits_zero(self):
        result = _run_bump(["--help"])
        assert result.returncode == 0
        assert "usage" in result.stdout.lower()

    def test_invalid_override_format_exits_one(self):
        result = _run_bump(["not.a.version"])
        assert result.returncode == 1
        assert "error" in result.stderr.lower()

    def test_dry_run_prints_version(self):
        result = _run_bump(["--dry-run", "2026.01.01"])
        assert result.returncode == 0
        assert result.stdout.strip() == "2026.01.01"

    def test_dry_run_no_write(self):
        """Verify --dry-run doesn't modify pyproject.toml."""
        pyproject = SCRIPT.parent.parent / "pyproject.toml"
        original = pyproject.read_text()

        result = _run_bump(["--dry-run", "2026.01.01"])

        after = pyproject.read_text()
        assert after == original
        assert result.returncode == 0


class TestVersionComputation:
    """Test CalVer computation logic."""

    def test_new_day_resets_micro(self):
        # Use actual current version from pyproject.toml (should be old)
        # and don't pass override - let it compute from current date
        result = _run_bump(["--dry-run"])
        assert result.returncode == 0
        # Should be today's date with micro=0
        assert result.stdout.strip().startswith("2026.09.07")
        assert not result.stdout.strip().endswith(".1")

    def test_same_day_increments_micro(self):
        from datetime import date
        from unittest.mock import patch

        from scripts.bump_version import _compute_next_version

        with patch("scripts.bump_version.datetime") as mock_dt:
            mock_dt.now.return_value.date.return_value = date(2026, 9, 7)
            new_version, changed = _compute_next_version("2026.09.07", None)
            assert new_version == "2026.09.07.1"
            assert changed is True

    def test_same_day_increments_existing_micro(self):
        from datetime import date
        from unittest.mock import patch

        from scripts.bump_version import _compute_next_version

        with patch("scripts.bump_version.datetime") as mock_dt:
            mock_dt.now.return_value.date.return_value = date(2026, 9, 7)
            new_version, changed = _compute_next_version("2026.09.07.3", None)
            assert new_version == "2026.09.07.4"
            assert changed is True

    def test_new_day_via_compute_function(self):
        from datetime import date
        from unittest.mock import patch

        from scripts.bump_version import _compute_next_version

        with patch("scripts.bump_version.datetime") as mock_dt:
            mock_dt.now.return_value.date.return_value = date(2026, 9, 8)
            new_version, changed = _compute_next_version("2026.09.07.5", None)
            assert new_version == "2026.09.08"
            assert changed is True

    def test_no_change_when_same_version(self):
        from datetime import date
        from unittest.mock import patch

        from scripts.bump_version import _compute_next_version

        with patch("scripts.bump_version.datetime") as mock_dt:
            mock_dt.now.return_value.date.return_value = date(2026, 9, 7)
            _new_version, changed = _compute_next_version("2026.09.07", "2026.09.07")
            assert changed is False

    def test_override_without_micro(self):
        result = _run_bump(["--dry-run", "2026.01.15"])
        assert result.returncode == 0
        assert result.stdout.strip() == "2026.01.15"

    def test_override_with_micro(self):
        result = _run_bump(["--dry-run", "2026.01.15.2"])
        assert result.returncode == 0
        assert result.stdout.strip() == "2026.01.15.2"

    def test_invalid_override_too_many_parts(self):
        result = _run_bump(["--dry-run", "2026.01.15.1.2"])
        assert result.returncode == 1

    def test_invalid_override_non_numeric(self):
        result = _run_bump(["--dry-run", "2026.01.xx"])
        assert result.returncode == 1


class TestVersionFormat:
    """Test version string formatting."""

    def test_format_no_micro(self):
        from scripts.bump_version import _format_calver

        assert _format_calver(2026, 9, 7, 0) == "2026.09.07"

    def test_format_with_micro(self):
        from scripts.bump_version import _format_calver

        assert _format_calver(2026, 9, 7, 1) == "2026.09.07.1"

    def test_format_zero_padded(self):
        from scripts.bump_version import _format_calver

        assert _format_calver(2026, 1, 1, 0) == "2026.01.01"

    def test_parse_valid_no_micro(self):
        from scripts.bump_version import _parse_calver

        assert _parse_calver("2026.09.07") == (2026, 9, 7, 0)

    def test_parse_valid_with_micro(self):
        from scripts.bump_version import _parse_calver

        assert _parse_calver("2026.09.07.3") == (2026, 9, 7, 3)

    def test_parse_invalid_parts(self):
        from scripts.bump_version import _parse_calver

        with pytest.raises(ValueError):
            _parse_calver("2026.09")
        with pytest.raises(ValueError):
            _parse_calver("2026.09.07.1.2")


class TestPyprojectIntegration:
    """Test reading/writing pyproject.toml."""

    def test_extract_version(self):
        from scripts.bump_version import _extract_version

        content = """[project]
name = "test"
version = "1.2.3"
"""
        assert _extract_version(content) == "1.2.3"

    def test_update_version_in_content(self):
        from scripts.bump_version import _update_version_in_content

        content = """[project]
name = "test"
version = "1.2.3"
"""
        updated = _update_version_in_content(content, "2026.09.07")
        assert 'version = "2026.09.07"' in updated
        assert 'version = "1.2.3"' not in updated


class TestMainInProcess:
    """Test main() directly (in-process) for coverage of CLI/error paths."""

    def test_main_dry_run_success(self, monkeypatch, capsys):
        import scripts.bump_version as bv

        monkeypatch.setattr(sys, "argv", ["bump_version.py", "--dry-run", "2026.05.05"])
        assert bv.main() == 0
        assert capsys.readouterr().out.strip() == "2026.05.05"

    def test_main_invalid_override(self, monkeypatch, capsys):
        import scripts.bump_version as bv

        monkeypatch.setattr(sys, "argv", ["bump_version.py", "--dry-run", "bad.version"])
        assert bv.main() == 1
        assert "error" in capsys.readouterr().err.lower()

    def test_main_writes_pyproject(self, monkeypatch, capsys, tmp_path):
        import scripts.bump_version as bv

        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "x"\nversion = "2020.01.01"\n', encoding="utf-8")
        monkeypatch.setattr(bv, "_repo_root", lambda: tmp_path)
        monkeypatch.setattr(sys, "argv", ["bump_version.py", "2026.05.05"])

        assert bv.main() == 0
        assert 'version = "2026.05.05"' in pyproject.read_text()
        assert capsys.readouterr().out.strip() == "2026.05.05"

    def test_main_no_change_returns_2(self, monkeypatch, capsys):
        import scripts.bump_version as bv

        monkeypatch.setattr(bv, "_extract_version", lambda content: "2026.05.05")
        monkeypatch.setattr(sys, "argv", ["bump_version.py", "2026.05.05"])

        assert bv.main() == 2
        assert "unchanged" in capsys.readouterr().err.lower()

    def test_read_pyproject_missing_file_raises(self, monkeypatch, tmp_path):
        import scripts.bump_version as bv

        monkeypatch.setattr(bv, "_repo_root", lambda: tmp_path)
        with pytest.raises(RuntimeError, match=r"Cannot read pyproject\.toml"):
            bv._read_pyproject()

    def test_write_pyproject_bad_path_raises(self, monkeypatch, tmp_path):
        import scripts.bump_version as bv

        monkeypatch.setattr(bv, "_repo_root", lambda: tmp_path / "does" / "not" / "exist")
        with pytest.raises(RuntimeError, match=r"Cannot write pyproject\.toml"):
            bv._write_pyproject("content")

    def test_extract_version_not_found_raises(self):
        from scripts.bump_version import _extract_version

        with pytest.raises(RuntimeError, match="version not found"):
            _extract_version('[project]\nname = "x"\n')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
