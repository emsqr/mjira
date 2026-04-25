import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,38}[a-z0-9])?$")


class TenantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    slug: str = Field(min_length=1, max_length=40)

    @field_validator("slug")
    @classmethod
    def _slug_format(cls, v: str) -> str:
        v = v.lower()
        if not SLUG_RE.match(v):
            raise ValueError(
                "slug must be lowercase alphanumeric with optional dashes (1-40 chars)"
            )
        return v


class TenantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    created_at: datetime


class MembershipCreate(BaseModel):
    user_id: UUID
    role: str = Field(pattern="^(owner|admin|member)$")


class MembershipOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    user_id: UUID
    role: str


class MembershipLookupOut(BaseModel):
    tenant_id: UUID
    role: str
