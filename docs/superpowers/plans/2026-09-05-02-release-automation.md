# Deterministic Release and GitHub Automation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a clean, reproducible release bundle from SEC evidence, block publication on any failed quality/Gate check, publish an immutable GHCR image, and manage failure/recovery GitHub Issues.

**Architecture:** A trusted GitHub workflow performs SEC refresh and clean staging outside Docker, validates the exact bundle, then passes it as an artifact to a no-network image build. CI is separate and unprivileged; release, package publication, deployment, and notification jobs each use minimum permissions.

**Tech Stack:** Python 3.11, SQLite, pytest, pip-tools generated hash lock, Docker BuildKit, GitHub Actions, GHCR, GitHub REST API.

## Global Constraints

- Plan 1 must have no unresolved P0 defect before this plan starts.
- CI is offline, secret-free, and `contents: read` only.
- Release runs only from `refs/heads/master` and checks out the exact event SHA with persisted credentials disabled.
- Docker must not contact SEC or derive data.
- Release identity excludes unrelated documentation but includes runtime code, locks, methodology, configuration, raw, effective state, DB, and Gate identities.
- Cache may accelerate work but is never evidence and never defines `NO_CHANGE`.
- Only a validated bundle can be built into an image.
- `latest` is convenience metadata; production deploys registry digest only.
- Gate 3 remains `PENDING_REAL_WORLD_VALIDATION`.

---

### Task 1: Define Canonical Hashing and Release Manifest

**Files:**
- Create: `src/thirteenf/release.py`
- Create: `tests/release/test_release_manifest.py`
- Modify: `src/thirteenf/__init__.py`

**Interfaces:**
- Produces: `sha256_file(path: Path) -> str`.
- Produces: `hash_tree(root: Path, include: tuple[str, ...]) -> str` using sorted POSIX relative paths and file bytes.
- Produces: `runtime_tree_hash(root: Path) -> str` using the fixed `RUNTIME_INPUTS` allowlist.
- Produces: `ReleaseManifest` dataclass with schema version, hashes, statuses, and source identities.
- Produces: `build_release_manifest(inputs: ReleaseInputs) -> ReleaseManifest`.
- Produces: `verify_release_bundle(bundle_dir: Path) -> VerificationResult`.

- [ ] **Step 1: Write failing determinism and tamper tests**

```python
def test_tree_hash_is_order_independent(tmp_path):
    first = make_tree(tmp_path / "a", [("z.py", b"z"), ("a.py", b"a")])
    second = make_tree(tmp_path / "b", [("a.py", b"a"), ("z.py", b"z")])
    assert hash_tree(first, ("**/*.py",)) == hash_tree(second, ("**/*.py",))


def test_unrelated_doc_does_not_change_runtime_hash(tmp_path):
    root = release_tree(tmp_path)
    before = runtime_tree_hash(root)
    (root / "notes.md").write_text("unrelated", encoding="utf-8")
    assert runtime_tree_hash(root) == before


def test_bundle_verifier_detects_database_tamper(bundle):
    manifest = build_release_manifest(bundle.inputs)
    write_manifest(bundle.path, manifest)
    (bundle.path / "data" / "thirteenf.db").write_bytes(b"changed")
    assert verify_release_bundle(bundle.path).status == "FAIL"
```

Add canonical JSON tests (`sort_keys=True`, compact separators, UTF-8, final newline), missing file tests, Gate 3 mutation rejection, and release identity stability.

- [ ] **Step 2: Run focused tests and confirm RED**

```powershell
python -m pytest tests/release/test_release_manifest.py -q
```

Expected: import errors for the new release module.

- [ ] **Step 3: Implement canonical manifest construction**

Use an explicit runtime include list:

```python
RUNTIME_INPUTS = (
    "src/**/*.py", "app/**/*.py", "scripts/**/*.py", "config/managers.csv",
    "config/manager_scoring.yaml", "config/methodology.yaml",
    "config/ticker_mappings.csv", "config/historical_symbols.csv",
    "requirements.lock", "Dockerfile",
)
```

Exclude `.git`, caches, local logs, unrelated reports, and timestamps from release identity. Keep build time and commit SHA as non-identity audit metadata. Verify every path remains inside bundle root.

