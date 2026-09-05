# 13F Data Correctness Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make SEC acquisition, amendment interpretation, economic-position aggregation, downstream analytics, and Gate 1/2 independently correct before any unattended release is permitted.

**Architecture:** Preserve each SEC information-table row unchanged, derive an explicit effective filing set through an amendment state machine, and materialize aggregated economic positions for all analytics. Independent Gate implementations reconcile raw and derived results without calling the production parser or change engine.

**Tech Stack:** Python 3.11 standard library, lxml with hardened parser settings, SQLite, pytest, existing CSV/YAML configuration.

## Global Constraints

- SEC EDGAR is the sole primary truth source.
- Raw rows use `(filing_id, row_ordinal)` identity and are never silently deduplicated.
- Effective position key is `(effective_period_id, security_id, put_call, shares_type)`.
- `put_call` is exactly `""`, `CALL`, or `PUT`; `shares_type` is at least `SH` or `PRN`.
- Restatement resets the effective set; add-new-holdings supplements it.
- Missing or contradictory amendment metadata is `AMENDMENT_PENDING` and blocks release.
- Missing/invalid numeric fields are not coerced to zero.
- Every product query must consume effective positions or derived tables, never mixed raw filings.
- Gate 3 remains `PENDING_REAL_WORLD_VALIDATION`.

---

### Task 1: Harden SEC Request Configuration and Response Metadata

**Files:**
- Modify: `src/thirteenf/sec_client.py`
- Modify: `src/thirteenf/cli.py`
- Modify: `tests/test_sec_client.py`
- Modify: `tests/test_update_data.py`

**Interfaces:**
- Produces: `validate_release_user_agent(value: str) -> str`.
- Produces: `SecClient(..., rate_limit_rps: float | None, max_response_bytes: int, max_decompressed_bytes: int)`.
- Produces: `SecResponse(url, final_url, status, body, fetched_at_utc, etag, last_modified)`.
- Produces: `fetch_bytes(url, *, etag=None, last_modified=None) -> SecResponse`, including status 304.

- [ ] **Step 1: Write failing validation and network-boundary tests**

Add tests that exercise exact failure behavior:

```python
def test_release_user_agent_rejects_placeholder():
    with pytest.raises(ValueError, match="real contact"):
        validate_release_user_agent("13F Intelligence contact@example.com")


def test_rate_limit_rps_must_be_bounded():
    with pytest.raises(ValueError, match="rate_limit_rps"):
        SecClient(user_agent="Research Ops ops@real-domain.test", rate_limit_rps=0)


def test_redirect_outside_sec_is_rejected(monkeypatch):
    client = SecClient(user_agent="Research Ops ops@real-domain.test", rate_limit_rps=1000)
    monkeypatch.setattr(client, "_open", lambda request: _FakeResponse(
        200, b"x", final_url="https://attacker.invalid/file.xml"
    ))
    with pytest.raises(SecError, match="unapproved SEC host"):
        client.fetch_bytes("https://www.sec.gov/file.xml")
```

Also add body-limit, gzip expansion-limit, `Retry-After`, conditional-header, and 304 tests. Replace CLI assertions that refer to `--rate-limit`/seconds with `--rate-limit-rps`.

- [ ] **Step 2: Run the focused tests and confirm RED**

Run:

```powershell
python -m pytest tests/test_sec_client.py tests/test_update_data.py -q
```

Expected: failures for missing validator/new response fields and unsupported `--rate-limit-rps`.

- [ ] **Step 3: Implement the minimal hardened client**

Use an allowlist and bounded reads rather than unbounded `resp.read()`:

```python
SEC_ALLOWED_HOSTS = frozenset({"sec.gov", "www.sec.gov", "data.sec.gov"})
DEFAULT_RATE_LIMIT_RPS = 2.0


def validate_release_user_agent(value: str) -> str:
    normalized = value.strip()
    lowered = normalized.lower()
    if not normalized or "example.com" in lowered or "@" not in normalized:
        raise ValueError("SEC_USER_AGENT must contain a real contact name and email")
    return normalized
```

