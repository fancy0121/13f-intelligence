# Hardened VPS Deployment and Production Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy only validated immutable 13F image digests through a restricted VPS account, preserve the running service on candidate failure, restore the prior container on promotion failure, and prove GitHub Issue/email notification behavior.

**Architecture:** GitHub passes one allowlisted digest over a forced-command SSH key. A root-owned host deployment engine validates and tests a loopback candidate before stopping production, preserves the old container for rollback, then verifies HTTP, bundle, and digest identity after promotion.

**Tech Stack:** Python 3.11, Docker Engine 29, Ubuntu 24.04, OpenSSH forced commands, sudoers, system `flock`, GitHub Actions/GHCR, pytest with a fake Docker runtime.

## Global Constraints

- Plans 1 and 2 must pass before any VPS mutation.
- VPS deploy user is not root, has no password, has no interactive shell, and is not in the docker group.
- The root helper and host configuration are root-owned and not writable by the deploy user.
- The only accepted image repository is `ghcr.io/fancy0121/13f-intelligence` and the only accepted version form is a lowercase SHA-256 digest.
- Workflow cannot choose ports, container names, mounts, environment files, or Docker security options.
- Candidate runs only on `127.0.0.1:18501`; current public service remains `0.0.0.0:8501` for this delivery.
- Old production is stopped but not removed until the new production passes all checks.
- Rollback failure is a distinct hard failure.
- Known hosts are verified out of band; runtime `ssh-keyscan` is forbidden.
- Direct port 8501 is HTTP, not HTTPS; do not claim transport security.

---

### Task 1: Implement a Testable Digest Deployment Engine

**Files:**
- Create: `deploy/thirteenf_deploy.py`
- Create: `deploy/thirteenf.env.example`
- Create: `tests/deploy/test_deploy_engine.py`
- Create: `tests/deploy/fake_runtime.py`

**Interfaces:**
- Produces: `validate_image_ref(value: str) -> str`.
- Produces: `DeployConfig.from_env_file(path: Path) -> DeployConfig`.
- Produces: `DeploymentResult(status, requested_digest, previous_image_id, active_image_id, checks)`.
- Produces: `deploy_digest(config, image_ref, runtime: ContainerRuntime) -> DeploymentResult`.
- Produces: `run_rollback_drill(config, runtime: ContainerRuntime) -> DeploymentResult` using isolated names and ports only.
- Status enum: `DEPLOYED`, `NO_CHANGE`, `CANDIDATE_FAILED`, `ROLLED_BACK`, `ROLLBACK_FAILED`.

- [ ] **Step 1: Write failing input-validation tests**

```python
@pytest.mark.parametrize("value", [
    "ghcr.io/fancy0121/13f-intelligence:latest",
    "docker.io/library/alpine@sha256:" + "a" * 64,
    "ghcr.io/fancy0121/13f-intelligence@sha256:" + "G" * 64,
    "ghcr.io/fancy0121/13f-intelligence@sha256:" + "a" * 64 + ";id",
])
def test_invalid_image_reference_is_rejected(value):
    with pytest.raises(ValueError):
        validate_image_ref(value)


def test_exact_digest_is_accepted():
    value = "ghcr.io/fancy0121/13f-intelligence@sha256:" + "a" * 64
    assert validate_image_ref(value) == value
```

- [ ] **Step 2: Write failing state-transition tests**

```python
def test_candidate_failure_never_stops_production(fake_runtime, config, image_ref):
    fake_runtime.candidate_health = False
    result = deploy_digest(config, image_ref, fake_runtime)
    assert result.status == "CANDIDATE_FAILED"
    assert "stop:thirteenf" not in fake_runtime.calls


def test_failed_promotion_restores_old_container(fake_runtime, config, image_ref):
    fake_runtime.candidate_health = True
    fake_runtime.production_health = False
    fake_runtime.rollback_health = True
    result = deploy_digest(config, image_ref, fake_runtime)
    assert result.status == "ROLLED_BACK"
    assert fake_runtime.active_name == "thirteenf"
    assert fake_runtime.active_image_id == fake_runtime.original_image_id


def test_failed_rollback_is_not_reported_as_success(fake_runtime, config, image_ref):
    fake_runtime.candidate_health = True
    fake_runtime.production_health = False
    fake_runtime.rollback_health = False
    assert deploy_digest(config, image_ref, fake_runtime).status == "ROLLBACK_FAILED"
```