- [ ] **Step 4: Run tests and commit**

```powershell
python -m pytest tests/release/test_release_manifest.py -q
git add src/thirteenf/release.py src/thirteenf/__init__.py tests/release/test_release_manifest.py
git commit -m "feat(release): define deterministic bundle identity"
```

---

### Task 2: Implement Expected-Quarter and Hard Release Quality Gate

**Files:**
- Create: `src/thirteenf/release_quality.py`
- Create: `tests/release/test_release_quality.py`
- Modify: `src/thirteenf/quality.py`

**Interfaces:**
- Produces: `expected_report_period(as_of: date, filing_delay_days: int = 45) -> date`.
- Produces: `QualityFinding(code, severity, message, evidence)`.
- Produces: `evaluate_release_quality(conn, raw_root, active_manager_ids, as_of, minimum_coverage=0.80) -> QualityGateResult`.
- Result status is `PASS` only with zero blocking findings.

- [ ] **Step 1: Write failing calendar and quality tests**

```python
@pytest.mark.parametrize(("as_of", "expected"), [
    (date(2026, 8, 13), date(2026, 3, 31)),
    (date(2026, 8, 14), date(2026, 6, 30)),
    (date(2026, 11, 14), date(2026, 9, 30)),
])
def test_expected_period_uses_45_day_window(as_of, expected):
    assert expected_report_period(as_of) == expected


def test_coverage_uses_active_manager_denominator(seed_release_db):
    result = evaluate_release_quality(
        seed_release_db.conn, seed_release_db.raw_root, set(range(1, 11)),
        as_of=date(2026, 8, 14), minimum_coverage=0.80,
    )
    assert result.covered_managers == 7
    assert result.status == "FAIL"
```

Add failures for `integrity_check`, foreign-key errors, unknown amendment, failed changed filing, missing raw object, checksum mismatch, incomplete effective state, and DB sidecar presence.

- [ ] **Step 2: Run focused tests and confirm RED**

```powershell
python -m pytest tests/release/test_release_quality.py -q
```

Expected: missing module/functions.

- [ ] **Step 3: Implement the gate as a pure read-only evaluation**

Calculate quarter ends without relying on current DB contents. Treat the current active manager CSV/DB set as the denominator. Run `PRAGMA integrity_check`, `PRAGMA foreign_key_check`, raw object/hash checks, filing/effective-component completeness checks, and changed-filing error checks. Return structured findings; never insert `quality_events` from this release gate.

- [ ] **Step 4: Run tests and commit**

```powershell
python -m pytest tests/release/test_release_quality.py tests/test_quality.py -q
git add src/thirteenf/release_quality.py src/thirteenf/quality.py tests/release/test_release_quality.py
git commit -m "feat(release): block incomplete filing quarters"
```

---

### Task 3: Build a Clean Release Bundle Orchestrator

**Files:**
- Create: `scripts/build_release.py`
- Create: `tests/release/test_build_release.py`
- Modify: `scripts/update_data.py`
- Modify: `.gitignore`
- Modify: `.dockerignore`

**Interfaces:**
- Produces CLI: `python scripts/build_release.py --raw-root PATH --work-dir PATH --output-dir PATH --as-of YYYY-MM-DD`.
- Produces bundle files: `data/thirteenf.db`, `raw/`, `reports/gate1.json`, `reports/gate2.json`, `release-manifest.json`.
- Exit 0 means all automated hard gates PASS; any partial state stays in work dir and is never promoted.

- [ ] **Step 1: Write failing atomicity and same-bundle tests**

```python
def test_failed_gate_does_not_publish_output(tmp_path, monkeypatch):
    monkeypatch.setattr(build_release, "run_gate2", lambda *_: failing_gate())
    rc = build_release.main(args(tmp_path))
    assert rc == 1
    assert not (tmp_path / "output" / "release-manifest.json").exists()


def test_manifest_hashes_the_database_checked_by_gates(successful_build):
    manifest = load_manifest(successful_build.output)
    assert manifest.database_sha256 == sha256_file(successful_build.output / "data/thirteenf.db")
    assert manifest.gate1.database_sha256 == manifest.database_sha256
    assert manifest.gate2.database_sha256 == manifest.database_sha256
```

