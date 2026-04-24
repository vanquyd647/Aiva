"""Validate that code changes include CHANGELOG and AI worklog updates."""

from __future__ import annotations

import argparse
import subprocess
import sys

REQUIRED_DOC_FILES = {"CHANGELOG.md", "docs/ai-worklog.md"}


def _normalize(path: str) -> str:
    return path.replace("\\", "/").strip()


def _is_code_change(path: str) -> bool:
    normalized = _normalize(path)
    if not normalized:
        return False
    if normalized in REQUIRED_DOC_FILES:
        return False
    if normalized.startswith("docs/"):
        return False
    if normalized.endswith(".md"):
        return False
    return True


def _changed_files(diff_range: str) -> list[str]:
    diff_command = ["git", "diff", "--name-only", diff_range]
    diff_completed = subprocess.run(diff_command, capture_output=True, text=True, check=False)
    if diff_completed.returncode != 0:
        return []

    untracked_command = ["git", "ls-files", "--others", "--exclude-standard"]
    untracked_completed = subprocess.run(
        untracked_command,
        capture_output=True,
        text=True,
        check=False,
    )

    lines = [_normalize(line) for line in diff_completed.stdout.splitlines()]
    untracked = (
        [_normalize(line) for line in untracked_completed.stdout.splitlines()]
        if untracked_completed.returncode == 0
        else []
    )
    combined = {line for line in lines + untracked if line}
    return sorted(combined)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Require CHANGELOG.md and docs/ai-worklog.md when code changes are present"
    )
    parser.add_argument(
        "--diff-range",
        default="HEAD",
        help="Git diff range to inspect (default: HEAD for local working tree)",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    changed = _changed_files(args.diff_range)
    if not changed:
        print(f"Doc guard: no diff detected for range {args.diff_range}, skipping")
        return 0

    code_changes = [path for path in changed if _is_code_change(path)]
    if not code_changes:
        print("Doc guard: no code changes detected, skipping")
        return 0

    changed_set = set(changed)
    missing = [path for path in sorted(REQUIRED_DOC_FILES) if path not in changed_set]
    if missing:
        print(
            "Doc guard failed: code changes detected but required docs were not updated:",
            file=sys.stderr,
        )
        for path in missing:
            print(f"- {path}", file=sys.stderr)
        print("Changed code files:", file=sys.stderr)
        for path in code_changes:
            print(f"- {path}", file=sys.stderr)
        return 1

    print("Doc guard passed: CHANGELOG.md and docs/ai-worklog.md were updated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
