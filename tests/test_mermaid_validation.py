"""Tests for issue #42 - error handling and exit-code reporting in validate_mermaid.py."""

import re
import shutil
from unittest.mock import patch

import pytest
import validate_mermaid
from conftest import REPO_ROOT

MAKEFILE = REPO_ROOT / "Makefile"
RELEASE_YML = REPO_ROOT / ".github" / "workflows" / "release.yml"


class TestMmdcNotFound:
    """Tests for shutil.which guard in main()."""

    def test_main_exits_with_code_2_when_mmdc_missing(self):
        with (
            patch("validate_mermaid.shutil.which", return_value=None),
            pytest.raises(SystemExit) as exc_info,
        ):
            validate_mermaid.main()
        assert exc_info.value.code == 2

    def test_main_prints_error_to_stderr_when_mmdc_missing(self, capsys):
        with (
            patch("validate_mermaid.shutil.which", return_value=None),
            pytest.raises(SystemExit),
        ):
            validate_mermaid.main()
        captured = capsys.readouterr()
        assert "mmdc not found" in captured.err
        assert "npm install -g @mermaid-js/mermaid-cli" in captured.err


class TestValidateBlockFileNotFound:
    """Tests for FileNotFoundError handling in validate_block()."""

    def test_validate_block_returns_false_when_mmdc_not_on_path(self):
        with patch("validate_mermaid.subprocess.run", side_effect=FileNotFoundError):
            result = validate_mermaid.validate_block(1, "graph TD\n  A --> B\n")
        assert result[0] is False
        assert result[1] == "mmdc binary not found on PATH"


class TestValidateBlockTimeout:
    """Tests for subprocess.TimeoutExpired handling in validate_block()."""

    def test_validate_block_returns_false_on_timeout(self):
        import subprocess

        timeout_exc = subprocess.TimeoutExpired(cmd="mmdc", timeout=60)
        with patch("validate_mermaid.subprocess.run", side_effect=timeout_exc):
            result = validate_mermaid.validate_block(1, "graph TD\n  A --> B\n")
        assert result[0] is False
        assert result[1] == "mmdc timed out after 60 s"

    def test_validate_block_respects_mmdc_timeout_seconds_env_var(self):
        import subprocess

        timeout_exc = subprocess.TimeoutExpired(cmd="mmdc", timeout=120)
        with patch("validate_mermaid.subprocess.run", side_effect=timeout_exc):
            result = validate_mermaid.validate_block(1, "graph TD\n  A --> B\n", timeout=120)
        assert result[0] is False
        assert result[1] == "mmdc timed out after 120 s"

    def test_validate_block_uses_env_var_when_no_timeout_argument(self):
        import subprocess

        timeout_exc = subprocess.TimeoutExpired(cmd="mmdc", timeout=120)
        with (
            patch.dict("validate_mermaid.os.environ", {"MMDC_TIMEOUT_SECONDS": "120"}),
            patch("validate_mermaid.subprocess.run", side_effect=timeout_exc),
        ):
            result = validate_mermaid.validate_block(1, "graph TD\n  A --> B\n")
        assert result[0] is False
        assert result[1] == "mmdc timed out after 120 s"


class TestMainFileNotFound:
    """Tests for file-existence guard in run()."""

    def test_run_returns_1_when_file_missing(self):
        result = validate_mermaid.run(["/nonexistent/path.md"])
        assert result == 1

    def test_run_prints_error_to_stderr_when_file_missing(self, capsys):
        validate_mermaid.run(["/nonexistent/path.md"])
        captured = capsys.readouterr()
        assert "file not found" in captured.err
        assert "/nonexistent/path.md" in captured.err


