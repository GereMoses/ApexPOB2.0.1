"""
Audit Trail API — query base_operationlog for who changed what and when.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from ..core.database import get_db
from ..core.dependencies import get_current_user

router = APIRouter(prefix="/api/v1/audit", tags=["Audit Trail"])


@router.get("/logs")
async def get_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user_id: int = None,
    module: str = None,
    action: str = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    # Require superuser or explicit audit.view permission
    if not getattr(current_user, "is_superuser", False):
        perm = db.execute(text("""
            SELECT 1 FROM auth_user_role ur
            JOIN auth_role r ON r.id = ur.role_id
            JOIN auth_role_permission rp ON rp.role_id = r.id
            JOIN auth_permission p ON p.id = rp.permission_id
            WHERE ur.user_id = :uid AND p.codename IN ('audit.view', 'audit.manage')
            LIMIT 1
        """), {"uid": current_user.id}).fetchone()
        if not perm:
            raise HTTPException(status_code=403, detail="Permission denied: audit.view required")

    # Non-admins may only query their own audit trail
    if not getattr(current_user, "is_superuser", False) and user_id and user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Cannot query another user's audit log")

    offset = (page - 1) * page_size
    filters, params = [], {"limit": page_size, "offset": offset}
    if user_id:
        filters.append("o.user_id = :user_id"); params["user_id"] = user_id
    if module:
        filters.append("o.table_name ILIKE :module"); params["module"] = f"%{module}%"
    if action:
        filters.append("o.action ILIKE :action"); params["action"] = f"%{action}%"
    where = ("WHERE " + " AND ".join(filters)) if filters else ""

    rows = db.execute(text(f"""
        SELECT o.id, o.created_at AS created_time, o.action AS operation_type,
               o.table_name AS module, o.table_name, o.record_id AS object_id,
               o.remark AS description,
               u.username, u.email,
               o.ip_address, o.user_agent
        FROM base_operationlog o
        LEFT JOIN auth_user u ON u.id = o.user_id
        {where}
        ORDER BY o.created_at DESC
        LIMIT :limit OFFSET :offset
    """), params).fetchall()

    total = db.execute(text(f"""
        SELECT COUNT(*) FROM base_operationlog o {where}
    """), {k: v for k, v in params.items() if k not in ('limit', 'offset')}).scalar()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "logs": [dict(r._mapping) for r in rows],
    }


@router.get("/summary")
async def audit_summary(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Top-level stats: most active users, most changed modules."""
    by_user = db.execute(text("""
        SELECT u.username, COUNT(*) AS actions
        FROM base_operationlog o
        LEFT JOIN auth_user u ON u.id = o.user_id
        WHERE o.created_at >= NOW() - INTERVAL '30 days'
        GROUP BY u.username ORDER BY actions DESC LIMIT 10
    """)).fetchall()

    by_module = db.execute(text("""
        SELECT table_name AS module, COUNT(*) AS actions
        FROM base_operationlog
        WHERE created_at >= NOW() - INTERVAL '30 days'
          AND table_name IS NOT NULL
        GROUP BY table_name ORDER BY actions DESC LIMIT 10
    """)).fetchall()

    total = db.execute(text(
        "SELECT COUNT(*) FROM base_operationlog WHERE created_at >= NOW() - INTERVAL '30 days'"
    )).scalar()

    return {
        "total_last_30_days": total,
        "top_users": [dict(r._mapping) for r in by_user],
        "top_modules": [dict(r._mapping) for r in by_module],
    }
