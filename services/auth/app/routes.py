import os
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from shared.jwt_utils import CurrentUser, create_access_token, get_current_user

from .db import get_db
from .models import User
from .schemas import LoginRequest, SignupRequest, TokenResponse, UserOut
from .security import hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])

TENANT_SERVICE_URL = os.getenv("TENANT_SERVICE_URL", "http://tenant:8000")


@router.post("/signup", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, db: Session = Depends(get_db)) -> User:
    user = User(email=payload.email.lower(), password_hash=hash_password(payload.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.query(User).filter(User.email == payload.email.lower()).one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")

    tenant_id: UUID | None = None
    role: str | None = None

    if payload.tenant_slug:
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(
                    f"{TENANT_SERVICE_URL}/internal/memberships/lookup",
                    params={"user_id": str(user.id), "tenant_slug": payload.tenant_slug},
                )
        except httpx.HTTPError as exc:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                f"Tenant service unreachable: {exc}",
            )
        if resp.status_code == 404:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not a member of this tenant")
        if resp.status_code != 200:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Tenant service error")
        data = resp.json()
        tenant_id = UUID(data["tenant_id"])
        role = data["role"]

    token = create_access_token(user_id=user.id, tenant_id=tenant_id, role=role)
    return TokenResponse(access_token=token, tenant_id=tenant_id, role=role)


@router.get("/me", response_model=UserOut)
def me(
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    user = db.get(User, current.user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return user