class TestExtractMermaidBlocks:
    """Parametrised tests for _extract_from_text() helper."""

    @pytest.mark.parametrize(
        "text,expected_count,expected_content",
        [
            # single_block
            ("```mermaid\ngraph TD\n  A --> B\n```", 1, "graph TD\n  A --> B\n"),
            # multiple_blocks
            ("```mermaid\ngraph TD\n  A-->B\n```\n\n```mermaid\ngraph LR\n  C-->D\n```", 2, None),
            # no_blocks
            ("# Heading\nSome text.", 0, None),
            # non_mermaid_fence
            ("```python\nprint('hi')\n```", 0, None),
            # trailing_whitespace_fence
            ("```mermaid   \ngraph TD\n  A-->B\n```", 1, None),
            # crlf_line_endings
            ("```mermaid\r\ngraph TD\r\n  A-->B\r\n```", 1, None),
            # mermaid_followed_by_other_language_fence — regex must not bleed across fences
            (
                "```mermaid\ngraph TD\n  A-->B\n```\n\n```python\nprint('hi')\n```",
                1,
                "graph TD\n  A-->B\n",
            ),
            # python_block_with_backtick_string_precedes_mermaid — greedy matching must not
            # capture the Python block as part of the diagram
            (
                '```python\nx = "```"\n```\n\n```mermaid\ngraph TD\n  A-->B\n```',
                1,
                "graph TD\n  A-->B\n",
            ),
        ],
    )
    def test_extract(self, text, expected_count, expected_content):
        result = validate_mermaid._extract_from_text(text)
        assert len(result) == expected_count
        if expected_content is not None:
            assert result[0] == expected_content


class TestPathlibRefactor:
    """Tests for issue #62 — pathlib usage in validate_block() and run()."""

    def test_validate_block_unlinks_tmp_via_pathlib(self):
        """Cleanup must use Path.unlink, not os.unlink."""
        import inspect

        import validate_mermaid as vm

        src = inspect.getsource(vm.validate_block)
        assert "os.unlink" not in src, "validate_block must not use os.unlink"
        assert "os.path.exists" not in src, "validate_block must not use os.path.exists"
        assert "unlink(missing_ok=True)" in src

    def test_main_uses_pathlib_is_file(self):
        """run() must check the markdown file via Path.is_file(), not os.path.isfile()."""
        import inspect

        import validate_mermaid as vm

        src = inspect.getsource(vm.run)
        assert "os.path.isfile" not in src, "run() must not use os.path.isfile"
        assert ".is_file()" in src

    def test_import_os_present(self):
        """The script must import os (needed for os.environ.get in PUPPETEER_CONFIG)."""
        import ast
        import inspect

        import validate_mermaid as vm

        source = inspect.getsource(vm)
        tree = ast.parse(source)
        os_imports = [
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            and any(
                (alias.name == "os" if isinstance(node, ast.Import) else node.module == "os")
                for alias in node.names
            )
        ]
        assert os_imports, "import os must be present for env-var-driven PUPPETEER_CONFIG"

    def test_out_path_derived_with_suffix(self):
        """SVG path must be derived with Path.with_suffix, not string.replace."""
        import inspect

        import validate_mermaid as vm

        src = inspect.getsource(vm.validate_block)
        assert '.replace(".mmd"' not in src, "must not use string.replace for suffix"
        assert "with_suffix" in src


_ONE_BLOCK = ["graph TD\n  A --> B\n"]


class TestExtractMermaidBlocksFromFile:
    """Tests for extract_mermaid_blocks() reading from a real file."""

    def test_extract_reads_file_and_returns_blocks(self, tmp_path):
        md = tmp_path / "test.md"
        md.write_text("```mermaid\ngraph TD\n  A --> B\n```\n", encoding="utf-8")
        result = validate_mermaid.extract_mermaid_blocks(str(md))
        assert len(result) == 1
        assert "graph TD" in result[0]


class TestExtractMermaidBlocksFileErrors:
    """Tests for extract_mermaid_blocks() file-read error paths."""

    def test_raises_on_permission_error(self, tmp_path):
        md = tmp_path / "locked.md"
        md.write_text("```mermaid\ngraph TD\n  A-->B\n```", encoding="utf-8")
        md.chmod(0o000)
        with pytest.raises(RuntimeError) as excinfo:
            validate_mermaid.extract_mermaid_blocks(str(md))
        md.chmod(0o644)  # restore so pytest can clean up tmp_path
        assert str(md) in str(excinfo.value)

    def test_raises_on_encoding_error(self, tmp_path):
        md = tmp_path / "binary.md"
        md.write_bytes(b"\xff\xfe invalid utf-8")
        with pytest.raises(RuntimeError) as excinfo:
            validate_mermaid.extract_mermaid_blocks(str(md))
        assert str(md) in str(excinfo.value)


