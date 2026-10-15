"""
BioTime 9.5 Compatible Models
These models align with ZKTeco BioTime 9.5 database schema
"""

from sqlalchemy import Column, Integer, String, DateTime, Date, Boolean, SmallInteger, ForeignKey, BigInteger, Text, Float, Time
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base

# Personnel Models (BioTime Standard)
class PersonnelEmployee(Base):
    __tablename__ = "personnel_employee"
    
    id = Column(Integer, primary_key=True, index=True)
    emp_code = Column(String(20), unique=True, nullable=False, index=True)
    first_name = Column(String(20))
    last_name = Column(String(25), nullable=False)
    dept_id = Column(Integer, ForeignKey("personnel_department.id"))
    area_id = Column(Integer, ForeignKey("personnel_area.id"))
    position_id = Column(Integer)
    hire_date = Column(Date)
    birthday = Column(Date)
    sex = Column(String(1))  # M, F, O
    photo = Column(String(255))
    card_no = Column(String(20))
    pwd = Column(String(20))
    status = Column(SmallInteger, default=0, index=True)  # 0=active, 1=inactive
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    @property
    def full_name(self) -> str:
        """There is no full_name column, but visitor host names, QR passes and host
        reminders/alerts all read one — every one of them raised AttributeError
        whenever a visitor had a host."""
        return f"{(self.first_name or '').strip()} {(self.last_name or '').strip()}".strip() or (self.emp_code or "")
    
    # Relationships
    department = relationship("PersonnelDepartment", back_populates="employees")
    area = relationship("PersonnelArea", back_populates="employees")
    # transactions relationship disabled — linked by emp_code string, no FK
    organized_meetings = relationship("MeetingBooking", foreign_keys="MeetingBooking.organizer_emp_id", back_populates="organizer")
    approved_meetings = relationship("MeetingBooking", foreign_keys="MeetingBooking.approval_by", back_populates="approver")
    meeting_attendances = relationship("MeetingAttendee", back_populates="employee")
    uploaded_meeting_minutes = relationship("MeetingMinutes", back_populates="uploader")
    assigned_meeting_actions = relationship("MeetingActionItem", foreign_keys="MeetingActionItem.assignee_emp_id", back_populates="assignee")
    created_meeting_actions = relationship("MeetingActionItem", foreign_keys="MeetingActionItem.created_by", back_populates="creator")