Rename the constructor field to `rate_limit_rps`; validate `0 < rate_limit_rps <= 10`. Read response chunks up to the configured compressed limit, bound gzip output, capture the actual final URL and HTTP metadata, and validate both requested and final hosts. Treat 304 as a successful metadata response with an empty body. Update CLI and `scripts/update_data.py` to pass RPS by the new name without masking the environment variable.

- [ ] **Step 4: Run focused and regression tests**

Run:

```powershell
python -m pytest tests/test_sec_client.py tests/test_update_data.py -q
python -m pytest tests/test_filings.py tests/test_parser.py -q
```

Expected: all selected tests pass.

- [ ] **Step 5: Commit**

```powershell
git add src/thirteenf/sec_client.py src/thirteenf/cli.py scripts/update_data.py tests/test_sec_client.py tests/test_update_data.py
git commit -m "fix(sec): enforce compliant bounded requests"
```

---

### Task 2: Discover Historical Submission Shards and Preserve Content-Addressed Raw Files

**Files:**
- Create: `src/thirteenf/raw_store.py`
- Modify: `src/thirteenf/filings.py`
- Modify: `tests/test_filings.py`
- Create: `tests/test_raw_store.py`

**Interfaces:**
- Produces: `RawObject(checksum: str, relative_path: str, byte_size: int)`.
- Produces: `RawStore.put(content: bytes) -> RawObject` and `RawStore.write_manifest(cik, accession, payload) -> Path`.
- Produces: `discover_filings(client, cik: int, quarters: int, as_of: date) -> list[FilingRecord]`.
- Updates: `FilingRecord` with `accepted_at` and `submission_source_url`.

- [ ] **Step 1: Write failing shard and preservation tests**

```python
def test_discovery_follows_historical_submission_files(fake_client):
    fake_client.json_by_url[main_url] = {
        "filings": {"recent": empty_recent(), "files": [{"name": "CIK0000000001-submissions-001.json"}]}
    }
    fake_client.json_by_url[history_url] = historical_payload_with_13f()
    records = discover_filings(fake_client, 1, quarters=12, as_of=date(2026, 9, 5))
    assert [r.accession_number for r in records] == ["0000000001-26-000001"]


def test_changed_accession_content_keeps_both_objects(tmp_path):
    store = RawStore(tmp_path)
    first = store.put(b"first")
    second = store.put(b"second")
    assert first.relative_path != second.relative_path
    assert (tmp_path / first.relative_path).read_bytes() == b"first"
```

Add deterministic ordering, path traversal rejection, checksum verification, and conditional-304 reuse tests.

- [ ] **Step 2: Run focused tests and confirm RED**

```powershell
python -m pytest tests/test_filings.py tests/test_raw_store.py -q
```

Expected: import failures for `RawStore`/`discover_filings`.

- [ ] **Step 3: Implement object storage and complete discovery**

Store objects at `objects/sha256/{first_two}/{full_sha256}` and accession manifests at `manifests/{ten_digit_cik}/{accession_without_dashes}.json`. Use atomic temp-file replacement inside the same directory. Reject any resolved path outside `raw_root`.

Parse both `filings.recent` and each referenced `filings.files` payload. Normalize to one `FilingRecord` per accession, sort by `(report_date, accepted_at, accession_number)`, then apply the 12Q filter. Do not use the current database maximum quarter as the window anchor.

- [ ] **Step 4: Run focused tests and verify deterministic replay**

```powershell
python -m pytest tests/test_filings.py tests/test_raw_store.py -q
python -m pytest tests/test_sec_client.py -q
```

Expected: pass; a second `RawStore.put()` of identical bytes returns the same relative path and does not rewrite content.

- [ ] **Step 5: Commit**

```powershell
git add src/thirteenf/raw_store.py src/thirteenf/filings.py tests/test_filings.py tests/test_raw_store.py
git commit -m "feat(sec): preserve versioned raw filing evidence"
```

---

### Task 3: Parse Cover Metadata and Reject Unsafe or Invalid XML