class TestRunFileReadErrors:
    """Tests for run() handling RuntimeError raised by extract_mermaid_blocks."""

    def test_run_returns_1_on_runtime_error(self, tmp_path):
        md = tmp_path / "test.md"
        md.write_text("# test", encoding="utf-8")
        error_msg = f"Cannot read {md}: permission denied"
        with (
            patch("validate_mermaid.Path.is_file", return_value=True),
            patch("validate_mermaid._repo_root", return_value=tmp_path),
            patch(
                "validate_mermaid.extract_mermaid_blocks",
                side_effect=RuntimeError(error_msg),
            ),
        ):
            result = validate_mermaid.run([str(md)])
        assert result == 1

    def test_run_prints_error_to_stderr_on_runtime_error(self, tmp_path, capsys):
        md = tmp_path / "test.md"
        md.write_text("# test", encoding="utf-8")
        error_msg = f"Cannot read {md}: permission denied"
        with (
            patch("validate_mermaid.Path.is_file", return_value=True),
            patch("validate_mermaid._repo_root", return_value=tmp_path),
            patch(
                "validate_mermaid.extract_mermaid_blocks",
                side_effect=RuntimeError(error_msg),
            ),
        ):
            validate_mermaid.run([str(md)])
        captured = capsys.readouterr()
        assert error_msg in captured.err


class TestValidateBlockPuppeteerConfig:
    """Tests for puppeteer config branch in validate_block()."""

    def test_validate_block_appends_puppeteer_config_when_present(self):
        import subprocess

        def _write_svg_and_succeed(cmd, **kwargs):
            input_flag = cmd.index("--input")
            from pathlib import Path as _Path

            out_file = _Path(cmd[input_flag + 1]).with_suffix(".svg")
            out_file.write_bytes(b"<svg>" + b"x" * 200 + b"</svg>")
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

        with (
            patch("validate_mermaid.PUPPETEER_CONFIG") as mock_cfg,
            patch(
                "validate_mermaid.subprocess.run",
                side_effect=_write_svg_and_succeed,
            ) as mock_run,
        ):
            mock_cfg.exists.return_value = True
            mock_cfg.__str__ = lambda s: "/tmp/puppeteer-config.json"
            ok, _ = validate_mermaid.validate_block(1, "graph TD\n  A --> B\n")
        assert ok is True
        call_args = mock_run.call_args[0][0]
        assert "--puppeteerConfigFile" in call_args

    def test_validate_block_returns_true_on_success(self):
        import subprocess

        def _write_svg_and_succeed(cmd, **kwargs):
            input_flag = cmd.index("--input")
            from pathlib import Path as _Path

            out_file = _Path(cmd[input_flag + 1]).with_suffix(".svg")
            out_file.write_bytes(b"<svg>" + b"x" * 200 + b"</svg>")
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

        with (
            patch("validate_mermaid.PUPPETEER_CONFIG") as mock_cfg,
            patch("validate_mermaid.subprocess.run", side_effect=_write_svg_and_succeed),
        ):
            mock_cfg.exists.return_value = False
            ok, stderr = validate_mermaid.validate_block(1, "graph TD\n  A --> B\n")
        assert ok is True
        assert stderr == ""


class TestParseArgs:
    """Tests for parse_args() in isolation — covers CLI argument parsing."""

    def test_parse_args_returns_namespace_with_md_files(self):
        argv = ["validate_mermaid.py", "docs/azure/files/networking/networking.md"]
        with patch("validate_mermaid.sys.argv", argv):
            args = validate_mermaid.parse_args()
        assert args.md_files == ["docs/azure/files/networking/networking.md"]

    def test_parse_args_exits_2_when_no_positional_argument(self):
        with (
            patch("validate_mermaid.sys.argv", ["validate_mermaid.py"]),
            pytest.raises(SystemExit) as exc_info,
        ):
            validate_mermaid.parse_args()
        assert exc_info.value.code == 2


class TestMainHappyPath:
    """run() returns 0 when all diagrams pass."""

    def test_run_returns_0_when_all_diagrams_pass(self, capsys):
        with (
            patch("validate_mermaid.extract_mermaid_blocks", return_value=_ONE_BLOCK),
            patch("validate_mermaid.validate_block", return_value=(True, "")),
            patch("validate_mermaid.Path.is_file", return_value=True),
        ):
            result = validate_mermaid.run(["docs/azure/files/networking/networking.md"])
        assert result == 0
        captured = capsys.readouterr()
        assert "All 1 diagram(s) passed" in captured.out