class PersonnelDepartment(Base):
    __tablename__ = "personnel_department"
    
    id = Column(Integer, primary_key=True, index=True)
    dept_code = Column(String(20))
    dept_name = Column(String(50), nullable=False)
    parent_id = Column(Integer, ForeignKey("personnel_department.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    employees = relationship("PersonnelEmployee", back_populates="department")
    parent = relationship("PersonnelDepartment", remote_side=[id])

class PersonnelArea(Base):
    __tablename__ = "personnel_area"
    
    id = Column(Integer, primary_key=True, index=True)
    area_code = Column(String(20))
    area_name = Column(String(50), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    employees = relationship("PersonnelEmployee", back_populates="area")
    terminals = relationship("IClockTerminal", back_populates="area")
    meeting_rooms = relationship("MeetingRoom", back_populates="area")

# Device Models (BioTime Standard)
class IClockTerminal(Base):
    __tablename__ = "iclock_terminal"

    id = Column(Integer, primary_key=True, index=True)
    sn = Column(String(20), unique=True, nullable=False, index=True)  # Serial Number
    alias = Column(String(50))  # Device Name
    ip_address = Column(String(45), index=True)
    area_id = Column(Integer, ForeignKey("personnel_area.id"))
    zone_id = Column(Integer, ForeignKey("zones.id"), nullable=True)  # POB zone assignment
    last_activity = Column(DateTime(timezone=True))
    # 0=pending approval, 1=approved/active, 2=rejected, 3=offline
    state = Column(SmallInteger, default=0, index=True)
    comm_key = Column(String(20), default="0")
    fw_ver = Column(String(20))  # Firmware Version
    device_name = Column(String(50), nullable=True)   # Human-readable device label
    device_model = Column(String(50), nullable=True)  # Hardware model (e.g. F18, H1)
    platform     = Column(String(30), nullable=True)   # Hardware platform (e.g. ZEM800)
    mac_address  = Column(String(17), nullable=True)   # MAC address (XX:XX:XX:XX:XX:XX)
    oem_vendor   = Column(String(50), nullable=True)   # OEM vendor name
    device_type = Column(SmallInteger, default=0)     # 0=Attendance,1=Access,2=Mustering,3=Emergency
    reader_purpose = Column(String(20), default='ATTENDANCE')  # ATTENDANCE | ACCESS_ENTRY | ACCESS_EXIT
    connection_mode = Column(String(10), nullable=False, default='adms')  # adms | direct | both
    is_auto_reg = Column(Boolean, default=False)      # Auto-registered via ADMS handshake
    pushver = Column(String(10), default="1.0")  # Last ADMS pushver seen from device
    # Capability counters (populated from ADMS options string)
    user_count  = Column(Integer, default=0)
    fp_count    = Column(Integer, default=0)
    face_count  = Column(Integer, default=0)
    palm_count  = Column(Integer, default=0)
    log_count   = Column(Integer, default=0)
    # Stamp watermarks — device only re-uploads records newer than these
    att_stamp   = Column(BigInteger, default=0)  # last attendance record Unix timestamp
    op_stamp    = Column(BigInteger, default=0)   # last operlog record Unix timestamp
    user_stamp  = Column(BigInteger, default=0)  # 0 = device must re-upload all users; >0 = already received
    # Per-device heartbeat interval in seconds (returned as Delay= in options block)
    heartbeat_interval = Column(Integer, default=30)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    area = relationship("PersonnelArea", back_populates="terminals")
    transactions = relationship("IClockTransaction", back_populates="terminal")
    doors = relationship("AccDoor", back_populates="terminal")
    meeting_attendances = relationship("MeetingAttendance", back_populates="device")

class IClockTransaction(Base):
    __tablename__ = "iclock_transaction"
    
    id = Column(BigInteger, primary_key=True, index=True)
    emp_code = Column(String(20), nullable=False, index=True)
    punch_time = Column(DateTime(timezone=True), nullable=False, index=True)
    punch_state = Column(SmallInteger)  # 0=check-in, 1=check-out, 2=break-out, 3=break-in
    verify_type = Column(SmallInteger)  # 0=password, 1=fingerprint, 2=face, 3=card
    work_code = Column(Integer)
    terminal_sn = Column(String(20), ForeignKey("iclock_terminal.sn"), index=True)
    area_alias = Column(String(50))
    upload_time = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Relationships
    # employee relationship disabled — linked by emp_code, no FK
    terminal = relationship("IClockTerminal", back_populates="transactions")

# Attendance Models (BioTime Standard)
class AttTimetable(Base):
    __tablename__ = "att_timetable"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    late_grace_minutes = Column(Integer, default=0)
    early_exit_minutes = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    shifts = relationship("AttShift", back_populates="timetable")

class AttShift(Base):
    __tablename__ = "att_shift"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False)
    timetable_id = Column(Integer, ForeignKey("att_timetable.id"))
    days_of_week = Column(String(20))  # comma-separated days: 1,2,3,4,5
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    timetable = relationship("AttTimetable", back_populates="shifts")
    schedules = relationship("AttSchedule", back_populates="shift")

class AttSchedule(Base):
    __tablename__ = "att_schedule"
    
    id = Column(Integer, primary_key=True, index=True)
    emp_code = Column(String(20), nullable=False)
    shift_id = Column(Integer, ForeignKey("att_shift.id"))
    start_date = Column(Date, nullable=False)
    end_date = Column(Date)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    shift = relationship("AttShift", back_populates="schedules")

class AttLeave(Base):
    __tablename__ = "att_leave"
    
    id = Column(Integer, primary_key=True, index=True)
    emp_code = Column(String(20), nullable=False)
    leave_type = Column(String(20), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    days_count = Column(Float, default=0)
    status = Column(SmallInteger, default=0)  # 0=pending, 1=approved, 2=rejected
    approved_by = Column(String(20))
    approved_time = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

# Access Control Models (BioTime Standard)
class AccLevel(Base):
    __tablename__ = "acc_level"
    __table_args__ = {'extend_existing': True}
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False)
    description = Column(Text)
    time_zone = Column(String(50), default="UTC")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    user_authorizations = relationship("AccUserAuthorize", back_populates="access_level")
    doors = relationship("AccDoor", back_populates="access_level")

class AccUserAuthorize(Base):
    __tablename__ = "acc_userauthorize"
    __table_args__ = {'extend_existing': True}
    
    id = Column(Integer, primary_key=True, index=True)
    emp_code = Column(String(20), nullable=False)
    acc_level_id = Column(Integer, ForeignKey("acc_level.id"))
    start_time = Column(Time)
    end_time = Column(Time)
    valid_days = Column(String(20))  # comma-separated days
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    access_level = relationship("AccLevel", back_populates="user_authorizations")

class AccDoor(Base):
    __tablename__ = "acc_door"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False)
    terminal_sn = Column(String(20), ForeignKey("iclock_terminal.sn"))  # legacy: standalone/T&A door
    controller_id = Column(Integer, ForeignKey("access_controllers.id"), nullable=True, index=True)  # C3/inBio panel
    port = Column(Integer, nullable=True)  # door_no / reader port on the controller
    acc_level_id = Column(Integer, ForeignKey("acc_level.id"))
    mustering_mode = Column(Boolean, default=False)
    emergency_action = Column(SmallInteger, default=0)  # 0=none, 1=lock, 2=unlock
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    terminal = relationship("IClockTerminal", back_populates="doors")
    access_level = relationship("AccLevel", back_populates="doors")
    meeting_room = relationship("MeetingRoom", back_populates="door", uselist=False)

# Authentication Models (BioTime Standard)
class AuthUser(Base):
    __tablename__ = "auth_user"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(150), unique=True, nullable=False, index=True)
    password = Column(String(128), nullable=False)
    email = Column(String(100))
    first_name = Column(String(50))
    last_name = Column(String(50))
    is_superuser = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True, index=True)
    last_login = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    operation_logs = relationship("BaseOperationLog", back_populates="user")

