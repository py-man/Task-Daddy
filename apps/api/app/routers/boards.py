from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import and_, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import write_audit
from app.deps import get_current_user, get_db, require_board_role
from app.models import (
  AuditEvent,
  Board,
  BoardMember,
  BoardTaskPriority,
  BoardTaskType,
  ChecklistItem,
  Comment,
  JiraSyncProfile,
  Lane,
  SyncRun,
  Task,
  TaskDependency,
  User,
)
from app.schemas import BoardCreateIn, BoardDeleteIn, BoardOut
from app.task_fields import ensure_board_task_fields

router = APIRouter(prefix="/boards", tags=["boards"])

def _name_key(name: str) -> str:
  return (name or "").strip().lower()


def _board_out(b: Board) -> BoardOut:
  return BoardOut(id=b.id, name=b.name, ownerId=b.owner_id, createdAt=b.created_at, updatedAt=b.updated_at)


async def _delete_board_everything(db: AsyncSession, *, board_id: str) -> None:
  # tasks and children
  await db.execute(delete(Comment).where(Comment.task_id.in_(select(Task.id).where(Task.board_id == board_id))))
  await db.execute(delete(ChecklistItem).where(ChecklistItem.task_id.in_(select(Task.id).where(Task.board_id == board_id))))
  await db.execute(delete(TaskDependency).where(TaskDependency.task_id.in_(select(Task.id).where(Task.board_id == board_id))))
  await db.execute(delete(TaskDependency).where(TaskDependency.depends_on_task_id.in_(select(Task.id).where(Task.board_id == board_id))))
  await db.execute(delete(Task).where(Task.board_id == board_id))
  await db.execute(delete(AuditEvent).where(AuditEvent.board_id == board_id))
  await db.execute(delete(SyncRun).where(SyncRun.board_id == board_id))
  await db.execute(delete(JiraSyncProfile).where(JiraSyncProfile.board_id == board_id))
  await db.execute(delete(BoardTaskType).where(BoardTaskType.board_id == board_id))
  await db.execute(delete(BoardTaskPriority).where(BoardTaskPriority.board_id == board_id))
  await db.execute(delete(BoardMember).where(BoardMember.board_id == board_id))
  await db.execute(delete(Lane).where(Lane.board_id == board_id))
  await db.execute(delete(Board).where(and_(Board.id == board_id)))