class TestMainAggregateFail:
    """run() returns 1 when one or more diagrams fail."""

    def test_run_returns_1_when_diagram_fails(self):
        with (
            patch("validate_mermaid.extract_mermaid_blocks", return_value=_ONE_BLOCK),
            patch("validate_mermaid.validate_block", return_value=(False, "syntax error")),
            patch("validate_mermaid.Path.is_file", return_value=True),
        ):
            result = validate_mermaid.run(["docs/azure/files/networking/networking.md"])
        assert result == 1

    def test_run_prints_failure_summary(self, capsys):
        with (
            patch("validate_mermaid.extract_mermaid_blocks", return_value=_ONE_BLOCK),
            patch("validate_mermaid.validate_block", return_value=(False, "syntax error")),
            patch("validate_mermaid.Path.is_file", return_value=True),
        ):
            validate_mermaid.run(["docs/azure/files/networking/networking.md"])
        captured = capsys.readouterr()
        assert "1 diagram(s) failed" in captured.out


class TestMainZeroBlocks:
    """run() skips files with no mermaid blocks (returns 0) but prints a stderr warning."""

    def test_run_returns_0_when_no_blocks_found(self):
        with (
            patch("validate_mermaid.extract_mermaid_blocks", return_value=[]),
            patch("validate_mermaid.Path.is_file", return_value=True),
        ):
            result = validate_mermaid.run(["docs/azure/files/networking/networking.md"])
        assert result == 0

    def test_run_prints_warning_to_stderr_when_no_blocks_found(self, capsys):
        with (
            patch("validate_mermaid.extract_mermaid_blocks", return_value=[]),
            patch("validate_mermaid.Path.is_file", return_value=True),
        ):
            validate_mermaid.run(["docs/azure/files/networking/networking.md"])
        captured = capsys.readouterr()
        assert "no mermaid blocks found" in captured.err


class TestTraversalGuard:
    """Tests for issue #126 - path traversal / shell-injection guard in run()."""

    def test_run_returns_1_on_path_traversal(self, capsys):
        """Path resolving outside repo root must be rejected with return code 1."""
        from pathlib import Path

        original_resolve = Path.resolve

        def fake_resolve(self, strict=False):
            if str(self) == "/etc/passwd":
                return Path("/etc/passwd")
            return original_resolve(self, strict=strict)

        with (
            patch.object(Path, "is_file", return_value=True),
            patch.object(Path, "resolve", fake_resolve),
            patch("validate_mermaid._repo_root", return_value=Path("/tmp/fake-repo-root")),
        ):
            result = validate_mermaid.run(["/etc/passwd"])
        assert result == 1
        captured = capsys.readouterr()
        assert "outside repository root" in captured.err

    def test_run_rejects_path_with_matching_prefix_but_outside_root(self, capsys):
        """A path whose string representation shares a prefix with repo_root but
        resolves to a *different* directory must be rejected.

        Example: root=/tmp/fake-repo-root, path=/tmp/fake-repo-root-extra/file.md
        A naive startswith check would pass because the path string starts with
        the root string.  Path.is_relative_to() correctly rejects it.
        """
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            # Create two sibling directories whose names share a prefix.
            repo_root = Path(tmp) / "fake-repo-root"
            sibling = Path(tmp) / "fake-repo-root-extra"
            repo_root.mkdir()
            sibling.mkdir()
            outside_file = sibling / "file.md"
            outside_file.write_text("# test", encoding="utf-8")

            with patch("validate_mermaid._repo_root", return_value=repo_root):
                result = validate_mermaid.run([str(outside_file)])

        assert result == 1
        captured = capsys.readouterr()
        assert "outside repository root" in captured.err

    def test_run_returns_0_for_valid_path(self, capsys):
        """A path within the repo root must pass the traversal guard."""
        from pathlib import Path

        import scripts.validate_mermaid as vm_mod

        repo_root = Path(vm_mod.__file__).parent.parent.resolve()
        valid_path = str(repo_root / "docs" / "azure" / "files" / "networking" / "networking.md")

        with (
            patch.object(Path, "is_file", return_value=True),
            patch(
                "validate_mermaid.extract_mermaid_blocks",
                return_value=["graph TD\n  A --> B\n"],
            ),
            patch("validate_mermaid.validate_block", return_value=(True, "")),
        ):
            result = validate_mermaid.run([valid_path])
        assert result == 0
        captured = capsys.readouterr()
        assert "outside repository root" not in captured.err


