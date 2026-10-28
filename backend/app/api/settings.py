from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field
import datetime

from ..core.database import get_db
from ..core.security import get_password_hash, verify_password, validate_password_strength
from ..core.dependencies import get_current_user

router = APIRouter(prefix="/api/v1/settings", tags=["Settings"])


# ─── Pydantic models ──────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    username: str
    password: str
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_superuser: bool = False
    is_active: bool = True
    role_ids: Optional[List[int]] = []

class UserUpdate(BaseModel):
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_superuser: Optional[bool] = None
    is_active: Optional[bool] = None

class PasswordChange(BaseModel):
    new_password: str
    current_password: Optional[str] = None

class RoleCreate(BaseModel):
    name: str
    description: Optional[str] = None
    is_active: bool = True

class RoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

class RolePermissionsUpdate(BaseModel):
    permission_ids: List[int]

class UserRolesUpdate(BaseModel):
    role_ids: List[int]

class CompanyUpdate(BaseModel):
    name: Optional[str] = None
    short_name: Optional[str] = None
    industry: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    logo_url: Optional[str] = None
    timezone: Optional[str] = None
    date_format: Optional[str] = None
    time_format: Optional[str] = None
    fiscal_year_start: Optional[str] = None


# ─── Users ────────────────────────────────────────────────────────────────────

def _has_db_permission(user_id: int, codename: str, db: Session) -> bool:
    row = db.execute(text("""
        SELECT 1 FROM auth_user_role ur
        JOIN auth_role r ON r.id = ur.role_id AND r.is_active = true
        JOIN auth_role_permission rp ON rp.role_id = r.id
        JOIN auth_permission p ON p.id = rp.permission_id AND p.codename = :perm
        WHERE ur.user_id = :uid
        LIMIT 1
    """), {"uid": user_id, "perm": codename}).fetchone()
    return row is not None


def _require(codename: str, current_user, db: Session):
    if current_user.is_superuser:
        return
    if not _has_db_permission(current_user.id, codename, db):
        raise HTTPException(403, f"Access denied: requires '{codename}' permission")


