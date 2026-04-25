from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from shared.jwt_utils import CurrentUser

from .db import get_db
from .deps import require_tenant
from .models import Issue
from .schemas import IssueCreate, IssueOut, IssueUpdate

router = APIRouter(prefix="/issues", tags=["issues"])


@router.post("", response_model=IssueOut, status_code=status.HTTP_201_CREATED)
def create_issue(
    payload: IssueCreate,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_tenant),
) -> Issue:
    issue = Issue(
        tenant_id=current.tenant_id,
        project_id=payload.project_id,
        title=payload.title,
        description=payload.description,
        assignee_id=payload.assignee_id,
        created_by=current.user_id,
    )
    db.add(issue)
    db.commit()
    db.refresh(issue)
    return issue


@router.get("", response_model=list[IssueOut])
def list_issues(
    project_id: UUID | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_tenant),
) -> list[Issue]:
    q = db.query(Issue).filter(Issue.tenant_id == current.tenant_id)
    if project_id is not None:
        q = q.filter(Issue.project_id == project_id)
    if status_filter is not None:
        q = q.filter(Issue.status == status_filter)
    return q.order_by(Issue.created_at.desc()).all()


@router.get("/{issue_id}", response_model=IssueOut)
def get_issue(
    issue_id: UUID,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_tenant),
) -> Issue:
    issue = (
        db.query(Issue)
        .filter(Issue.id == issue_id, Issue.tenant_id == current.tenant_id)
        .one_or_none()
    )
    if issue is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Issue not found")
    return issue


@router.patch("/{issue_id}", response_model=IssueOut)
def update_issue(
    issue_id: UUID,
    payload: IssueUpdate,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_tenant),
) -> Issue:
    issue = (
        db.query(Issue)
        .filter(Issue.id == issue_id, Issue.tenant_id == current.tenant_id)
        .one_or_none()
    )
    if issue is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Issue not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(issue, field, value)
    db.commit()
    db.refresh(issue)
    return issue


@router.delete("/{issue_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_issue(
    issue_id: UUID,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_tenant),
) -> None:
    issue = (
        db.query(Issue)
        .filter(Issue.id == issue_id, Issue.tenant_id == current.tenant_id)
        .one_or_none()
    )
    if issue is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Issue not found")
    db.delete(issue)
    db.commit()
