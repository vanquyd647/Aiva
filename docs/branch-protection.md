# Branch Protection Baseline

Use this baseline for both `main` and `develop` branches.

## Recommended Rules

1. Require a pull request before merging.
2. Require at least 1 approving review.
3. Dismiss stale approvals when new commits are pushed.
4. Require status checks to pass before merging:
   - `lint-and-format`
   - `Test (ubuntu-latest)`
   - `Test (windows-latest)`
5. Require branches to be up to date before merging.
6. Restrict force pushes.
7. Restrict branch deletion.
8. Require conversation resolution before merging.

## Optional Rules for Mature Repositories

1. Require signed commits.
2. Require linear history.
3. Require merge queue.
4. Restrict who can push directly to protected branches.

## Apply via Script

Use the script from repository root:

```bash
python scripts/apply_branch_protection.py --owner <github-owner> --repo <repo-name> --branch main
python scripts/apply_branch_protection.py --owner <github-owner> --repo <repo-name> --branch develop
```

The script requires:

- GitHub CLI (`gh`) installed
- Authenticated `gh auth login`
- Permission to administer branch protection for the repo