Also test no current container, already-active digest (`NO_CHANGE`), host lock busy, bundle hash mismatch, release fingerprint mismatch, HTTP timeout, and cleanup of old candidates.

- [ ] **Step 3: Run and confirm RED**

```powershell
python -m pytest tests/deploy/test_deploy_engine.py -q
```

Expected: deploy module absent.

- [ ] **Step 4: Implement the engine with argument-list subprocess calls**

Never invoke `shell=True`. The real runtime issues fixed-list Docker commands equivalent to:

```text
docker pull IMAGE@DIGEST
docker run --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m --cap-drop ALL
  --security-opt no-new-privileges --pids-limit 256 --memory 1g --cpus 1
  -p 127.0.0.1:18501:8501 --name thirteenf-candidate IMAGE@DIGEST
```

Candidate checks are: bounded HTTP `/_stcore/health == ok`, `docker exec ... verify_bundle.py`, container image repo digest equality, and release fingerprint equality. Promotion renames stopped old production to `thirteenf-backup-YYYYMMDDTHHMMSSZ`, creates new production with the same fixed security flags and `0.0.0.0:8501`, then repeats checks. On failure, remove the failed new container, rename/start the backup, and verify it.

- [ ] **Step 5: Run tests and commit**

```powershell
python -m pytest tests/deploy/test_deploy_engine.py -q
git add deploy/thirteenf_deploy.py deploy/thirteenf.env.example tests/deploy/test_deploy_engine.py tests/deploy/fake_runtime.py
git commit -m "feat(deploy): promote digests with verified rollback"
```

---

### Task 2: Add Forced-Command Entry Point and Idempotent VPS Bootstrap

**Files:**
- Create: `deploy/thirteenf-ssh-entrypoint`
- Create: `deploy/bootstrap_vps.sh`
- Create: `deploy/sudoers-thirteenf-deploy`
- Create: `tests/deploy/test_host_scripts.py`
- Modify: `deploy/hostinger_vps.md`

**Interfaces:**
- SSH command accepted only when it matches `^deploy ghcr\.io/fancy0121/13f-intelligence@sha256:[0-9a-f]{64}$`.
- Root helper path: `/usr/local/sbin/thirteenf-deploy`.
- Root config path: `/etc/thirteenf/deploy.env`.
- Lock path: `/run/lock/thirteenf-deploy.lock`.

- [ ] **Step 1: Write failing static and entrypoint tests**

```python
def test_entrypoint_rejects_extra_commands(repo_root, run_entrypoint):
    result = run_entrypoint("deploy " + valid_ref() + "; id")
    assert result.returncode != 0


def test_sudoers_grants_only_fixed_entrypoint(repo_root):
    text = (repo_root / "deploy/sudoers-thirteenf-deploy").read_text()
    assert text.strip() == (
        "thirteenf-deploy ALL=(root) NOPASSWD: "
        "/usr/local/sbin/thirteenf-deploy *"
    )


def test_bootstrap_never_adds_user_to_docker_group(repo_root):
    text = (repo_root / "deploy/bootstrap_vps.sh").read_text()
    assert "usermod -aG docker" not in text
```

Add checks for `restrict,command=`, root ownership/modes, `visudo -cf`, no `curl | sh`, idempotent directory creation, and shell quoting.

- [ ] **Step 2: Run and confirm RED**

```powershell
python -m pytest tests/deploy/test_host_scripts.py -q
```

Expected: files absent.

- [ ] **Step 3: Implement the narrow entrypoint**

The forced entrypoint reads only `SSH_ORIGINAL_COMMAND`, validates the exact two-token form with an anchored regex, extracts the image reference, clears nonessential environment variables, and execs:

```text
sudo -n /usr/local/sbin/thirteenf-deploy "$IMAGE_REF"
```

The root helper validates its single image-reference argument again, obtains `flock`, loads the fixed root config, and calls `thirteenf_deploy.py`. Do not pass Docker options supplied by SSH.

- [ ] **Step 4: Implement idempotent bootstrap with a check mode**