**Files:**
- Modify: `src/thirteenf/parser.py`
- Modify: `src/thirteenf/filings.py`
- Create: `tests/fixtures/sec_add_holdings_primary_doc.xml`
- Create: `tests/fixtures/sec_restatement_primary_doc.xml`
- Modify: `tests/test_parser.py`
- Modify: `tests/test_golden_fixtures.py`

**Interfaces:**
- Produces: `AmendmentType` enum with `RESTATEMENT` and `ADD_NEW_HOLDINGS`.
- Produces: `CoverMetadata(report_period, amendment_number, amendment_type)`.
- Produces: `parse_cover_page(xml_bytes: bytes) -> CoverMetadata`.
- Updates: `HoldingRow.shares` to exact `int | None`; normalization persists `ssh_prnamt_type`, `investment_discretion`, and `other_manager`.

- [ ] **Step 1: Save two minimal real SEC cover fixtures with provenance comments**

Use only the relevant XML nodes from these official filings and record URL, accession, retrieval date, and SHA-256 in fixture comments:

```text
ADD_NEW_HOLDINGS: CIK 1055964, accession 0001140361-26-029214
RESTATEMENT: CIK 1140771, accession 0001140771-26-000004
```

Do not synthesize values or copy unrelated personal contact fields into fixtures.

- [ ] **Step 2: Write failing parser tests**

```python
def test_cover_add_new_holdings_fixture():
    cover = parse_cover_page(ADD_FIXTURE.read_bytes())
    assert cover.amendment_number == 1
    assert cover.amendment_type is AmendmentType.ADD_NEW_HOLDINGS


def test_cover_restatement_fixture():
    cover = parse_cover_page(RESTATE_FIXTURE.read_bytes())
    assert cover.amendment_type is AmendmentType.RESTATEMENT


def test_external_entity_is_rejected():
    with pytest.raises(XmlParseError, match="DTD|entity"):
        parse_info_table(b'<!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]><informationTable>&e;</informationTable>')
```

Add tests for both amendment boxes selected, neither box selected on `13F-HR/A`, invalid numeric fields, negative values, and unknown `sshPrnamtType`.

- [ ] **Step 3: Run parser tests and confirm RED**

```powershell
python -m pytest tests/test_parser.py tests/test_golden_fixtures.py -q
```

Expected: failures for missing cover parser and strict validation.

- [ ] **Step 4: Implement hardened XML parsing**

Create a shared parser factory:

```python
def _safe_parser() -> etree.XMLParser:
    return etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        load_dtd=False,
        recover=False,
        huge_tree=False,
    )
```

Explicitly reject `DOCTYPE`/entity declarations before parsing. Parse critical numeric fields with exact integer conversion; raise `HoldingValidationError(row_ordinal, field, value)` for malformed, missing, negative, or unsupported critical values. Preserve empty `put_call` only for ordinary reported positions.

- [ ] **Step 5: Run tests and commit**

```powershell
python -m pytest tests/test_parser.py tests/test_golden_fixtures.py -q
git add src/thirteenf/parser.py src/thirteenf/filings.py tests/fixtures/sec_add_holdings_primary_doc.xml tests/fixtures/sec_restatement_primary_doc.xml tests/test_parser.py tests/test_golden_fixtures.py
git commit -m "fix(parser): validate holdings and amendment metadata"
```

---

### Task 4: Add Versioned Schema for Filing Components and Effective Positions

**Files:**
- Modify: `src/thirteenf/database.py`
- Modify: `tests/test_database.py`
- Create: `tests/test_database_migration.py`
- Modify: `docs/data_model.md`

**Interfaces:**
- Produces: `connect_readonly(db_path, *, immutable=False) -> sqlite3.Connection`.
- Keeps: `connect(db_path)` as the writable connection used by ingestion/tests.
- Produces tables: `effective_periods`, `effective_filing_components`, `effective_positions`.
- Extends keys in `position_changes`, `consensus_scores`, and `trends` with `shares_type`.

- [ ] **Step 1: Write failing schema and read-only tests**