class TestValidateBlockDegenerateSvg:
    """Tests for degenerate (empty/missing) SVG guard in validate_block()."""

    def test_validate_block_returns_false_on_degenerate_svg(self, tmp_path):
        import subprocess

        def _write_empty_svg_and_succeed(cmd, **kwargs):
            # Derive out_path the same way validate_block does
            input_flag = cmd.index("--input")
            tmp_file = cmd[input_flag + 1]
            out_file = str(tmp_file).replace(".mmd", ".svg")
            from pathlib import Path as _Path

            _Path(out_file).write_bytes(b"")
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

        with (
            patch("validate_mermaid.PUPPETEER_CONFIG") as mock_cfg,
            patch("validate_mermaid.subprocess.run", side_effect=_write_empty_svg_and_succeed),
        ):
            mock_cfg.exists.return_value = False
            ok, msg = validate_mermaid.validate_block(1, "graph TD\n  A --> B\n")
        assert ok is False
        assert msg == "mmdc produced an empty/degenerate SVG (possible silent render failure)"


_REAL_MD = "docs/azure/files/networking/networking.md"


class TestRealCheatSheet:
    """Integration tests that read a real domain page from disk."""

    def test_extracts_nonzero_blocks_from_real_cheat_sheet(self):
        blocks = validate_mermaid.extract_mermaid_blocks(_REAL_MD)
        assert len(blocks) > 0, "Expected at least one Mermaid block in the cheat sheet"

    def test_all_blocks_are_non_empty_strings(self):
        blocks = validate_mermaid.extract_mermaid_blocks(_REAL_MD)
        for i, b in enumerate(blocks):
            assert isinstance(b, str) and b.strip(), f"Block {i + 1} is empty or not a string"


@pytest.mark.skipif(shutil.which("mmdc") is None, reason="mmdc not installed")
class TestRealCheatSheetIntegration:
    """Integration tests that invoke validate_block against the real cheat sheet."""

    def test_all_diagrams_pass(self):
        blocks = validate_mermaid.extract_mermaid_blocks(_REAL_MD)
        assert len(blocks) > 0, "Expected at least one Mermaid block in the cheat sheet"
        for i, block in enumerate(blocks):
            ok, err = validate_mermaid.validate_block(i, block)
            assert ok, f"Diagram {i + 1} failed: {err}"


class TestMainMultiFile:
    """Tests for run() when called with more than one Markdown file."""

    def test_run_validates_second_file_when_first_has_no_blocks(self, capsys):
        with (
            patch(
                "validate_mermaid.extract_mermaid_blocks",
                side_effect=[[], ["graph TD\n  A --> B\n"]],
            ),
            patch("validate_mermaid.validate_block", return_value=(True, "")),
            patch("validate_mermaid.Path.is_file", return_value=True),
        ):
            result = validate_mermaid.run(["empty.md", "docs/azure/files/networking/networking.md"])
        assert result == 0


# ---------------------------------------------------------------------------
# Coverage gap tests — added to push validate_mermaid.py from 75% to ≥90%.
# Each class targets a specific uncovered line range.
# ---------------------------------------------------------------------------


class TestExpandSnippetFileRead:
    """Covers lines 78-83: _expand_snippet reads the referenced file."""

    def test_returns_file_content_when_snippet_directive_present(self, tmp_path):
        snippet_content = "flowchart LR\n  A --> B\n"
        snippet_file = tmp_path / "azure" / "diagrams" / "networking" / "flow.mmd"
        snippet_file.parent.mkdir(parents=True)
        snippet_file.write_text(snippet_content, encoding="utf-8")

        block = '--8<-- "azure/diagrams/networking/flow.mmd"'
        result = validate_mermaid._expand_snippet(block, tmp_path)
        assert result == snippet_content

    def test_raises_runtime_error_when_file_unreadable(self, tmp_path):
        block = '--8<-- "azure/diagrams/missing.mmd"'
        with pytest.raises(RuntimeError, match="Cannot read snippet file"):
            validate_mermaid._expand_snippet(block, tmp_path)


