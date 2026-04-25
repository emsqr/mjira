from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

IssueStatus = Literal["open", "in_progress", "done"]


class IssueCreate(BaseModel):
    project_id: UUID
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    assignee_id: UUID | None = None


class IssueUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    status: IssueStatus | None = None
    assignee_id: UUID | None = None


class IssueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    project_id: UUID
    title: str
    description: str | None
    status: IssueStatus
    assignee_id: UUID | None
    created_by: UUID
    created_at: datetime
