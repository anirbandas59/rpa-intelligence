# End-to-End Test Suite

Complete workflow tests validating multi-stage data flows.

## Test Files

### 1. `test_s2_to_s3_flow.py` - Stage 2 → Stage 3 Flow
**Purpose:** Validates S2 complexity assessment → S3 timeline calculation + task decomposition

**What it tests:**
- S2 completion verification
- S2 data loading into S3 inputs
- S3 timeline calculation (synchronous)
- S3 task decomposition (decoupled, asynchronous)
- Task breakdown hour sum validation
- Task extraction verification

**Prerequisites:**
- Backend server running on `http://localhost:8000`
- Existing use-case with completed S2 run
- Use-case ID: `a6478c03-ec2c-41c9-b572-058f18fbb937` (configurable in script)

**Run command:**
```bash
cd backend
uv run python tests/e2e/test_s2_to_s3_flow.py
```

**Expected output:**
```
======================================================================
  STEP 1: Verify S2 Completion
======================================================================

✓ S2 run exists: <run-id>
✓ S2 Status: complete
  - Complexity Class: M
  - Effort Range: 5-5 weeks
  - Total Score: 13

...

✅ ALL VALIDATIONS PASSED - S2 → S3 FLOW WORKING CORRECTLY!
```

**Success criteria:**
- ✓ S2 run exists and is complete
- ✓ S2 data loaded into S3 inputs
- ✓ Timeline calculated with correct phases
- ✓ Task decomposition completed
- ✓ Hour sum matches effort budget (within 30% tolerance)
- ✓ Verification passed

---

### 2. `test_s3_to_s4_flow.py` - Stage 3 → Stage 4 Flow
**Purpose:** Validates S3 task breakdown → S4 WBS grouping + sprint assignment

**What it tests:**
- S3 completion verification (timeline + task decomposition)
- Task breakdown prerequisite check
- S3 data loading into S4 inputs
- Sprint parameter configuration
- S4 WBS grouping (LLM-based)
- Sprint assignment (deterministic)
- Hour sum integrity across stages

**Prerequisites:**
- Backend server running on `http://localhost:8000`
- Existing use-case with completed S3 run (including task decomposition)
- Use-case ID: `a6478c03-ec2c-41c9-b572-058f18fbb937` (configurable in script)
- **Run `test_s2_to_s3_flow.py` first** to ensure task decomposition is complete

**Run command:**
```bash
cd backend
uv run python tests/e2e/test_s3_to_s4_flow.py
```

**Expected output:**
```
======================================================================
  STEP 1: Verify S3 Completion (Timeline + Task Decomposition)
======================================================================

✓ S3 run exists: <run-id>
✓ S3 Timeline Status: complete
  - Total Weeks: 10
  - Phases: 6
  - Build+SIT Window: 2026-07-15 to 2026-08-25

✓ Task Decomposition Status: complete
  - Activities: 8
  - Total Net Hours: 208.0h
  - Verification Passed: True

...

✅ ALL VALIDATIONS PASSED - S3 → S4 FLOW WORKING CORRECTLY!
```

**Success criteria:**
- ✓ S3 timeline and task decomposition both complete
- ✓ Task breakdown loaded into S4 inputs
- ✓ Sprint parameters configured
- ✓ WBS rows generated (>0 features)
- ✓ All rows sequenced into sprints
- ✓ Total WBS hours match S3 task extraction hours (within 1h)
- ✓ All features assigned to sprints

---

## Full Test Sequence

To test the complete multi-stage flow from S2 through S4:

```bash
cd backend

# 1. Run S2 → S3 flow (includes task decomposition)
uv run python tests/e2e/test_s2_to_s3_flow.py

# 2. Run S3 → S4 flow (requires S3 task decomposition from step 1)
uv run python tests/e2e/test_s3_to_s4_flow.py
```

**Total expected time:** 5-10 minutes (including LLM calls)

---

## Test Results

Both tests save detailed JSON results in the same directory:

```
backend/tests/e2e/
├── s2_to_s3_test_results_<timestamp>.json
└── s3_to_s4_test_results_<timestamp>.json
```

**S2→S3 results include:**
- S2 run details (complexity, effort, process summary)
- S3 timeline phases
- Task extraction activities and hours
- Verification status

**S3→S4 results include:**
- S3 task extraction summary
- S4 WBS grouping rows
- Sprint assignment distribution
- Hour sum validation

---

## Common Issues

### 1. S2 run not found
**Error:** `✗ No S2 run found. Run main E2E test first`

**Solution:** Create a use-case and run S2 complexity assessment first, or run the main E2E test suite:
```bash
cd backend
uv run python tests/e2e/run_e2e_tests.py
```

### 2. Task decomposition not complete
**Error:** `✗ Task decomposition not complete (status: pending)`

**Solution:** Wait for the background task to complete, or re-run the S2→S3 test:
```bash
cd backend
uv run python tests/e2e/test_s2_to_s3_flow.py
```

### 3. Authentication failed
**Error:** `✗ Authentication failed, cannot continue`

**Solution:** Ensure the backend server is running and the test credentials are valid. The test will auto-register if the user doesn't exist.

### 4. S4 JSON parsing error
**Error:** `Failed to parse WBS JSON response: Extra data`

**Solution:** This is fixed in the latest code. Ensure you have the updated `tracker_agent.py` with improved JSON parsing.

### 5. Hour sum mismatch
**Error:** `✗ Total WBS hours (XXXh) must match S3 task extraction (YYYh)`

**Solution:** This indicates the LLM didn't respect the hour constraint. The tracker agent will retry up to 2 times. If it persists, check the prompt in `tracker_prompts.py`.

---

## Validation Rules

### S2→S3 Flow
1. **Extraction Status:** Must be 'complete'
2. **Hour Sum Verification:** `verification_passed` must be `true`
3. **Activity Count:** Must have at least 1 activity
4. **Hour Budget Tolerance:** Net hours must match expected hours within 30% (configurable via `HOUR_TOLERANCE_PERCENTAGE`)

### S3→S4 Flow
1. **WBS Row Count:** Must have at least 1 WBS row
2. **Sequenced Row Count:** Must match WBS row count
3. **Hour Sum Integrity:** Total WBS hours must match S3 task extraction within 1h
4. **Sprint Assignment:** All features must be assigned to sprints
5. **Field Completeness:** All rows must have 'feature', 'hours', 'sprint_number'

---

## Debugging

### Enable verbose output
Both tests print detailed progress. To capture output:

```bash
cd backend
uv run python tests/e2e/test_s2_to_s3_flow.py 2>&1 | tee s2_s3_debug.log
uv run python tests/e2e/test_s3_to_s4_flow.py 2>&1 | tee s3_s4_debug.log
```

### Check backend logs
Monitor the FastAPI server logs for detailed agent execution:

```bash
# In a separate terminal
cd backend
uv run uvicorn api.main:app --reload --log-level debug
```

### Inspect saved results
Load the JSON results for detailed inspection:

```bash
cd backend/tests/e2e
python3 -m json.tool s2_to_s3_test_results_*.json | less
python3 -m json.tool s3_to_s4_test_results_*.json | less
```

---

## CI/CD Integration

To run both tests in CI pipeline:

```bash
#!/bin/bash
set -e

cd backend

# Run S2→S3 flow
echo "Running S2→S3 flow test..."
uv run python tests/e2e/test_s2_to_s3_flow.py

# Run S3→S4 flow
echo "Running S3→S4 flow test..."
uv run python tests/e2e/test_s3_to_s4_flow.py

echo "✅ All E2E tests passed!"
```

---

## Next Steps

After both tests pass:

1. **Manual UI Testing:** Test the complete flow in the frontend (S2 → S3 → S4)
2. **Performance Testing:** Measure LLM latency and optimize prompts if needed
3. **Edge Case Testing:** Test with various complexity classes and effort ranges
4. **Integration Testing:** Test with real process documents