@router.get("/users")
async def list_users(
    search: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    where = ["1=1"]
    params: dict = {}

    if search:
        where.append("(u.username ILIKE :search OR u.email ILIKE :search OR u.first_name ILIKE :search OR u.last_name ILIKE :search)")
        params["search"] = f"%{search}%"
    if is_active is not None:
        where.append("u.is_active = :is_active")
        params["is_active"] = is_active

    cond = " AND ".join(where)
    total = db.execute(text(f"SELECT count(*) FROM auth_user u WHERE {cond}"), params).scalar()

    params["limit"]  = page_size
    params["offset"] = (page - 1) * page_size

    rows = db.execute(text(f"""
        SELECT u.id, u.username, u.email, u.first_name, u.last_name,
               u.is_superuser, u.is_active, u.last_login, u.created_at,
               COALESCE(
                   json_agg(json_build_object('id', r.id, 'name', r.name))
                   FILTER (WHERE r.id IS NOT NULL), '[]'
               ) AS roles
        FROM auth_user u
        LEFT JOIN auth_user_role ur ON ur.user_id = u.id
        LEFT JOIN auth_role r ON r.id = ur.role_id
        WHERE {cond}
        GROUP BY u.id
        ORDER BY u.username
        LIMIT :limit OFFSET :offset
    """), params).fetchall()

    _require("settings.manage_users", current_user, db)
    return {"data": [dict(r._mapping) for r in rows], "total": total, "page": page, "page_size": page_size}


@router.post("/users", status_code=201)
async def create_user(body: UserCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    body.username = body.username.strip().lower()
    exists = db.execute(text("SELECT id FROM auth_user WHERE lower(username) = :u"), {"u": body.username}).fetchone()
    if exists:
        raise HTTPException(400, f"Username '{body.username}' is already taken")

    try:
        validate_password_strength(body.password, body.username)
    except ValueError as e:
        raise HTTPException(400, str(e))
    hashed = get_password_hash(body.password)
    row = db.execute(text("""
        INSERT INTO auth_user (username, password, email, first_name, last_name, is_superuser, is_active)
        VALUES (:username, :password, :email, :first_name, :last_name, :is_superuser, :is_active)
        RETURNING id, username, email, first_name, last_name, is_superuser, is_active, created_at
    """), {
        "username":     body.username,
        "password":     hashed,
        "email":        body.email,
        "first_name":   body.first_name,
        "last_name":    body.last_name,
        "is_superuser": body.is_superuser,
        "is_active":    body.is_active,
    }).fetchone()
    _require("settings.manage_users", current_user, db)
    new_id = row.id
    for role_id in (body.role_ids or []):
        db.execute(text(
            "INSERT INTO auth_user_role (user_id, role_id) VALUES (:u, :r) ON CONFLICT DO NOTHING"
        ), {"u": new_id, "r": role_id})
    db.commit()
    return dict(row._mapping)


@router.get("/users/{user_id}")
async def get_user(user_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    row = db.execute(text("""
        SELECT u.id, u.username, u.email, u.first_name, u.last_name,
               u.is_superuser, u.is_active, u.last_login, u.created_at,
               COALESCE(
                   json_agg(json_build_object('id', r.id, 'name', r.name))
                   FILTER (WHERE r.id IS NOT NULL), '[]'
               ) AS roles
        FROM auth_user u
        LEFT JOIN auth_user_role ur ON ur.user_id = u.id
        LEFT JOIN auth_role r ON r.id = ur.role_id
        WHERE u.id = :id
        GROUP BY u.id
    """), {"id": user_id}).fetchone()
    if not row:
        raise HTTPException(404, "User not found")
    _require("settings.manage_users", current_user, db)
    return dict(row._mapping)


@router.put("/users/{user_id}")
async def update_user(user_id: int, body: UserUpdate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    _require("settings.manage_users", current_user, db)
    existing = db.execute(text("SELECT id FROM auth_user WHERE id = :id"), {"id": user_id}).fetchone()
    if not existing:
        raise HTTPException(404, "User not found")

    sets, params = [], {"id": user_id}
    for field in ["email", "first_name", "last_name", "is_superuser", "is_active"]:
        val = getattr(body, field)
        if val is not None:
            sets.append(f"{field} = :{field}")
            params[field] = val

    if sets:
        sets.append("updated_at = now()")
        db.execute(text(f"UPDATE auth_user SET {', '.join(sets)} WHERE id = :id"), params)
        db.commit()

    return await get_user(user_id, db, current_user)


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(user_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    _require("settings.manage_users", current_user, db)
    row = db.execute(text("SELECT id, is_superuser FROM auth_user WHERE id = :id"), {"id": user_id}).fetchone()
    if not row:
        raise HTTPException(404, "User not found")
    if row.is_superuser:
        raise HTTPException(400, "Cannot delete a superuser account")
    db.execute(text("DELETE FROM auth_user WHERE id = :id"), {"id": user_id})
    db.commit()


@router.put("/users/{user_id}/password")
async def change_password(user_id: int, body: PasswordChange, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    row = db.execute(text("SELECT id, password FROM auth_user WHERE id = :id"), {"id": user_id}).fetchone()
    if not row:
        raise HTTPException(404, "User not found")

    if body.current_password:
        if not verify_password(body.current_password, row.password):
            raise HTTPException(400, "Current password is incorrect")

    try:
        validate_password_strength(body.new_password)
    except ValueError as e:
        raise HTTPException(400, str(e))
    hashed = get_password_hash(body.new_password)
    db.execute(text("UPDATE auth_user SET password = :p, updated_at = now() WHERE id = :id"), {"p": hashed, "id": user_id})
    db.commit()
    return {"detail": "Password updated"}


@router.get("/users/{user_id}/roles")
async def get_user_roles(user_id: int, db: Session = Depends(get_db)):
    rows = db.execute(text("""
        SELECT r.id, r.name, r.description, r.is_active
        FROM auth_role r
        JOIN auth_user_role ur ON ur.role_id = r.id
        WHERE ur.user_id = :uid
        ORDER BY r.name
    """), {"uid": user_id}).fetchall()
    return [dict(r._mapping) for r in rows]


@router.put("/users/{user_id}/roles")
async def set_user_roles(user_id: int, body: UserRolesUpdate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    _require("settings.manage_roles", current_user, db)
    db.execute(text("DELETE FROM auth_user_role WHERE user_id = :uid"), {"uid": user_id})
    for role_id in body.role_ids:
        db.execute(text("INSERT INTO auth_user_role (user_id, role_id) VALUES (:u, :r) ON CONFLICT DO NOTHING"), {"u": user_id, "r": role_id})
    db.commit()
    return await get_user_roles(user_id, db)


# ─── Roles ────────────────────────────────────────────────────────────────────

@router.get("/roles")
async def list_roles(
    search: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    where, params = ["1=1"], {}
    if search:
        where.append("(r.name ILIKE :search OR r.description ILIKE :search)")
        params["search"] = f"%{search}%"
    if is_active is not None:
        where.append("r.is_active = :is_active")
        params["is_active"] = is_active
    cond = " AND ".join(where)

    rows = db.execute(text(f"""
        SELECT r.id, r.name, r.description, r.is_active, r.created_at,
               count(DISTINCT ur.user_id)::int AS user_count,
               count(DISTINCT rp.permission_id)::int AS permission_count
        FROM auth_role r
        LEFT JOIN auth_user_role ur ON ur.role_id = r.id
        LEFT JOIN auth_role_permission rp ON rp.role_id = r.id
        WHERE {cond}
        GROUP BY r.id
        ORDER BY r.name
    """), params).fetchall()
    _require("settings.manage_roles", current_user, db)
    return [dict(r._mapping) for r in rows]


@router.post("/roles", status_code=201)
async def create_role(body: RoleCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    _require("settings.manage_roles", current_user, db)
    exists = db.execute(text("SELECT id, name FROM auth_role WHERE lower(name) = lower(:n)"), {"n": body.name.strip()}).fetchone()
    if exists:
        raise HTTPException(400, f"A role named '{exists.name}' already exists")
    row = db.execute(text("""
        INSERT INTO auth_role (name, description, is_active)
        VALUES (:name, :description, :is_active)
        RETURNING id, name, description, is_active, created_at
    """), {"name": body.name, "description": body.description, "is_active": body.is_active}).fetchone()
    db.commit()
    return dict(row._mapping)


@router.get("/roles/{role_id}")
async def get_role(role_id: int, db: Session = Depends(get_db)):
    row = db.execute(text("""
        SELECT r.id, r.name, r.description, r.is_active, r.created_at,
               COALESCE(
                   json_agg(json_build_object('id', p.id, 'name', p.name, 'codename', p.codename))
                   FILTER (WHERE p.id IS NOT NULL), '[]'
               ) AS permissions
        FROM auth_role r
        LEFT JOIN auth_role_permission rp ON rp.role_id = r.id
        LEFT JOIN auth_permission p ON p.id = rp.permission_id
        WHERE r.id = :id
        GROUP BY r.id
    """), {"id": role_id}).fetchone()
    if not row:
        raise HTTPException(404, "Role not found")
    return dict(row._mapping)


@router.put("/roles/{role_id}")
async def update_role(role_id: int, body: RoleUpdate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    _require("settings.manage_roles", current_user, db)
    existing = db.execute(text("SELECT id FROM auth_role WHERE id = :id"), {"id": role_id}).fetchone()
    if not existing:
        raise HTTPException(404, "Role not found")

    sets, params = [], {"id": role_id}
    for field in ["name", "description", "is_active"]:
        val = getattr(body, field)
        if val is not None:
            sets.append(f"{field} = :{field}")
            params[field] = val

    if sets:
        sets.append("updated_at = now()")
        db.execute(text(f"UPDATE auth_role SET {', '.join(sets)} WHERE id = :id"), params)
        db.commit()

    return await get_role(role_id, db)


@router.delete("/roles/{role_id}", status_code=204)
async def delete_role(role_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    _require("settings.manage_roles", current_user, db)
    row = db.execute(text("SELECT id FROM auth_role WHERE id = :id"), {"id": role_id}).fetchone()
    if not row:
        raise HTTPException(404, "Role not found")
    in_use = db.execute(text("SELECT count(*) FROM auth_user_role WHERE role_id = :id"), {"id": role_id}).scalar()
    if in_use:
        raise HTTPException(400, f"Role is assigned to {in_use} user(s); unassign first")
    db.execute(text("DELETE FROM auth_role WHERE id = :id"), {"id": role_id})
    db.commit()


@router.get("/roles/{role_id}/permissions")
async def get_role_permissions(role_id: int, db: Session = Depends(get_db)):
    rows = db.execute(text("""
        SELECT p.id, p.name, p.codename, p.description
        FROM auth_permission p
        JOIN auth_role_permission rp ON rp.permission_id = p.id
        WHERE rp.role_id = :rid
        ORDER BY p.codename
    """), {"rid": role_id}).fetchall()
    return [dict(r._mapping) for r in rows]


@router.put("/roles/{role_id}/permissions")
async def set_role_permissions(role_id: int, body: RolePermissionsUpdate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    _require("settings.manage_roles", current_user, db)
    db.execute(text("DELETE FROM auth_role_permission WHERE role_id = :rid"), {"rid": role_id})
    for perm_id in body.permission_ids:
        db.execute(text("INSERT INTO auth_role_permission (role_id, permission_id) VALUES (:r, :p) ON CONFLICT DO NOTHING"), {"r": role_id, "p": perm_id})
    db.commit()
    return await get_role_permissions(role_id, db)


# ─── Permissions ──────────────────────────────────────────────────────────────

@router.get("/permissions")
async def list_permissions(db: Session = Depends(get_db)):
    rows = db.execute(text("""
        SELECT id, name, codename, description,
               split_part(codename, '.', 1) AS module
        FROM auth_permission
        ORDER BY codename
    """)).fetchall()
    return [dict(r._mapping) for r in rows]


# ─── Company ──────────────────────────────────────────────────────────────────

def _company_row(db: Session):
    """Return the single company row, creating it from column defaults if absent.

    A fresh install has no row, and both GET and PUT used to 404 on that — which
    left the Company tab permanently unusable on a new deployment: you could not
    read the settings, and you could not create them either. Every column carries
    a sensible default, so materialising the row on first access is safe and makes
    the screen work out of the box.
    """
    row = db.execute(text("SELECT * FROM system_company ORDER BY id LIMIT 1")).fetchone()
    if row is None:
        db.execute(text("INSERT INTO system_company DEFAULT VALUES"))
        db.commit()
        row = db.execute(text("SELECT * FROM system_company ORDER BY id LIMIT 1")).fetchone()
    return row


@router.get("/company")
async def get_company(db: Session = Depends(get_db)):
    row = _company_row(db)
    if not row:
        raise HTTPException(404, "Company settings not found")
    return dict(row._mapping)


@router.put("/company")
async def update_company(body: CompanyUpdate, db: Session = Depends(get_db)):
    row = _company_row(db)
    if not row:
        raise HTTPException(404, "Company settings not found")

    fields = body.model_dump(exclude_none=True)
    if not fields:
        return await get_company(db)

    sets   = [f"{k} = :{k}" for k in fields]
    sets.append("updated_at = now()")
    params = {**fields, "id": row.id}
    db.execute(text(f"UPDATE system_company SET {', '.join(sets)} WHERE id = :id"), params)
    db.commit()
    return await get_company(db)


# ─── Audit Log ────────────────────────────────────────────────────────────────

@router.get("/audit-log")
async def get_audit_log(
    search: Optional[str] = Query(None),
    user_id: Optional[int] = Query(None),
    action: Optional[str] = Query(None),
    table_name: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    where, params = ["1=1"], {}

    if search:
        where.append("(u.username ILIKE :search OR l.action ILIKE :search OR l.table_name ILIKE :search)")
        params["search"] = f"%{search}%"
    if user_id:
        where.append("l.user_id = :user_id")
        params["user_id"] = user_id
    if action:
        where.append("l.action ILIKE :action")
        params["action"] = f"%{action}%"
    if table_name:
        where.append("l.table_name ILIKE :table_name")
        params["table_name"] = f"%{table_name}%"
    if start_date:
        where.append("l.created_at >= :start_date")
        params["start_date"] = start_date
    if end_date:
        where.append("l.created_at < CAST(:end_date AS date) + interval '1 day'")
        params["end_date"] = end_date

    cond = " AND ".join(where)
    total = db.execute(text(f"""
        SELECT count(*) FROM base_operationlog l
        LEFT JOIN auth_user u ON u.id = l.user_id
        WHERE {cond}
    """), params).scalar()

    params["limit"]  = page_size
    params["offset"] = (page - 1) * page_size

    rows = db.execute(text(f"""
        SELECT l.id, l.action, l.table_name, l.record_id,
               l.old_values, l.new_values, l.ip_address, l.created_at,
               u.username, u.first_name, u.last_name
        FROM base_operationlog l
        LEFT JOIN auth_user u ON u.id = l.user_id
        WHERE {cond}
        ORDER BY l.created_at DESC
        LIMIT :limit OFFSET :offset
    """), params).fetchall()

    return {"data": [dict(r._mapping) for r in rows], "total": total, "page": page, "page_size": page_size}


# ─── Security / Session ───────────────────────────────────────────────────────

_DEFAULT_TIMEOUT = 480  # 8 hours

class SecuritySettingsUpdate(BaseModel):
    session_timeout_minutes: int = Field(..., ge=0, le=525960)


@router.get("/security")
async def get_security_settings(db: Session = Depends(get_db)):
    row = db.execute(text("SELECT rule_value FROM att_rules WHERE rule_key = 'session_timeout_minutes'")).fetchone()
    timeout = int(row.rule_value) if row and row.rule_value else _DEFAULT_TIMEOUT
    return {"session_timeout_minutes": timeout}


@router.put("/security")
async def update_security_settings(
    body: SecuritySettingsUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not current_user.is_superuser:
        raise HTTPException(403, "Superuser access required")
    db.execute(text("""
        INSERT INTO att_rules (rule_key, rule_value)
        VALUES ('session_timeout_minutes', :v)
        ON CONFLICT (rule_key) DO UPDATE SET rule_value = :v, updated_at = now()
    """), {"v": str(body.session_timeout_minutes)})
    db.commit()
    return {"session_timeout_minutes": body.session_timeout_minutes}