```python
def test_schema_preserves_raw_and_effective_keys(tmp_path):
    conn = connect(tmp_path / "db.sqlite")
    init_db(conn)
    columns = {r[1] for r in conn.execute("PRAGMA table_info(holdings)")}
    assert {"ssh_prnamt_type", "investment_discretion", "other_manager"} <= columns
    effective = {r[1] for r in conn.execute("PRAGMA table_info(effective_positions)")}
    assert {"effective_period_id", "security_id", "put_call", "shares_type", "shares", "value"} <= effective


def test_readonly_connection_cannot_write(tmp_path):
    path = tmp_path / "db.sqlite"
    writable = connect(path)
    init_db(writable)
    writable.close()
    readonly = connect_readonly(path, immutable=True)
    with pytest.raises(sqlite3.OperationalError, match="readonly"):
        readonly.execute("CREATE TABLE forbidden(x)")
```

Add migration coverage starting from a minimal schema-v2 database. The migration must preserve raw rows and must not invent amendment metadata.

- [ ] **Step 2: Run schema tests and confirm RED**

```powershell
python -m pytest tests/test_database.py tests/test_database_migration.py -q
```

Expected: new columns/tables/functions absent.

- [ ] **Step 3: Implement schema version 3**

Add explicit constraints:

```sql
UNIQUE(effective_period_id, security_id, put_call, shares_type)
CHECK(put_call IN ('', 'CALL', 'PUT'))
CHECK(shares_type IN ('SH', 'PRN'))
CHECK(value >= 0)
CHECK(shares >= 0)
```

`effective_filing_components` stores `component_role IN ('BASE','SUPPLEMENT')` and a deterministic sequence. `filings.amends_filing_id` references the immediate predecessor in the same manager/quarter audit chain. Store raw paths relative to release root.

For a schema-v2 database, add non-destructive columns/tables and mark every amendment without parsed cover metadata as `AMENDMENT_PENDING`; do not populate effective tables until re-normalization from raw/SEC completes.

- [ ] **Step 4: Run schema and complete unit tests**

```powershell
python -m pytest tests/test_database.py tests/test_database_migration.py tests/test_changes.py -q
```

Expected: all pass.

- [ ] **Step 5: Commit**

```powershell
git add src/thirteenf/database.py tests/test_database.py tests/test_database_migration.py docs/data_model.md
git commit -m "feat(db): model effective filing components"
```

---

### Task 5: Implement the Amendment State Machine and Economic Aggregation

**Files:**
- Create: `src/thirteenf/effective.py`
- Modify: `src/thirteenf/changes.py`
- Create: `tests/test_effective.py`
- Modify: `tests/test_changes.py`

**Interfaces:**
- Produces: `FilingVersion(filing_id, accession_number, accepted_at, amendment_number, amendment_type)`.
- Produces: `EffectiveSelection(base_filing_id, supplement_filing_ids, state_hash)`.
- Produces: `select_effective_components(versions) -> EffectiveSelection`.
- Produces: `rebuild_effective_positions(conn, methodology_version: str) -> int`.
- Produces: `load_effective_positions(conn, manager_id: int, report_period: str) -> dict[tuple[int, str, str], EffectivePosition]`.
- Updates: `compute_position_changes` to consume `effective_positions` and include `shares_type`.

- [ ] **Step 1: Write failing state-machine tests**

```python
def test_addition_supplements_current_base():
    selection = select_effective_components([base(1), addition(2, number=1)])
    assert selection.base_filing_id == 1
    assert selection.supplement_filing_ids == (2,)


def test_later_restatement_resets_prior_supplements():
    selection = select_effective_components([
        base(1), addition(2, number=1), restatement(3, number=2), addition(4, number=3)
    ])
    assert selection.base_filing_id == 3
    assert selection.supplement_filing_ids == (4,)


def test_unknown_amendment_blocks_selection():
    with pytest.raises(AmendmentPendingError):
        select_effective_components([base(1), unknown_amendment(2)])
```

- [ ] **Step 2: Write failing aggregation tests**

