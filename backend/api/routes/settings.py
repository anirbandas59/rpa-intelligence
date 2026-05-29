"""
Settings API routes — Superuser-only configuration management.
All endpoints require superuser role.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Literal

from api.dependencies import get_db, require_superuser
from db.models import User, LLMConfig, PromptVariant
from auth import hash_password

router = APIRouter()


# ==================== LLM Configuration ====================


class LLMConfigResponse(BaseModel):
    """Response model for LLM config."""

    id: str
    stage: str
    model: str
    temperature: float
    max_tokens: int
    is_active: bool
    updated_at: str


class LLMConfigUpdate(BaseModel):
    """Request to update LLM config for a stage."""

    stage: str = Field(..., pattern="^(s1_scoring|s1_followup|s2_extract|s3_narrative|s4_decompose)$")
    model: str = Field(..., pattern="^claude-(haiku|sonnet|opus)-4")
    temperature: float = Field(0.3, ge=0.0, le=1.0)
    max_tokens: int = Field(1000, ge=100, le=4000)


@router.get("/llm")
async def list_llm_configs(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_superuser),
):
    """List all active LLM configurations."""
    result = await db.execute(select(LLMConfig).where(LLMConfig.is_active).order_by(LLMConfig.stage))
    configs = result.scalars().all()

    return {
        "configs": [
            {
                "id": cfg.id,
                "stage": cfg.stage,
                "model": cfg.model,
                "temperature": cfg.temperature,
                "max_tokens": cfg.max_tokens,
                "is_active": cfg.is_active,
                "updated_at": cfg.updated_at.isoformat() if cfg.updated_at else None,
            }
            for cfg in configs
        ]
    }


@router.put("/llm")
async def update_llm_config(
    update_req: LLMConfigUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_superuser),
):
    """Update LLM config for a stage. Creates if doesn't exist."""
    # Check if config exists for this stage
    result = await db.execute(select(LLMConfig).where(LLMConfig.stage == update_req.stage, LLMConfig.is_active))
    config = result.scalar_one_or_none()

    if config:
        # Update existing
        config.model = update_req.model
        config.temperature = update_req.temperature
        config.max_tokens = update_req.max_tokens
        config.updated_by = user.id
        config.updated_at = datetime.utcnow()
    else:
        # Create new
        config = LLMConfig(
            stage=update_req.stage,
            model=update_req.model,
            temperature=update_req.temperature,
            max_tokens=update_req.max_tokens,
            is_active=True,
            updated_by=user.id,
        )
        db.add(config)

    await db.commit()
    await db.refresh(config)

    return {
        "id": config.id,
        "stage": config.stage,
        "model": config.model,
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
        "message": "LLM config updated successfully",
    }


# ==================== Prompt Variants ====================


class PromptVariantResponse(BaseModel):
    """Response model for prompt variant."""

    id: str
    stage: str
    name: str
    is_active: bool
    created_at: str


class PromptVariantCreate(BaseModel):
    """Request to create a new prompt variant."""

    stage: str = Field(..., pattern="^(s1_scoring|s1_followup|s2_extract|s3_narrative|s4_decompose)$")
    name: str = Field(..., min_length=1, max_length=100)
    content: dict = Field(..., description="JSON dict with 'system' and 'user' keys")


class PromptVariantUpdate(BaseModel):
    """Request to update a prompt variant."""

    content: dict = Field(..., description="JSON dict with 'system' and 'user' keys")


@router.get("/prompts")
async def list_prompt_variants(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_superuser),
):
    """List all prompt variants."""
    result = await db.execute(select(PromptVariant).order_by(PromptVariant.stage, PromptVariant.created_at.desc()))
    variants = result.scalars().all()

    return {
        "variants": [
            {
                "id": v.id,
                "stage": v.stage,
                "name": v.name,
                "is_active": v.is_active,
                "created_at": v.created_at.isoformat() if v.created_at else None,
            }
            for v in variants
        ]
    }


@router.post("/prompts", status_code=status.HTTP_201_CREATED)
async def create_prompt_variant(
    create_req: PromptVariantCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_superuser),
):
    """Create a new prompt variant."""
    # Validate content structure
    if "system" not in create_req.content or "user" not in create_req.content:
        raise HTTPException(status_code=400, detail="content must contain 'system' and 'user' keys")

    variant = PromptVariant(
        stage=create_req.stage,
        name=create_req.name,
        content=create_req.content,
        is_active=False,  # New variants start inactive
        created_by=user.id,
    )

    db.add(variant)
    await db.commit()
    await db.refresh(variant)

    return {
        "id": variant.id,
        "stage": variant.stage,
        "name": variant.name,
        "is_active": variant.is_active,
        "message": "Prompt variant created successfully",
    }