`bootstrap_vps.sh --check` performs no mutation and reports exact missing/mismatched state. Normal mode requires root and a public-key file argument, creates system account `thirteenf-deploy` with locked password and `/bin/sh`, installs a single forced/restricted authorized key that denies PTY/forwarding, installs files with root ownership, validates sudoers before install, and writes this fixed non-secret config. The account has no unrestricted SSH or password login even though `/bin/sh` is required for OpenSSH to execute the forced command:

```text
IMAGE_REPOSITORY=ghcr.io/fancy0121/13f-intelligence
PRODUCTION_CONTAINER=thirteenf
PRODUCTION_BIND=0.0.0.0
PRODUCTION_PORT=8501
CANDIDATE_BIND=127.0.0.1
CANDIDATE_PORT=18501
MEMORY_LIMIT=1g
CPU_LIMIT=1
PIDS_LIMIT=256
```

- [ ] **Step 5: Test and commit**

```powershell
python -m pytest tests/deploy/test_host_scripts.py tests/deploy/test_deploy_engine.py -q
git add deploy/thirteenf-ssh-entrypoint deploy/bootstrap_vps.sh deploy/sudoers-thirteenf-deploy tests/deploy/test_host_scripts.py deploy/hostinger_vps.md
git commit -m "feat(deploy): restrict VPS automation entrypoint"
```

---

### Task 3: Add the Production Deploy Job and Policy Files

**Files:**
- Modify: `.github/workflows/refresh-and-release.yml`
- Create: `.github/CODEOWNERS`
- Create: `deploy/github-branch-protection.json`
- Modify: `tests/release/test_workflow_policy.py`
- Modify: `docs/automation.md`

**Interfaces:**
- Deploy job consumes only the build job's validated digest.
- Deploy job environment: `production`.
- Deploy outputs: `deployment_status`, `active_digest`, `release_fingerprint`.
- Manual `notification-test` mode skips refresh/build/deploy and exercises only the fixed Issue lifecycle.

- [ ] **Step 1: Extend failing workflow tests**

```python
def test_only_deploy_job_can_reference_vps_secrets(load_workflow):
    workflow = load_workflow("refresh-and-release.yml")
    for name, job in workflow["jobs"].items():
        text = json.dumps(job)
        if name == "deploy":
            assert "VPS_SSH_PRIVATE_KEY" in text
            assert job["environment"] == "production"
        else:
            assert "VPS_SSH_PRIVATE_KEY" not in text


def test_deploy_uses_strict_host_verification(workflow_text):
    text = workflow_text("refresh-and-release.yml")
    assert "StrictHostKeyChecking=yes" in text
    assert "ssh-keyscan" not in text
```

Also assert key file mode 0600, cleanup trap, fixed image regex, master ref guard, deploy job has only `contents: read`, notification-test isolation, intentional `AUTOMATION_DEPLOY_ENABLED=false` skip behavior, and notification closure only after digest/fingerprint readback.

- [ ] **Step 2: Run and confirm RED**

```powershell
python -m pytest tests/release/test_workflow_policy.py -q
```

Expected: deploy job/policies absent.

- [ ] **Step 3: Implement the deploy job**

Write the private key and known-hosts secret to `${RUNNER_TEMP}` with umask 077; install an EXIT trap before the first use. Validate `VPS_HOST`, `VPS_PORT`, `VPS_USER`, and image digest before invoking SSH. Send exactly one quoted remote command: `deploy $IMAGE_REF`. Parse one final JSON result line and reject unknown status/fields.

The job succeeds only for `DEPLOYED` or `NO_CHANGE` with matching active digest and release fingerprint. `ROLLED_BACK` is a successful recovery action but a failed release job so the incident Issue remains open.

The deploy job runs only when repository variable `AUTOMATION_DEPLOY_ENABLED` is exactly `true`. Missing/false produces the explicit non-production status `DEPLOY_DISABLED` and must not be interpreted as deployment success or generate an incident. Add the manual notification-test mode here so it is reviewed before the first PR merge.

- [ ] **Step 4: Add ownership/protection policy**

`CODEOWNERS` assigns `.github/workflows/`, `deploy/`, `Dockerfile`, dependency locks, Gate scripts, and SEC/effective modules to `@fancy0121`. Because this is currently a solo-owner repository, the branch-protection JSON requires the exact CI check but zero approving reviews; it also requires conversation resolution and forbids force push/deletion. Apply it only in Task 5 after the workflow exists remotely.

