"""Authentication and role-based permissions."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db
from .domain import Role
from .models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token", auto_error=False)

#: Capability -> roles permitted.  Kept in one table so the UI and the API
#: enforce the same thing.
PERMISSIONS: dict[str, set[Role]] = {
    "view": {Role.ADMIN, Role.ENGINEER, Role.TECHNICIAN, Role.VIEWER},
    "measure": {Role.ADMIN, Role.ENGINEER, Role.TECHNICIAN},
    "diagnose": {Role.ADMIN, Role.ENGINEER, Role.TECHNICIAN},
    "report": {Role.ADMIN, Role.ENGINEER, Role.TECHNICIAN},
    "edit_schematic": {Role.ADMIN, Role.ENGINEER},
    "configure_controllers": {Role.ADMIN, Role.ENGINEER},
    "manage_projects": {Role.ADMIN, Role.ENGINEER},
    "administer": {Role.ADMIN},
}

_ITERATIONS = 240_000


# --- Minimal HS256 JWT ----------------------------------------------------
# Symmetric signing needs nothing beyond hmac/hashlib, and a self-contained
# implementation removes a native-crypto dependency from the deployment.
# If asymmetric tokens or an external IdP are ever required, replace this
# block with PyJWT rather than extending it.

class TokenError(ValueError):
    pass


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _b64d(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def encode_jwt(payload: dict[str, Any], secret: str) -> str:
    header = _b64e(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    body = _b64e(json.dumps(payload, separators=(",", ":"), default=str).encode())
    signing_input = f"{header}.{body}".encode()
    signature = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
    return f"{header}.{body}.{_b64e(signature)}"


def decode_jwt(token: str, secret: str) -> dict[str, Any]:
    try:
        header_b64, body_b64, sig_b64 = token.split(".")
    except ValueError as exc:
        raise TokenError("malformed token") from exc
    signing_input = f"{header_b64}.{body_b64}".encode()
    expected = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
    if not hmac.compare_digest(expected, _b64d(sig_b64)):
        raise TokenError("signature mismatch")
    payload = json.loads(_b64d(body_b64))
    exp = payload.get("exp")
    if exp is not None and datetime.now(timezone.utc).timestamp() > float(exp):
        raise TokenError("token expired")
    return payload


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS)
    return f"pbkdf2_sha256${_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iterations, salt_hex, digest_hex = stored.split("$")
    except ValueError:
        return False
    if algo != "pbkdf2_sha256":
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex),
                                 int(iterations))
    return hmac.compare_digest(digest.hex(), digest_hex)


def create_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "role": str(user.role),
        "iat": now.timestamp(),
        "exp": (now + timedelta(minutes=settings.access_token_ttl_minutes)).timestamp(),
    }
    return encode_jwt(payload, settings.secret_key)


def current_user(token: str | None = Depends(oauth2_scheme),
                 db: Session = Depends(get_db)) -> User:
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    try:
        payload = decode_jwt(token, settings.secret_key)
    except TokenError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Invalid token: {exc}") from exc
    user = db.scalars(select(User).where(User.id == int(payload["sub"]))).first()
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found or inactive")
    return user


def requires(capability: str):
    """Dependency factory enforcing a capability."""
    allowed = PERMISSIONS[capability]

    def guard(user: User = Depends(current_user)) -> User:
        if Role(user.role) not in allowed:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"Role {user.role} may not {capability.replace('_', ' ')}.",
            )
        return user

    return guard


def ensure_seed_admin(db: Session) -> User | None:
    """Create the first admin from environment variables if no user exists."""
    if db.scalars(select(User).limit(1)).first():
        return None
    email = os.environ.get("POWERTRACE_ADMIN_EMAIL", "admin@example.com")
    password = os.environ.get("POWERTRACE_ADMIN_PASSWORD", "powertrace")
    user = User(email=email, full_name="Initial administrator",
                password_hash=hash_password(password), role=Role.ADMIN)
    db.add(user)
    db.commit()
    return user
