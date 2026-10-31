from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models import ProjectMember, User
from app.realtime import manager

router = APIRouter(tags=["realtime"])


@router.websocket("/ws/projects/{project_id}")
async def project_socket(
    websocket: WebSocket,
    project_id: str,
    db: Session = Depends(get_db),
):
    token = websocket.query_params.get("token", "")
    user_id = decode_access_token(token)
    if not user_id:
        await websocket.close(code=4401)
        return

    user = db.get(User, user_id)
    membership = db.scalar(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
    )
    if not user or not user.is_active or not membership:
        await websocket.close(code=4403)
        return

    await manager.connect(project_id, websocket)
    try:
        while True:
            message = await websocket.receive_text()
            if message == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        await manager.disconnect(project_id, websocket)