class AuthRole(Base):
    __tablename__ = "auth_role"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False)
    description = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class AuthPermission(Base):
    __tablename__ = "auth_permission"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    codename = Column(String(50), unique=True, nullable=False)
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class BaseOperationLog(Base):
    __tablename__ = "base_operationlog"
    
    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("auth_user.id"), index=True)
    action = Column(String(50), nullable=False, index=True)
    table_name = Column(String(50))
    record_id = Column(Integer)
    old_values = Column(Text)
    new_values = Column(Text)
    ip_address = Column(String(45))
    user_agent = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Relationships
    user = relationship("AuthUser", back_populates="operation_logs")

# Extension Models (POB v2.0 Specific)

# Mustering Models
class MusteringExpected(Base):
    """Expected personnel for mustering events"""
    __tablename__ = "mustering_expected"
    
    id = Column(BigInteger, primary_key=True, index=True)
    event_id = Column(BigInteger, ForeignKey("mustering_event.id"), nullable=False, index=True)
    emp_code = Column(String(50), nullable=False, index=True)
    emp_name = Column(String(100), nullable=False)
    dept_id = Column(Integer, ForeignKey("personnel_department.id"), nullable=True)
    shift_id = Column(Integer, ForeignKey("att_shift.id"), nullable=True)
    last_punch_time = Column(DateTime(timezone=True), nullable=True)
    last_punch_area = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    event = relationship("MusteringEvent")
    department = relationship("PersonnelDepartment")
    shift = relationship("AttShift")


class MusteringEvent(Base):
    __tablename__ = "mustering_event"
    
    id = Column(BigInteger, primary_key=True, index=True)
    zone_id = Column(Integer, ForeignKey("zones.id"), nullable=True, index=True)
    zone_ids = Column(JSONB, default=list)  # list of AFFECTED/source zone IDs (who is expected)
    muster_zone_id = Column(Integer, ForeignKey("zones.id"), nullable=True, index=True)  # PRIMARY assembly point (= muster_zone_ids[0]); anchor for manual-mark attribution
    muster_zone_ids = Column(JSONB, default=list)  # all target assembly points (MUSTER_POINT zones) — personnel report to whichever is nearest
    event_type = Column(SmallInteger, nullable=False)  # 0=drill, 1=emergency, 2=lockdown
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True))
    status = Column(SmallInteger, default=0, index=True)  # 0=active, 1=completed, 2=cancelled
    initiated_by = Column(Integer, ForeignKey("auth_user.id"))
    description = Column(Text)
    notes = Column(Text, nullable=True)
    total_expected = Column(Integer, default=0)
    total_safe = Column(Integer, default=0)
    total_missing = Column(Integer, default=0)
    total_injured = Column(Integer, default=0)
    # 0 = no auto-end; >0 = auto-end after this many minutes (safety net for forgotten drills)
    max_duration_minutes = Column(Integer, default=0, nullable=False, server_default="0")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    zone = relationship("Zone", foreign_keys=[zone_id])
    muster_zone = relationship("Zone", foreign_keys=[muster_zone_id])
    logs = relationship("MusteringLog", back_populates="event")

