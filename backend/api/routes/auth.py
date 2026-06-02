from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from auth import create_access_token, hash_password, verify_password
from db.models import User

router = APIRouter()


class RegisterRequest(BaseModel):
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str


@router.post("/register", response_model=TokenResponse)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == req.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    user = User(email=req.email, hashed_password=hash_password(req.password), role="user")
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(user.id)
    return {"access_token": token, "token_type": "bearer"}


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == req.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token(user.id)
    return {"access_token": token, "token_type": "bearer"}
