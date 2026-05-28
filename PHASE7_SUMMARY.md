# Phase 7 — Settings + Roles

**Status:** ✅ **COMPLETE**

## Overview

Phase 7 implements superuser-only settings management routes for LLM configuration, prompt variants, and user management. All settings routes enforce role-based access control.

## Implemented Features

### 1. Settings Routes (✅ Complete)

**Location:** `backend/api/routes/settings.py`

All routes require `Depends(require_superuser)` — regular users get `403 Forbidden`.

#### LLM Configuration

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/settings/llm` | GET | List all active LLM configs |
| `/api/v1/settings/llm` | PUT | Update or create LLM config for a stage |

**Config fields:**
- `stage`: s1_scoring \| s1_followup \| s2_extract \| s3_narrative \| s4_decompose
- `model`: claude-(haiku\|sonnet\|opus)-4*
- `temperature`: 0.0–1.0
- `max_tokens`: 100–4000

#### Prompt Variants

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/settings/prompts` | GET | List all prompt variants |
| `/api/v1/settings/prompts` | POST | Create new prompt variant (starts inactive) |
| `/api/v1/settings/prompts/{id}` | PUT | Update prompt variant content |
| `/api/v1/settings/prompts/{id}/activate` | PUT | Activate variant (deactivates others for same stage) |

**Prompt structure:**
```json
{
  "content": {
    "system": "System prompt template",
    "user": "User prompt template with {placeholders}"
  }
}
```

#### User Management

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/settings/users` | GET | List all users |
| `/api/v1/settings/users/invite` | POST | Create new user account |
| `/api/v1/settings/users/{id}` | PATCH | Update user role or active status |

**Safety features:**
- Cannot deactivate your own account (400 error)
- Cannot create duplicate email addresses (400 error)
- Passwords hashed with bcrypt

### 2. Seed Migration (✅ Complete)

**Location:** `backend/db/migrations/versions/025da49b8923_seed_default_llm_configs.py`

Seeds 5 default LLM configurations on `alembic upgrade head`:

| Stage | Model | Temperature | Max Tokens |
|-------|-------|-------------|------------|
| s1_scoring | claude-haiku-4-5 | 0.3 | 1000 |
| s1_followup | claude-haiku-4-5 | 0.3 | 500 |
| s2_extract | claude-haiku-4-5 | 0.2 | 800 |
| s3_narrative | claude-sonnet-4-5 | 0.5 | 1500 |
| s4_decompose | claude-sonnet-4-5 | 0.4 | 2000 |

**Usage:**
```bash
uv run alembic upgrade head
```

**Rollback:**
```bash
uv run alembic downgrade -1
```

### 3. Role-Based Access Control (✅ Complete)

**Implementation:** `backend/api/dependencies.py`

```python
async def require_superuser(user: User = Depends(get_current_user)) -> User:
    if user.role != "superuser":
        raise HTTPException(status_code=403, detail="Superuser required")
    return user
```

**Test coverage:**
- `test_regular_user_cannot_access_settings` — Verifies 403 on all settings routes
- `test_superuser_can_access_settings` — Verifies 200 on all settings routes

## API Examples

### Update LLM Config

```bash
curl -X PUT http://localhost:8000/api/v1/settings/llm \
  -H "Authorization: Bearer $SUPERUSER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "stage": "s1_scoring",
    "model": "claude-sonnet-4-5",
    "temperature": 0.4,
    "max_tokens": 1200
  }'
```

### Create Prompt Variant

```bash
curl -X POST http://localhost:8000/api/v1/settings/prompts \
  -H "Authorization: Bearer $SUPERUSER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "stage": "s2_extract",
    "name": "v2_detailed",
    "content": {
      "system": "Extract complexity attributes with detailed notes.",
      "user": "Analyze this document:\n\n{document_text}"
    }
  }'
```

### Invite User

```bash
curl -X POST http://localhost:8000/api/v1/settings/users/invite \
  -H "Authorization: Bearer $SUPERUSER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "analyst@company.com",
    "password": "secure_password_123",
    "role": "user"
  }'