@router.get("", response_model=list[BoardOut])
async def list_boards(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> list[BoardOut]:
  res = await db.execute(
    select(Board)
    .join(BoardMember, BoardMember.board_id == Board.id)
    .where(BoardMember.user_id == user.id)
    .order_by(Board.updated_at.desc())
  )
  return [_board_out(b) for b in res.scalars().all()]


@router.post("", response_model=BoardOut)
async def create_board(payload: BoardCreateIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> BoardOut:
  name = payload.name.strip()
  if not name:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="name is required")
  key = _name_key(name)
  # prevent duplicates by normalized name key (case-insensitive, trimmed)
  exists = await db.execute(select(Board.id).where(Board.name_key == key))
  if exists.scalar_one_or_none():
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Board name already exists")

  b = Board(name=name, name_key=key, owner_id=user.id)
  db.add(b)
  await db.flush()
  db.add(BoardMember(board_id=b.id, user_id=user.id, role="admin"))

  # default lanes
  defaults = [
    ("Backlog", "backlog", "backlog"),
    ("In Progress", "in_progress", "active"),
    ("Blocked", "blocked", "blocked"),
    ("Done", "done", "done"),
  ]
  for idx, (name, state_key, ltype) in enumerate(defaults):
    db.add(Lane(board_id=b.id, name=name, state_key=state_key, type=ltype, wip_limit=None, position=idx))

  await ensure_board_task_fields(db, board_id=b.id)

  await write_audit(
    db,
    event_type="board.created",
    entity_type="Board",
    entity_id=b.id,
    board_id=b.id,
    actor_id=user.id,
    payload={"name": b.name},
  )
  await db.commit()
  return _board_out(b)


@router.get("/{board_id}", response_model=BoardOut)
async def get_board(board_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> BoardOut:
  await require_board_role(board_id, "viewer", user, db)
  res = await db.execute(select(Board).where(Board.id == board_id))
  b = res.scalar_one_or_none()
  if not b:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board not found")
  return _board_out(b)


@router.patch("/{board_id}", response_model=BoardOut)
async def update_board(
  board_id: str,
  payload: BoardCreateIn,
  user: User = Depends(get_current_user),
  db: AsyncSession = Depends(get_db),
) -> BoardOut:
  await require_board_role(board_id, "member", user, db)
  res = await db.execute(select(Board).where(Board.id == board_id))
  b = res.scalar_one_or_none()
  if not b:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board not found")
  name = payload.name.strip()
  if not name:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="name is required")
  key = _name_key(name)
  exists = await db.execute(select(Board.id).where(Board.name_key == key, Board.id != b.id))
  if exists.scalar_one_or_none():
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Board name already exists")
  b.name = name
  b.name_key = key
  await write_audit(
    db, event_type="board.updated", entity_type="Board", entity_id=b.id, board_id=b.id, actor_id=user.id, payload={"name": b.name}
  )
  await db.commit()
  return _board_out(b)


@router.delete("/{board_id}")
async def delete_board(board_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
  await require_board_role(board_id, "admin", user, db)
  res = await db.execute(select(Board).where(Board.id == board_id))
  b = res.scalar_one_or_none()
  if not b:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board not found")

  await _delete_board_everything(db, board_id=board_id)
  await write_audit(db, event_type="board.deleted", entity_type="Board", entity_id=board_id, board_id=board_id, actor_id=user.id, payload={})
  await db.commit()
  return {"ok": True}


@router.post("/{board_id}/delete")
async def delete_board_with_mode(
  board_id: str,
  payload: BoardDeleteIn,
  user: User = Depends(get_current_user),
  db: AsyncSession = Depends(get_db),
) -> dict:
  await require_board_role(board_id, "admin", user, db)
  res = await db.execute(select(Board).where(Board.id == board_id))
  b = res.scalar_one_or_none()
  if not b:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board not found")

  if payload.mode == "delete":
    await _delete_board_everything(db, board_id=board_id)
    await write_audit(
      db,
      event_type="board.deleted",
      entity_type="Board",
      entity_id=board_id,
      board_id=board_id,
      actor_id=user.id,
      payload={"mode": "delete"},
    )
    await db.commit()
    return {"ok": True}

  # transfer tasks then delete board shell
  if not payload.transferToBoardId:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="transferToBoardId is required")
  if payload.transferToBoardId == board_id:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="transferToBoardId must be different")
  await require_board_role(payload.transferToBoardId, "admin", user, db)
  dres = await db.execute(select(Board).where(Board.id == payload.transferToBoardId))
  dest = dres.scalar_one_or_none()
  if not dest:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Destination board not found")

  lanes_res = await db.execute(select(Lane).where(Lane.board_id == dest.id).order_by(Lane.position.asc()))
  dest_lanes = lanes_res.scalars().all()
  if not dest_lanes:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Destination board has no lanes")
  lane_by_state = {l.state_key: l for l in dest_lanes}
  backlog_lane = next((l for l in dest_lanes if l.type == "backlog"), dest_lanes[0])

  members_res = await db.execute(select(BoardMember.user_id).where(BoardMember.board_id == dest.id))
  dest_member_ids = set([x for x in members_res.scalars().all() if x])

  tasks_res = await db.execute(select(Task).where(Task.board_id == board_id).order_by(Task.lane_id.asc(), Task.order_index.asc()))
  tasks = tasks_res.scalars().all()

  # Ensure destination has defaults, and later ensure it contains any custom moved values.
  await ensure_board_task_fields(db, board_id=dest.id)

  lane_counters: dict[str, int] = {}
  moved_task_ids: list[str] = []
  moved_types: set[str] = set()
  moved_priorities: set[str] = set()
  for t in tasks:
    target_lane = lane_by_state.get(t.state_key) or backlog_lane
    if t.owner_id and t.owner_id not in dest_member_ids:
      t.owner_id = None
    t.board_id = dest.id
    t.lane_id = target_lane.id
    t.state_key = target_lane.state_key
    idx = lane_counters.get(target_lane.id, 0)
    t.order_index = idx
    lane_counters[target_lane.id] = idx + 1
    moved_types.add(str(t.type or "").strip())
    moved_priorities.add(str(t.priority or "").strip())
    t.version += 1
    moved_task_ids.append(t.id)

  # Preserve custom type/priority keys by creating them in the destination if missing.
  if moved_task_ids:
    existing_t = await db.execute(select(BoardTaskType.key).where(BoardTaskType.board_id == dest.id))
    existing_type_keys = set([k for k in existing_t.scalars().all() if k])
    pos = 100
    for key in sorted([x for x in moved_types if x and x not in existing_type_keys]):
      db.add(BoardTaskType(board_id=dest.id, key=key, name=key, enabled=True, color=None, position=pos))
      pos += 1

    existing_p = await db.execute(select(BoardTaskPriority.key).where(BoardTaskPriority.board_id == dest.id))
    existing_prio_keys = set([k for k in existing_p.scalars().all() if k])
    rank = 100
    for key in sorted([x for x in moved_priorities if x and x not in existing_prio_keys]):
      db.add(BoardTaskPriority(board_id=dest.id, key=key, name=key, enabled=True, color=None, rank=rank))
      rank += 1

  if moved_task_ids:
    # Move audit events for transferred tasks to the destination board for visibility.
    await db.execute(
      update(AuditEvent).where(AuditEvent.board_id == board_id, AuditEvent.task_id.in_(moved_task_ids)).values(board_id=dest.id)
    )
    await write_audit(
      db,
      event_type="board.tasks.transferred",
      entity_type="Board",
      entity_id=board_id,
      board_id=dest.id,
      actor_id=user.id,
      payload={"fromBoardId": board_id, "toBoardId": dest.id, "count": len(moved_task_ids)},
    )

  # Delete board-level artifacts but keep moved tasks and their children.
  await db.execute(delete(SyncRun).where(SyncRun.board_id == board_id))
  await db.execute(delete(JiraSyncProfile).where(JiraSyncProfile.board_id == board_id))
  await db.execute(delete(BoardTaskType).where(BoardTaskType.board_id == board_id))
  await db.execute(delete(BoardTaskPriority).where(BoardTaskPriority.board_id == board_id))
  await db.execute(delete(BoardMember).where(BoardMember.board_id == board_id))
  await db.execute(delete(Lane).where(Lane.board_id == board_id))
  await db.execute(delete(Board).where(Board.id == board_id))

  await write_audit(
    db,
    event_type="board.deleted",
    entity_type="Board",
    entity_id=board_id,
    board_id=dest.id,
    actor_id=user.id,
    payload={"mode": "transfer", "toBoardId": dest.id},
  )
  await db.commit()
  return {"ok": True, "transferred": len(moved_task_ids)}


