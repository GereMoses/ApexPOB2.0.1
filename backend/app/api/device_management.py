"""
Device Management API - BioTime 9.5 Compatible
Comprehensive device CRUD, commands, firmware, and real-time monitoring
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import text, func, and_, or_
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta, timezone
import logging
import json
import os
import uuid

from ..core.database import get_db
from ..services.device_pin import rewrite_command, pin_for
from ..core.dependencies import get_current_user
from ..models.user import User
from ..models.biotime_models import IClockTerminal, IClockTransaction, PersonnelEmployee
from ..models.device import Device, DeviceStatus, DeviceSchedule, DeviceMaintenance
from ..services.device_planes import is_controller as _is_controller

# Router
router = APIRouter()

# Configure logging
logger = logging.getLogger(__name__)

# Constants
DEVICE_ONLINE_THRESHOLD_MINUTES = 2   # 2× a 30s heartbeat interval before marking offline
COMMAND_TIMEOUT_MINUTES = 10
FIRMWARE_UPLOAD_DIR = "uploads/firmware"

# Pydantic Models
class DeviceCreate(BaseModel):
    sn: str = Field(..., min_length=1, max_length=20, description="Device serial number")
    alias: Optional[str] = Field(None, max_length=100, description="Device alias/name")
    ip_address: Optional[str] = Field(None, description="Device IP address")
    area_id: Optional[int] = Field(None, description="Area ID (T&A readers)")
    comm_key: Optional[str] = Field("0", max_length=20, description="Communication key")
    device_type: Optional[int] = Field(0, ge=0, le=3, description="Device type: 0=Attendance,1=Access,2=Mustering,3=Emergency")
    zone_id: Optional[int] = Field(None, description="Zone ID (Access Control readers)")
    reader_purpose: Optional[str] = Field("ATTENDANCE", description="ATTENDANCE | ACCESS_ENTRY | ACCESS_EXIT | MUSTERING | POB | EMERGENCY")
    device_name: Optional[str] = Field(None, max_length=50, description="Device name")
    device_model: Optional[str] = Field(None, max_length=50, description="Device model")
    connection_mode: Optional[str] = Field("adms", description="adms | direct | both")

_PURPOSE_TO_DEVICE_TYPE = {
    "ATTENDANCE":   0,
    "ACCESS_ENTRY": 1,
    "ACCESS_EXIT":  1,
    "MUSTERING":    2,
    "POB":          1,
    "EMERGENCY":    3,
}

class DeviceUpdate(BaseModel):
    model_config = {"coerce_numbers_to_str": False, "str_strip_whitespace": True}

    alias: Optional[str] = Field(None, max_length=100)
    ip_address: Optional[str] = Field(None)
    area_id: Optional[int] = Field(None)
    comm_key: Optional[str] = Field(None, max_length=20)
    device_type: Optional[int] = Field(None, ge=0, le=3)
    zone_id: Optional[int] = Field(None)
    reader_purpose: Optional[str] = Field(None, description="ATTENDANCE | ACCESS_ENTRY | ACCESS_EXIT | MUSTERING | POB | EMERGENCY")
    device_name: Optional[str] = Field(None, max_length=50)
    device_model: Optional[str] = Field(None, max_length=50)
    connection_mode: Optional[str] = Field(None, description="adms | direct | both")
    state: Optional[int] = Field(None, ge=0, le=1)

    @classmethod
    def model_validate(cls, obj, *args, **kwargs):
        # Coerce string integers sent from plain HTML <input type="number">
        if isinstance(obj, dict):
            for field in ("zone_id", "area_id", "device_type", "state"):
                v = obj.get(field)
                if isinstance(v, str):
                    obj[field] = int(v) if v.strip() else None
        return super().model_validate(obj, *args, **kwargs)

class DeviceResponse(BaseModel):
    id: int
    sn: str
    alias: Optional[str]
    ip_address: Optional[str]
    area_id: Optional[int]
    comm_key: Optional[str]
    device_name: Optional[str]
    device_model: Optional[str]
    fw_version: Optional[str]   # alias for fw_ver — kept for frontend compatibility
    platform: Optional[str]
    mac_address: Optional[str]
    oem_vendor: Optional[str]
    user_count: int
    fp_count: int
    face_count: int
    palm_count: int
    log_count: int
    device_type: int
    zone_id: Optional[int]
    reader_purpose: str = "ATTENDANCE"
    connection_mode: str = "adms"
    is_auto_reg: bool
    state: int
    last_activity: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    status: str  # Online/Offline based on last_activity

class DeviceCommandRequest(BaseModel):
    sn: str = Field(..., description="Device serial number")
    cmd: str = Field(..., description="Command to send")
    command_type: Optional[str] = Field(None, description="Command type for categorization")

class DeviceCommandResponse(BaseModel):
    id: int
    sn: str
    cmd_content: str
    status: int  # 0=pending,1=sent,2=success,3=fail
    cmd_commit_time: datetime
    cmd_trans_time: Optional[datetime]
    cmd_return_time: Optional[datetime]
    cmd_return: Optional[str]

class BatchImportRequest(BaseModel):
    devices: List[Dict[str, Any]] = Field(..., description="List of devices to import")

class FirmwareUploadResponse(BaseModel):
    firmware_id: str
    filename: str
    file_size: int
    upload_time: datetime
    device_types: List[str]

class FirmwarePushRequest(BaseModel):
    firmware_id: str = Field(..., description="Firmware file ID")
    sn_list: List[str] = Field(..., description="List of device serial numbers")

# Helper Functions
def get_device_status(last_activity: Optional[datetime], state: Optional[int] = None) -> str:
    """
    Determine device status.
    State constants: 0=PENDING, 1=APPROVED/online, 2=REJECTED, 3=OFFLINE (heartbeat-set).
    The heartbeat service owns state transitions — trust state=1 as online and state=3 as offline.
    Returns lowercase 'online' or 'offline' to match frontend switch() comparisons.
    """
    if state in (2, 3):   # heartbeat or admin marked offline/rejected
        return "offline"
    if state == 1:         # heartbeat confirmed online within ADMS_STALE_SECS (5 min)
        return "online"
    # PENDING (0) or no state yet — fall back to last_activity recency
    if not last_activity:
        return "offline"
    now = datetime.now(timezone.utc)
    if last_activity.tzinfo is None:
        last_activity = last_activity.replace(tzinfo=timezone.utc)
    if (now - last_activity).total_seconds() <= DEVICE_ONLINE_THRESHOLD_MINUTES * 60:
        return "online"
    return "offline"

def queue_command(db: Session, device_sn: str, command: str, user_id: Optional[int] = None):
    """Queue a command for a device"""
    try:
        command = rewrite_command(db, command)   # PIN=<emp_code> -> reader PIN
        # Insert command into iclock_devcmd table
        result = db.execute(text("""
            INSERT INTO iclock_devcmd (sn, cmd_content, cmd_commit_time, status)
            VALUES (:sn, :cmd_content, :commit_time, 0)
            RETURNING id
        """), {
            'sn': device_sn,
            'cmd_content': command,
            'commit_time': datetime.utcnow()
        })
        
        command_id = result.scalar()
        db.commit()
        
        logger.info(f"✅ Queued command '{command}' for device {device_sn} (ID: {command_id})")
        return command_id
        
    except Exception as e:
        logger.error(f"❌ Error queuing command: {e}")
        db.rollback()
        raise

def _build_adms_userinfo_cmd(row) -> str:
    """Build a ZKTeco PUSH-protocol DATA UPDATE USERINFO command.

    Format is confirmed working (reader replies Return=0): a SPACE after USERINFO,
    then tab-separated PIN/Name/Pri/Passwd/Card/Grp/TZ. The previous form
    (`USERINFO\\tPin=..Privilege=..Password=..Group=..TimeZone=..`) was rejected
    with Return=-1 — wrong leading separator AND wrong field names — which is why
    Sync All Employees / Sync User / Sync Department silently never landed.
    """
    name = (f"{row.first_name or ''} {row.last_name or ''}".strip() or row.emp_code)[:24]
    card = getattr(row, 'card_no', '') or ''
    pwd  = getattr(row, 'pwd', '') or ''
    return (
        f"DATA UPDATE USERINFO PIN={row.emp_code}\t"
        f"Name={name}\tPri=0\tPasswd={pwd}\tCard={card}\tGrp=1\tTZ=0"
    )


def validate_device_exists(db: Session, device_sn: str) -> IClockTerminal:
    """Validate that device exists and return it"""
    device = db.query(IClockTerminal).filter(IClockTerminal.sn == device_sn).first()
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device {device_sn} not found"
        )
    return device

def get_real_time_device_stats(db: Session, device_sn: str) -> Dict[str, Any]:
    """Get real-time statistics for a device"""
    try:
        # Get recent transactions
        recent_txns = db.execute(text("""
            SELECT COUNT(*) as count, MAX(punch_time) as last_punch
            FROM iclock_transaction 
            WHERE terminal_sn = :sn 
            AND punch_time >= :since
        """), {
            'sn': device_sn,
            'since': datetime.utcnow() - timedelta(hours=24)
        }).fetchone()
        
        # Get pending commands
        pending_cmds = db.execute(text("""
            SELECT COUNT(*) as count
            FROM iclock_devcmd 
            WHERE sn = :sn AND status = 0
        """), {'sn': device_sn}).fetchone()
        
        return {
            'transactions_24h': recent_txns.count if recent_txns else 0,
            'last_punch': recent_txns.last_punch if recent_txns and recent_txns.last_punch else None,
            'pending_commands': pending_cmds.count if pending_cmds else 0
        }
        
    except Exception as e:
        logger.error(f"Error getting device stats: {e}")
        return {
            'transactions_24h': 0,
            'last_punch': None,
            'pending_commands': 0
        }

# Device CRUD Endpoints

@router.get("/api/device/areas/")
async def get_areas(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all T&A areas (personnel_area table)."""
    rows = db.execute(text(
        "SELECT id, area_code, area_name FROM personnel_area ORDER BY area_name"
    )).fetchall()
    return [{"id": r.id, "area_code": r.area_code, "name": r.area_name} for r in rows]


