# CI Pipeline Enhancement — Implementation Plan

**Objective**: Enhance the existing CI/CD pipeline with:
1. ✅ PR gates (already exists via `lint.yml` on `pull_request`)
2. 🔄 Deploy/release pipeline with CalVer versioning
3. 📦 Automated release creation with changelog

---

## Current State Analysis

### Existing Workflows

| Workfile | Trigger | Jobs | Notes |
|----------|---------|------|-------|
| `lint.yml` | `push` to main, `pull_request` | markdownlint, python-lint, python-test (matrix), link-check, docs-build, npm-audit, mermaid-check | Full PR gate — runs on every PR |
| `prod-deploy.yml` | `workflow_run` (Lint success on main) | Vercel deploy | Production deploy only, no versioning |

### Gaps Identified

| Requirement | Status | Gap |
|-------------|--------|-----|
| PR gates | ✅ Done | `lint.yml` runs on `pull_request` |
| Deploy pipeline | 🟡 Partial | Deploys to Vercel but no version/tag/release |
| CalVer releases | ❌ Missing | No version bump, tagging, GitHub Release, changelog |

---

## CalVer Strategy

**Format**: `YYYY.MM.DD[.micro]` (e.g., `2026.09.07`, `2026.09.07.1`)

- **Major**: Year.Month.Day of release
- **Micro**: Increment for multiple releases same day (optional)
- **No semantic versioning** — pure calendar versioning

### Version Sources
- **Single source of truth**: `pyproject.toml` `[project] version`
- **Git tag**: `v<version>` (e.g., `v2026.09.07`)
- **GitHub Release**: Auto-generated from changelog

---

## Implementation Plan

### Phase 1: Version Management Infrastructure