- [ ] **Step 5: Test and commit**

```powershell
python -m pytest tests/release/test_workflow_policy.py -q
git add .github/workflows/refresh-and-release.yml .github/CODEOWNERS deploy/github-branch-protection.json tests/release/test_workflow_policy.py docs/automation.md
git commit -m "ci: deploy validated digests through production gate"
```

---

### Task 4: Add External Configuration Audit Commands

**Files:**
- Create: `scripts/audit_automation_config.py`
- Create: `tests/deploy/test_audit_automation_config.py`
- Modify: `docs/automation.md`

**Interfaces:**
- CLI: `python scripts/audit_automation_config.py --repo fancy0121/13f-intelligence --expected-host 187.77.187.100`.
- Reads GitHub/VPS configuration metadata but never secret values.
- Emits FACT/UNKNOWN JSON and exits nonzero for missing required configuration.
- Produces: `audit_github(client: GitHubClient) -> AutomationAuditReport`.

- [ ] **Step 1: Write failing audit tests**

```python
def test_secret_audit_checks_names_not_values(fake_github):
    report = audit_github(fake_github.with_secret_names(
        "SEC_USER_AGENT", "VPS_SSH_PRIVATE_KEY", "VPS_SSH_KNOWN_HOSTS"
    ))
    assert report.secrets_present is True
    assert "secret_value" not in report.to_json()


def test_missing_environment_is_unknown_not_pass(fake_github):
    report = audit_github(fake_github.without_environment("production"))
    assert report.status == "FAIL"
    assert "production" in report.missing
```

- [ ] **Step 2: Run and confirm RED**

```powershell
python -m pytest tests/deploy/test_audit_automation_config.py -q
```

Expected: audit script absent.

- [ ] **Step 3: Implement read-only GitHub and host audit**

Use `gh api` through argument-list subprocess calls. Verify repo visibility/default branch, Actions variable names, environment existence/policy, secret names, branch protection, security settings, workflow schedule, GHCR package visibility, and latest production deployment metadata. For VPS, accept a previously captured JSON readback; do not silently SSH during a local audit.

- [ ] **Step 4: Test and commit**

```powershell
python -m pytest tests/deploy/test_audit_automation_config.py -q
git add scripts/audit_automation_config.py tests/deploy/test_audit_automation_config.py docs/automation.md
git commit -m "feat(ops): audit automation configuration"
```

---

### Task 5: Publish the Reviewed Branch and Configure GitHub

**Files:**
- External state: GitHub repository `fancy0121/13f-intelligence`.
- Generated locally outside Git: temporary ED25519 key pair and known-hosts file.

**Interfaces:**
- Produces repository variable names: `VPS_HOST`, `VPS_PORT`, `VPS_USER`, `MIN_MANAGER_COVERAGE`, `SEC_RATE_LIMIT_RPS`.
- Produces secret names: repository `SEC_USER_AGENT`; production environment `VPS_SSH_PRIVATE_KEY`, `VPS_SSH_KNOWN_HOSTS`.

- [ ] **Step 1: Run final local branch review**

```powershell
python -m pytest -q
python -m compileall -q src app scripts deploy
git diff master...HEAD --check
git status --short
```

Expected: clean branch, all tests pass, no secrets/raw databases/cache in tracked files.

- [ ] **Step 2: Push the feature branch and open a PR**

```powershell
git push -u origin codex/unattended-refresh-deploy
gh pr create --repo fancy0121/13f-intelligence --base master --head codex/unattended-refresh-deploy --title "Add correctness-gated unattended 13F releases" --body-file reports/validation/RELEASE_AUTOMATION_STATUS.md
gh pr checks --watch
```

Expected: remote CI passes. Do not merge while any check is pending or failed.

- [ ] **Step 3: Verify the SEC contact secret name without reading its value**

Run `gh secret list --repo fancy0121/13f-intelligence` and require the `SEC_USER_AGENT` name created in Plan 1. GitHub must not reveal the value; absence blocks release.

- [ ] **Step 4: Generate the dedicated deploy key outside the repository**

```powershell
$keyDir = Join-Path $env:TEMP ("thirteenf-deploy-" + [guid]::NewGuid())
New-Item -ItemType Directory -Path $keyDir | Out-Null
ssh-keygen -t ed25519 -N "" -C "github-actions-13f-deploy" -f (Join-Path $keyDir "id_ed25519")
```

