# Release Checklist

Use this checklist before creating a release tag.

## Pre-release Validation

1. Pull latest `main` and ensure CI is green.
2. Run local quality gate:

```powershell
./scripts/quality_gate.ps1 -SkipStyleChecks
```

3. Ensure migrations are up to date:

```powershell
./scripts/db_migrate.ps1
```

4. Update `CHANGELOG.md`:
   - Keep `## [Unreleased]` section.
   - Add a version section in this format:

```markdown
## [0.1.0] - 2026-04-23

### Added
- ...
```

## Tag and Release

1. Create tag:

```bash
git tag v0.1.0
```

2. Push tag:

```bash
git push origin v0.1.0
```

3. Verify GitHub Release workflow succeeds.

## Post-release

1. Confirm release artifact is downloadable.
2. Verify docs and changelog links in release notes.
3. Start next cycle under `## [Unreleased]`.
