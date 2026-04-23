"""Apply GitHub branch protection rules via gh CLI."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Apply standard branch protection rules to a GitHub repository branch."
    )
    parser.add_argument("--owner", required=True, help="GitHub repository owner")
    parser.add_argument("--repo", required=True, help="GitHub repository name")
    parser.add_argument(
        "--branch",
        required=True,
        choices=["main", "develop"],
        help="Branch name to protect",
    )
    parser.add_argument(
        "--required-approvals",
        type=int,
        default=1,
        help="Required approving review count",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    if shutil.which("gh") is None:
        print("GitHub CLI (gh) is required. Install gh and run 'gh auth login'.", file=sys.stderr)
        return 1

    body = {
        "required_status_checks": {
            "strict": True,
            "checks": [
                {"context": "lint-and-format"},
                {"context": "Test (ubuntu-latest)"},
                {"context": "Test (windows-latest)"},
            ],
        },
        "enforce_admins": True,
        "required_pull_request_reviews": {
            "dismiss_stale_reviews": True,
            "require_code_owner_reviews": True,
            "required_approving_review_count": args.required_approvals,
        },
        "restrictions": None,
        "required_linear_history": False,
        "allow_force_pushes": False,
        "allow_deletions": False,
        "required_conversation_resolution": True,
    }

    api_path = f"/repos/{args.owner}/{args.repo}/branches/{args.branch}/protection"

    try:
        subprocess.run(
            [
                "gh",
                "api",
                api_path,
                "--method",
                "PUT",
                "--input",
                "-",
                "--header",
                "Accept: application/vnd.github+json",
            ],
            input=json.dumps(body),
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        print(f"Failed to apply branch protection: {exc}", file=sys.stderr)
        return exc.returncode

    print("Branch protection applied successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