Add failure tests for ingestion, normalize, analysis, quality, Gate 1, bundle verify, and interrupted atomic rename.

- [ ] **Step 2: Run focused tests and confirm RED**

```powershell
python -m pytest tests/release/test_build_release.py -q
```

Expected: build script absent.

- [ ] **Step 3: Implement orchestration without shell-output parsing**

Call Python APIs directly and exchange typed summaries, not `key=value` stdout scraping. Build in `{work_dir}/{run_id}`, checkpoint SQLite, remove/forbid `-wal` and `-shm`, open immutable read-only for Gates, verify DB hash before/after each Gate, then call `verify_manual_baseline` and atomically rename the complete directory to output. Add `--offline` for deterministic rebuilds from a frozen raw root; release workflow mode omits it and performs live SEC discovery/revalidation.

Write step status JSON with fixed enums (`DISCOVER`, `FETCH`, `NORMALIZE`, `ANALYZE`, `QUALITY`, `GATE1`, `GATE2`, `VERIFY`) and redacted error summaries. Keep `update_data.py` as a local wrapper around the same APIs.

- [ ] **Step 4: Run focused and full release tests**

```powershell
python -m pytest tests/release tests/test_update_data.py -q
```

Expected: pass; every failure leaves output absent or leaves the previous complete output untouched.

- [ ] **Step 5: Commit**

```powershell
git add scripts/build_release.py scripts/update_data.py tests/release/test_build_release.py .gitignore .dockerignore
git commit -m "feat(release): build validated bundles atomically"
```

---

### Task 4: Lock Python Dependencies and Verify the Lock

**Files:**
- Create: `requirements.in`
- Create: `requirements-dev.in`
- Create: `requirements.lock`
- Create: `requirements-dev.lock`
- Modify: `requirements.txt`
- Modify: `pyproject.toml`
- Create: `scripts/verify_lock.py`
- Create: `tests/release/test_dependency_lock.py`

**Interfaces:**
- Runtime install: `python -m pip install --require-hashes -r requirements.lock`.
- Test install: `python -m pip install --require-hashes -r requirements-dev.lock`.
- Produces: `python scripts/verify_lock.py` nonzero if an input dependency is absent, unpinned, or unhashed.

- [ ] **Step 1: Write the failing lock-policy test**

```python
def test_runtime_lock_is_exact_and_hashed(repo_root):
    result = verify_lock(repo_root / "requirements.in", repo_root / "requirements.lock")
    assert result.unpinned == ()
    assert result.missing_hashes == ()
```

- [ ] **Step 2: Run and confirm RED**

```powershell
python -m pytest tests/release/test_dependency_lock.py -q
```

Expected: lock files/verifier absent.

- [ ] **Step 3: Generate locks under Python 3.11**

Put direct runtime dependencies in `requirements.in` and `-r requirements.in` plus pytest/coverage tooling in `requirements-dev.in`. Generate both lock files with hashes:

```powershell
python -m pip install "pip-tools==7.5.1"
python -m piptools compile --generate-hashes --resolver=backtracking --output-file=requirements.lock requirements.in
python -m piptools compile --generate-hashes --resolver=backtracking --output-file=requirements-dev.lock requirements-dev.in
python -m pip install --dry-run --require-hashes -r requirements-dev.lock
```

Do not generate the runtime wheelhouse on Windows: it must contain Linux wheels for the image and is produced under the pinned Linux base in Task 5.

Keep `requirements.txt` as a documented compatibility pointer or exact runtime constraints; Docker and CI use only the lock files.

- [ ] **Step 4: Verify and commit**

```powershell
python scripts/verify_lock.py
python -m pytest tests/release/test_dependency_lock.py -q
git add requirements.in requirements-dev.in requirements.lock requirements-dev.lock requirements.txt pyproject.toml scripts/verify_lock.py tests/release/test_dependency_lock.py
git commit -m "build: lock Python dependencies with hashes"
```

---

### Task 5: Build a Non-Root, Read-Only, No-Network Image

**Files:**
- Modify: `Dockerfile`
- Modify: `.dockerignore`
- Create: `scripts/verify_bundle.py`
- Create: `tests/release/test_docker_contract.py`
- Modify: `app/store.py`

