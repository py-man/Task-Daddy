from __future__ import annotations

import asyncio
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Board, BoardMember, Comment, Lane, Task, User
from app.security import hash_password
from app.task_fields import ensure_board_task_fields

def _name_key(name: str) -> str:
  return (name or "").strip().lower()

def _bootstrap_password(env_key: str) -> tuple[str, bool]:
  configured = (os.getenv(env_key) or "").strip()
  if configured:
    return configured, False
  return secrets.token_urlsafe(14), True


async def seed() -> None:
  async with SessionLocal() as db:
    admin_email = "admin@taskdaddy.local"
    member_email = "member@taskdaddy.local"
    admin_password, admin_generated = _bootstrap_password("SEED_ADMIN_PASSWORD")
    member_password, member_generated = _bootstrap_password("SEED_MEMBER_PASSWORD")
    boot_lines: list[str] = []

    res = await db.execute(select(User).where(User.email == admin_email))
    admin = res.scalar_one_or_none()
    if not admin:
      admin = User(email=admin_email, name="Admin", role="admin", password_hash=hash_password(admin_password), avatar_url=None)
      db.add(admin)
      boot_lines.append(f"{admin_email}={admin_password} (generated={str(admin_generated).lower()})")

    res = await db.execute(select(User).where(User.email == member_email))
    member = res.scalar_one_or_none()
    if not member:
      member = User(email=member_email, name="Member", role="member", password_hash=hash_password(member_password), avatar_url=None)
      db.add(member)
      boot_lines.append(f"{member_email}={member_password} (generated={str(member_generated).lower()})")

    await db.flush()

    # Ensure all boards have default task fields (types/priorities).
    boards_res = await db.execute(select(Board.id))
    for bid in boards_res.scalars().all():
      await ensure_board_task_fields(db, board_id=bid)

    if os.getenv("SEED_DEMO_BOARD", "").strip().lower() in ("1", "true", "yes", "y"):
      # Optional sample board owned by admin (idempotent by name+owner for MVP)
      board_name = "Task-Daddy Demo"
      bres = await db.execute(select(Board).where(Board.name == board_name, Board.owner_id == admin.id))
      board = bres.scalar_one_or_none()
      if not board:
        board = Board(name=board_name, name_key=_name_key(board_name), owner_id=admin.id)
        db.add(board)
        await db.flush()
        db.add(BoardMember(board_id=board.id, user_id=admin.id, role="admin"))
        db.add(BoardMember(board_id=board.id, user_id=member.id, role="member"))
        defaults = [
          ("Backlog", "backlog", "backlog"),
          ("In Progress", "in_progress", "active"),
          ("Blocked", "blocked", "blocked"),
          ("Done", "done", "done"),
        ]
        for idx, (name, state_key, ltype) in enumerate(defaults):
          db.add(Lane(board_id=board.id, name=name, state_key=state_key, type=ltype, position=idx, wip_limit=None))
        await ensure_board_task_fields(db, board_id=board.id)

      # Seed a few demo tasks if the board is empty. Keep it generic (no real org data).
      tres = await db.execute(select(Task.id).where(Task.board_id == board.id).limit(1))
      any_task = tres.scalar_one_or_none()
      if not any_task:
        lres = await db.execute(select(Lane).where(Lane.board_id == board.id).order_by(Lane.position.asc()))
        lanes = lres.scalars().all()
        lanes_by_state = {l.state_key: l for l in lanes}
        backlog = lanes_by_state.get("backlog") or lanes[0]
        doing = lanes_by_state.get("in_progress") or backlog
        blocked = lanes_by_state.get("blocked") or backlog
        done = lanes_by_state.get("done") or backlog

        now = datetime.now(timezone.utc)
        samples = [
          (backlog, "Welcome to Task-Daddy", "This is a demo task. Open it to see the task drawer + Copilot.\n\n- Try editing fields\n- Add a checklist\n- Add a comment", ["welcome", "demo"], False),
          (doing, "Try moving tasks", "Use drag & drop on desktop.\n\nOn mobile: long-press → Move to lane.", ["demo"], False),
          (blocked, "Blocked example", "This card is blocked to demonstrate visual signals + reminders.", ["blocked", "demo"], True),
          (done, "Done example", "A completed task in the Done lane.", ["done", "demo"], False),
        ]
        for idx, (lane, title, desc, tags, is_blocked) in enumerate(samples):
          t = Task(
            board_id=board.id,
            lane_id=lane.id,
            state_key=lane.state_key,
            title=title,
            description=desc,
            owner_id=member.id,
            priority="P2",
            type="Feature",
            tags=tags,
            due_date=(now + timedelta(days=idx + 1)),
            estimate_minutes=30,
            blocked=is_blocked,
            blocked_reason=("Waiting on dependency" if is_blocked else None),
            order_index=idx,
            version=0,
          )
          db.add(t)
          await db.flush()
          if title == "Welcome to Task-Daddy":
            db.add(Comment(task_id=t.id, author_id=admin.id, body="Tip: press `/` to focus search, `n` to create a task, `esc` to close the drawer."))

    await db.commit()
    if boot_lines:
      out_dir = Path(os.getenv("BOOTSTRAP_CREDENTIALS_DIR", "data/backups"))
      out_dir.mkdir(parents=True, exist_ok=True)
      out_file = out_dir / "bootstrap_credentials.txt"
      stamp = datetime.now(timezone.utc).isoformat()
      out_file.write_text(f"[{stamp}]\n" + "\n".join(boot_lines) + "\n", encoding="utf-8")
      print("Task-Daddy seed credentials created:")
      for ln in boot_lines:
        print(f"  {ln}")
      print(f"Saved to {out_file}")


def main() -> None:
  asyncio.run(seed())


if __name__ == "__main__":
  main()