#### 1.1 Add Version Bump Script
Create `scripts/bump_version.py`:
- Read current version from `pyproject.toml`
- Compute next CalVer (today's date + micro if same day)
- Update `pyproject.toml` version
- Return new version for use in workflow

#### 1.2 Add Changelog Generator
Create `scripts/generate_changelog.py`:
- Parse git log since last tag
- Categorize commits (feat, fix, docs, chore, etc.)
- Output Markdown for GitHub Release body

---

### Phase 2: Release Workflow (`.github/workflows/release.yml`)

**Trigger**: Manual (`workflow_dispatch`) + optional schedule

**Jobs**:

| Job | Purpose | Key Steps |
|-----|---------|-----------|
| `prepare-release` | Version bump, tag, push | Run bump script, commit `pyproject.toml`, create git tag `v<version>`, push |
| `build-release` | Build artifacts | Run `make ci`, build MkDocs site |
| `create-github-release` | GitHub Release | Use `generate_changelog.py`, create release via `gh release create` |
| `deploy-vercel` | Deploy to Vercel | Reuse existing prod-deploy logic, but triggered by release |

**Flow**:
```
workflow_dispatch
    │
    ▼
prepare-release ──► tag pushed
    │
    ▼
build-release (needs: prepare-release)
    │
    ▼
create-github-release (needs: build-release)
    │
    ▼
deploy-vercel (needs: create-github-release)
```

---

### Phase 3: PR Gate Enhancement

#### 3.1 Add PR Gate Workflow (`.github/workflows/pr-gate.yml`)
Separate lightweight gate for PRs that runs **before** full lint:
- Quick checks: markdownlint, ruff check, test (single Python version)
- Fail fast on obvious issues
- Optional: Label-based skip for docs-only changes

#### 3.2 Update `lint.yml`
- Keep as the "full CI" running on push to main
- Remove `pull_request` trigger (moved to `pr-gate.yml`)
- Add `needs: pr-gate` for main branch runs (optional optimization)

---

### Phase 4: Dependabot Integration

#### 4.1 Update `.github/dependabot.yml`
- Add `labels` for auto-assigning PRs
- Ensure grouped PRs pass PR gate before merge

---

### Phase 5: Documentation Updates

- Update `CONTRIBUTING.md` with release process
- Update `AGENTS.md` with new workflow targets
- Add `RELEASE.md` for release manager reference

---

## File Changes Summary

### New Files
```
.github/workflows/pr-gate.yml          # Lightweight PR gate
.github/workflows/release.yml          # Release + deploy pipeline
scripts/bump_version.py                # CalVer bump logic
scripts/generate_changelog.py          # Changelog from git log
RELEASE.md                             # Release process docs
```

### Modified Files
```
.github/workflows/lint.yml             # Remove pull_request trigger
.github/dependabot.yml                 # Add labels
pyproject.toml                         # Version managed by bump script
CONTRIBUTING.md                        # Release process section
AGENTS.md                              # Update CI targets table
Makefile                               # Add release targets (optional)
```

---

## Workflow Details

### `pr-gate.yml` (New)
```yaml
name: PR Gate
on:
  pull_request:
    types: [opened, synchronize, reopened]

jobs:
  quick-lint:
    runs-on: ubuntu-latest
    steps:
      - checkout
      - setup-python (3.11)
      - install dev deps
      - ruff check scripts/ tests/
      - ruff format --check scripts/ tests/
  quick-test:
    runs-on: ubuntu-latest
    steps:
      - checkout
      - setup-python (3.11)
      - install dev deps
      - pytest tests/ -v --cov=scripts --cov-fail-under=90
  markdownlint:
    runs-on: ubuntu-latest
    steps:
      - checkout
      - markdownlint-cli2-action
```

### `release.yml` (New)
```yaml
name: Release
on:
  workflow_dispatch:
    inputs:
      version:
        description: 'Override version (CalVer YYYY.MM.DD[.micro])'
        required: false
        type: string
      skip_deploy:
        description: 'Skip Vercel deploy'
        required: false
        type: boolean
        default: false

permissions:
  contents: write    # for tag, release, commit
  id-token: write    # for Vercel (if using OIDC)

jobs:
  prepare-release:
    runs-on: ubuntu-latest
    outputs:
      version: ${{ steps.bump.outputs.version }}
      tag: ${{ steps.bump.outputs.tag }}
    steps:
      - checkout (fetch-depth: 0)
      - setup-python
      - run: python scripts/bump_version.py ${{ inputs.version }}
      - commit & push pyproject.toml
      - create tag v<version>
      - push tag

  build-release:
    needs: prepare-release
    runs-on: ubuntu-latest
    steps:
      - checkout (ref: ${{ needs.prepare-release.outputs.tag }})
      - make ci

  create-github-release:
    needs: [prepare-release, build-release]
    runs-on: ubuntu-latest
    steps:
      - checkout
      - run: python scripts/generate_changelog.py ${{ needs.prepare-release.outputs.tag }}
      - gh release create ${{ needs.prepare-release.outputs.tag }} --notes-file CHANGELOG.md

  deploy-vercel:
    needs: create-github-release
    if: ${{ !inputs.skip_deploy }}
    runs-on: ubuntu-latest
    steps:
      - checkout (ref: ${{ needs.prepare-release.outputs.tag }})
      - vercel pull --environment=production
      - vercel build --prod
      - vercel deploy --prebuilt --prod
```

---

## Rollout Strategy

1. **Phase 1** (Version scripts): Create `bump_version.py` and `generate_changelog.py`, test locally
2. **Phase 2** (PR gate): Add `pr-gate.yml`, verify it runs on PRs
3. **Phase 3** (Release workflow): Add `release.yml`, test manual dispatch
4. **Phase 4** (Cleanup): Remove `pull_request` from `lint.yml`, update docs
5. **Phase 5** (First release): Run release workflow, verify end-to-end

---

## Testing Checklist

- [ ] `make ci` passes locally
- [ ] `pr-gate.yml` runs on new PR
- [ ] `lint.yml` runs on push to main (no PR trigger)
- [ ] `release.yml` manual dispatch creates correct CalVer tag
- [ ] GitHub Release created with proper changelog
- [ ] Vercel deploy triggered from release workflow
- [ ] Version in `pyproject.toml` matches tag
- [ ] Dependabot PRs pass PR gate

---

## Notes

- **No `needs:` between lint jobs** — they run in parallel (current design)
- **Release is manual** — no auto-release on merge to main (explicit control)
- **Micro version** — bump script handles same-day multiple releases
- **Vercel deploy** — uses existing secrets, triggered only on successful release
- **Rollback** — delete tag + release, re-run with corrected version