class MusteringLog(Base):
    __tablename__ = "mustering_log"
    
    id = Column(BigInteger, primary_key=True, index=True)
    event_id = Column(BigInteger, ForeignKey("mustering_event.id"), nullable=False, index=True)
    emp_code = Column(String(20), nullable=False, index=True)
    emp_name = Column(String(100), nullable=True)
    dept_name = Column(String(50), nullable=True)
    check_time = Column(DateTime(timezone=True), nullable=False)
    device_sn = Column(String(20), ForeignKey("iclock_terminal.sn"), nullable=True)
    device_alias = Column(String(50), nullable=True)
    status = Column(SmallInteger, default=0)  # 0=missing, 1=safe, 2=injured
    last_punch_area = Column(String(20), nullable=True)
    location = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    # Mobile muster check-in (a marshal accounting for someone by hand at the
    # assembly point). mustering_mobile.py has always written these two, but they
    # were never declared or created, so every mobile check-in failed with
    # "'gps' is an invalid keyword argument for MusteringLog".
    gps = Column(String(50), nullable=True)      # "lat,lon" captured by the device
    photo = Column(Text, nullable=True)          # base64 proof-of-presence image
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    event = relationship("MusteringEvent", back_populates="logs")


class MusteringDrillSchedule(Base):
    __tablename__ = "mustering_drill_schedule"

    id             = Column(Integer, primary_key=True, index=True)
    zone_id        = Column(Integer, ForeignKey("zones.id"), nullable=False)
    event_type     = Column(SmallInteger, default=1)
    scheduled_time = Column(DateTime(timezone=True), nullable=False)
    participant_type = Column(SmallInteger, default=0)  # 0=all, 1=dept, 2=shift
    participant_id = Column(Integer, nullable=True)
    template_id    = Column(Integer, nullable=True)
    auto_start     = Column(Boolean, default=True)
    created_by     = Column(Integer, nullable=True)
    created_at     = Column(DateTime(timezone=True), server_default=func.now())
    processed      = Column(Boolean, default=False)
    processed_time = Column(DateTime(timezone=True), nullable=True)
    status         = Column(String(20), default='PENDING')

    zone = relationship("Zone", foreign_keys=[zone_id])


class MusteringEventTemplate(Base):
    __tablename__ = "mustering_template"

    id            = Column(Integer, primary_key=True, index=True)
    template_name = Column(String(100), nullable=False)
    event_type    = Column(SmallInteger, nullable=True)
    notify_sms    = Column(Boolean, default=False)
    notify_email  = Column(Boolean, default=False)
    notify_users  = Column(Text, nullable=True)
    actions       = Column(Text, nullable=True)  # JSON stored as text
    created_at    = Column(DateTime(timezone=True), server_default=func.now())
    updated_at    = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# Onboarding Models
class OnboardingTaskBioTime(Base):
    __tablename__ = "onboarding_task"
    
    id = Column(Integer, primary_key=True, index=True)
    emp_id = Column(Integer, ForeignKey("personnel_employee.id"), nullable=False)
    task_name = Column(String(100), nullable=False)
    doc_path = Column(String(255))
    status = Column(SmallInteger, default=0)  # 0=pending, 1=in_progress, 2=completed, 3=rejected
    due_date = Column(Date)
    approved_by = Column(Integer, ForeignKey("auth_user.id"))
    approved_time = Column(DateTime(timezone=True))
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

