from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from shared.jwt_utils import CurrentUser, get_current_user

from .db import get_db
from .models import Membership, Tenant
from .schemas import (
    MembershipCreate,
    MembershipLookupOut,
    MembershipOut,
    TenantCreate,
    TenantOut,
)

router = APIRouter()
internal_router = APIRouter(prefix="/internal", tags=["internal"])


def _require_tenant_role(
    db: Session, tenant_id: UUID, user_id: UUID, allowed: tuple[str, ...]
) -> Membership:
    m = (
        db.query(Membership)
        .filter(Membership.tenant_id == tenant_id, Membership.user_id == user_id)
        .one_or_none()
    )
    if m is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tenant not found")
    if m.role not in allowed:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient role")
    return m


@router.post("/tenants", response_model=TenantOut, status_code=status.HTTP_201_CREATED)
def create_tenant(
    payload: TenantCreate,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
) -> Tenant:
    tenant = Tenant(name=payload.name, slug=payload.slug)
    db.add(tenant)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Slug already taken") from None

    membership = Membership(tenant_id=tenant.id, user_id=current.user_id, role="owner")
    db.add(membership)
    db.commit()
    db.refresh(tenant)
    return tenant


@router.get("/tenants", response_model=list[TenantOut])
def list_my_tenants(
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
) -> list[Tenant]:
    return (
        db.query(Tenant)
        .join(Membership, Membership.tenant_id == Tenant.id)
        .filter(Membership.user_id == current.user_id)
        .all()
    )


@router.get("/tenants/{tenant_id}", response_model=TenantOut)
def get_tenant(
    tenant_id: UUID,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
) -> Tenant:
    _require_tenant_role(db, tenant_id, current.user_id, ("owner", "admin", "member"))
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tenant not found")
    return tenant


@router.post(
    "/tenants/{tenant_id}/members",
    response_model=MembershipOut,
    status_code=status.HTTP_201_CREATED,
)
def add_member(
    tenant_id: UUID,
    payload: MembershipCreate,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
) -> Membership:
    _require_tenant_role(db, tenant_id, current.user_id, ("owner", "admin"))
    m = Membership(tenant_id=tenant_id, user_id=payload.user_id, role=payload.role)
    db.add(m)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "User is already a member") from None
    db.refresh(m)
    return m


@router.get("/tenants/{tenant_id}/members", response_model=list[MembershipOut])
def list_members(
    tenant_id: UUID,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
) -> list[Membership]:
    _require_tenant_role(db, tenant_id, current.user_id, ("owner", "admin", "member"))
    return db.query(Membership).filter(Membership.tenant_id == tenant_id).all()


# NOTE: /internal/* endpoints are reachable only on the docker internal network
# (the gateway does NOT proxy /internal). In production this should also require
# a service-to-service auth token.
@internal_router.get("/memberships/lookup", response_model=MembershipLookupOut)
def lookup_membership(
    user_id: UUID,
    tenant_slug: str,
    db: Session = Depends(get_db),
) -> MembershipLookupOut:
    row = (
        db.query(Membership, Tenant)
        .join(Tenant, Tenant.id == Membership.tenant_id)
        .filter(Tenant.slug == tenant_slug, Membership.user_id == user_id)
        .one_or_none()
    )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Membership not found")
    membership, tenant = row
    return MembershipLookupOut(tenant_id=tenant.id, role=membership.role)