@router.get("/{board_id}/members")
async def list_members(board_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> list[dict]:
  await require_board_role(board_id, "viewer", user, db)
  res = await db.execute(
    select(BoardMember, User)
    .join(User, User.id == BoardMember.user_id)
    .where(BoardMember.board_id == board_id)
    .order_by(BoardMember.created_at.asc())
  )
  out = []
  for m, u in res.all():
    out.append({"userId": u.id, "email": u.email, "name": u.name, "role": m.role})
  return out


@router.post("/{board_id}/members")
async def add_member(board_id: str, payload: dict, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
  await require_board_role(board_id, "admin", user, db)
  email = payload.get("email")
  role = payload.get("role") or "viewer"
  if role not in ("admin", "member", "viewer"):
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role")
  if not email:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="email is required")
  ures = await db.execute(select(User).where(User.email == email))
  u = ures.scalar_one_or_none()
  if not u:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found (create user in DB for MVP)")
  existing = await db.execute(select(BoardMember.id).where(BoardMember.board_id == board_id, BoardMember.user_id == u.id))
  if existing.scalar_one_or_none():
    return {"ok": True, "already": True}
  db.add(BoardMember(board_id=board_id, user_id=u.id, role=role))
  await write_audit(
    db,
    event_type="board.member.added",
    entity_type="BoardMember",
    entity_id=None,
    board_id=board_id,
    actor_id=user.id,
    payload={"email": email, "role": role},
  )
  await db.commit()
  return {"ok": True}


@router.get("/{board_id}/export/tasks.csv")
async def export_board_tasks_csv(
  board_id: str,
  user: User = Depends(get_current_user),
  db: AsyncSession = Depends(get_db),
) -> Response:
  await require_board_role(board_id, "viewer", user, db)
  bres = await db.execute(select(Board).where(Board.id == board_id))
  b = bres.scalar_one_or_none()
  if not b:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board not found")

  ures = await db.execute(select(User.id, User.email, User.name))
  user_map = {row.id: {"email": row.email, "name": row.name} for row in ures.all()}

  lanes_res = await db.execute(select(Lane).where(Lane.board_id == board_id).order_by(Lane.position.asc()))
  lane_map = {l.id: l for l in lanes_res.scalars().all()}

  tasks_res = await db.execute(select(Task).where(Task.board_id == board_id).order_by(Task.updated_at.desc()))
  tasks = tasks_res.scalars().all()

  buf = io.StringIO(newline="")
  w = csv.writer(buf, lineterminator="\r\n")
  w.writerow(
    [
      "id",
      "title",
      "description",
      "ownerEmail",
      "ownerName",
      "priority",
      "type",
      "tags",
      "dueDate",
      "blocked",
      "blockedReason",
      "lane",
      "stateKey",
      "jiraKey",
      "updatedAt",
    ]
  )
  for t in tasks:
    u = user_map.get(t.owner_id) if t.owner_id else None
    lane = lane_map.get(t.lane_id)
    w.writerow(
      [
        t.id,
        t.title,
        t.description,
        (u.get("email") if u else "") if u else "",
        (u.get("name") if u else "") if u else "",
        t.priority,
        t.type,
        ",".join(t.tags or []),
        t.due_date.isoformat() if t.due_date else "",
        "true" if t.blocked else "false",
        t.blocked_reason or "",
        lane.name if lane else "",
        t.state_key,
        t.jira_key or "",
        t.updated_at.isoformat() if t.updated_at else "",
      ]
    )

  raw = buf.getvalue().encode("utf-8-sig")
  filename = f"task_daddy_tasks_{b.name_key}.csv"
  return Response(
    content=raw,
    media_type="text/csv; charset=utf-8",
    headers={"Content-Disposition": f'attachment; filename="{filename}"'},
  )
