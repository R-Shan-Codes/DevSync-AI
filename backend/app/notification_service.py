from app.models import Notification


def add_notification(
    db,
    *,
    user_id: str,
    project_id: str,
    actor_id: str | None,
    notification_type: str,
    title: str,
    message: str = "",
    resource_path: str = "",
):
    if not user_id or user_id == actor_id:
        return None
    row = Notification(
        user_id=user_id,
        project_id=project_id,
        actor_id=actor_id,
        notification_type=notification_type,
        title=title[:180],
        message=message[:4000],
        resource_path=resource_path[:500],
    )
    db.add(row)
    return row
