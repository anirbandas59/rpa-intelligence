"""
Phase 7 Integration Test — Settings + Roles

Verifies:
1. Superuser-only settings routes enforced
2. Regular user gets 403 on settings routes
3. Superuser can access all settings routes
4. Default LLM configs seeded correctly
5. User management works
"""

from datetime import UTC
from unittest.mock import patch

import pytest


@pytest.mark.asyncio
async def test_regular_user_cannot_access_settings(async_client, test_user_token):
    """Verify regular user gets 403 on settings routes."""
    headers = {"Authorization": f"Bearer {test_user_token}"}

    # Try to access LLM configs
    response = await async_client.get("/api/v1/settings/llm", headers=headers)
    assert response.status_code == 403, "Regular user should get 403 on /settings/llm"

    # Try to access prompt variants
    response = await async_client.get("/api/v1/settings/prompts", headers=headers)
    assert response.status_code == 403, "Regular user should get 403 on /settings/prompts"

    # Try to access user management
    response = await async_client.get("/api/v1/settings/users", headers=headers)
    assert response.status_code == 403, "Regular user should get 403 on /settings/users"

    print("✅ Regular user correctly blocked from settings routes")


@pytest.mark.asyncio
async def test_superuser_can_access_settings(async_client, test_superuser_token):
    """Verify superuser can access all settings routes."""
    headers = {"Authorization": f"Bearer {test_superuser_token}"}

    # Access LLM configs
    response = await async_client.get("/api/v1/settings/llm", headers=headers)
    assert response.status_code == 200, "Superuser should access /settings/llm"
    data = response.json()
    assert "configs" in data

    # Access prompt variants
    response = await async_client.get("/api/v1/settings/prompts", headers=headers)
    assert response.status_code == 200, "Superuser should access /settings/prompts"
    data = response.json()
    assert "variants" in data

    # Access user management
    response = await async_client.get("/api/v1/settings/users", headers=headers)
    assert response.status_code == 200, "Superuser should access /settings/users"
    data = response.json()
    assert "users" in data

    print("✅ Superuser can access all settings routes")


@pytest.mark.asyncio
async def test_default_llm_configs_seeded(async_client, test_superuser_token, test_db_session):
    """Verify default LLM configs can be created via API (test DB doesn't have seeds)."""
    from datetime import datetime

    from db.models import LLMConfig

    headers = {"Authorization": f"Bearer {test_superuser_token}"}

    # Seed configs manually in test DB (migration doesn't run on in-memory DB)
    default_configs = [
        LLMConfig(
            stage="s1_scoring",
            model="claude-haiku-4-5",
            temperature=0.3,
            max_tokens=1000,
            is_active=True,
            updated_at=datetime.now(UTC),
        ),
        LLMConfig(
            stage="s1_followup",
            model="claude-haiku-4-5",
            temperature=0.3,
            max_tokens=500,
            is_active=True,
            updated_at=datetime.now(UTC),
        ),
        LLMConfig(
            stage="s2_extract",
            model="claude-haiku-4-5",
            temperature=0.2,
            max_tokens=800,
            is_active=True,
            updated_at=datetime.now(UTC),
        ),
        LLMConfig(
            stage="s3_narrative",
            model="claude-sonnet-4-5",
            temperature=0.5,
            max_tokens=1500,
            is_active=True,
            updated_at=datetime.now(UTC),
        ),
        LLMConfig(
            stage="s4_decompose",
            model="claude-sonnet-4-5",
            temperature=0.4,
            max_tokens=2000,
            is_active=True,
            updated_at=datetime.now(UTC),
        ),
    ]
    for cfg in default_configs:
        test_db_session.add(cfg)
    await test_db_session.commit()

    # Now test that we can fetch them
    response = await async_client.get("/api/v1/settings/llm", headers=headers)
    assert response.status_code == 200

    configs = response.json()["configs"]

    # Should have 5 default configs
    assert len(configs) >= 5, f"Expected at least 5 configs, got {len(configs)}"

    # Verify config structure
    s1_scoring = next(cfg for cfg in configs if cfg["stage"] == "s1_scoring")
    assert s1_scoring["model"] == "claude-haiku-4-5"
    assert s1_scoring["temperature"] == 0.3
    assert s1_scoring["max_tokens"] == 1000
    assert s1_scoring["is_active"] is True

    print("✅ Default LLM configs seeded correctly")