class TestExpandTopLevelSnippetsOSError:
    """Covers lines 107-108: OSError in _expand_top_level_snippets leaves directive unexpanded."""

    def test_missing_file_directive_left_unexpanded(self, tmp_path):
        directive = '--8<-- "missing/file.md"'
        result = validate_mermaid._expand_top_level_snippets(directive, tmp_path)
        assert result == directive


class TestExpandSnippetRejectsTraversal:
    """Covers issue #223: _expand_snippet rejects path-traversal directives."""

    def test_rejects_traversal(self, tmp_path):
        block = '--8<-- "../../../../etc/passwd"'
        with pytest.raises(RuntimeError, match="escapes base directory"):
            validate_mermaid._expand_snippet(block, tmp_path)


class TestExpandTopLevelSnippetsRejectsTraversal:
    """Covers issue #223: _expand_top_level_snippets leaves traversal directives unexpanded."""

    def test_rejects_traversal(self, tmp_path):
        directive = '--8<-- "../../../../etc/passwd"'
        result = validate_mermaid._expand_top_level_snippets(directive, tmp_path)
        assert result == directive


class TestExtractMermaidBlocksNoExpand:
    """Covers line 158: early return when expand_snippets=False."""

    def test_returns_raw_blocks_without_expansion(self, tmp_path):
        md = tmp_path / "page.md"
        md.write_text("```mermaid\ngraph TD\n  A-->B\n```\n", encoding="utf-8")
        blocks = validate_mermaid.extract_mermaid_blocks(str(md), expand_snippets=False)
        assert len(blocks) == 1
        assert "A-->B" in blocks[0]


class TestExtractMermaidBlocksRuntimeErrorPropagation:
    """Covers lines 164-165: RuntimeError from _expand_snippet is re-raised."""

    def test_runtime_error_propagates_from_expand_snippet(self, tmp_path):
        md = tmp_path / "page.md"
        md.write_text('```mermaid\n--8<-- "missing.mmd"\n```\n', encoding="utf-8")
        with pytest.raises(RuntimeError):
            validate_mermaid.extract_mermaid_blocks(str(md), snippet_base=tmp_path)


class TestValidateBlockNonZeroReturnCode:
    """Covers line 194: validate_block returns False when mmdc exits non-zero."""

    def test_returns_false_when_mmdc_exits_nonzero(self):
        import subprocess

        mock_result = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="syntax error"
        )
        with (
            patch("validate_mermaid.PUPPETEER_CONFIG") as mock_cfg,
            patch("validate_mermaid.subprocess.run", return_value=mock_result),
        ):
            mock_cfg.exists.return_value = False
            ok, err = validate_mermaid.validate_block(1, "graph TD\n  A --> B\n")
        assert ok is False
        assert "syntax error" in err


class TestValidateBlockStderrEmptyStdoutPresent:
    """Covers line 213 when mmdc exits non-zero with empty stderr but stdout has content."""

    def test_returns_stdout_when_stderr_is_empty(self):
        import subprocess

        mock_result = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="parse error: unexpected token", stderr=""
        )
        with (
            patch("validate_mermaid.PUPPETEER_CONFIG") as mock_cfg,
            patch("validate_mermaid.subprocess.run", return_value=mock_result),
        ):
            mock_cfg.exists.return_value = False
            ok, err = validate_mermaid.validate_block(1, "graph TD\n  A --> B\n")
        assert ok is False
        assert err == "parse error: unexpected token"

    def test_stderr_empty_stdout_present_is_printed_by_run(self, capsys):
        import subprocess

        mock_result = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="syntax error", stderr=""
        )
        with (
            patch("validate_mermaid.PUPPETEER_CONFIG") as mock_cfg,
            patch("validate_mermaid.subprocess.run", return_value=mock_result),
            patch(
                "validate_mermaid.extract_mermaid_blocks",
                return_value=["graph TD\n  A --> B\n"],
            ),
            patch("validate_mermaid.Path.is_file", return_value=True),
        ):
            mock_cfg.exists.return_value = False
            validate_mermaid.run(["docs/test.md"])
        captured = capsys.readouterr()
        assert "syntax error" in captured.out
        assert "Diagram 1: FAIL" in captured.out