Never add this directory to Git. Keep it only until VPS bootstrap and GitHub secret upload both succeed, then securely delete the private key using one PowerShell process after verifying the resolved path is under `$env:TEMP`.

- [ ] **Step 5: Determine and verify SSH host metadata out of band**

On the already-authenticated Hostinger VPS terminal, run:

```bash
sshd -T | awk '/^port /{print $2; exit}'
ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub -E sha256
```

From the local machine, capture the ED25519 host key for `187.77.187.100` at the reported port and compare its SHA-256 fingerprint to the VPS console output. Abort on mismatch. Only the matched known-hosts line may be stored as `VPS_SSH_KNOWN_HOSTS`.

- [ ] **Step 6: Create environment, variables, and secrets**

Use GitHub CLI/API to create `production`, restrict it to master, then set the fixed variables and validate the observed SSH port before storing it:

```powershell
gh variable set VPS_HOST --repo fancy0121/13f-intelligence --body "187.77.187.100"
gh variable set VPS_USER --repo fancy0121/13f-intelligence --body "thirteenf-deploy"
gh variable set MIN_MANAGER_COVERAGE --repo fancy0121/13f-intelligence --body "0.80"
gh variable set SEC_RATE_LIMIT_RPS --repo fancy0121/13f-intelligence --body "2.0"
gh variable set AUTOMATION_DEPLOY_ENABLED --repo fancy0121/13f-intelligence --body "false"
$observedVpsPort = Read-Host "Enter the integer printed by sshd -T"
if ($observedVpsPort -notmatch '^[1-9][0-9]{0,4}$' -or [int]$observedVpsPort -gt 65535) { throw "Invalid observed SSH port" }
gh variable set VPS_PORT --repo fancy0121/13f-intelligence --body $observedVpsPort
```

`VPS_PORT` is the observed integer, not an assumed 22. Upload the private key and verified known-hosts line as production environment secrets. Verify only secret names through GitHub readback.

- [ ] **Step 7: Merge only after CI review, then apply protection**

Merge the PR with a merge commit or squash according to repository convention, verify master contains the reviewed SHA, then apply `deploy/github-branch-protection.json`. Enable secret scanning/push protection through the repository API when supported; if GitHub returns an entitlement error, record `UNSUPPORTED` rather than claiming success.

---

### Task 6: Bootstrap the VPS Through the Hostinger Console

**Files:**
- External state: VPS `187.77.187.100`.
- Source artifacts: reviewed `deploy/` files from master.

**Interfaces:**
- Produces system account `thirteenf-deploy`, forced authorized key, root helper/config, sudoers rule, and lock path.

- [ ] **Step 1: Capture non-destructive baseline evidence**

On VPS:

```bash
docker inspect thirteenf --format '{{json .Config.Image}} {{json .HostConfig.PortBindings}} {{json .State.Health}}'
docker ps --filter name=^/thirteenf$ --format '{{.ID}} {{.Image}} {{.Status}} {{.Ports}}'
curl -fsS http://127.0.0.1:8501/_stcore/health
```

Expected: current container is running and health returns `ok`. Save redacted output in the validation report; do not expose environment variables.

- [ ] **Step 2: Transfer only reviewed deploy files and public key**

Use an authenticated transfer or paste verified SHA-256 checked files through the Hostinger console. Transfer the public key only; the private key never reaches the VPS filesystem except through SSH authentication later.

- [ ] **Step 3: Run bootstrap and its check mode**

```bash
sudo bash deploy/bootstrap_vps.sh /root/thirteenf-deploy.pub
sudo bash deploy/bootstrap_vps.sh --check
```

Expected: second command reports every owner/mode/account/sudoers/authorized-key/config check as PASS. Verify `id thirteenf-deploy` shows no docker group, the password is locked, and the only installed SSH key has the forced `restrict,command=` prefix.

- [ ] **Step 4: Test the forced key before enabling workflow deployment**

From local machine, attempt the valid readback/deploy protocol and one invalid command (`id`). The invalid command must be rejected, and the current `thirteenf` container must remain unchanged.

- [ ] **Step 5: Record VPS configuration evidence**