# Emergency Device Models
class EmergencyDevice(Base):
    __tablename__ = "emergency_device"

    id = Column(Integer, primary_key=True, index=True)
    terminal_sn = Column(String(20), ForeignKey("iclock_terminal.sn"))
    device_type = Column(SmallInteger, default=0)  # 0=reader, 1=siren, 2=strobe, 3=alarm
    zone_id = Column(Integer, ForeignKey("zones.id"))
    status = Column(SmallInteger, default=0)  # 0=inactive, 1=active, 2=error
    last_heartbeat = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class IClockDevcmd(Base):
    """Device command queue — mirrors BioTime iclock_devcmd table"""
    __tablename__ = "iclock_devcmd"

    id = Column(BigInteger, primary_key=True, index=True)
    sn = Column(String(20), ForeignKey("iclock_terminal.sn"), nullable=False, index=True)
    cmd_content = Column(Text, nullable=False)
    # status: 0=pending, 1=transmitted, 2=success, 3=failed
    status = Column(SmallInteger, default=0, index=True)
    cmd_commit_time = Column(DateTime(timezone=True), server_default=func.now())
    cmd_trans_time = Column(DateTime(timezone=True), nullable=True)
    cmd_return_time = Column(DateTime(timezone=True), nullable=True)
    cmd_return = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("auth_user.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ZonePersonnelTracking(Base):
    """Tracks personnel movements through zones via ADMS punch events"""
    __tablename__ = "zone_personnel_tracking"

    id = Column(BigInteger, primary_key=True, index=True)
    zone_id = Column(Integer, nullable=False, index=True)
    emp_code = Column(String(20), nullable=False, index=True)
    device_sn = Column(String(20), nullable=True)
    # CLOCK_IN = entry, CLOCK_OUT = exit
    event_type = Column(String(20), nullable=False)
    punch_time = Column(DateTime(timezone=True), nullable=False, index=True)
    previous_zone_id = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class IClockOperLog(Base):
    """OPERLOG records pushed by ZKTeco devices — door events, alarms, tamper, anti-passback"""
    __tablename__ = "iclock_operlog"

    id = Column(BigInteger, primary_key=True, index=True)
    terminal_sn = Column(String(20), ForeignKey("iclock_terminal.sn"), nullable=False, index=True)
    # ZKTeco OPERLOG event codes: 0=door_normal, 1=alarm, 2=tamper, 3=anti_passback,
    # 4=duress, 5=fire_unlock, 6=emergency_lock, 9=door_open_too_long, 200=admin_op
    oper_event   = Column(SmallInteger, nullable=False, index=True)
    event_time   = Column(DateTime(timezone=True), nullable=False, index=True)
    admin_id     = Column(String(20), nullable=True)   # employee who triggered (if any)
    door_id      = Column(Integer, nullable=True)
    object_name  = Column(String(100), nullable=True)  # door name, user name, etc.
    param1       = Column(String(100), nullable=True)
    param2       = Column(String(100), nullable=True)
    raw_data     = Column(Text, nullable=True)          # full raw tab-delimited line
    created_at   = Column(DateTime(timezone=True), server_default=func.now())


class MusteringSearchSweep(Base):
    """Search sweeps recorded for missing persons during active mustering events"""
    __tablename__ = "mustering_search_sweep"

    id = Column(BigInteger, primary_key=True, index=True)
    event_id = Column(BigInteger, ForeignKey("mustering_event.id"), nullable=False, index=True)
    emp_code = Column(String(20), nullable=False, index=True)
    area_searched = Column(String(200), nullable=False)
    # NOT_FOUND | FOUND_SAFE | FOUND_INJURED
    result = Column(String(20), nullable=False, default='NOT_FOUND')
    searcher_id = Column(Integer, ForeignKey("auth_user.id"), nullable=True)
    searcher_name = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    sweep_time = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    event = relationship("MusteringEvent")


class MusteringEscalationRecord(Base):
    """Tracks which escalation-level notifications have been sent per person per event"""
    __tablename__ = "mustering_escalation_record"

    id = Column(BigInteger, primary_key=True, index=True)
    event_id = Column(BigInteger, ForeignKey("mustering_event.id"), nullable=False, index=True)
    emp_code = Column(String(20), nullable=False, index=True)
    # 1 = 10-min ALERT, 2 = 20-min SEARCH ORDERED, 3 = 30-min CRITICAL
    level = Column(SmallInteger, nullable=False)
    notification_type = Column(String(20), default='ALERT')
    notified_at = Column(DateTime(timezone=True), server_default=func.now())

    event = relationship("MusteringEvent")


class IClockBioTemplate(Base):
    """Biometric templates (fingerprint/face) uploaded by ZKTeco devices via ADMS"""
    __tablename__ = "iclock_bio_template"

    id = Column(BigInteger, primary_key=True, index=True)
    emp_code     = Column(String(20), nullable=False, index=True)
    # finger_id: 0-9 = finger index, -1 = face template
    finger_id    = Column(SmallInteger, nullable=False, default=0)
    template_size= Column(Integer, nullable=True)
    valid        = Column(Boolean, default=True)
    # template_data stored as hex/base64 string from device
    template_data= Column(Text, nullable=True)
    source_sn    = Column(String(20), ForeignKey("iclock_terminal.sn"), nullable=True)
    created_at   = Column(DateTime(timezone=True), server_default=func.now())
    updated_at   = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