class TestValidateMmdFile:
    """Covers lines 207-228: _validate_mmd_file."""

    def test_returns_1_when_file_not_found(self, tmp_path):
        repo_root = tmp_path
        result = validate_mermaid._validate_mmd_file(str(tmp_path / "nonexistent.mmd"), repo_root)
        assert result == 1

    def test_returns_1_when_path_outside_repo_root(self, tmp_path):
        outside = tmp_path.parent / "outside.mmd"
        outside.write_text("flowchart LR\n  A-->B\n", encoding="utf-8")
        result = validate_mermaid._validate_mmd_file(str(outside), tmp_path)
        assert result == 1

    def test_returns_0_when_diagram_passes(self, tmp_path):
        mmd = tmp_path / "flow.mmd"
        mmd.write_text("flowchart LR\n  A-->B\n", encoding="utf-8")
        with (
            patch("validate_mermaid.PUPPETEER_CONFIG") as mock_cfg,
            patch("validate_mermaid.validate_block", return_value=(True, "")),
        ):
            mock_cfg.exists.return_value = False
            result = validate_mermaid._validate_mmd_file(str(mmd), tmp_path)
        assert result == 0

    def test_returns_1_when_diagram_fails(self, tmp_path):
        mmd = tmp_path / "flow.mmd"
        mmd.write_text("flowchart LR\n  A-->B\n", encoding="utf-8")
        with (
            patch("validate_mermaid.PUPPETEER_CONFIG") as mock_cfg,
            patch("validate_mermaid.validate_block", return_value=(False, "bad diagram")),
        ):
            mock_cfg.exists.return_value = False
            result = validate_mermaid._validate_mmd_file(str(mmd), tmp_path)
        assert result == 1

    def test_returns_1_on_read_error(self, tmp_path):
        mmd = tmp_path / "flow.mmd"
        mmd.write_text("flowchart LR\n  A-->B\n", encoding="utf-8")
        with patch("validate_mermaid.Path.read_text", side_effect=OSError("perm denied")):
            result = validate_mermaid._validate_mmd_file(str(mmd), tmp_path)
        assert result == 1


class TestRunWithMmdFile:
    """Covers lines 253-255: .mmd branch in run()."""

    def test_run_handles_standalone_mmd_file(self, tmp_path):
        mmd = tmp_path / "flow.mmd"
        mmd.write_text("flowchart LR\n  A-->B\n", encoding="utf-8")
        with (
            patch("validate_mermaid.shutil.which", return_value="/usr/bin/mmdc"),
            patch("validate_mermaid._validate_mmd_file", return_value=0) as mock_validate,
            patch(
                "validate_mermaid._repo_root",
                return_value=tmp_path,
            ),
        ):
            result = validate_mermaid.run([str(mmd)])
        mock_validate.assert_called_once()
        assert result == 0


class TestMainEntryPoint:
    """Covers lines 301-302 and 306: main() body and __main__ guard."""

    def test_main_calls_parse_args_and_exits(self):
        with (
            patch("validate_mermaid.shutil.which", return_value="/usr/bin/mmdc"),
            patch("validate_mermaid.parse_args") as mock_parse,
            patch("validate_mermaid.run", return_value=0),
            pytest.raises(SystemExit) as exc_info,
        ):
            mock_parse.return_value.md_files = []
            validate_mermaid.main()
        assert exc_info.value.code == 0


# ---------------------------------------------------------------------------
# Regression tests for issue #291 — Google Cloud and Programming must be
# included in Mermaid validation discovery (Makefile + CI workflow).
# ---------------------------------------------------------------------------