Seed two raw rows with the same CUSIP/ordinary/SH but different `investment_discretion`, plus ordinary/CALL/PUT/PRN control rows:

```python
positions = load_effective_positions(conn, manager_id, "2026-06-30")
assert positions[(security_id, "", "SH")].shares == 300
assert positions[(security_id, "", "SH")].value == 3000
assert positions[(security_id, "CALL", "SH")].shares == 5
assert positions[(security_id, "PUT", "SH")].shares == 7
assert positions[(security_id, "", "PRN")].shares == 1000
```

Also assert that portfolio weights use aggregated values, provenance lists every `(filing_id, row_ordinal)`, and a restatement does not retain superseded base rows.

- [ ] **Step 3: Run tests and confirm RED**

```powershell
python -m pytest tests/test_effective.py tests/test_changes.py -q
```

Expected: missing effective module and current overwrite behavior fails the sum assertions.

- [ ] **Step 4: Implement selection and materialization**

Sort filings by `(accepted_at, amendment_number or 0, accession_number)`. Require exactly one usable base before supplements. Rebuild `effective_periods`, components, and positions inside one transaction. Aggregate with SQL `SUM(shares), SUM(value)` grouped by `security_id, put_call, ssh_prnamt_type`; save ordered provenance JSON and calculate weights from the grouped total.

Replace `_holding_map(filing_id)` with an effective-period loader keyed by `(security_id, put_call, shares_type)`. An absent prior key produces NEW; an absent current key produces EXIT. Missing/incomplete effective periods produce no transition and a quality event.

- [ ] **Step 5: Run tests and commit**

```powershell
python -m pytest tests/test_effective.py tests/test_changes.py -q
git add src/thirteenf/effective.py src/thirteenf/changes.py tests/test_effective.py tests/test_changes.py
git commit -m "fix(analysis): aggregate effective economic positions"
```

---

### Task 6: Rewire Consensus, Trends, Portfolio, and Product Evidence

**Files:**
- Modify: `src/thirteenf/consensus.py`
- Modify: `src/thirteenf/trends.py`
- Modify: `src/thirteenf/portfolio.py`
- Modify: `src/thirteenf/product/evidence.py`
- Modify: `tests/test_consensus.py`
- Create: `tests/test_trends.py`
- Modify: `tests/test_portfolio.py`
- Modify: `tests/product/test_product_evidence.py`
- Modify: `tests/product/conftest.py`

**Interfaces:**
- Consumes: `effective_positions` and `position_changes` keyed by `shares_type`.
- Produces: the same public `ProductStore`, consensus, trend, and portfolio result shapes unless a new `shares_type` field is required for disambiguation.
- Produces: `ProductStore` connection through `connect_readonly(..., immutable=True)` in public mode.

- [ ] **Step 1: Replace raw-row expectations with effective-position expectations**

Add a synthetic database fixture containing an original, an add-new-holdings amendment, duplicate ordinary SH rows, and a CALL row. Assert:

```python
ev = store.manager_evidence(manager_id)
assert ev.position_count == 3  # ordinary SH, CALL SH, and one supplemental security
assert ev.top_holdings[0]["shares"] == 300
assert len({item["cusip"] for item in ev.top_holdings}) == len(ev.top_holdings)
```

For security and portfolio evidence, assert holder counts are unique managers and original/amendment rows are not double counted. Add an assertion that public-mode store cannot create `-wal` or `-shm` files.

- [ ] **Step 2: Run focused tests and confirm RED**

```powershell
python -m pytest tests/test_consensus.py tests/test_trends.py tests/test_portfolio.py tests/product/test_product_evidence.py -q
```

Expected: raw-row count/top-holding and read-only assertions fail.

- [ ] **Step 3: Rewire every query**

Search before editing:

```powershell
rg -n "FROM holdings|JOIN holdings|FROM filings|JOIN filings" src/thirteenf app
```

Classify each query as raw-audit or product/analytics. Only raw-audit views may keep `holdings`; all user evidence must read `effective_positions` or derived tables. Thread `shares_type` through consensus/trend uniqueness without merging PRN into SH. Preserve the existing no-trading language and unresolved mapping behavior.