@router.get("/api/device/terminals/", response_model=None)
async def get_terminals(
    search: Optional[str] = Query(None, description="Search by SN or alias"),
    area_id: Optional[int] = Query(None, description="Filter by area ID"),
    device_type: Optional[int] = Query(None, ge=0, le=3, description="Filter by device type"),
    status: Optional[str] = Query(None, description="Filter by status: online/offline"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(50, ge=1, le=1000, description="Items per page"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all terminals with filtering and pagination.
    Returns devices from iclock_terminal (ADMS) PLUS any devices in the `devices`
    table that have no iclock_terminal entry (ZKLib direct-mode devices).
    """
    try:
        status_filter = status.lower() if status else None

        # ── Phase 1: iclock_terminal rows (ADMS / dual-mode) ─────────────────
        query = db.query(IClockTerminal)
        if search:
            query = query.filter(or_(
                IClockTerminal.sn.ilike(f"%{search}%"),
                IClockTerminal.alias.ilike(f"%{search}%"),
                IClockTerminal.device_name.ilike(f"%{search}%"),
            ))
        if area_id:
            query = query.filter(IClockTerminal.area_id == area_id)
        if device_type is not None:
            query = query.filter(IClockTerminal.device_type == device_type)

        terminals = query.all()

        device_responses = []
        seen_sns = set()

        for terminal in terminals:
            device_status = get_device_status(terminal.last_activity, getattr(terminal, "state", None))
            if status_filter and device_status != status_filter:
                continue
            seen_sns.add(terminal.sn)
            device_responses.append(DeviceResponse(
                id=terminal.id,
                sn=terminal.sn,
                alias=getattr(terminal, 'alias', None),
                ip_address=getattr(terminal, 'ip_address', None),
                area_id=getattr(terminal, 'area_id', None),
                comm_key=getattr(terminal, 'comm_key', None),
                device_name=getattr(terminal, 'device_name', None),
                device_model=getattr(terminal, 'device_model', None),
                fw_version=getattr(terminal, 'fw_ver', None),
                platform=getattr(terminal, 'platform', None),
                mac_address=getattr(terminal, 'mac_address', None),
                oem_vendor=getattr(terminal, 'oem_vendor', None),
                user_count=getattr(terminal, 'user_count', 0) or 0,
                fp_count=getattr(terminal, 'fp_count', 0) or 0,
                face_count=getattr(terminal, 'face_count', 0) or 0,
                palm_count=getattr(terminal, 'palm_count', 0) or 0,
                log_count=getattr(terminal, 'log_count', 0) or 0,
                device_type=getattr(terminal, 'device_type', 0) or 0,
                zone_id=getattr(terminal, 'zone_id', None),
                reader_purpose=getattr(terminal, 'reader_purpose', None) or 'ATTENDANCE',
                connection_mode=getattr(terminal, 'connection_mode', 'adms') or 'adms',
                is_auto_reg=getattr(terminal, 'is_auto_reg', False) or False,
                state=terminal.state or 0,
                last_activity=terminal.last_activity,
                created_at=terminal.created_at,
                updated_at=terminal.updated_at,
                status=device_status,
            ))

        # ── Phase 2: direct-mode `devices` rows not in iclock_terminal ───────
        # These are ZKLib-only devices that never pushed via ADMS and therefore
        # have no iclock_terminal entry — they would otherwise be invisible.
        direct_q = db.query(Device).filter(
            Device.serial_number.isnot(None),
            ~db.query(IClockTerminal.id).filter(
                IClockTerminal.sn == Device.serial_number
            ).exists(),
        )
        if search:
            direct_q = direct_q.filter(Device.name.ilike(f"%{search}%") | Device.serial_number.ilike(f"%{search}%"))

        for dev in direct_q.all():
            sn = dev.serial_number
            if sn in seen_sns:
                continue
            dev_status = "online" if dev.status == DeviceStatus.ONLINE else "offline"
            if status_filter and dev_status != status_filter:
                continue
            # Derive state integer from device status so the UI renders correctly
            dev_state = 1 if dev.status == DeviceStatus.ONLINE else 3
            now_dt = datetime.now(timezone.utc)
            device_responses.append(DeviceResponse(
                id=dev.id,
                sn=sn,
                alias=dev.name,
                ip_address=dev.ip_address,
                area_id=None,
                comm_key=None,
                device_name=dev.name,
                device_model=None,
                fw_version=None,
                platform=None,
                mac_address=None,
                oem_vendor=None,
                user_count=0,
                fp_count=0,
                face_count=0,
                palm_count=0,
                log_count=0,
                device_type=0,
                zone_id=dev.zone_id,
                reader_purpose='ATTENDANCE',
                connection_mode=dev.connection_mode or 'direct',
                is_auto_reg=False,
                state=dev_state,
                last_activity=dev.last_seen,
                created_at=dev.created_at or now_dt,
                updated_at=dev.updated_at or dev.created_at or now_dt,
                status=dev_status,
            ))

        # Sort: online first, then by sn
        device_responses.sort(key=lambda d: (0 if d.status == "online" else 1, d.sn))

        # Apply pagination after merging both sources
        total = len(device_responses)
        offset_val = (page - 1) * limit
        page_items = device_responses[offset_val: offset_val + limit]

        # Return paginated list. model_dump(mode='json') converts datetime → ISO string
        # so JSONResponse can serialize it without TypeError.
        from fastapi.responses import JSONResponse
        return JSONResponse({
            "data":  [r.model_dump(mode='json') for r in page_items],
            "total": total,
        })

    except Exception as e:
        logger.error(f"Error getting terminals: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch terminals"
        )

def _sync_device_row(db: Session, sn: str, *, connection_mode: Optional[str] = None,
                     ip_address: Optional[str] = None, zone_id: Optional[int] = None,
                     name: Optional[str] = None) -> None:
    """
    Create or update the `devices` row that the ZKTeco background services
    (poller, live_capture, heartbeat) read, so a change made in the UI to a
    terminal ALWAYS controls real behaviour and stays in sync with the database.

    Crucially this sets `auto_poll` from the connection mode: direct/both readers
    must be polled, adms readers are push-only. Without it, switching a reader to
    'direct' in the UI updated iclock_terminal but the services never started
    polling (auto_poll stayed False from ADMS registration), so 'direct' silently
    did nothing. It also CREATES the devices row when missing, so manually-added
    or ADMS-only readers can be switched to direct and immediately start working.
    """
    mode = (connection_mode or 'adms').strip().lower()
    if mode not in ('adms', 'direct', 'both'):
        mode = 'adms'
    dev = db.query(Device).filter(Device.serial_number == sn).first()
    if dev is None:
        dev = Device(serial_number=sn, status=DeviceStatus.OFFLINE, poll_interval_sec=300)
        db.add(dev)
    dev.connection_mode = mode
    dev.auto_poll = mode in ('direct', 'both')
    if name:
        dev.name = name
    elif not dev.name:
        dev.name = f"Terminal-{sn}"
    if ip_address is not None:
        dev.ip_address = ip_address
    if not dev.port:
        dev.port = 4370
    if zone_id is not None:
        dev.zone_id = zone_id


@router.post("/api/device/terminals", response_model=DeviceResponse)
async def create_terminal(
    terminal_data: DeviceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new terminal
    BioTime compatible endpoint
    """
    try:
        # Check if terminal already exists
        existing = db.query(IClockTerminal).filter(IClockTerminal.sn == terminal_data.sn).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Terminal with SN {terminal_data.sn} already exists"
            )
        
        # Create new terminal
        new_terminal = IClockTerminal(
            sn=terminal_data.sn,
            alias=terminal_data.alias or f"Terminal {terminal_data.sn}",
            ip_address=terminal_data.ip_address,
            area_id=terminal_data.area_id,
            comm_key=terminal_data.comm_key,
            device_name=terminal_data.device_name,
            device_model=terminal_data.device_model,
            reader_purpose=terminal_data.reader_purpose or 'ATTENDANCE',
            connection_mode=terminal_data.connection_mode or 'adms',
            device_type=_PURPOSE_TO_DEVICE_TYPE.get(terminal_data.reader_purpose or 'ATTENDANCE',
                        terminal_data.device_type or 0),
            zone_id=terminal_data.zone_id,
            is_auto_reg=False,
            state=0,  # Initially offline
            user_count=0,
            fp_count=0,
            face_count=0,
            palm_count=0,
            log_count=0,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.add(new_terminal)
        db.commit()
        db.refresh(new_terminal)

        # Create the matching `devices` row so the polling/heartbeat/live-capture
        # services actually see this reader (they read from `devices`). Without it
        # a manually-added direct reader would never be polled or come online.
        _sync_device_row(db, new_terminal.sn,
                         connection_mode=new_terminal.connection_mode,
                         ip_address=new_terminal.ip_address,
                         zone_id=new_terminal.zone_id,
                         name=new_terminal.alias)
        # Re-adding a reader through the UI clears any prior deletion suppression.
        from .adms_protocol import unsuppress_device
        unsuppress_device(db, new_terminal.sn)
        db.commit()

        # Convert to response format
        device_status = get_device_status(new_terminal.last_activity, getattr(new_terminal, "state", None))
        
        return DeviceResponse(
            id=new_terminal.id,
            sn=new_terminal.sn,
            alias=new_terminal.alias,
            ip_address=new_terminal.ip_address,
            area_id=new_terminal.area_id,
            comm_key=new_terminal.comm_key,
            device_name=new_terminal.device_name,
            device_model=new_terminal.device_model,
            fw_version=new_terminal.fw_ver,
            platform=new_terminal.platform,
            mac_address=new_terminal.mac_address,
            oem_vendor=new_terminal.oem_vendor,
            user_count=new_terminal.user_count or 0,
            fp_count=new_terminal.fp_count or 0,
            face_count=new_terminal.face_count or 0,
            palm_count=new_terminal.palm_count or 0,
            log_count=new_terminal.log_count or 0,
            device_type=new_terminal.device_type or 0,
            zone_id=new_terminal.zone_id,
            reader_purpose=new_terminal.reader_purpose or 'ATTENDANCE',
            connection_mode=new_terminal.connection_mode or 'adms',
            is_auto_reg=new_terminal.is_auto_reg or False,
            state=new_terminal.state or 0,
            last_activity=new_terminal.last_activity,
            created_at=new_terminal.created_at,
            updated_at=new_terminal.updated_at,
            status=device_status
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating terminal: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create terminal"
        )

@router.get("/api/device/terminals/{device_id}", response_model=DeviceResponse)
async def get_terminal(
    device_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get terminal by ID"""
    try:
        terminal = db.query(IClockTerminal).filter(IClockTerminal.id == device_id).first()
        if not terminal:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Terminal not found"
            )
        
        device_status = get_device_status(terminal.last_activity, getattr(terminal, "state", None))
        
        return DeviceResponse(
            id=terminal.id,
            sn=terminal.sn,
            alias=terminal.alias,
            ip_address=terminal.ip_address,
            area_id=terminal.area_id,
            comm_key=terminal.comm_key,
            device_name=terminal.device_name,
            device_model=terminal.device_model,
            fw_version=terminal.fw_ver,
            platform=terminal.platform,
            mac_address=terminal.mac_address,
            oem_vendor=terminal.oem_vendor,
            user_count=terminal.user_count or 0,
            fp_count=terminal.fp_count or 0,
            face_count=terminal.face_count or 0,
            palm_count=terminal.palm_count or 0,
            log_count=terminal.log_count or 0,
            device_type=terminal.device_type or 0,
            zone_id=terminal.zone_id,
            reader_purpose=terminal.reader_purpose or 'ATTENDANCE',
            connection_mode=terminal.connection_mode or 'adms',
            is_auto_reg=terminal.is_auto_reg or False,
            state=terminal.state or 0,
            last_activity=terminal.last_activity,
            created_at=terminal.created_at,
            updated_at=terminal.updated_at,
            status=device_status
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting terminal: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch terminal"
        )

@router.put("/api/device/terminals/{device_id}", response_model=DeviceResponse)
async def update_terminal(
    device_id: int,
    terminal_data: DeviceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update terminal"""
    try:
        terminal = db.query(IClockTerminal).filter(IClockTerminal.id == device_id).first()
        if not terminal:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Terminal not found"
            )
        
        # Update fields
        update_data = terminal_data.dict(exclude_unset=True)
        # Auto-derive device_type from reader_purpose when purpose is being changed
        if 'reader_purpose' in update_data:
            update_data['device_type'] = _PURPOSE_TO_DEVICE_TYPE.get(
                update_data['reader_purpose'], update_data.get('device_type', terminal.device_type or 0)
            )
        for field, value in update_data.items():
            setattr(terminal, field, value)

        terminal.updated_at = datetime.utcnow()

        # Keep the `devices` row (the services' source of truth) fully in sync with
        # the terminal — creating it if missing and, critically, setting auto_poll
        # from the connection mode so switching to 'direct' in the UI actually
        # starts polling (and 'adms' stops it). The heartbeat/poller/live_capture
        # read connection_mode + auto_poll from `devices`, not iclock_terminal.
        if any(f in update_data for f in ('connection_mode', 'ip_address', 'zone_id', 'alias')):
            _sync_device_row(
                db, terminal.sn,
                connection_mode=update_data.get('connection_mode') or terminal.connection_mode,
                ip_address=update_data['ip_address'] if 'ip_address' in update_data else None,
                zone_id=update_data['zone_id'] if 'zone_id' in update_data else None,
                name=update_data.get('alias') or None,
            )

        db.commit()
        db.refresh(terminal)
        
        device_status = get_device_status(terminal.last_activity, getattr(terminal, "state", None))
        
        return DeviceResponse(
            id=terminal.id,
            sn=terminal.sn,
            alias=terminal.alias,
            ip_address=terminal.ip_address,
            area_id=terminal.area_id,
            comm_key=terminal.comm_key,
            device_name=terminal.device_name,
            device_model=terminal.device_model,
            fw_version=terminal.fw_ver,
            platform=terminal.platform,
            mac_address=terminal.mac_address,
            oem_vendor=terminal.oem_vendor,
            user_count=terminal.user_count or 0,
            fp_count=terminal.fp_count or 0,
            face_count=terminal.face_count or 0,
            palm_count=terminal.palm_count or 0,
            log_count=terminal.log_count or 0,
            device_type=terminal.device_type or 0,
            zone_id=terminal.zone_id,
            reader_purpose=terminal.reader_purpose or 'ATTENDANCE',
            connection_mode=terminal.connection_mode or 'adms',
            is_auto_reg=terminal.is_auto_reg or False,
            state=terminal.state or 0,
            last_activity=terminal.last_activity,
            created_at=terminal.created_at,
            updated_at=terminal.updated_at,
            status=device_status
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating terminal: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update terminal"
        )

@router.delete("/api/device/terminals/{device_id}")
async def delete_terminal(
    device_id: int,
    force: bool = Query(False, description="Force delete even with transactions"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete terminal and clean up all referencing records."""
    try:
        terminal = db.query(IClockTerminal).filter(IClockTerminal.id == device_id).first()
        if not terminal:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Terminal not found")

        sn = terminal.sn

        # Check transaction count — block non-forced deletes that have attendance history
        txn_count = db.execute(
            text("SELECT COUNT(*) FROM iclock_transaction WHERE terminal_sn = :sn"), {'sn': sn}
        ).scalar()
        if txn_count > 0 and not force:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot delete terminal with {txn_count} transactions. Use force=true to override.",
            )

        # ── Cascade cleanup ──────────────────────────────────────────────────
        # 1. Always delete device-specific records (each table uses its own FK column name)
        db.execute(text("DELETE FROM iclock_devcmd WHERE sn = :sn"), {'sn': sn})
        db.execute(text("DELETE FROM device_schedules WHERE device_id = :sn"), {'sn': sn})
        db.execute(text("DELETE FROM device_maintenance WHERE device_id = :sn"), {'sn': sn})

        # 2. Nullify informational FK references (SET NULL where allowed)
        nullable_refs = [
            ('acc_door',                  'terminal_sn'),
            ('mustering_log',             'device_sn'),
            ('emergency_device',          'terminal_sn'),
            ('emergency_device_enhanced', 'terminal_sn'),
            ('checkinout',                'terminal_sn'),
            ('vis_visit_log',             'device_sn'),
            ('mtg_attendance',            'device_sn'),
            ('iclock_operlog',            'terminal_sn'),
            ('iclock_bio_template',       'source_sn'),
        ]
        for tbl, col in nullable_refs:
            try:
                db.execute(text(f"UPDATE {tbl} SET {col} = NULL WHERE {col} = :sn"), {'sn': sn})
            except Exception:
                db.rollback()  # table may not exist — safe to skip

        # 3. Attendance transactions: delete on force, nullify otherwise
        if force:
            db.execute(text("DELETE FROM iclock_transaction WHERE terminal_sn = :sn"), {'sn': sn})
        else:
            try:
                db.execute(text("UPDATE iclock_transaction SET terminal_sn = NULL WHERE terminal_sn = :sn"), {'sn': sn})
            except Exception:
                db.execute(text("DELETE FROM iclock_transaction WHERE terminal_sn = :sn"), {'sn': sn})

        db.flush()

        # Also remove the matching Device row (and its zone assignments) if one exists
        try:
            device_row = db.execute(
                text("SELECT id FROM devices WHERE serial_number = :sn"), {'sn': sn}
            ).fetchone()
            if device_row:
                dev_id = device_row[0]
                db.execute(text("DELETE FROM zone_reader_assignments WHERE reader_id = :id"), {'id': dev_id})
                db.execute(text("DELETE FROM devices WHERE id = :id"), {'id': dev_id})
        except Exception as dev_err:
            logger.warning(f"Could not clean up devices row for {sn}: {dev_err}")
            db.rollback()

        db.delete(terminal)

        # Remember the deletion so the LAN scanner / ADMS auto-register don't
        # silently re-add this reader while it's still powered on and reachable.
        from .adms_protocol import suppress_device
        suppress_device(db, sn)

        db.commit()

        return {"message": f"Terminal {sn} deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting terminal {device_id}: {e}")
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete terminal")

@router.post("/api/device/terminals/batch-import")
async def batch_import_terminals(
    import_data: BatchImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Batch import terminals from CSV data"""
    try:
        imported_count = 0
        skipped_count = 0
        errors = []
        
        for device_data in import_data.devices:
            try:
                # Validate required fields
                if 'sn' not in device_data or not device_data['sn']:
                    errors.append(f"Missing SN for device: {device_data}")
                    skipped_count += 1
                    continue
                
                # Check if already exists
                existing = db.query(IClockTerminal).filter(IClockTerminal.sn == device_data['sn']).first()
                if existing:
                    skipped_count += 1
                    continue
                
                # Create terminal
                new_terminal = IClockTerminal(
                    sn=device_data['sn'],
                    alias=device_data.get('alias', f"Terminal {device_data['sn']}"),
                    ip_address=device_data.get('ip_address'),
                    area_id=device_data.get('area_id'),
                    comm_key=device_data.get('comm_key', '0'),
                    device_name=device_data.get('device_name'),
                    device_model=device_data.get('device_model'),
                    device_type=device_data.get('device_type', 0),
                    zone_id=device_data.get('zone_id'),
                    is_auto_reg=False,
                    state=0,
                    user_count=0,
                    fp_count=0,
                    face_count=0,
                    palm_count=0,
                    log_count=0,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                
                db.add(new_terminal)
                imported_count += 1
                
            except Exception as e:
                errors.append(f"Error importing {device_data.get('sn', 'unknown')}: {str(e)}")
                skipped_count += 1
        
        db.commit()
        
        return {
            "imported": imported_count,
            "skipped": skipped_count,
            "errors": errors
        }
        
    except Exception as e:
        logger.error(f"Error in batch import: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to import terminals"
        )

# Device Commands Endpoints

@router.get("/api/device/devcmd/", response_model=List[DeviceCommandResponse])
async def get_device_commands(
    sn: Optional[str] = Query(None, description="Filter by device serial number"),
    status: Optional[int] = Query(None, ge=0, le=3, description="Filter by status"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get device command queue"""
    try:
        # Build query
        query = "SELECT id, sn, cmd_content, status, cmd_commit_time, cmd_trans_time, cmd_return_time, cmd_return FROM iclock_devcmd WHERE 1=1"
        params = {}
        
        if sn:
            query += " AND sn = :sn"
            params['sn'] = sn
        
        if status is not None:
            query += " AND status = :status"
            params['status'] = status
        
        query += " ORDER BY cmd_commit_time DESC LIMIT :limit OFFSET :offset"
        params['limit'] = limit
        params['offset'] = (page - 1) * limit
        
        result = db.execute(text(query), params)
        commands = []
        
        for row in result:
            command = DeviceCommandResponse(
                id=row.id,
                sn=row.sn,
                cmd_content=row.cmd_content,
                status=row.status,
                cmd_commit_time=row.cmd_commit_time,
                cmd_trans_time=row.cmd_trans_time,
                cmd_return_time=row.cmd_return_time,
                cmd_return=row.cmd_return
            )
            commands.append(command)
        
        return commands
        
    except Exception as e:
        logger.error(f"Error getting device commands: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch device commands"
        )

async def _execute_direct_command(device: Device, cmd: str) -> dict:
    """
    Execute a command immediately via ZKLib for direct-connect devices.
    Pauses live_capture so the device's single TCP slot is free, then reconnects.
    Returns {"success": bool, "message": str, "error": str|None}.
    """
    from ..services.zkteco.direct_connection import zkteco_direct
    from ..services.zkteco.live_capture import with_device_released
    ip = device.ip_address
    port = device.port or 4370
    cmd_upper = cmd.strip().upper()

    if cmd_upper in ("REBOOT", "RESTART"):
        coro = zkteco_direct.restart_device(ip, port)
    elif cmd_upper in ("UNLOCK", "OPEN", "OPEN DOOR"):
        coro = zkteco_direct.open_door(ip, port)
    elif cmd_upper in ("DISABLE", "LOCK"):
        coro = zkteco_direct.disable_device(ip, port)
    elif cmd_upper in ("ENABLE", "UNLOCK DEVICE"):
        coro = zkteco_direct.enable_device(ip, port)
    elif cmd_upper in ("SYNC TIME", "SYNCTIME", "SET TIME"):
        coro = zkteco_direct.sync_time(ip, port)
    elif cmd_upper in ("CHECK", "TEST", "PING", "TEST CONNECTION"):
        coro = zkteco_direct.test_connection(ip, port)
    elif cmd_upper in ("GET LOG", "GETALLLOG", "PULL LOG", "PULL ATTENDANCE"):
        coro = zkteco_direct.get_attendance(ip, port)
    elif cmd_upper in ("GET USERINFO", "GET USERS", "GETUSERINFO"):
        coro = zkteco_direct.get_users(ip, port)
    elif cmd_upper in ("CLEAR LOG", "CLEARATTLOG", "CLEAR ATTENDANCE"):
        coro = zkteco_direct.clear_attendance(ip, port)
    elif cmd_upper in ("INFO", "GET INFO", "GET TIME"):
        coro = zkteco_direct.get_time(ip, port)
    else:
        return {"success": False, "error": f"Command '{cmd}' not supported for direct devices. Supported: REBOOT, UNLOCK, DISABLE, ENABLE, SYNC TIME, CHECK, GET LOG, GET USERINFO, CLEAR LOG, INFO"}

    try:
        return await with_device_released(device.id, coro)
    except Exception as exc:
        return {"success": False, "error": str(exc)}


async def _direct_delete_user(device: Device, emp_code: str) -> dict:
    """Delete an employee from a direct (ZKLib) reader: resolve uid by emp_code,
    then delete. Wrapped in with_device_released so it doesn't fight live_capture."""
    from ..services.zkteco.direct_connection import zkteco_direct
    from ..services.zkteco.live_capture import with_device_released
    if not emp_code:
        return {"success": False, "error": "emp_code is required"}
    ip, port = device.ip_address, device.port or 4370

    async def _do():
        users = await zkteco_direct.get_users_from_device(ip, port)
        if not users.get("success"):
            return {"success": False, "error": users.get("error", "could not read device users")}
        uid = next((u["uid"] for u in users.get("users", [])
                    if str(u.get("user_id")) == str(emp_code)), None)
        if uid is None:
            return {"success": False, "error": f"User {emp_code} is not on this device"}
        return await zkteco_direct.delete_user(ip=ip, uid=uid, port=port)

    try:
        return await with_device_released(device.id, _do())
    except Exception as exc:
        return {"success": False, "error": str(exc)}


# ── Control-plane classification (single source of truth for command routing) ──
PLANE_DIRECT     = "direct"      # server → ZKLib (pyzk) TCP; command runs immediately
PLANE_ADMS       = "adms"        # reader → polls /iclock/getrequest; command is QUEUED
PLANE_CONTROLLER = "controller"  # InBio/C3 access panel — C3/PULL protocol (driver pending)

# Access-control panels (InBio / C3-400) speak neither pyzk's standalone protocol
# nor (necessarily) ADMS push. Flag them so the UI can warn and callers never
# silently send a command that can't reach them.
_ACCESS_PANEL_HINTS = ("inbio", "c3-400", "c3-200", "c3-100", "c3400", "c3 400", "c3pro", "c3 pro")


def _looks_like_access_panel(*texts) -> bool:
    blob = " ".join(t.lower() for t in texts if t)
    return any(h in blob for h in _ACCESS_PANEL_HINTS)


def classify_control_plane(sn: str, db: Session) -> dict:
    """Decide HOW a command must reach a device — the one place this is decided:
         connection_mode in (direct, both) AND a reachable IP  → DIRECT (ZKLib)
         otherwise                                             → ADMS (queued poll)
       Also flags InBio/C3 access panels (pyzk can't drive them)."""
    dev  = db.query(Device).filter(Device.serial_number == sn).first()
    term = db.query(IClockTerminal).filter(IClockTerminal.sn == sn).first()
    dev_mode  = (getattr(dev, "connection_mode", None) or "").strip().lower()
    term_mode = (getattr(term, "connection_mode", None) or "").strip().lower()
    mode = dev_mode or term_mode or "adms"
    # A 'controller' flag in EITHER table wins — never let table drift cause a panel
    # to be misrouted to ZKLib/ADMS (which would silently fail or send junk).
    if PLANE_CONTROLLER in (dev_mode, term_mode):
        mode = PLANE_CONTROLLER
    ip    = getattr(dev, "ip_address", None) or getattr(term, "ip_address", None)
    port  = getattr(dev, "port", None) or 4370
    model = (getattr(term, "device_model", None) or getattr(term, "device_name", None)
             or getattr(dev, "device_name", None) or "")
    alias = getattr(term, "alias", None) or ""
    if mode == PLANE_CONTROLLER:
        plane = PLANE_CONTROLLER          # admin explicitly flagged an InBio/C3 panel
    elif mode in ("direct", "both") and ip:
        plane = PLANE_DIRECT
    else:
        plane = PLANE_ADMS
    return {
        "sn": sn, "plane": plane, "connection_mode": mode,
        "ip": ip, "port": port, "model": model,
        "is_access_panel": _looks_like_access_panel(model, alias, sn),
    }


def _block_controller(sn: str, db: Session) -> None:
    """Refuse generic ADMS/ZKLib command paths for InBio/C3 controllers — they have
    no driver yet, so a queued/ZKLib command would silently fail or send junk.
    Call at the top of every command endpoint that isn't controller-specific."""
    if _is_controller(sn, db):
        raise HTTPException(
            status_code=400,
            detail=("InBio/C3 access controller — POB's controller (C3/PULL) driver "
                    "isn't available yet, so this command can't be sent from here."))


@router.post("/api/device/devcmd")
async def send_device_command(
    command_data: DeviceCommandRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Send command to device — direct via ZKLib for direct-connect devices, queued for ADMS devices."""
    try:
        validate_device_exists(db, command_data.sn)

        # InBio/C3 access controllers speak the C3/PULL protocol — neither ZKLib nor
        # ADMS. No driver yet, so never silently queue/ZKLib; tell the caller plainly.
        if classify_control_plane(command_data.sn, db)["plane"] == PLANE_CONTROLLER:
            return {
                "sn": command_data.sn, "cmd": command_data.cmd, "status": "not_supported",
                "message": ("This is an InBio/C3 access controller. POB's controller "
                            "(C3/PULL) driver isn't available yet — manage it on its "
                            "access-control software until that integration ships."),
            }

        # Check if this is a direct-connect device (ZKLib, not ADMS queue)
        direct_device = (
            db.query(Device)
            .filter(
                Device.serial_number == command_data.sn,
                Device.connection_mode.in_(["direct", "both"]),
                Device.ip_address.isnot(None),
            )
            .first()
        )

        if direct_device:
            result = await _execute_direct_command(direct_device, command_data.cmd)
            if not result.get("success"):
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=result.get("error", "Command failed on device"),
                )
            # Record in devcmd as success so command history is visible
            db.execute(text("""
                INSERT INTO iclock_devcmd (sn, cmd_content, cmd_commit_time, cmd_trans_time, cmd_return_time, status)
                VALUES (:sn, :cmd, :now, :now, :now, 2)
            """), {"sn": command_data.sn, "cmd": command_data.cmd, "now": datetime.utcnow()})
            db.commit()
            return {
                "sn": command_data.sn,
                "cmd": command_data.cmd,
                "status": "success",
                "message": result.get("message", "Command executed successfully"),
            }

        # ADMS device — reject commands that are ZKLib-only and have no ADMS equivalent
        _ZKLIB_ONLY = {
            'PULL ATTENDANCE', 'GET LOG', 'GETALLLOG', 'PULL LOG',
            'GET USERINFO', 'GETUSERINFO', 'GET USERS',
            'CLEAR LOG', 'CLEARATTLOG', 'CLEAR ATTENDANCE',
        }
        if command_data.cmd.strip().upper() in _ZKLIB_ONLY:
            return {
                "sn": command_data.sn,
                "cmd": command_data.cmd,
                "status": "not_applicable",
                "message": (
                    f"'{command_data.cmd}' is a ZKLib (direct TCP) command and cannot be sent to an ADMS device. "
                    "For ADMS devices, attendance records are pushed automatically by the reader on every heartbeat — "
                    "no manual pull is needed."
                ),
            }

        # Queue as normal — device picks up on next /iclock/getrequest poll
        command_id = queue_command(db, command_data.sn, command_data.cmd, current_user.id)
        return {
            "id": command_id,
            "sn": command_data.sn,
            "cmd": command_data.cmd,
            "status": "pending",
            "message": "Command queued — will be delivered on next device poll",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending device command: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send command"
        )


@router.get("/api/device/control-planes/")
async def get_control_planes(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Per-device control-plane map (plane=direct|adms, is_access_panel) so the
    Command UI can segregate ADMS (push/queue) from Direct (ZKLib) readers and
    flag InBio/C3 access panels. Backend stays the single source of truth."""
    sns = [r[0] for r in db.execute(text("SELECT sn FROM iclock_terminal")).fetchall()]
    return {"data": [classify_control_plane(sn, db) for sn in sns]}


# ── InBio/C3 access-controller endpoints (Phase 2 — transport under validation) ─
class ControllerActionRequest(BaseModel):
    sn: str
    door_id: int = 1
    duration: int = 5


def _require_controller(sn: str, db: Session) -> dict:
    info = classify_control_plane(sn, db)
    if info["plane"] != PLANE_CONTROLLER:
        raise HTTPException(status_code=400,
                            detail="Device isn't a Controller. Set Connection Mode = Controller first.")
    if not info["ip"]:
        raise HTTPException(status_code=400, detail="Controller has no IP address configured.")
    return info


@router.post("/api/device/controller/test")
async def controller_test(
    sn: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Try to reach an InBio/C3 controller and read its realtime-event buffer.
    Returns success/error — used to validate the C3 driver against real hardware."""
    info = _require_controller(sn, db)
    from ..services.zkteco.c3_controller import test_connection
    return test_connection(info["ip"], info["port"] or 4370)


@router.post("/api/device/controller/open-door")
async def controller_open_door(
    payload: ControllerActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Open (unlock) a door on an InBio/C3 controller for N seconds."""
    info = _require_controller(payload.sn, db)
    from ..services.zkteco.c3_controller import open_door
    return open_door(info["ip"], payload.door_id, payload.duration, info["port"] or 4370)


@router.delete("/api/device/devcmd/{command_id}")
async def delete_device_command(
    command_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a command record from the command history."""
    row = db.execute(
        text("SELECT id FROM iclock_devcmd WHERE id = :id"),
        {"id": command_id}
    ).fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Command not found")
    db.execute(text("DELETE FROM iclock_devcmd WHERE id = :id"), {"id": command_id})
    db.commit()
    return {"id": command_id, "deleted": True}


@router.post("/api/device/devcmd/sync-user")
async def sync_user_to_device(
    sn: str,
    emp_code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Sync a single employee to the device.
    Direct-connect devices: pushed immediately via ZKLib.
    ADMS devices: queued for pickup on next device poll.
    """
    try:
        terminal = validate_device_exists(db, sn)
        _block_controller(sn, db)

        # Check personnel table first (UI-created employees), then personnel_employee (bulk import)
        row = db.execute(text("""
            SELECT id, emp_code, first_name, last_name, NULL::text AS card_no, NULL::text AS pwd
            FROM personnel WHERE emp_code = :emp_code AND status = 'ACTIVE'
            UNION ALL
            SELECT id, emp_code, first_name, last_name, card_no, pwd
            FROM personnel_employee WHERE emp_code = :emp_code AND status = 0
            LIMIT 1
        """), {"emp_code": emp_code}).fetchone()

        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail=f"Employee {emp_code} not found")

        # Direct-connect: push via ZKLib immediately
        direct_device = (
            db.query(Device)
            .filter(
                Device.serial_number == sn,
                Device.connection_mode.in_(["direct", "both"]),
                Device.ip_address.isnot(None),
            )
            .first()
        )

        if direct_device:
            from ..services.zkteco.direct_connection import _make_zk, _run_sync
            from zk import const as zk_const

            ip = direct_device.ip_address
            port = direct_device.port or 4370
            name = f"{row.first_name or ''} {row.last_name or ''}".strip()[:24] or row.emp_code
            card = int(row.card_no) if row.card_no and row.card_no.isdigit() else 0
            uid = row.id

            def _push():
                zk = _make_zk(ip, port)
                conn = zk.connect()
                try:
                    conn.set_user(uid=uid, name=name, privilege=zk_const.USER_DEFAULT,
                                  password=row.pwd or "", group_id="",
                                  user_id=pin_for(db, row.emp_code), card=card)
                finally:
                    conn.disconnect()

            direct_ok = False
            try:
                await _run_sync(_push)
                direct_ok = True
            except Exception as exc:
                logger.warning(f"Direct push failed for {sn}, falling back to ADMS queue: {exc}")

            if direct_ok:
                db.execute(text("""
                    INSERT INTO iclock_devcmd (sn, cmd_content, cmd_commit_time, cmd_trans_time, cmd_return_time, status)
                    VALUES (:sn, :cmd, :now, :now, :now, 2)
                """), {"sn": sn, "cmd": f"SYNC USER {emp_code}", "now": datetime.utcnow()})
                db.commit()
                return {"message": f"Employee {emp_code} pushed to device directly", "synced": 1, "method": "direct"}

        # ADMS fallback — queue command (also used when direct push fails)
        cmd_id = queue_command(db, sn, _build_adms_userinfo_cmd(row), current_user.id)
        return {"message": f"User {emp_code} sync queued for device {sn} (will deliver on next poll)",
                "commands_queued": 1, "command_ids": [cmd_id], "method": "adms"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error syncing user to device: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Failed to sync user to device")

@router.post("/api/device/devcmd/sync-all-users")
async def sync_all_users_to_device(
    sn: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Sync all active employees to the device.
    Direct-connect devices: ZKLib push runs in background so the HTTP request
    returns immediately — avoids long-held connections that crash the frontend.
    ADMS devices: queued for pickup on next device poll (already fast).
    """
    try:
        terminal = validate_device_exists(db, sn)
        _block_controller(sn, db)

        # Fetch all active employees from both tables (personnel = UI-created, personnel_employee = bulk-imported)
        rows = db.execute(text("""
            SELECT id, emp_code, first_name, last_name, NULL::text AS card_no, NULL::text AS pwd
            FROM personnel
            WHERE status = 'ACTIVE' AND emp_code IS NOT NULL
            UNION ALL
            SELECT pe.id, pe.emp_code, pe.first_name, pe.last_name, pe.card_no, pe.pwd
            FROM personnel_employee pe
            WHERE pe.status = 0 AND pe.emp_code IS NOT NULL
              AND pe.emp_code NOT IN (SELECT emp_code FROM personnel WHERE emp_code IS NOT NULL)
            ORDER BY id
        """)).fetchall()

        if not rows:
            return {"message": "No active employees found to sync", "synced": 0}

        # Check if this is a direct-connect device — push via ZKLib immediately
        direct_device = (
            db.query(Device)
            .filter(
                Device.serial_number == sn,
                Device.connection_mode.in_(["direct", "both"]),
                Device.ip_address.isnot(None),
            )
            .first()
        )

        if direct_device:
            from ..services.zkteco.direct_connection import _make_zk
            from zk import const as zk_const

            ip = direct_device.ip_address
            port = direct_device.port or 4370
            employees_snapshot = list(rows)   # snapshot before handing off to background thread
            total_count = len(employees_snapshot)

            def _push_in_background():
                """Runs in FastAPI's background thread pool after the HTTP response is sent."""
                synced = 0
                errors = []
                try:
                    zk = _make_zk(ip, port)
                    conn = zk.connect()
                    conn.disable_device()
                    try:
                        for row in employees_snapshot:
                            try:
                                name = f"{row.first_name or ''} {row.last_name or ''}".strip()[:24] or row.emp_code
                                card = int(row.card_no) if row.card_no and row.card_no.isdigit() else 0
                                conn.set_user(
                                    uid=row.id,
                                    name=name,
                                    privilege=zk_const.USER_DEFAULT,
                                    password=row.pwd or "",
                                    group_id="",
                                    user_id=pin_for(db, row.emp_code),
                                    card=card,
                                )
                                synced += 1
                            except Exception as exc:
                                errors.append(f"{row.emp_code}: {exc}")
                    finally:
                        conn.enable_device()
                        conn.disconnect()
                    logger.info(f"Background sync {sn}: pushed {synced}/{total_count} users, {len(errors)} errors")
                except Exception as exc:
                    logger.warning(f"Background sync {sn} failed: {exc}")

            background_tasks.add_task(_push_in_background)
            return {
                "message": f"Sync started in background — pushing {total_count} employees to {sn}",
                "total": total_count,
                "method": "direct_background",
                "status": "started",
            }

        # ADMS fallback: check if terminal supports DATA UPDATE USERINFO (PushVer 2.x)
        # For PushVer 1.x, DATA UPDATE USERINFO is not supported — use ZKLib if IP available
        pushver = (terminal.pushver or "").strip() if hasattr(terminal, 'pushver') else ""
        terminal_ip = getattr(terminal, 'ip_address', None)

        # Detect remote ADMS devices: connection_mode='adms' AND IP is a Docker gateway
        # (real device IP is not known because Docker Desktop rewrites source IPs).
        # ZKLib (port 4370) is unreachable on remote devices behind NAT — don't attempt it.
        from ..api.adms_protocol import _DOCKER_GATEWAY_IPS
        adms_device = db.query(Device).filter(
            Device.serial_number == sn,
            Device.connection_mode == 'adms',
        ).first()
        is_adms = bool(adms_device)

        # An ADMS reader is reachable ONLY through the command queue — never ZKLib,
        # regardless of the PushVer it reported. (The stored ip_address is the
        # reader's own remote LAN IP, unreachable from here, so a ZKLib attempt just
        # hangs/fails in the background and nothing syncs.) cmd_push_users uses the
        # same rule, and this reader has confirmed it accepts DATA UPDATE USERINFO
        # (Return=0) even though its pushver reads as 1.x. So: ADMS → queue.
        if not is_adms and not pushver.startswith("2") and terminal_ip:
            # Genuine direct/legacy PushVer 1.x reader on a reachable LAN IP —
            # background ZKLib push
            from ..services.zkteco.direct_connection import _make_zk
            from zk import const as zk_const
            employees_snapshot = list(rows)
            total_count = len(employees_snapshot)
            _tip = terminal_ip

            def _push_adms_bg():
                synced = 0
                try:
                    zk = _make_zk(_tip, 4370)
                    conn = zk.connect()
                    existing_users = conn.get_users()
                    code_to_uid = {str(u.user_id): u.uid for u in (existing_users or []) if u.user_id}
                    max_uid = max((u.uid for u in (existing_users or [])), default=0)
                    conn.disable_device()
                    try:
                        for row in employees_snapshot:
                            try:
                                name = f"{row.first_name or ''} {row.last_name or ''}".strip()[:24] or row.emp_code
                                card = int(row.card_no) if row.card_no and row.card_no.isdigit() else 0
                                uid = code_to_uid.get(row.emp_code)
                                if uid is None:
                                    max_uid += 1
                                    uid = max_uid
                                conn.set_user(
                                    uid=uid, name=name, privilege=zk_const.USER_DEFAULT,
                                    password=row.pwd or "", group_id="",
                                    user_id=pin_for(db, row.emp_code), card=card,
                                )
                                synced += 1
                            except Exception as exc:
                                logger.warning(f"Sync {sn} user {row.emp_code}: {exc}")
                    finally:
                        conn.enable_device()
                        conn.disconnect()
                    logger.info(f"Background ADMS sync {sn}: pushed {synced}/{total_count}")
                except Exception as exc:
                    logger.warning(f"Background ADMS sync {sn} failed: {exc}")

            background_tasks.add_task(_push_adms_bg)
            return {
                "message": f"Sync started in background — pushing {total_count} employees to {sn} (PushVer 1.x)",
                "total": total_count,
                "method": "zklib_background",
                "status": "started",
            }

        # Queue DATA UPDATE USERINFO commands (ADMS readers, or any PushVer 2.x).
        # Reader applies them on its next /iclock/getrequest poll.
        count = 0
        for row in rows:
            queue_command(db, sn, _build_adms_userinfo_cmd(row), current_user.id)
            count += 1

        return {
            "message": f"Queued {count} user sync commands for device {sn} (will deliver on next poll)",
            "employees_count": len(rows),
            "commands_queued": count,
            "method": "adms",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error syncing all users to device: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to sync users to device"
        )

@router.post("/api/device/devcmd/flush-pending-zklib")
async def flush_pending_commands_via_zklib(
    sn: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    For ZKLib / dual-mode devices: read pending ADMS queue commands, execute
    them directly via ZKLib, then mark them as delivered.  Clears the backlog
    that builds up when the ADMS fallback queued commands a device never picks up.
    """
    _block_controller(sn, db)
    device = db.execute(text("""
        SELECT ip_address, port FROM devices
        WHERE serial_number = :sn AND ip_address IS NOT NULL
    """), {"sn": sn}).fetchone()

    if not device or not device.ip_address:
        raise HTTPException(status_code=404, detail="Device not found or has no IP address")

    # Get all pending USERINFO commands for this device
    pending = db.execute(text("""
        SELECT id, cmd_content FROM iclock_devcmd
        WHERE sn = :sn AND status = 0
        ORDER BY cmd_commit_time ASC
    """), {"sn": sn}).fetchall()

    if not pending:
        return {"message": "No pending commands", "flushed": 0, "method": "zklib"}

    # Collect unique emp_codes from pending USERINFO commands
    import re
    emp_codes = []
    for cmd in pending:
        m = re.search(r'Pin=([^\t\s]+)', cmd.cmd_content or '')
        if m:
            ec = m.group(1).strip()
            if ec and ec not in emp_codes:
                emp_codes.append(ec)

    # Fetch employee data for those codes
    if emp_codes:
        placeholders = ','.join(f"'{ec}'" for ec in emp_codes)
        rows = db.execute(text(f"""
            SELECT id, emp_code, first_name, last_name, NULL::text AS card_no, NULL::text AS pwd
            FROM personnel WHERE emp_code IN ({placeholders})
            UNION ALL
            SELECT pe.id, pe.emp_code, pe.first_name, pe.last_name, pe.card_no, pe.pwd
            FROM personnel_employee pe
            WHERE pe.emp_code IN ({placeholders})
              AND pe.emp_code NOT IN (SELECT emp_code FROM personnel WHERE emp_code IS NOT NULL)
        """)).fetchall()
    else:
        rows = []

    if not rows and not pending:
        return {"message": "No user data found for pending commands", "flushed": 0}

    from ..services.zkteco.direct_connection import _make_zk, _run_sync
    from zk import const as zk_const

    ip   = device.ip_address
    port = device.port or 4370
    employees_snapshot = list(rows)
    synced = 0
    errors = []

    def _push():
        nonlocal synced
        zk = _make_zk(ip, port)
        conn = zk.connect()
        # Build uid map from existing device users to avoid uid collisions
        existing = conn.get_users() or []
        code_to_uid = {str(u.user_id): u.uid for u in existing if u.user_id}
        max_uid = max((u.uid for u in existing), default=0)
        conn.disable_device()
        try:
            for row in employees_snapshot:
                try:
                    name = f"{row.first_name or ''} {row.last_name or ''}".strip()[:24] or row.emp_code
                    card = int(row.card_no) if row.card_no and str(row.card_no).isdigit() else 0
                    uid = code_to_uid.get(str(row.emp_code))
                    if uid is None:
                        max_uid += 1
                        uid = max_uid
                    conn.set_user(uid=uid, name=name, privilege=zk_const.USER_DEFAULT,
                                  password=row.pwd or "", group_id="",
                                  user_id=pin_for(db, str(row.emp_code)), card=card)
                    synced += 1
                except Exception as exc:
                    errors.append(f"{row.emp_code}: {exc}")
        finally:
            conn.enable_device()
            conn.disconnect()

    try:
        await _run_sync(_push)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"ZKLib connection failed: {exc}")

    # Mark all pending commands as delivered
    cmd_ids = [c.id for c in pending]
    db.execute(text("""
        UPDATE iclock_devcmd SET status = 2, cmd_trans_time = :now, cmd_return_time = :now
        WHERE id = ANY(:ids)
    """), {"now": datetime.utcnow(), "ids": cmd_ids})
    db.commit()

    return {
        "message": f"Flushed {len(cmd_ids)} pending commands via ZKLib ({synced} users pushed)",
        "flushed": len(cmd_ids),
        "synced": synced,
        "errors": errors,
        "method": "zklib",
    }


@router.post("/api/device/devcmd/sync-department")
async def sync_department_to_device(
    sn: str,
    department: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Sync all active employees in a department to the device."""
    try:
        terminal = validate_device_exists(db, sn)
        _block_controller(sn, db)

        rows = db.execute(text("""
            SELECT p.id, p.emp_code, p.first_name, p.last_name, NULL::text AS card_no, NULL::text AS pwd
            FROM personnel p
            JOIN personnel_department pd ON pd.personnel_id = p.id
            JOIN departments d ON d.id = pd.department_id
            WHERE p.status = 'ACTIVE' AND p.emp_code IS NOT NULL
              AND LOWER(d.name) = LOWER(:dept)
            UNION ALL
            SELECT pe.id, pe.emp_code, pe.first_name, pe.last_name, pe.card_no, pe.pwd
            FROM personnel_employee pe
            WHERE pe.status = 0 AND pe.emp_code IS NOT NULL
              AND LOWER(pe.department) = LOWER(:dept)
              AND pe.emp_code NOT IN (SELECT emp_code FROM personnel WHERE emp_code IS NOT NULL)
            ORDER BY id
        """), {"dept": department}).fetchall()

        if not rows:
            return {"message": f"No active employees found in department '{department}'", "synced": 0}

        direct_device = (
            db.query(Device)
            .filter(
                Device.serial_number == sn,
                Device.connection_mode.in_(["direct", "both"]),
                Device.ip_address.isnot(None),
            )
            .first()
        )

        if direct_device:
            from ..services.zkteco.direct_connection import _make_zk, _run_sync
            from zk import const as zk_const

            ip = direct_device.ip_address
            port = direct_device.port or 4370
            snapshot = list(rows)
            errors = []
            synced = 0

            def _push():
                nonlocal synced
                zk = _make_zk(ip, port)
                conn = zk.connect()
                conn.disable_device()
                try:
                    for row in snapshot:
                        try:
                            name = f"{row.first_name or ''} {row.last_name or ''}".strip()[:24] or row.emp_code
                            card = int(row.card_no) if row.card_no and row.card_no.isdigit() else 0
                            conn.set_user(uid=row.id, name=name, privilege=zk_const.USER_DEFAULT,
                                          password=row.pwd or "", group_id="",
                                          user_id=pin_for(db, row.emp_code), card=card)
                            synced += 1
                        except Exception as exc:
                            errors.append(f"{row.emp_code}: {exc}")
                finally:
                    conn.enable_device()
                    conn.disconnect()

            direct_ok = False
            try:
                await _run_sync(_push)
                direct_ok = True
            except Exception as exc:
                logger.warning(f"Direct push failed for {sn}, falling back to ADMS queue: {exc}")

            if direct_ok:
                db.execute(text("""
                    INSERT INTO iclock_devcmd (sn, cmd_content, cmd_commit_time, cmd_trans_time, cmd_return_time, status)
                    VALUES (:sn, :cmd, :now, :now, :now, 2)
                """), {"sn": sn, "cmd": f"SYNC DEPT {department} ({synced} pushed)", "now": datetime.utcnow()})
                db.commit()
                return {"message": f"Pushed {synced} of {len(rows)} employees from '{department}' to device directly",
                        "synced": synced, "total": len(rows), "errors": errors, "method": "direct"}

        # ADMS fallback — queue DATA UPDATE commands (also used when direct push fails)
        count = 0
        for row in rows:
            queue_command(db, sn, _build_adms_userinfo_cmd(row), current_user.id)
            count += 1
        return {"message": f"Queued {count} sync commands for department '{department}' (will deliver on next poll)",
                "commands_queued": count, "method": "adms"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error syncing department to device: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Failed to sync department to device")


@router.post("/api/device/devcmd/emergency")
async def emergency_device_command(
    sn: str,
    action: str = Query(..., pattern="^(ON|OFF)$", description="Emergency action: ON or OFF"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Send emergency device command"""
    try:
        # Validate device exists and is emergency type
        device = validate_device_exists(db, sn)
        _block_controller(sn, db)
        
        if device.device_type != 3:  # Not emergency device
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Device {sn} is not an emergency device"
            )
        
        # Check user permissions (could implement role check here)
        # For now, assume authenticated user has permission
        
        # Queue emergency command
        cmd = f"EMERGENCY_{action}"
        command_id = queue_command(db, sn, cmd, current_user.id)
        
        # Update emergency device status
        db.execute(text("""
            UPDATE emergency_device 
            SET status = :status, last_heartbeat = :heartbeat
            WHERE terminal_sn = :sn
        """), {
            'status': 1 if action == "ON" else 0,
            'heartbeat': datetime.utcnow(),
            'sn': sn
        })
        db.commit()
        
        return {
            "id": command_id,
            "sn": sn,
            "action": action,
            "status": "pending",
            "message": f"Emergency {action} command queued for device {sn}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending emergency command: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send emergency command"
        )

# Real-time Monitoring Endpoints

@router.get("/api/device/real-time/")
async def get_real_time_devices(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all devices with real-time stats for monitoring"""
    try:
        # Get all terminals
        terminals = db.query(IClockTerminal).all()
        
        devices = []
        for terminal in terminals:
            device_status = get_device_status(terminal.last_activity, getattr(terminal, "state", None))
            stats = get_real_time_device_stats(db, terminal.sn)
            
            device_data = {
                "id": terminal.id,
                "sn": terminal.sn,
                "alias": terminal.alias,
                "ip_address": terminal.ip_address,
                "device_type": getattr(terminal, 'device_type', 0),
                "zone_id": terminal.zone_id,
                "status": device_status,
                "last_activity": terminal.last_activity.isoformat() if terminal.last_activity else None,
                "user_count": terminal.user_count or 0,
                "fp_count": terminal.fp_count or 0,
                "face_count": terminal.face_count or 0,
                "fw_version": getattr(terminal, 'fw_ver', None),
                "platform": getattr(terminal, 'platform', None),
                "mac_address": getattr(terminal, 'mac_address', None),
                "oem_vendor": getattr(terminal, 'oem_vendor', None),
                "emergency_status": "off",
                "transactions_24h": stats['transactions_24h'],
                "last_punch": stats['last_punch'].isoformat() if stats['last_punch'] else None,
                "pending_commands": stats['pending_commands']
            }
            
            devices.append(device_data)
        
        return {
            "devices": devices,
            "total_count": len(devices),
            "online_count":  len([d for d in devices if d['status'].lower() == 'online']),
            "offline_count": len([d for d in devices if d['status'].lower() == 'offline']),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting real-time devices: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch real-time devices"
        )

# Firmware Management Endpoints

@router.post("/api/device/firmware/upload", response_model=FirmwareUploadResponse)
async def upload_firmware(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    device_types: Optional[str] = Query(None, description="Comma-separated device types"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Upload firmware file"""
    try:
        # Validate file
        if not file.filename or not file.filename.endswith('.bin'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only .bin firmware files are allowed"
            )
        
        # Create upload directory if not exists
        os.makedirs(FIRMWARE_UPLOAD_DIR, exist_ok=True)
        
        # Generate unique filename
        firmware_id = str(uuid.uuid4())
        filename = f"{firmware_id}_{file.filename}"
        file_path = os.path.join(FIRMWARE_UPLOAD_DIR, filename)
        
        # Save file
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # Parse device types
        device_type_list = []
        if device_types:
            device_type_list = [dt.strip() for dt in device_types.split(',')]
        
        # TODO: Store firmware metadata in database
        
        return FirmwareUploadResponse(
            firmware_id=firmware_id,
            filename=filename,
            file_size=len(content),
            upload_time=datetime.utcnow(),
            device_types=device_type_list
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading firmware: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload firmware"
        )

@router.post("/api/device/firmware/push")
async def push_firmware(
    push_request: FirmwarePushRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Push firmware to devices"""
    try:
        # Validate firmware exists (TODO: check database)
        firmware_path = os.path.join(FIRMWARE_UPLOAD_DIR, f"{push_request.firmware_id}_*.bin")
        
        # Validate devices exist
        valid_devices = []
        for sn in push_request.sn_list:
            try:
                validate_device_exists(db, sn)
                valid_devices.append(sn)
            except HTTPException:
                logger.warning(f"Device {sn} not found, skipping")
        
        if not valid_devices:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No valid devices found"
            )
        
        # Queue firmware update commands
        command_ids = []
        for sn in valid_devices:
            cmd_id = queue_command(db, sn, f"FIRMWARE UPDATE {push_request.firmware_id}", current_user.id)
            command_ids.append(cmd_id)
        
        return {
            "firmware_id": push_request.firmware_id,
            "devices_queued": len(valid_devices),
            "valid_devices": valid_devices,
            "command_ids": command_ids,
            "message": f"Firmware update queued for {len(valid_devices)} devices"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error pushing firmware: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to push firmware"
        )

# Utility Endpoints

@router.get("/api/device/health")
async def device_health_check(db: Session = Depends(get_db)):
    """Check device module health"""
    try:
        # Get device counts
        total_devices = db.query(IClockTerminal).count()
        online_devices = db.execute(text("""
            SELECT COUNT(*) FROM iclock_terminal 
            WHERE last_activity >= :since
        """), {
            'since': datetime.utcnow() - timedelta(minutes=DEVICE_ONLINE_THRESHOLD_MINUTES)
        }).scalar()
        
        # Get command queue stats
        pending_commands = db.execute(text("""
            SELECT COUNT(*) FROM iclock_devcmd WHERE status = 0
        """)).scalar()
        
        return {
            "status": "healthy",
            "total_devices": total_devices,
            "online_devices": online_devices,
            "offline_devices": total_devices - online_devices,
            "pending_commands": pending_commands,
            "uptime_percentage": round((online_devices / total_devices * 100) if total_devices > 0 else 0, 2),
            "last_check": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


@router.get("/api/device/network-diagnostics")
async def device_network_diagnostics(
    current_user: User = Depends(get_current_user),
):
    """
    Self-check for "the server can't see our readers" deployment issues.

    Reports whether this backend is running in a container (whose own network
    interfaces are NOT the reader LAN), what DEVICE_SCAN_SUBNETS is set to,
    and live TCP reachability to every registered device's IP:port. Run this
    on-site before declaring a deployment broken — it surfaces exactly which
    layer (auto-discovery config vs. actual network reachability) is failing.
    """
    from ..services.zkteco.device_heartbeat import get_network_diagnostics, _tcp_reachable

    diag = get_network_diagnostics()

    # Live TCP reachability probes, run concurrently
    from ..core.database import SessionLocal
    db = SessionLocal()
    try:
        devices = db.query(Device).filter(Device.ip_address.isnot(None)).all()
        targets = [(d, d.ip_address, d.port or 4370) for d in devices]
    finally:
        db.close()

    import asyncio as _asyncio

    async def _probe(d, ip, port):
        ok = await _tcp_reachable(ip, port)
        result = {
            "id": d.id, "name": d.name, "serial_number": d.serial_number,
            "ip_address": ip, "port": port, "connection_mode": d.connection_mode,
            "db_status": d.status.value if d.status else None,
            "live_reachable": ok,
        }
        # For direct/both devices, TCP-reachable-but-offline means the heartbeat/
        # poller is broken (code-level bug — investigate immediately). For ADMS
        # devices, the heartbeat never TCP-probes them at all; "online" only
        # comes from the device actively pushing to /iclock/cdata. A reachable-
        # but-offline ADMS device almost always means the reader is powered on
        # and on the network, but its configured ADMS server address/port
        # (set on the reader itself, e.g. via its menu or web UI) is wrong, or
        # a firewall is blocking its outbound push to this server's port 80.
        if ok and result["db_status"] == "offline":
            if d.connection_mode in ("direct", "both"):
                result["likely_cause"] = (
                    "Device answers on its port but the heartbeat/poller isn't marking it "
                    "online — check backend logs for heartbeat/poller errors for this device."
                )
            else:
                result["likely_cause"] = (
                    "Device is powered on and reachable, but isn't pushing ADMS data. "
                    "Check the reader's configured ADMS server address/port points to "
                    "this server, and that nothing blocks its outbound HTTP to port 80."
                )
        return result

    results = await _asyncio.gather(*[_probe(d, ip, port) for d, ip, port in targets]) if targets else []

    unreachable = [r for r in results if not r["live_reachable"]]
    flapping = [r for r in results if r["live_reachable"] and r["db_status"] == "offline"]

    return {
        "containerized": diag["containerized"],
        "local_interface_subnets": diag["local_interface_subnets"],
        "device_scan_subnets_env": diag["device_scan_subnets_env"],
        "effective_scan_subnets": diag["effective_scan_subnets"],
        "discovery_warning": diag["warning"],
        "devices_checked": len(results),
        "devices_unreachable_now": unreachable,
        "devices_reachable_but_marked_offline": flapping,
        "all_devices": results,
        "checked_at": datetime.utcnow().isoformat(),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# LIVE TRANSACTION FEED
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/api/device/transactions/live/")
async def get_live_transactions(
    limit: int = Query(50, ge=1, le=200),
    terminal_sn: Optional[str] = Query(None),
    emp_code: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Recent punch transactions — the live feed shown in the Real-time Monitor."""
    try:
        where = "WHERE 1=1"
        params: dict = {"limit": limit}
        if terminal_sn:
            where += " AND t.terminal_sn = :sn"
            params["sn"] = terminal_sn
        if emp_code:
            where += " AND t.emp_code = :emp_code"
            params["emp_code"] = emp_code

        rows = db.execute(text(f"""
            SELECT
                t.id, t.emp_code, t.punch_time, t.punch_state, t.verify_type,
                t.terminal_sn, t.area_alias,
                COALESCE(e.first_name || ' ' || e.last_name, t.emp_code) AS emp_name,
                d.alias AS device_alias
            FROM iclock_transaction t
            LEFT JOIN personnel_employee e ON e.emp_code = t.emp_code
            LEFT JOIN iclock_terminal d ON d.sn = t.terminal_sn
            {where}
            ORDER BY t.punch_time DESC
            LIMIT :limit
        """), params).fetchall()

        PUNCH_STATE = {0: "Check-In", 1: "Check-Out", 2: "Break-Out", 3: "Break-In", 4: "OT-In", 5: "OT-Out"}
        VERIFY_TYPE = {0: "Password", 1: "Fingerprint", 2: "Face", 3: "Card", 15: "Multi"}

        return {"success": True, "data": [
            {
                "id": r[0],
                "emp_code": r[1],
                "punch_time": r[2].isoformat() if r[2] else None,
                "punch_state": r[3],
                "punch_state_label": PUNCH_STATE.get(r[3], "Unknown"),
                "verify_type": r[4],
                "verify_type_label": VERIFY_TYPE.get(r[4], "Unknown"),
                "terminal_sn": r[5],
                "area_alias": r[6],
                "emp_name": r[7],
                "device_alias": r[8] or r[5],
            }
            for r in rows
        ]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# DEVICE SCHEDULES
# ═══════════════════════════════════════════════════════════════════════════════

class ScheduleCreate(BaseModel):
    terminal_sn: str
    name: str
    description: Optional[str] = None
    monday_enabled: bool = True
    tuesday_enabled: bool = True
    wednesday_enabled: bool = True
    thursday_enabled: bool = True
    friday_enabled: bool = True
    saturday_enabled: bool = False
    sunday_enabled: bool = False
    time_ranges: Optional[List[Dict[str, Any]]] = None
    access_mode: str = "NORMAL"
    is_active: bool = True
    priority: int = 1

class ScheduleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    monday_enabled: Optional[bool] = None
    tuesday_enabled: Optional[bool] = None
    wednesday_enabled: Optional[bool] = None
    thursday_enabled: Optional[bool] = None
    friday_enabled: Optional[bool] = None
    saturday_enabled: Optional[bool] = None
    sunday_enabled: Optional[bool] = None
    time_ranges: Optional[List[Dict[str, Any]]] = None
    access_mode: Optional[str] = None
    is_active: Optional[bool] = None
    priority: Optional[int] = None


@router.get("/api/device/schedules/")
async def list_schedules(
    terminal_sn: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        q = db.query(DeviceSchedule)
        if terminal_sn:
            q = q.filter(DeviceSchedule.device_id == terminal_sn)
        rows = q.order_by(DeviceSchedule.priority.desc(), DeviceSchedule.name).all()
        return {"success": True, "data": [
            {
                "id": r.id, "terminal_sn": r.device_id, "name": r.name,
                "description": r.description,
                "monday_enabled": r.monday_enabled, "tuesday_enabled": r.tuesday_enabled,
                "wednesday_enabled": r.wednesday_enabled, "thursday_enabled": r.thursday_enabled,
                "friday_enabled": r.friday_enabled, "saturday_enabled": r.saturday_enabled,
                "sunday_enabled": r.sunday_enabled,
                "time_ranges": r.time_ranges or [],
                "access_mode": r.access_mode, "is_active": r.is_active, "priority": r.priority,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/device/schedules")
async def create_schedule(
    payload: ScheduleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        sched = DeviceSchedule(
            device_id=payload.terminal_sn,
            name=payload.name, description=payload.description,
            monday_enabled=payload.monday_enabled, tuesday_enabled=payload.tuesday_enabled,
            wednesday_enabled=payload.wednesday_enabled, thursday_enabled=payload.thursday_enabled,
            friday_enabled=payload.friday_enabled, saturday_enabled=payload.saturday_enabled,
            sunday_enabled=payload.sunday_enabled,
            time_ranges=payload.time_ranges or [],
            access_mode=payload.access_mode,
            is_active=payload.is_active, priority=payload.priority,
        )
        db.add(sched)
        db.commit()
        db.refresh(sched)

        # Push schedule to device as SET OPTION
        days = ",".join([d for d, f in [
            ("MON", payload.monday_enabled), ("TUE", payload.tuesday_enabled),
            ("WED", payload.wednesday_enabled), ("THU", payload.thursday_enabled),
            ("FRI", payload.friday_enabled), ("SAT", payload.saturday_enabled),
            ("SUN", payload.sunday_enabled),
        ] if f])
        queue_command(db, payload.terminal_sn,
                      f"SET OPTION SCHEDULE={sched.id} NAME={payload.name} DAYS={days} MODE={payload.access_mode}",
                      current_user.id)

        return {"success": True, "data": {"id": sched.id, "name": sched.name}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/api/device/schedules/{sched_id}")
async def update_schedule(
    sched_id: int,
    payload: ScheduleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    sched = db.query(DeviceSchedule).filter(DeviceSchedule.id == sched_id).first()
    if not sched:
        raise HTTPException(status_code=404, detail="Schedule not found")
    for k, v in payload.dict(exclude_none=True).items():
        setattr(sched, k, v)
    db.commit()
    return {"success": True}


@router.delete("/api/device/schedules/{sched_id}")
async def delete_schedule(
    sched_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from sqlalchemy import text as _text
    count = db.execute(_text("DELETE FROM device_schedules WHERE id = :id"), {"id": sched_id}).rowcount
    db.commit()
    if count == 0:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return {"success": True}


# ═══════════════════════════════════════════════════════════════════════════════
# MAINTENANCE TRACKING
# ═══════════════════════════════════════════════════════════════════════════════

class MaintenanceCreate(BaseModel):
    terminal_sn: str
    maintenance_type: str  # ROUTINE, REPAIR, CALIBRATION, CLEANING
    description: Optional[str] = None
    scheduled_date: str   # ISO format
    estimated_duration: Optional[int] = None
    technician_notes: Optional[str] = None
    parts_used: Optional[List[Dict[str, Any]]] = None
    cost: Optional[int] = None

class MaintenanceUpdate(BaseModel):
    maintenance_type: Optional[str] = None
    description: Optional[str] = None
    scheduled_date: Optional[str] = None
    estimated_duration: Optional[int] = None
    status: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    actual_duration: Optional[int] = None
    technician_notes: Optional[str] = None
    parts_used: Optional[List[Dict[str, Any]]] = None
    cost: Optional[int] = None
    test_results: Optional[Dict[str, Any]] = None
    next_maintenance_date: Optional[str] = None


@router.get("/api/device/maintenance/")
async def list_maintenance(
    terminal_sn: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        q = db.query(DeviceMaintenance)
        if terminal_sn:
            q = q.filter(DeviceMaintenance.device_id == terminal_sn)
        if status:
            q = q.filter(DeviceMaintenance.status == status.upper())
        rows = q.order_by(DeviceMaintenance.scheduled_date.desc()).all()

        alias_map = {t.sn: (t.alias or t.sn) for t in db.query(IClockTerminal).all()}

        return {"success": True, "data": [
            {
                "id": r.id, "terminal_sn": r.device_id,
                "device_alias": alias_map.get(r.device_id, r.device_id),
                "maintenance_type": r.maintenance_type, "description": r.description,
                "scheduled_date": r.scheduled_date.isoformat() if r.scheduled_date else None,
                "estimated_duration": r.estimated_duration,
                "status": r.status,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                "actual_duration": r.actual_duration,
                "technician_notes": r.technician_notes,
                "parts_used": r.parts_used or [],
                "cost": r.cost,
                "test_results": r.test_results or {},
                "next_maintenance_date": r.next_maintenance_date.isoformat() if r.next_maintenance_date else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _parse_dt(s: Optional[str]):
    """Parse ISO datetime string, tolerating the Z suffix Python <3.11 rejects."""
    if not s:
        return None
    from datetime import datetime as dt
    return dt.fromisoformat(s.replace("Z", "+00:00"))


@router.post("/api/device/maintenance")
async def create_maintenance(
    payload: MaintenanceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        maint = DeviceMaintenance(
            device_id=payload.terminal_sn,
            maintenance_type=payload.maintenance_type,
            description=payload.description,
            scheduled_date=_parse_dt(payload.scheduled_date),
            estimated_duration=payload.estimated_duration,
            status="SCHEDULED",
            performed_by=current_user.id,
            technician_notes=payload.technician_notes,
            parts_used=payload.parts_used or [],
            cost=payload.cost,
        )
        db.add(maint)
        db.commit()
        db.refresh(maint)
        return {"success": True, "data": {"id": maint.id}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/api/device/maintenance/{maint_id}")
async def update_maintenance(
    maint_id: int,
    payload: MaintenanceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    maint = db.query(DeviceMaintenance).filter(DeviceMaintenance.id == maint_id).first()
    if not maint:
        raise HTTPException(status_code=404, detail="Record not found")

    data = payload.dict(exclude_none=True)
    for date_field in ["scheduled_date", "started_at", "completed_at", "next_maintenance_date"]:
        if date_field in data and data[date_field]:
            data[date_field] = _parse_dt(data[date_field])
    for k, v in data.items():
        setattr(maint, k, v)
    db.commit()
    return {"success": True}


@router.delete("/api/device/maintenance/{maint_id}")
async def delete_maintenance(
    maint_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from sqlalchemy import text as _text
    count = db.execute(_text("DELETE FROM device_maintenance WHERE id = :id"), {"id": maint_id}).rowcount
    db.commit()
    if count == 0:
        raise HTTPException(status_code=404, detail="Record not found")
    return {"success": True}


# ═══════════════════════════════════════════════════════════════════════════════
# EXTENDED COMMANDS  (OPEN DOOR / SET ACCESS / SET OPTION / BIODATA SYNC)
# ═══════════════════════════════════════════════════════════════════════════════

class ExtendedCommandRequest(BaseModel):
    sn: str
    command_type: str  # OPEN_DOOR | SET_ACCESS | SET_OPTION | BIODATA | ENROLL | LOCK | UNLOCK
    params: Dict[str, Any] = {}


@router.post("/api/device/devcmd/extended")
async def send_extended_command(
    payload: ExtendedCommandRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Extended command dispatcher — maps high-level command types to
    the actual ADMS command strings queued for the device.
    """
    try:
        terminal = db.execute(
            text("SELECT id, sn, alias FROM iclock_terminal WHERE sn = :sn"),
            {"sn": payload.sn}
        ).fetchone()
        if not terminal:
            raise HTTPException(status_code=404, detail="Device not found")

        p = payload.params or {}
        ct = payload.command_type
        info = classify_control_plane(payload.sn, db)

        if info["plane"] == PLANE_CONTROLLER:
            raise HTTPException(
                status_code=400,
                detail=("InBio/C3 access controller — POB's controller (C3/PULL) driver "
                        "isn't available yet, so this command can't be sent from here."))

        # Correct ADMS (PUSH-protocol) wire strings. None ⇒ no ADMS equivalent.
        adms_cmd = {
            "OPEN_DOOR":   f"CONTROL DEVICE 01 01 {p.get('door_id', 1)} {p.get('hold_seconds', 5)} 0",
            "LOCK":        "DISABLE",
            "UNLOCK":      "ENABLE",
            "DISABLE":     "DISABLE",
            "ENABLE":      "ENABLE",
            "DELETE_USER": f"DATA DELETE USERINFO PIN={p.get('emp_code', '')}",
            "SET_ACCESS":  f"DATA UPDATE USERINFO PIN={p.get('emp_code', '')}\tGrp={p.get('acc_level_id', 1)}\tPri={p.get('privilege', 0)}",
            "ENROLL":      f"ENROLL_FP PIN={p.get('emp_code', '')}\tFID={p.get('finger_id', 0)}\tRETRY=3\tOVERWRITE=1",
            "BLACKLIST":   f"DATA UPDATE USERINFO PIN={p.get('emp_code', '')}\tPri=0\tGrp=0",
        }.get(ct)

        # ── DIRECT plane → run immediately via ZKLib ──────────────────────────
        if info["plane"] == PLANE_DIRECT:
            device = db.query(Device).filter(Device.serial_number == payload.sn).first()
            if ct == "OPEN_DOOR":
                result = await _execute_direct_command(device, "OPEN DOOR")
            elif ct in ("DISABLE", "LOCK"):
                result = await _execute_direct_command(device, "DISABLE")
            elif ct in ("ENABLE", "UNLOCK"):
                result = await _execute_direct_command(device, "ENABLE")
            elif ct == "DELETE_USER":
                result = await _direct_delete_user(device, p.get("emp_code", ""))
            else:
                raise HTTPException(
                    status_code=400,
                    detail=(f"'{ct}' can't run on a direct (ZKLib) reader from here. "
                            "Use the Enrollment tab for biometric/access changes, or set "
                            "the reader to ADMS mode."))
            if not result.get("success"):
                raise HTTPException(status_code=502, detail=result.get("error", "Command failed on device"))
            db.execute(text("""
                INSERT INTO iclock_devcmd (sn, cmd_content, cmd_commit_time, cmd_trans_time, cmd_return_time, status)
                VALUES (:sn, :cmd, :now, :now, :now, 2)
            """), {"sn": payload.sn, "cmd": f"{ct} (direct)", "now": datetime.utcnow()})
            db.commit()
            return {"success": True, "data": {
                "sn": payload.sn, "command_type": ct, "status": "executed", "method": "direct"}}

        # ── ADMS plane → queue for the next poll ──────────────────────────────
        if not adms_cmd:
            raise HTTPException(
                status_code=400,
                detail=f"'{ct}' has no ADMS equivalent — it only works on a direct (ZKLib) reader.")
        cmd_id = queue_command(db, payload.sn, adms_cmd, current_user.id)
        return {"success": True, "data": {
            "command_id": cmd_id,
            "sn": payload.sn,
            "command_type": ct,
            "cmd_string": adms_cmd,
            "status": "pending",
            "method": "adms",
        }}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── ADMS Server Configuration ─────────────────────────────────────────────────

_ADMS_PARAM_URL  = 'adms.server_url'
_ADMS_PARAM_AUTO = 'adms.auto_register'


def _get_param(db: Session, key: str) -> Optional[str]:
    row = db.execute(
        text("SELECT param_value FROM sys_parameters WHERE param_key = :k"),
        {"k": key},
    ).fetchone()
    return row.param_value if row else None


def _set_param(db: Session, key: str, value: str, description: str = "") -> None:
    db.execute(text("""
        INSERT INTO sys_parameters (param_key, param_value, module, description, updated_at)
        VALUES (:k, :v, 'device', :d, NOW())
        ON CONFLICT (param_key) DO UPDATE
            SET param_value = :v, updated_at = NOW()
    """), {"k": key, "v": value, "d": description})
    db.commit()


@router.get("/api/device/adms-config")
async def get_adms_config(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Return the ADMS server URL that readers should be configured with."""
    server_url   = _get_param(db, _ADMS_PARAM_URL)
    auto_register = _get_param(db, _ADMS_PARAM_AUTO)
    return {
        "success": True,
        "data": {
            "server_url":    server_url or "",
            "auto_register": auto_register != "false",
            "endpoints": {
                "cdata":      "/iclock/cdata",
                "getrequest": "/iclock/getrequest",
                "devicecmd":  "/iclock/devicecmd",
            },
        },
    }


@router.put("/api/device/adms-config")
async def update_adms_config(
    body: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Save the ADMS server URL and auto-register toggle."""
    if "server_url" in body:
        url = (body["server_url"] or "").strip()
        _set_param(db, _ADMS_PARAM_URL, url, "URL readers use to reach this ADMS server")
    if "auto_register" in body:
        _set_param(db, _ADMS_PARAM_AUTO, "true" if body["auto_register"] else "false",
                   "Auto-register unknown devices on first heartbeat")
    return {"success": True, "message": "ADMS config saved"}
