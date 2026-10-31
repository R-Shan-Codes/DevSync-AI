from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import get_current_user
from app.models import Notification, Project, User

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _serialize(row: Notification, project_name: str):
    return {
        "id": row.id,
        "project_id": row.project_id,
        "project_name": project_name,
        "actor_id": row.actor_id,
        "type": row.notification_type,
        "title": row.title,
        "message": row.message,
        "resource_path": row.resource_path,
        "read_at": row.read_at.isoformat() if row.read_at else None,
        "created_at": row.created_at.isoformat(),
    }


@router.get("")
def list_notifications(
    unread_only: bool = False,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    statement = select(Notification, Project.name).join(
        Project, Project.id == Notification.project_id
    ).where(Notification.user_id == user.id)
    if unread_only:
        statement = statement.where(Notification.read_at.is_(None))
    rows = db.execute(statement.order_by(Notification.created_at.desc()).limit(limit)).all()
    unread_count = db.scalar(
        select(Notification.id).where(
            Notification.user_id == user.id, Notification.read_at.is_(None)
        ).limit(1)
    )
    count = len(db.scalars(select(Notification.id).where(
        Notification.user_id == user.id, Notification.read_at.is_(None)
    )).all())
    return {
        "items": [_serialize(notification, project_name) for notification, project_name in rows],
        "unread_count": count,
    }


@router.patch("/{notification_id}/read")
def mark_notification_read(
    notification_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = db.scalar(select(Notification).where(
        Notification.id == notification_id, Notification.user_id == user.id
    ))
    if not row:
        raise HTTPException(status_code=404, detail="Notification not found")
    if row.read_at is None:
        row.read_at = datetime.now(timezone.utc)
        db.commit()
    return {"id": row.id, "read_at": row.read_at.isoformat()}


@router.post("/read-all")
def mark_all_notifications_read(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = db.scalars(select(Notification).where(
        Notification.user_id == user.id, Notification.read_at.is_(None)
    )).all()
    now = datetime.now(timezone.utc)
    for row in rows:
        row.read_at = now
    db.commit()
    return {"updated": len(rows)}
