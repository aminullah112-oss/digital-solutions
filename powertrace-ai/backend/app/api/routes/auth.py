from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...db import get_db
from ...domain import Role, utcnow
from ...models import User
from ...schemas import LoginRequest, TokenResponse, UserCreate, UserOut
from ...security import PERMISSIONS, create_token, current_user, hash_password, requires, \
    verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


def permissions_for(role: Role) -> list[str]:
    return sorted(cap for cap, roles in PERMISSIONS.items() if role in roles)


@router.post("/token", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.scalars(select(User).where(User.email == payload.email.lower().strip())).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account disabled")
    user.last_login_at = utcnow()
    db.commit()
    return TokenResponse(
        access_token=create_token(user), role=str(user.role), email=user.email,
        permissions=permissions_for(Role(user.role)),
    )


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)) -> User:
    return user


@router.get("/permissions")
def my_permissions(user: User = Depends(current_user)) -> dict:
    return {"role": str(user.role), "permissions": permissions_for(Role(user.role))}


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, db: Session = Depends(get_db),
                _: User = Depends(requires("administer"))) -> User:
    email = payload.email.lower().strip()
    if db.scalars(select(User).where(User.email == email)).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "email already registered")
    user = User(email=email, full_name=payload.full_name,
                password_hash=hash_password(payload.password), role=payload.role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db),
               _: User = Depends(requires("administer"))) -> list[User]:
    return list(db.scalars(select(User).order_by(User.email)))
