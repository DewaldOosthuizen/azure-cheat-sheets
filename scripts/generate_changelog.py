#!/usr/bin/env python3
"""Generate changelog from git history since last tag.

Outputs Markdown suitable for GitHub Release notes.

Categories (in order):
    feat     — New features / content additions
    fix      — Bug fixes / corrections
    docs     — Documentation only changes
    chore    — Tooling, CI, dependencies, maintenance
    refactor — Code restructuring without behavior change
    test     — Test additions or modifications
    other    — Uncategorized

Exit codes:
    0 — Success, changelog printed to stdout
    1 — Error (no git repo, no tags, etc.)
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

# Commit message prefixes mapped to changelog sections
CATEGORIES = [
    ("feat", "✨ Features"),
    ("fix", "🐛 Bug Fixes"),
    ("docs", "📚 Documentation"),
    ("chore", "🔧 Chores & Maintenance"),
    ("refactor", "♻️ Refactoring"),
    ("test", "✅ Tests"),
    ("other", "📦 Other Changes"),
]

# Conventional commit regex: type(scope): description
COMMIT_RE = re.compile(r"^(?P<type>\w+)(?:\((?P<scope>[^)]+)\))?:\s*(?P<subject>.+)$")


def _repo_root() -> Path:
    return Path(__file__).parent.parent.resolve()


def _run(cmd: list[str], cwd: Path | None = None) -> str:
    try:
        result = subprocess.run(
            cmd, cwd=cwd or _repo_root(), capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{exc.stderr}") from exc


def _get_last_tag() -> str:
    """Return the most recent tag name, or empty string if none."""
    tags = _run(["git", "tag", "--sort=-v:refname"]).splitlines()
    return tags[0] if tags else ""


def _get_commits_since(tag: str) -> list[str]:
    """Return list of commit subjects since tag (or all if tag empty)."""
    range_spec = f"{tag}..HEAD" if tag else "HEAD"
    log = _run(["git", "log", range_spec, "--pretty=format:%s", "--no-merges"])
    return log.splitlines() if log else []


def _categorize(commits: list[str]) -> dict[str, list[str]]:
    """Group commits by category."""
    buckets: dict[str, list[str]] = {cat: [] for cat, _ in CATEGORIES}

    for commit in commits:
        m = COMMIT_RE.match(commit)
        if not m:
            buckets["other"].append(commit)
            continue

        ctype = m.group("type").lower()
        subject = m.group("subject")
        scope = m.group("scope")

        # Normalize common variations
        if ctype in ("feature", "features"):
            ctype = "feat"
        elif ctype in ("bug", "bugfix"):
            ctype = "fix"
        elif ctype in ("doc",):
            ctype = "docs"

        if ctype not in buckets:
            ctype = "other"

        formatted = f"- {subject}"
        if scope:
            formatted = f"- **{scope}**: {subject}"
        buckets[ctype].append(formatted)

    return buckets


def _format_changelog(buckets: dict[str, list[str]], tag: str) -> str:
    """Render changelog as Markdown."""
    lines = []

    if tag:
        lines.append(f"## Changes since `{tag}`\n")
    else:
        lines.append("## All Changes\n")

    for key, title in CATEGORIES:
        items = buckets.get(key, [])
        if not items:
            continue
        lines.append(f"### {title}\n")
        lines.extend(items)
        lines.append("")  # blank line between sections

    if not any(buckets.values()):
        lines.append("*No changes recorded.*\n")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate changelog from git commits since last tag"
    )
    parser.add_argument(
        "--since-tag",
        help="Generate changelog since this tag (default: latest tag)",
    )
    parser.add_argument(
        "--output",
        help="Write to file instead of stdout",
    )
    args = parser.parse_args()

    try:
        tag = args.since_tag or _get_last_tag()
        commits = _get_commits_since(tag)
        buckets = _categorize(commits)
        changelog = _format_changelog(buckets, tag)

        if args.output:
            Path(args.output).write_text(changelog, encoding="utf-8")
        else:
            print(changelog)
        return 0

    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