@router.put("/prompts/{variant_id}")
async def update_prompt_variant(
    variant_id: str,
    update_req: PromptVariantUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_superuser),
):
    """Update prompt variant content."""
    result = await db.execute(select(PromptVariant).where(PromptVariant.id == variant_id))
    variant = result.scalar_one_or_none()

    if not variant:
        raise HTTPException(status_code=404, detail="Prompt variant not found")

    # Validate content structure
    if "system" not in update_req.content or "user" not in update_req.content:
        raise HTTPException(status_code=400, detail="content must contain 'system' and 'user' keys")

    variant.content = update_req.content
    await db.commit()
    await db.refresh(variant)

    return {"id": variant.id, "message": "Prompt variant updated successfully"}


@router.put("/prompts/{variant_id}/activate")
async def activate_prompt_variant(
    variant_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_superuser),
):
    """
    Activate a prompt variant.
    Deactivates all other variants for the same stage.
    """
    # Get the variant to activate
    result = await db.execute(select(PromptVariant).where(PromptVariant.id == variant_id))
    variant = result.scalar_one_or_none()

    if not variant:
        raise HTTPException(status_code=404, detail="Prompt variant not found")

    # Deactivate all other variants for this stage
    await db.execute(update(PromptVariant).where(PromptVariant.stage == variant.stage).values(is_active=False))

    # Activate this variant
    variant.is_active = True
    await db.commit()
    await db.refresh(variant)

    return {
        "id": variant.id,
        "stage": variant.stage,
        "name": variant.name,
        "is_active": variant.is_active,
        "message": f"Activated '{variant.name}' for stage {variant.stage}",
    }


# ==================== User Management ====================


class UserResponse(BaseModel):
    """Response model for user."""

    id: str
    email: str
    role: str
    is_active: bool
    created_at: str


class UserInvite(BaseModel):
    """Request to invite a new user."""

    email: str = Field(..., pattern=r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
    password: str = Field(..., min_length=8)
    role: Literal["user", "superuser"] = "user"


class UserUpdate(BaseModel):
    """Request to update user."""

    role: Literal["user", "superuser"] | None = None
    is_active: bool | None = None


@router.get("/users")
async def list_users(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_superuser),
):
    """List all users."""
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    users = result.scalars().all()

    return {
        "users": [
            {
                "id": u.id,
                "email": u.email,
                "role": u.role,
                "is_active": u.is_active,
                "created_at": u.created_at.isoformat() if u.created_at else None,
            }
            for u in users
        ]
    }


@router.post("/users/invite", status_code=status.HTTP_201_CREATED)
async def invite_user(
    invite_req: UserInvite,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_superuser),
):
    """
    Create a new user account.
    Credentials are sent out-of-band (email, Slack, etc.).
    """
    # Check if email already exists
    result = await db.execute(select(User).where(User.email == invite_req.email))
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(status_code=400, detail="User with this email already exists")

    # Create user
    new_user = User(
        email=invite_req.email,
        hashed_password=hash_password(invite_req.password),
        role=invite_req.role,
        is_active=True,
    )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return {
        "id": new_user.id,
        "email": new_user.email,
        "role": new_user.role,
        "message": "User created successfully. Send credentials out-of-band.",
    }


@router.patch("/users/{user_id}")
async def update_user(
    user_id: str,
    update_req: UserUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_superuser),
):
    """Update user role or active status."""
    result = await db.execute(select(User).where(User.id == user_id))
    target_user = result.scalar_one_or_none()

    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Prevent superuser from deactivating themselves
    if user_id == user.id and update_req.is_active is False:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own account")

    if update_req.role is not None:
        target_user.role = update_req.role

    if update_req.is_active is not None:
        target_user.is_active = update_req.is_active

    await db.commit()
    await db.refresh(target_user)

    return {
        "id": target_user.id,
        "email": target_user.email,
        "role": target_user.role,
        "is_active": target_user.is_active,
        "message": "User updated successfully",
    }
