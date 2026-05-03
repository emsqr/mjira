from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from shared.jwt_utils import CurrentUser

from .db import get_db
from .deps import require_tenant
from .models import Project
from .schemas import ProjectCreate, ProjectOut

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_tenant),
) -> Project:
    project = Project(
        tenant_id=current.tenant_id,
        key=payload.key,
        name=payload.name,
        created_by=current.user_id,
    )
    db.add(project)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Project key '{payload.key}' already exists"
        ) from None
    db.refresh(project)
    return project


@router.get("", response_model=list[ProjectOut])
def list_projects(
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_tenant),
) -> list[Project]:
    return db.query(Project).filter(Project.tenant_id == current.tenant_id).all()


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(
    project_id: UUID,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_tenant),
) -> Project:
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.tenant_id == current.tenant_id)
        .one_or_none()
    )
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: UUID,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_tenant),
) -> None:
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.tenant_id == current.tenant_id)
        .one_or_none()
    )
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    db.delete(project)
    db.commit()