- [ ] **Step 4: Run all analytics/product tests**

```powershell
python -m pytest tests/test_changes.py tests/test_consensus.py tests/test_trends.py tests/test_portfolio.py tests/product -q
```

Expected: pass; no database sidecar files appear when opening a copied release DB in public mode.

- [ ] **Step 5: Commit**

```powershell
git add src/thirteenf/consensus.py src/thirteenf/trends.py src/thirteenf/portfolio.py src/thirteenf/product/evidence.py tests/test_consensus.py tests/test_trends.py tests/test_portfolio.py tests/product/test_product_evidence.py tests/product/conftest.py
git commit -m "fix(product): read only effective positions"
```

---

### Task 7: Make Normalization Fail Closed and Rebuild Amendment Chains

**Files:**
- Modify: `src/thirteenf/cli.py`
- Modify: `scripts/update_data.py`
- Modify: `tests/test_update_data.py`
- Create: `tests/test_normalization.py`

**Interfaces:**
- Produces: `NormalizationSummary(processed, failed, pending_amendments, skipped)`.
- Produces: `normalize_raw_tree(raw_root: Path, db_path: Path) -> NormalizationSummary`.
- Produces: process exit 0 only when every discovered new/changed filing is normalized and no unknown amendment remains.
- Consumes: content-addressed accession manifests and cover metadata from Tasks 2–3.

- [ ] **Step 1: Write failing fail-closed tests**

```python
def test_changed_filing_failure_blocks_update(update_data, monkeypatch):
    monkeypatch.setattr(update_data, "_run", scripted_steps(
        ingest=(0, "raw_files=2 failures=1 changed_failures=1"),
    ))
    assert update_data.main(["--release-mode"]) == 1


def test_unknown_manifest_status_is_not_silently_skipped(tmp_path):
    summary = normalize_raw_tree(raw_tree_with_status(tmp_path, "MYSTERY"), db_path)
    assert summary.failed == 1
    assert summary.skipped == 0
```

Add cases for missing primary document, checksum mismatch, unknown amendment type, and correct immediate-predecessor `amends_filing_id` links.

- [ ] **Step 2: Run tests and confirm RED**

```powershell
python -m pytest tests/test_update_data.py tests/test_normalization.py -q
```

Expected: current warning-only and silent-skip behavior fails.

- [ ] **Step 3: Implement atomic fail-closed normalization**

Normalize into an explicit staging DB transaction. Every accession manifest must have a recognized terminal status. Abort and roll back on missing objects, checksum mismatch, parser failure, pending amendment, or invalid numbers. Populate filing chains per manager/quarter after all versions are inserted; then call `rebuild_effective_positions` and downstream analytics. Add `--normalize-only`, `--raw-root`, and `--db` arguments so a frozen raw set can be rebuilt without network access.

Keep a non-release local mode only if it prints `NOT_RELEASEABLE` and never writes a success status consumed by automation.

- [ ] **Step 4: Run focused and CLI tests**

```powershell
python -m pytest tests/test_update_data.py tests/test_normalization.py tests/test_database.py tests/test_effective.py -q
```

Expected: pass; an injected failure leaves no partially promoted database.

- [ ] **Step 5: Commit**

```powershell
git add src/thirteenf/cli.py scripts/update_data.py tests/test_update_data.py tests/test_normalization.py
git commit -m "fix(ingest): fail closed on incomplete filings"
```

---

### Task 8: Rebuild Gate 1 and Gate 2 as Independent Read-Only Validators

**Files:**
- Create: `src/thirteenf/validation/__init__.py`
- Create: `src/thirteenf/validation/reference_xml.py`
- Create: `src/thirteenf/validation/gate_context.py`
- Create: `src/thirteenf/validation/compare_databases.py`
- Create: `src/thirteenf/validation/manual_baseline.py`
- Modify: `scripts/gate1_reconciliation.py`
- Modify: `scripts/gate2_review.py`
- Create: `tests/validation/test_reference_xml.py`
- Create: `tests/validation/test_gate1.py`
- Create: `tests/validation/test_gate2.py`
- Create: `tests/validation/test_manual_baseline.py`
- Create: `reports/validation/gate2_manual_review_template.csv`

