# Unattended 13F Refresh and Deployment Master Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the existing 13F dashboard into a correctness-gated, unattended SEC refresh and immutable VPS deployment system with rollback and GitHub Issue/email notification.

**Architecture:** Execute three independently reviewable plans in strict order: repair data correctness, build a deterministic release pipeline, then add hardened VPS deployment and production validation. Production remains on its current container until all correctness and release gates have passed.

**Tech Stack:** Python 3.11, SQLite, lxml, pytest, Streamlit, Docker/BuildKit, GitHub Actions, GHCR, Ubuntu 24.04, OpenSSH.

## Global Constraints

- SEC EDGAR is the only primary truth source.
- Deterministic calculations only; no LLM-derived numbers or mappings.
- Unknown security mapping remains `UNRESOLVED`; never guess a ticker.
- `13F-HR/A` must follow SEC `RESTATEMENT` versus `ADD_NEW_HOLDINGS` semantics.
- Raw information-table rows remain immutable; analytics use explicit effective-position aggregation.
- Gate 1 must reconcile at least 5 managers × 3 quarters × 10 rows with 100% agreement.
- Gate 2 must independently verify at least 30 real transitions across at least 5 managers.
- Gate 3 remains `PENDING_REAL_WORLD_VALIDATION`.
- Any hard-gate failure blocks image publication and deployment.
- Production deploys only references matching `^ghcr\.io/fancy0121/13f-intelligence@sha256:[0-9a-f]{64}$`.
- No secret may enter Git, an image layer, cache, artifact, log, or Issue body.
- Do not overwrite, delete, or stage `reports/USER_GUIDE_SIMPLE.md` unless separately reviewed and explicitly selected.
- Keep the current uncommitted UI/bilingual changes separate from automation commits.

---

## Plan Set and Dependency Order

1. `docs/superpowers/plans/2026-09-05-01-data-correctness-foundation.md`
   - Repairs SEC metadata, amendment state, duplicate-row aggregation, product queries, and Gate 1/2.
   - Blocks every later plan.
2. `docs/superpowers/plans/2026-09-05-02-release-automation.md`
   - Creates clean release bundles, hard quality gates, locked dependencies, hardened images, CI, refresh, and Issue notification.
   - Requires Plan 1 PASS.
3. `docs/superpowers/plans/2026-09-05-03-vps-deployment-validation.md`
   - Adds restricted digest deployment, candidate promotion, rollback, GitHub/VPS configuration, and real production evidence.
   - Requires Plan 2 PASS.

## Preflight: Preserve the Existing Working Tree

**Files:**
- Review and commit only the already-modified UI/product/documentation files shown by `git status`.
- Preserve untracked: `reports/USER_GUIDE_SIMPLE.md`.
- Create execution worktree: `../13f-intelligence-unattended` on branch `codex/unattended-refresh-deploy`.

**Interfaces:**
- Consumes: current `master` at design commit `e6eb873` plus reviewed UI changes.
- Produces: a clean base commit and an isolated worktree for Plans 1–3.

- [ ] **Step 1: Capture the exact dirty-file allowlist**

Run:

```powershell
git status --short
git diff --name-only
git ls-files --others --exclude-standard
```

Expected: UI/bilingual files remain modified; the design is committed; `reports/USER_GUIDE_SIMPLE.md` remains untracked.

- [ ] **Step 2: Re-run the existing baseline before committing UI work**

Run:

```powershell
python -m pytest -q
python -m compileall -q src app scripts
git diff --check
```

Expected: all existing tests pass, compile exits 0, and diff check is clean. If any fails, stop and fix only the pre-existing UI scope before continuing.

- [ ] **Step 3: Stage the reviewed UI allowlist only**

Run:

```powershell
git add -- Dockerfile README_DEPLOY.md README_USER.md app/pages/activity.py app/pages/managers.py app/pages/methodology.py app/pages/observation.py app/pages/overview.py app/pages/portfolio.py app/pages/securities.py app/ui.py config/display_names.csv deploy/hostinger_vps.md docs/limitations.md docs/product_methodology_and_limitations.md src/thirteenf/product/evidence.py tests/product/test_app_smoke.py tests/product/test_user_delivery.py
git diff --cached --name-status
git diff --cached --check
```

Expected: the staged list contains only the named UI/product delivery files and never contains `reports/USER_GUIDE_SIMPLE.md`.

- [ ] **Step 4: Commit the UI checkpoint**

Run:

```powershell
git commit -m "fix(ui): complete bilingual public dashboard"
```

Expected: one focused UI commit; `git status --short` shows only the preserved untracked user guide.

- [ ] **Step 5: Create the isolated implementation worktree**

Run the `using-git-worktrees` skill. Select a repository-local ignored worktree directory if the repository already has one; otherwise use the sibling path below:

```powershell
git worktree add ..\13f-intelligence-unattended -b codex/unattended-refresh-deploy master
git -C ..\13f-intelligence-unattended status --short --branch
```

Expected: clean `codex/unattended-refresh-deploy` worktree based on the UI checkpoint; the original worktree still contains the untouched untracked user guide.

## Cross-Plan Review Rules

- Every task begins with a failing focused test and ends with focused tests plus the relevant broader suite.
- Each commit contains one independently reviewable behavior; never batch data semantics, workflow permissions, and VPS operations together.
- After every plan, run full pytest, compile, `git diff --check`, a secret-pattern scan, and a fresh-database rebuild appropriate to that plan.
- A reviewer must compare implementation against `docs/superpowers/specs/2026-09-05-unattended-refresh-deploy-design.md` before the next plan starts.
- Existing production remains untouched until Plan 3's explicit deployment task.

## Completion State

The project may report `AUTOMATION_IMPLEMENTED_LOCAL` after Plans 1–2 pass locally. It may report `AUTOMATION_CONFIGURED` only after GitHub and VPS readback confirms configuration. It may report `UNATTENDED_DELIVERY_COMPLETE` only after the production digest, public health, rollback drill, Issue lifecycle, and email receipt are evidenced. The first scheduled run remains `SCHEDULE_CONFIGURED_NOT_YET_OBSERVED` until it actually executes.