Run the read-only audit and save only owners, modes, fingerprints, account groups, container digest, and health state. Mark all unobserved properties `UNKNOWN`.

---

### Task 7: Run the First Controlled Release and Rollback Drills

**Files:**
- Create: `reports/validation/PRODUCTION_AUTOMATION_ACCEPTANCE.md`
- External state: GitHub Actions, GHCR, and VPS.

**Interfaces:**
- Produces immutable workflow run URL, release fingerprint, GHCR digest, active VPS digest, health evidence, rollback drill result, and schedule state.

- [ ] **Step 1: Trigger the manual master release**

```powershell
gh variable set AUTOMATION_DEPLOY_ENABLED --repo fancy0121/13f-intelligence --body "true"
gh workflow run refresh-and-release.yml --repo fancy0121/13f-intelligence --ref master
gh run list --repo fancy0121/13f-intelligence --workflow refresh-and-release.yml --limit 1
```

Wait for the exact run to finish. Do not infer success from image existence; inspect every job conclusion and download the Gate/release artifact.

- [ ] **Step 2: Cross-check immutable identities**

Verify:

```text
workflow build digest == GHCR manifest digest
workflow release fingerprint == image /app/release/release-manifest.json
image digest == VPS docker inspect RepoDigests
VPS bundle fingerprint == workflow release fingerprint
```

Any mismatch is a deployment failure and opens/keeps the incident Issue.

- [ ] **Step 3: Verify public functionality**

Check `http://187.77.187.100:8501/_stcore/health` returns HTTP 200/`ok`. Use browser automation to open all five primary pages, enter manager/security/portfolio inputs, switch bilingual labels, and capture rendered screenshots. HTTP 200 alone is not UI acceptance.

- [ ] **Step 4: Run candidate-failure drill against production**

Deploy a digest from the fixed repository whose bundle fingerprint intentionally does not match the requested release, or invoke the root-only isolated drill mode. Confirm the helper returns `CANDIDATE_FAILED`, the original production container ID never stops, and public health remains 200 throughout.

- [ ] **Step 5: Run promotion/rollback drill in an isolated namespace**

Use the deploy engine's root-only drill config with container names `thirteenf-drill-*` and ports 28501/28502. Force the promoted health check to fail after the old drill container is stopped. Confirm the old drill container is renamed back, restarted, and healthy; no production container/network/port is touched.

- [ ] **Step 6: Record actual results**

Write run URL, commit SHA, release/data/DB/Gate hashes, digest, VPS inspect output, public/browser results, drill result, and exact remaining unknowns. If a test fails, keep status FAIL and stop.

---

### Task 8: Prove Issue Lifecycle and Email Delivery

**Files:**
- Modify: `reports/validation/PRODUCTION_AUTOMATION_ACCEPTANCE.md`

**Interfaces:**
- Manual mode `notification-test` creates/updates the fixed labeled incident without SEC, package, SSH, or production access, then a recovery run closes it.

- [ ] **Step 1: Re-verify notification-test isolation**

Run `python -m pytest tests/release/test_workflow_policy.py -q` and inspect the remote workflow at the merged master SHA. Require proof that notification-test skips refresh/build/deploy and grants only `contents: read, issues: write` to its notification job.

- [ ] **Step 2: Trigger one controlled failure notification**

Run the notification-test mode, then query the resulting Issue by label. Verify title, allowlisted fields, assignee, run URL, and absence of secrets/log dumps.

- [ ] **Step 3: Obtain human email evidence**

Ask the repository owner only: `GitHub 是否已把这条测试 Issue 的通知邮件发送到你的邮箱？`

Until the owner answers yes, record `EMAIL_DELIVERY_UNKNOWN`; an Issue API response is not email proof.

- [ ] **Step 4: Trigger recovery and verify closure**

Run recovery mode. Verify the same Issue receives a recovery comment and is closed; no duplicate open automation incident remains.

- [ ] **Step 5: Commit the production acceptance report**

```powershell
git add reports/validation/PRODUCTION_AUTOMATION_ACCEPTANCE.md
git commit -m "docs: record production automation acceptance"
```

If the first scheduled run has not yet occurred, final status must remain `SCHEDULE_CONFIGURED_NOT_YET_OBSERVED`. Only an observed scheduled Actions run may change it to `SCHEDULE_OBSERVED_PASS`.
