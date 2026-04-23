"""Validate release tag and changelog consistency."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

SEMVER_TAG = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate release metadata before publishing")
    parser.add_argument("--tag", required=True, help="Git tag (expected format: vMAJOR.MINOR.PATCH)")
    parser.add_argument(
        "--changelog",
        default="CHANGELOG.md",
        help="Path to changelog file (default: CHANGELOG.md)",
    )
    return parser


def _fail(message: str) -> int:
    print(f"Release validation failed: {message}", file=sys.stderr)
    return 1


def main() -> int:
    args = build_parser().parse_args()

    tag_match = SEMVER_TAG.match(args.tag)
    if not tag_match:
        return _fail("tag must follow vMAJOR.MINOR.PATCH format")

    version = ".".join(tag_match.groups())

    changelog_path = Path(args.changelog)
    if not changelog_path.exists():
        return _fail(f"changelog file not found: {changelog_path}")

    changelog_text = changelog_path.read_text(encoding="utf-8")

    if "## [Unreleased]" not in changelog_text:
        return _fail("CHANGELOG.md must contain an [Unreleased] section")

    version_heading = f"## [{version}]"
    if version_heading not in changelog_text:
        return _fail(
            f"CHANGELOG.md must include a heading '{version_heading}' before releasing tag {args.tag}"
        )

    print(f"Release validation passed for tag {args.tag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