**Interfaces:**
- Produces: `reference_rows(xml_bytes) -> tuple[ReferenceHolding, ...]` using `xml.etree.ElementTree`, not the production parser.
- Produces: `GateContext(raw_fingerprint, effective_fingerprint, db_sha256, runtime_hash, methodology_version, gate_hash)`.
- Produces: `python -m thirteenf.validation.compare_databases DB_A DB_B`, which compares sorted canonical exports of deterministic tables.
- Produces: `run_gate1(bundle, managers, quarters, rows_per_filing) -> Gate1Result` and `run_gate2(bundle) -> Gate2Result`.
- Produces: `verify_manual_baseline(path, methodology_version, effective_version) -> ManualBaselineResult`.
- Produces: each Gate CLI returns nonzero on any mismatch and writes JSON plus Markdown reports to a caller-provided output directory.

- [ ] **Step 1: Write failing independence and sampling tests**

```python
def test_gate1_does_not_call_production_parser(monkeypatch, sample_bundle):
    monkeypatch.setattr("thirteenf.parser.parse_info_table", lambda _: (_ for _ in ()).throw(AssertionError))
    result = run_gate1(sample_bundle, managers=5, quarters=3, rows_per_filing=10)
    assert result.checked_rows == 150


def test_gate2_dedupes_periods_and_aggregates_rows(sample_bundle):
    result = run_gate2(sample_bundle)
    assert result.period_pairs == (("2026-03-31", "2026-06-30"),)
    assert result.mismatches == ()
    assert len(result.manager_ids) >= 5
```

Add negative tests that deliberately corrupt one raw field, one aggregate share count, one weight direction, and one amendment type; each must make the corresponding Gate fail. Assert Gate execution leaves DB SHA unchanged.

Add manual-baseline tests proving that blank results, any result other than `MATCH`, fewer than 30 transitions, fewer than 5 managers, or a methodology/effective-version mismatch blocks release.

- [ ] **Step 2: Run validation tests and confirm RED**

```powershell
python -m pytest tests/validation -q
```

Expected: new validator imports fail.

- [ ] **Step 3: Implement independent reference calculations**

Gate 1 uses only raw XML, manifest, and direct SQL lookup. Its deterministic sample seed is the release raw fingerprint. It reports the actual count and sample identities.

Gate 2 independently replays the documented amendment state machine and aggregates raw rows by `(CUSIP, put_call, shares_type)`, calculates weights, then computes transitions. It must not call `select_effective_components`, `rebuild_effective_positions`, `compute_position_changes`, or production parser functions. Stratify 30 transitions across at least 5 managers and `NEW/ADD/REDUCE/EXIT`; include UNCHANGED controls and shares-up/weight-down whenever real candidates exist.

- [ ] **Step 4: Generate the manual-review packet without scoring it**

Run against the first corrected clean database:

```powershell
python scripts/gate2_review.py --db data/staging/thirteenf.db --raw-root data/raw --output-dir reports/validation/current --emit-manual-packet reports/validation/gate2_manual_review.csv
```

Expected: the CSV contains raw accession/path/row provenance, independent expected values, production values, and empty `human_result`/`reviewer_notes` fields. Do not auto-fill or claim human PASS. Present the packet to the product owner; only a reviewed file with at least 30 `MATCH` rows across 5 managers, reviewer identity, review date, methodology version, and effective-state version may satisfy `verify_manual_baseline`.

- [ ] **Step 5: Run tests and commit**

```powershell
python -m pytest tests/validation tests/test_changes.py tests/test_golden_fixtures.py -q
git add src/thirteenf/validation scripts/gate1_reconciliation.py scripts/gate2_review.py tests/validation reports/validation/gate2_manual_review_template.csv
git commit -m "fix(gates): independently verify raw and analytical data"
```