**Interfaces:**
- Build argument: `RELEASE_BUNDLE_DIR=dist/release`.
- Runtime command: Streamlit on port 8501 as an unprivileged UID.
- Produces: `python /app/scripts/verify_bundle.py /app/release` for deploy readback.

- [ ] **Step 1: Write failing Docker contract tests**

```python
def test_dockerfile_has_no_sec_update(repo_root):
    text = (repo_root / "Dockerfile").read_text(encoding="utf-8")
    assert "update_data.py" not in text
    assert "USER app" in text
    assert "COPY . ." not in text
    assert "--require-hashes" in text


def test_base_image_is_digest_pinned(repo_root):
    first = (repo_root / "Dockerfile").read_text(encoding="utf-8").splitlines()[0]
    assert re.fullmatch(r"FROM python:3\.11[^@]*@sha256:[0-9a-f]{64}", first)
```

Add assertions for explicit COPY allowlist, healthcheck, release manifest location, and no writable DB path.

- [ ] **Step 2: Run and confirm RED**

```powershell
python -m pytest tests/release/test_docker_contract.py -q
```

Expected: current Dockerfile violates all relevant assertions.

- [ ] **Step 3: Resolve and record the current official base digest**

Run:

```powershell
$baseDigest = docker buildx imagetools inspect python:3.11-slim-bookworm --format '{{.Manifest.Digest}}'
if ($baseDigest -notmatch '^sha256:[0-9a-f]{64}$') { throw "Unverified Python base digest" }
$verifiedDigest = $baseDigest.Substring(7)
```

Copy the returned `sha256:` value into the first Dockerfile line and record the tag/digest/retrieval date in a comment. Never use an unverified example digest.

- [ ] **Step 4: Implement the minimal runtime image**

Use the exact pinned base reference from Step 3 to prepare Linux wheels, then build without RUN-step network access:

```powershell
$root = (Get-Location).Path
New-Item -ItemType Directory -Force dist/wheelhouse | Out-Null
docker run --rm -v "${root}:/work" -w /work python:3.11-slim-bookworm@sha256:$verifiedDigest python -m pip download --require-hashes -r requirements.lock --dest dist/wheelhouse
```

Here `$verifiedDigest` is assigned directly from the successful Step 3 output after validating `^[0-9a-f]{64}$`; it is never guessed or hard-coded before lookup. Create an `app` system user, copy `dist/wheelhouse`, install from `requirements.lock` with `--no-index --find-links=/wheelhouse --require-hashes`, then copy only `src`, `app`, required config, startup files, verifier, and release bundle. Set `THIRTEENF_DB_PATH=/app/release/data/thirteenf.db`. Refactor `app/store.py` to use this environment path and immutable read-only connection in public mode.

- [ ] **Step 5: Build and run without network/write privileges**

```powershell
docker build --network=none --build-arg RELEASE_BUNDLE_DIR=dist/release -t thirteenf:test .
docker run -d --name thirteenf-test --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m --cap-drop ALL --security-opt no-new-privileges --pids-limit 256 --memory 1g --cpus 1 -p 127.0.0.1:18501:8501 thirteenf:test
docker exec thirteenf-test python /app/scripts/verify_bundle.py /app/release
curl.exe -fsS http://127.0.0.1:18501/_stcore/health
docker rm -f thirteenf-test
```

Expected: verifier exits 0, health body is `ok`, container user is non-root, and bundle directory is unchanged.

- [ ] **Step 6: Commit**

```powershell
git add Dockerfile .dockerignore scripts/verify_bundle.py tests/release/test_docker_contract.py app/store.py
git commit -m "build: package validated data in hardened image"
```

---

### Task 6: Add Unprivileged Offline CI

**Files:**
- Create: `.github/workflows/ci.yml`
- Create: `tests/release/test_workflow_policy.py`

**Interfaces:**
- Trigger: pull request and push.
- Job permission: `contents: read` only.
- Runs lock verification, full pytest, compileall, and secret-pattern checks without SEC credentials.

- [ ] **Step 1: Write failing workflow-policy tests**

