#!/usr/bin/env python3
"""CalVer version bump utility.

Computes the next calendar version (YYYY.MM.DD[.micro]) and updates pyproject.toml.

Exit codes:
    0 — Success, new version printed to stdout
    1 — Error (invalid input, file not found, etc.)
    2 — Version unchanged (already at latest for today)
"""

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).parent.parent.resolve()


def _read_pyproject() -> str:
    path = _repo_root() / "pyproject.toml"
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"Cannot read pyproject.toml: {exc}") from exc


def _write_pyproject(content: str) -> None:
    path = _repo_root() / "pyproject.toml"
    try:
        path.write_text(content, encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"Cannot write pyproject.toml: {exc}") from exc


def _extract_version(content: str) -> str:
    match = re.search(r'^version\s*=\s*"([^"]+)"', content, re.MULTILINE)
    if not match:
        raise RuntimeError("version not found in pyproject.toml [project] section")
    return match.group(1)


def _parse_calver(version: str) -> tuple[int, int, int, int]:
    """Parse CalVer string into (year, month, day, micro).

    Accepts YYYY.MM.DD or YYYY.MM.DD.micro
    """
    parts = version.split(".")
    if len(parts) not in (3, 4):
        raise ValueError(f"Invalid CalVer format: {version} (expected YYYY.MM.DD[.micro])")
    try:
        year, month, day = map(int, parts[:3])
        micro = int(parts[3]) if len(parts) == 4 else 0
    except ValueError as exc:
        raise ValueError(f"Non-numeric version component in: {version}") from exc
    return year, month, day, micro


def _format_calver(year: int, month: int, day: int, micro: int) -> str:
    if micro == 0:
        return f"{year:04d}.{month:02d}.{day:02d}"
    return f"{year:04d}.{month:02d}.{day:02d}.{micro}"


def _compute_next_version(current: str, override: str | None) -> tuple[str, bool]:
    """Return (new_version, changed)."""
    if override:
        # Validate override format
        _parse_calver(override)
        return override, override != current

    today = datetime.now().date()
    cur_year, cur_month, cur_day, cur_micro = _parse_calver(current)

    if (cur_year, cur_month, cur_day) == (today.year, today.month, today.day):
        # Same day — increment micro
        return _format_calver(today.year, today.month, today.day, cur_micro + 1), True
    else:
        # New day — reset micro to 0
        return _format_calver(today.year, today.month, today.day, 0), True


def _update_version_in_content(content: str, new_version: str) -> str:
    return re.sub(
        r'^version\s*=\s*"[^"]+"',
        f'version = "{new_version}"',
        content,
        count=1,
        flags=re.MULTILINE,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Bump CalVer version in pyproject.toml")
    parser.add_argument(
        "override",
        nargs="?",
        help=(
            "Explicit version to set (CalVer YYYY.MM.DD[.micro]). "
            "If omitted, computes next version from current date."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print new version without writing pyproject.toml",
    )
    args = parser.parse_args()

    try:
        content = _read_pyproject()
        current = _extract_version(content)
        new_version, changed = _compute_next_version(current, args.override)

        if not changed:
            print(f"Version unchanged: {current}", file=sys.stderr)
            return 2

        if args.dry_run:
            print(new_version)
            return 0

        updated = _update_version_in_content(content, new_version)
        _write_pyproject(updated)
        print(new_version)
        return 0

    except (RuntimeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