---

### Task 9: Correctness Plan Acceptance Checkpoint

**Files:**
- Modify: `docs/methodology.md`
- Modify: `docs/limitations.md`
- Create: `reports/validation/CORRECTNESS_FOUNDATION_STATUS.md`

**Interfaces:**
- Consumes: all Task 1–8 APIs and reports.
- Produces: a factual PASS/FAIL/UNKNOWN checkpoint; it is not the final production report.

- [ ] **Step 1: Obtain a compliant SEC contact once and refresh the corrected raw set**

Ask exactly one question: `请提供用于 SEC 官方请求标识的真实联系人名称和可收件邮箱。`

Enter it through a secure prompt, keep it only in the current process environment, stream it directly to GitHub secret input, run the live refresh, and clear it in `finally`:

```powershell
$secureUa = Read-Host "SEC contact name and email" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureUa)
try {
    $plainUa = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    $env:SEC_USER_AGENT = $plainUa
    $plainUa | gh secret set SEC_USER_AGENT --repo fancy0121/13f-intelligence
    New-Item -ItemType Directory -Force .tmp | Out-Null
    python scripts/update_data.py --release-mode --raw-root data/raw --db .tmp/correctness-seed.db --rate-limit-rps 2.0
    if ($LASTEXITCODE -ne 0) { throw "Correctness seed refresh failed" }
} finally {
    Remove-Item Env:SEC_USER_AGENT -ErrorAction SilentlyContinue
    $plainUa = $null
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
}
```

Do not write or echo the value. Expected: all discovered 12Q cover/info-table documents have actual fetch timestamps and known amendment types.

- [ ] **Step 2: Build twice from the same frozen local raw set**

Run normalization/analyze twice into separate temporary databases using the refreshed raw manifest. Compare canonical table exports rather than SQLite file bytes:

```powershell
python scripts/update_data.py --normalize-only --raw-root data/raw --db .tmp/correctness-a.db
python scripts/update_data.py --normalize-only --raw-root data/raw --db .tmp/correctness-b.db
python -m thirteenf.validation.compare_databases .tmp/correctness-a.db .tmp/correctness-b.db
```

Expected: semantic hashes match exactly.

- [ ] **Step 3: Run the full offline suite**

```powershell
python -m pytest -q
python -m compileall -q src app scripts
git diff --check
```

Expected: all pass.

- [ ] **Step 4: Run integrity and anomaly checks on the corrected database**

Run:

```powershell
python -m thirteenf.validation.gate_context --db .tmp/correctness-a.db --raw-root data/raw
python scripts/gate1_reconciliation.py --db .tmp/correctness-a.db --raw-root data/raw --output-dir .tmp/gate1
python scripts/gate2_review.py --db .tmp/correctness-a.db --raw-root data/raw --output-dir .tmp/gate2
```

Expected: integrity/foreign-key checks pass, Gate 1 checks the real required sample with 100% agreement, and Gate 2 independently checks at least 30 transitions across at least 5 managers. Human Gate 2 status remains `NOT_REVIEWED` until a person reviews its packet.

- [ ] **Step 5: Complete the manual Gate 2 baseline**

Present `reports/validation/gate2_manual_review.csv` with its raw provenance to the product owner. After review, require at least 30 rows across 5 managers to be explicitly marked `MATCH`, with reviewer/date/methodology/effective-state versions. Run `verify_manual_baseline`; any blank or mismatch keeps Gate 2 failed.

- [ ] **Step 6: Record factual status and commit**

Document actual commands, counts, hashes, PASS/FAIL, and unresolved human review in `reports/validation/CORRECTNESS_FOUNDATION_STATUS.md`. Never copy old Gate PASS labels.

```powershell
git add docs/methodology.md docs/limitations.md reports/validation/CORRECTNESS_FOUNDATION_STATUS.md
git commit -m "docs: record corrected data validation status"
```

Stop before Plan 2 unless automated checks pass, the manual baseline passes, and the report contains no unresolved P0 data defect.