```

## Testing

**File:** `tests/integration/test_phase7_settings.py`

| Test | Verifies |
|------|----------|
| `test_regular_user_cannot_access_settings` | Regular user gets 403 on settings routes |
| `test_superuser_can_access_settings` | Superuser gets 200 on settings routes |
| `test_default_llm_configs_seeded` | Default configs exist and have correct values |
| `test_update_llm_config` | Superuser can update LLM config |
| `test_create_prompt_variant` | Superuser can create and activate variants |
| `test_invite_user` | Superuser can create new users |
| `test_update_user_role` | Superuser can change user roles |
| `test_deactivate_user` | Superuser can deactivate users |
| `test_cannot_deactivate_self` | Superuser blocked from self-deactivation |
| `test_duplicate_email_rejected` | Duplicate email returns 400 |

**All pass:** ✅ 10/10

## Phase 7 Exit Condition

From `IMPLEMENTATION_GUIDE.md`:

> Login as regular user → GET /settings/llm → 403
> Login as superuser → GET /settings/llm → 200

**Status:** ✅ **VERIFIED**

Tests explicitly verify:
- Regular user → 403 ✅
- Superuser → 200 ✅

## Files Created/Modified

### New Files
- `backend/api/routes/settings.py` — Settings API routes (superuser-only)
- `backend/db/migrations/versions/025da49b8923_seed_default_llm_configs.py` — Seed migration
- `backend/tests/integration/test_phase7_settings.py` — Phase 7 integration tests
- `PHASE7_SUMMARY.md` — This file

### Modified Files
- `backend/api/main.py` — Added settings router
- (No other changes needed — auth/dependencies already had `require_superuser`)

## Design Decisions

### 1. Why superuser-only for all settings?

**Rationale:** Settings affect platform behavior globally. Regular users should not be able to:
- Change which AI model is used (cost/quality implications)
- Modify prompts (affects all assessments going forward)
- Manage other users' accounts

**Alternative considered:** Separate "admin" role with subset of permissions

**Decision:** Keep it simple with just `user` and `superuser` roles. Can add granular permissions later if needed.

### 2. Why do new prompt variants start inactive?

**Rationale:** Prevents accidental use of untested prompts. Superuser must explicitly activate after review.

**Flow:**
1. Create variant → `is_active: false`
2. Test variant manually
3. PUT `/activate` → sets `is_active: true`, deactivates others

### 3. Why allow multiple LLM configs per stage?

**Design:** Currently each stage has one active config, but DB allows multiple (historical tracking, A/B testing future).

**Current behavior:** PUT `/settings/llm` updates existing or creates new, always sets `is_active: true`.

**Future-ready:** Can add variant selection logic later (like prompt variants).

### 4. Why separate invite endpoint vs standard user creation?

**Rationale:** "Invite" implies credentials sent out-of-band (email, Slack). Password is set by superuser, not by invitee.

**Alternative:** Send email with password reset link

**Decision:** Out-of-band credential distribution is simpler for MVP. Can add email workflow later.

## Security Considerations

### 1. Password Hashing

All passwords hashed with bcrypt via `passlib.context.CryptContext`:

```python
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
```

**Never store plaintext passwords.**

### 2. Role Check on Every Request

`require_superuser` dependency runs on **every settings route**, not just at router level.

**Why:** Defense in depth — even if router config changes, individual routes still protected.

### 3. Self-Deactivation Block

Superusers cannot deactivate their own account:

```python
if user_id == user.id and update_req.is_active is False:
    raise HTTPException(status_code=400, detail="Cannot deactivate your own account")
```

**Why:** Prevents lockout scenario where last superuser deactivates themselves.

## Next Steps (Phase 8)

Phase 7 is complete. Ready to proceed to Phase 8: Next.js Frontend.

**Phase 8 checklist:**
- [ ] API client (`lib/api.ts`)
- [ ] TypeScript types (`lib/types.ts`)
- [ ] Client-side scoring (`lib/scoring.ts`)
- [ ] Shared components (StageCard, RunHistoryDrawer, etc.)
- [ ] Page implementations (projects, stages, settings)
- [ ] Tailwind v4 + shadcn Nova setup
- [ ] End-to-end browser flow working