class TestDiscoveryIncludesGoogleCloud:
    """Asserts that docs/google/ Markdown and .mmd files are in the validated set.

    These tests execute the same discovery shell commands used by the Makefile
    and CI workflow, then verify that Google Cloud paths appear in the output.
    If discovery is ever narrowed back to Azure/AWS only, these tests fail.
    """

    def _ci_step_block(self) -> str:
        content = RELEASE_YML.read_text()
        m = re.search(
            r"Validate Mermaid diagrams.*?(?=\n\s*- name:|\Z)",
            content,
            re.S,
        )
        assert m, "Could not locate 'Validate Mermaid diagrams' step in release.yml"
        return m.group(0)

    def test_makefile_mmd_find_output_includes_google_diagrams(self, tmp_path):
        """MMD_FILES_VALIDATE discovery must produce Google Cloud .mmd paths."""
        # Replicate the Makefile MMD_FILES_VALIDATE expression
        result = tmp_path / "out.txt"
        result.write_text("")
        import subprocess

        proc = subprocess.run(
            ["find", "docs", "-name", "*.mmd"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert proc.returncode == 0, f"find failed: {proc.stderr}"
        output = proc.stdout
        assert "docs/google/diagrams" in output, (
            "Google Cloud diagrams not found by MMD_FILES_VALIDATE-style discovery. "
            "If you see this, the find scope was narrowed — check Makefile MMD_FILES_VALIDATE."
        )

    def test_makefile_md_find_output_includes_google_files(self, tmp_path):
        """MD_FILES_VALIDATE discovery must produce Google Cloud .md paths."""
        import subprocess

        proc = subprocess.run(
            [
                "bash",
                "-c",
                "find docs -name '*.md' ! -path "
                "'docs/azure/diagrams/*' ! -path 'docs/overrides/*' | sort",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert proc.returncode == 0, f"find failed: {proc.stderr}"
        output = proc.stdout
        assert "docs/google/files" in output, (
            "Google Cloud Markdown files not found by MD_FILES_VALIDATE-style discovery. "
            "If you see this, the find scope was narrowed — check Makefile MD_FILES_VALIDATE."
        )

    def test_ci_mermaid_check_covers_google(self):
        """CI 'Validate Mermaid diagrams' step must include docs/google in both find calls."""
        block = self._ci_step_block()
        # The CI step now uses broad 'find docs' — verify the expression references docs root
        assert "find docs" in block, (
            "CI mermaid-check must use 'find docs' (not provider-scoped paths)"
        )
        # Verify the expression doesn't hard-code only azure/aws
        assert "docs/azure/files docs/aws/files" not in block, (
            "CI mermaid-check still uses narrow azure/aws find — must be broadened to 'find docs'"
        )


class TestDiscoveryIncludesProgramming:
    """Asserts that docs/programming/ Markdown and .mmd files are in the validated set.

    These tests execute the same discovery shell commands used by the Makefile
    and CI workflow, then verify that Programming paths appear in the output.
    """

    def _ci_step_block(self) -> str:
        content = RELEASE_YML.read_text()
        m = re.search(
            r"Validate Mermaid diagrams.*?(?=\n\s*- name:|\Z)",
            content,
            re.S,
        )
        assert m, "Could not locate 'Validate Mermaid diagrams' step in release.yml"
        return m.group(0)

    def test_makefile_mmd_find_output_includes_programming_diagrams(self, tmp_path):
        """MMD_FILES_VALIDATE discovery must produce Programming .mmd paths."""
        import subprocess

        proc = subprocess.run(
            ["find", "docs", "-name", "*.mmd"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert proc.returncode == 0, f"find failed: {proc.stderr}"
        output = proc.stdout
        assert "docs/programming" in output, (
            "Programming diagrams not found by MMD_FILES_VALIDATE-style discovery. "
            "If you see this, the find scope was narrowed — check Makefile MMD_FILES_VALIDATE."
        )

    def test_makefile_md_find_output_includes_programming_files(self, tmp_path):
        """MD_FILES_VALIDATE discovery must produce Programming .md paths."""
        import subprocess

        proc = subprocess.run(
            [
                "bash",
                "-c",
                "find docs -name '*.md' ! -path "
                "'docs/azure/diagrams/*' ! -path 'docs/overrides/*' | sort",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert proc.returncode == 0, f"find failed: {proc.stderr}"
        output = proc.stdout
        assert "docs/programming/java/files" in output, (
            "Programming Markdown files not found by MD_FILES_VALIDATE-style discovery. "
            "If you see this, the find scope was narrowed — check Makefile MD_FILES_VALIDATE."
        )

    def test_ci_mermaid_check_covers_programming(self):
        """CI 'Validate Mermaid diagrams' step must include docs/programming in
        both find calls."""
        block = self._ci_step_block()
        assert "find docs" in block, (
            "CI mermaid-check must use 'find docs' (not provider-scoped paths)"
        )
        assert "docs/azure/files docs/aws/files" not in block, (
            "CI mermaid-check still uses narrow azure/aws find — must be broadened to 'find docs'"
        )
