# Contributing

## Branch Strategy

- main: stable branch
- develop: integration branch
- feature/*: new features
- fix/*: bug fixes
- chore/*: maintenance work

## Pull Request Rules

1. Keep PR focused and small.
2. Add or update tests for changed behavior.
3. Update CHANGELOG.md when behavior is user-visible.
4. Update docs/ai-worklog.md for every code change (include date, scope, and verification).
5. Ensure local quality gate passes before requesting review.

## Required CI Checks

Protected branches require these checks:

- lint-and-format
- Test (ubuntu-latest)
- Test (windows-latest)

## Branch Protection

See docs/branch-protection.md for policy details.

Apply from repository root:

```bash
python scripts/apply_branch_protection.py --owner <github-owner> --repo <repo-name> --branch main
python scripts/apply_branch_protection.py --owner <github-owner> --repo <repo-name> --branch develop
```

## Commit Convention

Use conventional commit prefixes:

- feat: new feature
- fix: bug fix
- refactor: internal change
- docs: documentation
- test: tests
- chore: tooling and maintenance

## Local Development Checklist

1. Install runtime and dev dependencies.
2. Configure .env from .env.example.
3. Run backend and verify health endpoints.
4. Run scripts/quality_gate.ps1.
5. Verify scripts/validate_change_docs.py passes (CHANGELOG.md + docs/ai-worklog.md updated when code changes).
6. Open PR with clear summary and test evidence.

## Release Preparation

Before tagging a release, follow docs/release-checklist.md.