```python
def test_ci_has_no_write_permission_or_secrets(load_workflow):
    workflow = load_workflow("ci.yml")
    assert workflow["permissions"] == {"contents": "read"}
    text = workflow_text("ci.yml")
    assert "pull_request_target" not in text
    assert "SEC_USER_AGENT" not in text
    assert "packages: write" not in text
```

Add assertions that every `uses:` value is a full 40-character commit SHA and that CI installs `requirements-dev.lock` with `--require-hashes`.

- [ ] **Step 2: Run and confirm RED**

```powershell
python -m pytest tests/release/test_workflow_policy.py -q
```

Expected: `ci.yml` missing.

- [ ] **Step 3: Create CI with immutable Action references**

Use these verified tag resolutions:

```text
actions/checkout@11d5960a326750d5838078e36cf38b85af677262
actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065
```

Configure checkout with `persist-credentials: false`, Python 3.11, hash-locked install, full pytest, compileall, `git diff --check`, and a repository secret scan that excludes `.git` object contents and test-only redaction patterns.

- [ ] **Step 4: Validate YAML policy and commit**

```powershell
python -m pytest tests/release/test_workflow_policy.py -q
python -m pytest -q
git add .github/workflows/ci.yml tests/release/test_workflow_policy.py
git commit -m "ci: add offline least-privilege checks"
```

---

### Task 7: Implement Safe GitHub Incident Issue Lifecycle

**Files:**
- Create: `scripts/github_incident.py`
- Create: `tests/release/test_github_incident.py`
- Create: `.github/ISSUE_TEMPLATE/automation-incident.yml`

**Interfaces:**
- CLI: `python scripts/github_incident.py fail|recover --repo OWNER/REPO --run-url URL --stage ENUM --sha HEX --fingerprint HEX_OR_UNKNOWN --digest DIGEST_OR_UNKNOWN --rollback ENUM`.
- Uses `GH_TOKEN` only at runtime.
- Fixed label: `automation-incident`.
- Fixed allowlists prevent arbitrary log or secret text entering the Issue.
- Produces: `build_issue_payload(incident: Incident) -> dict[str, object]`.

- [ ] **Step 1: Write failing payload and redaction tests**

```python
def test_issue_body_contains_only_allowlisted_fields():
    payload = build_issue_payload(valid_incident())
    assert set(payload) <= {"title", "body", "labels", "assignees"}
    assert "PRIVATE KEY" not in payload["body"]
    assert payload["labels"] == ["automation-incident"]


def test_invalid_stage_is_rejected():
    with pytest.raises(ValueError, match="stage"):
        build_issue_payload(valid_incident(stage="$(env)"))
```

Mock GitHub API tests must cover create, append to one open labeled Issue, recovery close, API failure, and title-spoofed Issue without the fixed label.

- [ ] **Step 2: Run and confirm RED**

```powershell
python -m pytest tests/release/test_github_incident.py -q
```

Expected: script absent.

- [ ] **Step 3: Implement with the GitHub REST API**

Use `urllib.request` and JSON; never invoke a shell. Search `state=open&labels=automation-incident`, verify repository owner/name against `GITHUB_REPOSITORY`, then create/comment/close. Assign `fancy0121`; if assignment alone is rejected, create the Issue without silently discarding the incident.

- [ ] **Step 4: Run tests and commit**

```powershell
python -m pytest tests/release/test_github_incident.py -q
git add scripts/github_incident.py tests/release/test_github_incident.py .github/ISSUE_TEMPLATE/automation-incident.yml
git commit -m "feat(ops): manage automation incident issues"
```

---

### Task 8: Replace the Mutable Build Workflow with Trusted Refresh and Release

**Files:**
- Delete: `.github/workflows/build-image.yml`
- Create: `.github/workflows/refresh-and-release.yml`
- Modify: `tests/release/test_workflow_policy.py`
- Create: `docs/automation.md`

**Interfaces:**
- Triggers: master push, `17 4 * * 2,5`, and manual dispatch.
- Jobs: `refresh`, `build`, `deploy` (wired in Plan 3), `notify`.
- Refresh output: release identity, bundle artifact name, status.
- Build output: exact `ghcr.io/fancy0121/13f-intelligence@sha256:...`.

- [ ] **Step 1: Extend failing policy tests**

Assert:

```python
assert workflow["on"]["schedule"] == [{"cron": "17 4 * * 2,5"}]
assert workflow["concurrency"]["cancel-in-progress"] is False
assert job_permissions("refresh") == {"contents": "read"}
assert job_permissions("build") == {"contents": "read", "packages": "write"}
assert job_permissions("notify") == {"contents": "read", "issues": "write"}
```

Also assert: no `pull_request_target`; exact master-ref guard; expressions enter `env` before shell use; SEC secret appears only in refresh; VPS secrets appear only in deploy; Docker build has no SEC secret; every Action is SHA-pinned.

- [ ] **Step 2: Run and confirm RED**

```powershell
python -m pytest tests/release/test_workflow_policy.py -q
```

Expected: release workflow missing/current workflow violates policy.

- [ ] **Step 3: Implement refresh, artifact, and build jobs**

Use these immutable Action references:

```text
actions/checkout@11d5960a326750d5838078e36cf38b85af677262
actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065
actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02
actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093
docker/setup-buildx-action@8d2750c68a42422c14e847fe6c8ac0403b4cbd6f
docker/login-action@c94ce9fb468520275223c153574b00df6fe4bcc9
docker/build-push-action@10e90e3645eae34f1e60eeb005ba3a3d33f178e8
```

The build job downloads the exact bundle artifact, verifies it again, builds with network disabled where supported, pushes unique run/runtime tags plus `latest`, and validates Buildx digest against the fixed GHCR regex.

Use the immutable tag `release-sha256-{64-character-release-identity}`. Before building, inspect that exact tag. If absent, build and publish it; if present, verify its digest and never overwrite it. Update `latest` only after the immutable tag exists. A matching release tag skips the build but does not skip deploy when VPS readback reports a different digest.

- [ ] **Step 4: Implement notification as an independent always-run job**

Pass only fixed outputs through validated environment variables. On any required job failure, call `github_incident.py fail`; after full success including deploy/readback, call `recover`. If notification itself fails, the workflow remains failed and GitHub's native failed-run email remains available.

- [ ] **Step 5: Validate policy and commit**

```powershell
python -m pytest tests/release/test_workflow_policy.py tests/release/test_github_incident.py -q
git add .github/workflows/build-image.yml .github/workflows/refresh-and-release.yml tests/release/test_workflow_policy.py docs/automation.md
git commit -m "ci: gate immutable SEC release images"
```

---

### Task 9: Release Automation Acceptance Checkpoint

**Files:**
- Create: `reports/validation/RELEASE_AUTOMATION_STATUS.md`
- Modify: `README.md`
- Modify: `README_DEPLOY.md`

**Interfaces:**
- Consumes: Tasks 1–8.
- Produces: factual local/CI-ready status; no production claim.

- [ ] **Step 1: Run all local checks**

```powershell
python scripts/verify_lock.py
python -m pytest -q
python -m compileall -q src app scripts
git diff --check
```

Expected: all pass.

- [ ] **Step 2: Run a clean release twice from one frozen raw set**

```powershell
python scripts/build_release.py --offline --raw-root data/raw --work-dir .tmp/release-a-work --output-dir .tmp/release-a --as-of 2026-09-05
python scripts/build_release.py --offline --raw-root data/raw --work-dir .tmp/release-b-work --output-dir .tmp/release-b --as-of 2026-09-05
python scripts/verify_bundle.py .tmp/release-a
python scripts/verify_bundle.py .tmp/release-b
```

Expected: release identities and canonical semantic hashes match. Build timestamps may differ but are excluded from identity.

- [ ] **Step 3: Build and smoke-test the image with network disabled**

Run the Task 5 Docker commands against `.tmp/release-a`. Verify non-root UID, read-only filesystem, health, bundle hash, and five Streamlit route smoke tests.

- [ ] **Step 4: Record actual evidence and commit**

Write exact test count, hashes, image ID, health result, and remaining external unknowns. State `AUTOMATION_IMPLEMENTED_LOCAL`, not deployed.

```powershell
git add reports/validation/RELEASE_AUTOMATION_STATUS.md README.md README_DEPLOY.md
git commit -m "docs: record release automation verification"
```

Do not start Plan 3 unless the release bundle, image, and workflow policy checks all pass.
