import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

KEY_RE = re.compile(r"^[A-Z][A-Z0-9]{1,9}$")


class ProjectCreate(BaseModel):
    key: str = Field(min_length=2, max_length=10)
    name: str = Field(min_length=1, max_length=120)

    @field_validator("key")
    @classmethod
    def _key_format(cls, v: str) -> str:
        v = v.upper()
        if not KEY_RE.match(v):
            raise ValueError("key must be 2-10 uppercase alphanumerics, starting with a letter")
        return v


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    key: str
    name: str
    created_by: UUID
    created_at: datetime
