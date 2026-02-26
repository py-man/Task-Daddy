from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.backups.service import (
  create_full_backup,
  create_machine_recovery_export,
  delete_backup,
  get_backup_policy,
  list_backups,
  purge_old_backups,
  restore_full_backup,
  update_backup_policy,
)
from app.deps import get_current_user, get_db, require_admin_mfa_guard
from app.models import User

router = APIRouter(prefix="/backups", tags=["backups"])


@router.get("")
async def backups_list(user: User = Depends(get_current_user), _: None = Depends(require_admin_mfa_guard)) -> list[dict]:
  if user.role != "admin":
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
  return [b.__dict__ for b in list_backups()]


@router.post("/full")
async def backups_full_create(
  user: User = Depends(get_current_user),
  db: AsyncSession = Depends(get_db),
  _: None = Depends(require_admin_mfa_guard),
) -> dict:
  if user.role != "admin":
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
  info = await create_full_backup(db)
  policy = await get_backup_policy(db)
  purge_old_backups(
    retention_days=policy.retentionDays,
    max_backups=policy.maxBackups,
    max_total_size_mb=policy.maxTotalSizeMb,
  )
  return info.__dict__


@router.post("/full_export")
async def backups_machine_recovery_export(
  user: User = Depends(get_current_user),
  db: AsyncSession = Depends(get_db),
  _: None = Depends(require_admin_mfa_guard),
) -> dict:
  if user.role != "admin":
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
  info = await create_machine_recovery_export(db)
  policy = await get_backup_policy(db)
  purge_old_backups(
    retention_days=policy.retentionDays,
    max_backups=policy.maxBackups,
    max_total_size_mb=policy.maxTotalSizeMb,
  )
  return info.__dict__


@router.get("/policy")
async def backups_policy_get(
  user: User = Depends(get_current_user),
  db: AsyncSession = Depends(get_db),
  _: None = Depends(require_admin_mfa_guard),
) -> dict:
  if user.role != "admin":
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
  return (await get_backup_policy(db)).__dict__


@router.patch("/policy")
async def backups_policy_patch(
  payload: dict,
  user: User = Depends(get_current_user),
  db: AsyncSession = Depends(get_db),
  _: None = Depends(require_admin_mfa_guard),
) -> dict:
  if user.role != "admin":
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
  try:
    updated = await update_backup_policy(db, payload)
    purge_old_backups(
      retention_days=updated.retentionDays,
      max_backups=updated.maxBackups,
      max_total_size_mb=updated.maxTotalSizeMb,
    )
    return updated.__dict__
  except ValueError as e:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.get("/{filename}/download")
async def backups_download(filename: str, user: User = Depends(get_current_user), _: None = Depends(require_admin_mfa_guard)) -> FileResponse:
  if user.role != "admin":
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
  # validate filename with service logic by calling restore dry-run path
  from pathlib import Path
  from app.config import settings

  if "/" in filename or "\\" in filename or ".." in filename:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid filename")
  p = Path(settings.backup_dir) / filename
  if not p.exists():
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backup not found")
  return FileResponse(path=str(p), filename=filename, media_type="application/gzip")


@router.post("/restore")
async def backups_restore(
  payload: dict,
  user: User = Depends(get_current_user),
  db: AsyncSession = Depends(get_db),
  _: None = Depends(require_admin_mfa_guard),
) -> dict:
  if user.role != "admin":
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
  filename = str(payload.get("filename") or "").strip()
  mode = str(payload.get("mode") or "skip_existing").strip()
  dry_run = bool(payload.get("dryRun", False))
  try:
    return await restore_full_backup(db, filename=filename, mode=mode, dry_run=dry_run)
  except FileNotFoundError as e:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
  except ValueError as e:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.post("/upload")
async def backups_upload_and_restore(
  mode: str = "skip_existing",
  dryRun: bool = False,
  file: UploadFile = File(...),
  user: User = Depends(get_current_user),
  db: AsyncSession = Depends(get_db),
  _: None = Depends(require_admin_mfa_guard),
) -> dict:
  if user.role != "admin":
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
  data = await file.read()
  if not data:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file")
  from pathlib import Path
  import uuid
  from app.config import settings

  backup_dir = Path(settings.backup_dir)
  backup_dir.mkdir(parents=True, exist_ok=True)
  name = (file.filename or "").strip()
  if not name.endswith(".tar.gz"):
    name = f"uploaded_backup_{uuid.uuid4().hex[:12]}.tar.gz"
  else:
    # Avoid path traversal
    name = Path(name).name
  out = backup_dir / name
  out.write_bytes(data)
  try:
    return await restore_full_backup(db, filename=out.name, mode=mode, dry_run=bool(dryRun))
  except ValueError as e:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.delete("/{filename}")
async def backups_delete(filename: str, user: User = Depends(get_current_user), _: None = Depends(require_admin_mfa_guard)) -> dict:
  if user.role != "admin":
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
  try:
    return delete_backup(filename)
  except ValueError as e:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
