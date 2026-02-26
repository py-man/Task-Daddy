from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import write_audit
from app.deps import get_current_user, get_db, require_board_role
from app.models import Lane, Task, User
from app.schemas import LaneCreateIn, LaneOut, LaneReorderIn, LaneUpdateIn

router = APIRouter(tags=["lanes"])


def _lane_out(l: Lane) -> LaneOut:
  return LaneOut(
    id=l.id,
    boardId=l.board_id,
    name=l.name,
    stateKey=l.state_key,
    type=l.type,
    wipLimit=l.wip_limit,
    position=l.position,
  )


@router.get("/boards/{board_id}/lanes", response_model=list[LaneOut])
async def list_lanes(board_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> list[LaneOut]:
  await require_board_role(board_id, "viewer", user, db)
  res = await db.execute(select(Lane).where(Lane.board_id == board_id).order_by(Lane.position.asc()))
  return [_lane_out(l) for l in res.scalars().all()]


@router.post("/boards/{board_id}/lanes", response_model=LaneOut)
async def create_lane(
  board_id: str,
  payload: LaneCreateIn,
  user: User = Depends(get_current_user),
  db: AsyncSession = Depends(get_db),
) -> LaneOut:
  await require_board_role(board_id, "member", user, db)
  res = await db.execute(select(func.max(Lane.position)).where(Lane.board_id == board_id))
  max_pos = res.scalar_one()
  pos = (max_pos + 1) if max_pos is not None else 0
  l = Lane(
    board_id=board_id,
    name=payload.name,
    state_key=payload.stateKey,
    type=payload.type,
    wip_limit=payload.wipLimit,
    position=pos,
  )
  db.add(l)
  await write_audit(
    db,
    event_type="lane.created",
    entity_type="Lane",
    entity_id=l.id,
    board_id=board_id,
    actor_id=user.id,
    payload={"name": l.name, "stateKey": l.state_key},
  )
  await db.commit()
  return _lane_out(l)


@router.patch("/lanes/{lane_id}", response_model=LaneOut)
async def update_lane(lane_id: str, payload: LaneUpdateIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> LaneOut:
  res = await db.execute(select(Lane).where(Lane.id == lane_id))
  l = res.scalar_one_or_none()
  if not l:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lane not found")
  await require_board_role(l.board_id, "member", user, db)

  if payload.name is not None:
    l.name = payload.name
  if payload.stateKey is not None:
    l.state_key = payload.stateKey
  if payload.type is not None:
    l.type = payload.type
  if payload.wipLimit is not None:
    l.wip_limit = payload.wipLimit

  await write_audit(
    db,
    event_type="lane.updated",
    entity_type="Lane",
    entity_id=l.id,
    board_id=l.board_id,
    actor_id=user.id,
    payload={"name": l.name, "stateKey": l.state_key, "type": l.type},
  )
  await db.commit()
  return _lane_out(l)


@router.delete("/lanes/{lane_id}")
async def delete_lane(lane_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
  res = await db.execute(select(Lane).where(Lane.id == lane_id))
  l = res.scalar_one_or_none()
  if not l:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lane not found")
  await require_board_role(l.board_id, "member", user, db)

  tres = await db.execute(select(func.count()).select_from(Task).where(Task.lane_id == lane_id))
  if (tres.scalar_one() or 0) > 0:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Lane has tasks; move them first")

  await db.execute(delete(Lane).where(Lane.id == lane_id))
  await write_audit(
    db,
    event_type="lane.deleted",
    entity_type="Lane",
    entity_id=lane_id,
    board_id=l.board_id,
    actor_id=user.id,
    payload={"name": l.name},
  )
  await db.commit()
  return {"ok": True}


@router.post("/boards/{board_id}/lanes/reorder")
async def reorder_lanes(
  board_id: str,
  payload: LaneReorderIn,
  user: User = Depends(get_current_user),
  db: AsyncSession = Depends(get_db),
) -> dict:
  await require_board_role(board_id, "member", user, db)
  res = await db.execute(select(Lane).where(Lane.board_id == board_id))
  lanes = {l.id: l for l in res.scalars().all()}
  if set(payload.laneIds) != set(lanes.keys()):
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="laneIds must include all lanes")
  for idx, lane_id in enumerate(payload.laneIds):
    lanes[lane_id].position = idx
  await write_audit(
    db,
    event_type="lanes.reordered",
    entity_type="Board",
    entity_id=board_id,
    board_id=board_id,
    actor_id=user.id,
    payload={"laneIds": payload.laneIds},
  )
  await db.commit()
  return {"ok": True}