@pytest.mark.asyncio
async def test_update_llm_config(async_client, test_superuser_token):
    """Verify superuser can update LLM config."""
    headers = {"Authorization": f"Bearer {test_superuser_token}"}

    # Update s1_scoring to use Sonnet
    update_payload = {
        "stage": "s1_scoring",
        "model": "claude-sonnet-4-5",
        "temperature": 0.4,
        "max_tokens": 1200,
    }

    response = await async_client.put("/api/v1/settings/llm", json=update_payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["model"] == "claude-sonnet-4-5"
    assert data["temperature"] == 0.4
    assert data["max_tokens"] == 1200

    # Verify updated config persisted
    list_response = await async_client.get("/api/v1/settings/llm", headers=headers)
    configs = list_response.json()["configs"]
    s1_scoring = next(cfg for cfg in configs if cfg["stage"] == "s1_scoring")
    assert s1_scoring["model"] == "claude-sonnet-4-5"

    print("✅ LLM config update works correctly")


@pytest.mark.asyncio
async def test_create_prompt_variant(async_client, test_superuser_token):
    """Verify superuser can create and activate prompt variants."""
    headers = {"Authorization": f"Bearer {test_superuser_token}"}

    # Create new variant
    create_payload = {
        "stage": "s1_scoring",
        "name": "v4_experimental",
        "content": {
            "system": "You are an experimental RPA assessment agent.",
            "user": "Assess this automation: {name}",
        },
    }

    response = await async_client.post("/api/v1/settings/prompts", json=create_payload, headers=headers)
    assert response.status_code == 201
    data = response.json()
    variant_id = data["id"]
    assert data["is_active"] is False  # New variants start inactive

    # Activate the variant
    activate_response = await async_client.put(f"/api/v1/settings/prompts/{variant_id}/activate", headers=headers)
    assert activate_response.status_code == 200
    activate_data = activate_response.json()
    assert activate_data["is_active"] is True

    print("✅ Prompt variant creation and activation works")


@pytest.mark.asyncio
async def test_invite_user(async_client, test_superuser_token, test_db_session):
    """Verify superuser can invite new users."""
    headers = {"Authorization": f"Bearer {test_superuser_token}"}

    # Invite a new user
    invite_payload = {"email": "newuser@example.com", "password": "securepass123", "role": "user"}

    # Mock hash_password to avoid bcrypt issues in tests
    with patch("api.v1.settings.hash_password", return_value="$2b$12$mocked_hash"):
        response = await async_client.post("/api/v1/settings/users/invite", json=invite_payload, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "newuser@example.com"
    assert data["role"] == "user"

    # Verify user appears in list
    list_response = await async_client.get("/api/v1/settings/users", headers=headers)
    users = list_response.json()["users"]
    new_user = next((u for u in users if u["email"] == "newuser@example.com"), None)
    assert new_user is not None
    assert new_user["is_active"] is True

    print("✅ User invitation works correctly")


@pytest.mark.asyncio
async def test_update_user_role(async_client, test_superuser_token, test_user):
    """Verify superuser can update user role."""
    headers = {"Authorization": f"Bearer {test_superuser_token}"}

    # Promote user to superuser
    update_payload = {"role": "superuser"}

    response = await async_client.patch(f"/api/v1/settings/users/{test_user.id}", json=update_payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "superuser"

    print("✅ User role update works correctly")


@pytest.mark.asyncio
async def test_deactivate_user(async_client, test_superuser_token):
    """Verify superuser can deactivate users."""
    headers = {"Authorization": f"Bearer {test_superuser_token}"}

    # First create a user to deactivate
    with patch("api.v1.settings.hash_password", return_value="$2b$12$mocked_hash"):
        invite_response = await async_client.post(
            "/api/v1/settings/users/invite",
            json={"email": "todeactivate@example.com", "password": "password123", "role": "user"},
            headers=headers,
        )
    user_id = invite_response.json()["id"]

    # Deactivate the user
    update_response = await async_client.patch(
        f"/api/v1/settings/users/{user_id}", json={"is_active": False}, headers=headers
    )
    assert update_response.status_code == 200
    data = update_response.json()
    assert data["is_active"] is False

    print("✅ User deactivation works correctly")


@pytest.mark.asyncio
async def test_cannot_deactivate_self(async_client, test_superuser_token, test_superuser):
    """Verify superuser cannot deactivate their own account."""
    headers = {"Authorization": f"Bearer {test_superuser_token}"}

    # Try to deactivate own account
    response = await async_client.patch(
        f"/api/v1/settings/users/{test_superuser.id}", json={"is_active": False}, headers=headers
    )
    assert response.status_code == 400
    data = response.json()
    assert "cannot deactivate your own account" in data["detail"].lower()

    print("✅ Self-deactivation correctly blocked")


@pytest.mark.asyncio
async def test_duplicate_email_rejected(async_client, test_superuser_token, test_user):
    """Verify duplicate email is rejected during user creation."""
    headers = {"Authorization": f"Bearer {test_superuser_token}"}

    # Try to create user with existing email
    response = await async_client.post(
        "/api/v1/settings/users/invite",
        json={
            "email": test_user.email,  # Existing email
            "password": "password123",
            "role": "user",
        },
        headers=headers,
    )
    assert response.status_code == 400
    data = response.json()
    assert "already exists" in data["detail"].lower()

    print("✅ Duplicate email correctly rejected")
