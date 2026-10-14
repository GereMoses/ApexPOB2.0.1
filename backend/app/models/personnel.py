from sqlalchemy import Column, Integer, BigInteger, String, Boolean, DateTime, Text, ForeignKey, Enum, JSON, Float, TIMESTAMP, Date
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from ..core.database import Base
import enum
import uuid


class PersonnelStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ON_LEAVE = "on_leave"
    TRANSIT = "transit"
    OFFSHORE = "offshore"
    ONSHORE = "onshore"


class Personnel(Base):
    __tablename__ = "personnel"

    id = Column(Integer, primary_key=True, index=True)
    emp_code = Column(String(20), unique=True, index=True, nullable=False)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    badge_id    = Column(String(50), unique=True, index=True, nullable=True)
    # SeamlessHR Attendance ID = the PIN on the ZKTeco reader (text; keeps leading zeros).
    attendance_id = Column(String(20), unique=True, nullable=True)
    card_number = Column(BigInteger, nullable=True, index=True)  # physical RFID card number
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    full_name = Column(String(200), nullable=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=True)
    phone = Column(String(20), nullable=True)
    company = Column(String(255), nullable=True)
    department = Column(String(100), nullable=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)
    role = Column(String(100), nullable=True)
    position = Column(String(100), nullable=True)
    
    # Status and Zone
    status = Column(Enum(PersonnelStatus), default=PersonnelStatus.ACTIVE)
    current_zone_id = Column(Integer, ForeignKey("zones.id"), nullable=True, index=True)
    current_location = Column(String(100), nullable=True)  # Current location description
    is_onboard = Column(Boolean, default=False, server_default='false')
    
    # Oil & Gas Specific Fields
    personnel_type = Column(String(20), default="STAFF")  # STAFF, CONTRACTOR, VISITOR
    safety_critical = Column(Boolean, default=False, server_default='false')
    biometric_enrolled = Column(Boolean, default=False, server_default='false')
    compliance_score = Column(Float, default=0.0)
    
    # Photo
    photo_url = Column(String(500), nullable=True)
    
    # Biometric Data - PostgreSQL-specific JSONB for better performance
    biometric_data = Column(JSONB, nullable=True)
    fingerprint_templates = Column(JSONB, nullable=True)
    face_template = Column(String(255), nullable=True)
    
    # Certifications and Training
    certifications = Column(JSONB, nullable=True)
    training_records = Column(JSONB, nullable=True)
    medical_fitness_date = Column(TIMESTAMP(timezone=True), nullable=True)
    
    # Emergency Information
    emergency_contact = Column(JSONB, nullable=True)
    blood_group = Column(String(10), nullable=True)
    medical_conditions = Column(Text, nullable=True)
    
    # Timestamps - PostgreSQL-specific with strict typing
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())
    last_seen = Column(TIMESTAMP(timezone=True), nullable=True)
    
    # DB columns not yet mapped in the ORM — exist in the actual table
    hire_date = Column(Date, nullable=True)
    nationality = Column(String(100), nullable=True)
    id_number = Column(String(50), nullable=True)
    passport_number = Column(String(50), nullable=True)
    emergency_contact_name = Column(String(200), nullable=True)
    emergency_contact_phone = Column(String(20), nullable=True)
    is_pob = Column(Boolean, default=False, server_default='false')
    pob_location = Column(String(100), nullable=True)
    pob_since = Column(TIMESTAMP(timezone=True), nullable=True)
    employment_type = Column(String(30), default='EMPLOYEE', server_default="'EMPLOYEE'")
    is_active = Column(Boolean, default=True, server_default='true')

    # HR system-of-record marker. When set to 'SEAMLESSHR', this employee's MASTER
    # fields (name, email, company, department, role, employment/ID data) are owned by
    # SeamlessHR and are read-only in ApexPOB. Operational fields (badge, zone, POB
    # status, biometrics, emergency contacts) remain editable here.
    hr_source = Column(String(20), nullable=True, index=True)
    hr_synced_at = Column(TIMESTAMP(timezone=True), nullable=True)

    # On approved leave (synced from SeamlessHR). Excluded from muster "expected"
    # rosters so someone away on leave is never counted as MISSING in an emergency.
    on_leave = Column(Boolean, default=False, server_default='false', index=True)
    leave_end_date = Column(Date, nullable=True)

    # BioTime Enhanced Fields
    biotime_employee_id = Column(String(50), nullable=True, index=True)  # BioTime employee ID
    work_schedule = Column(JSON, nullable=True)  # BioTime work schedule
    access_groups = Column(JSON, nullable=True)  # BioTime access group assignments
    device_groups = Column(JSON, nullable=True)  # BioTime device group assignments
    biometric_quality_score = Column(Float, default=0.0)  # BioTime biometric quality metrics
    last_sync_timestamp = Column(DateTime(timezone=True), nullable=True)  # BioTime sync tracking
    timezone_preference = Column(String(50), default='UTC')  # Personnel timezone preference
    language_preference = Column(String(10), default='en')  # Personnel language preference
    
    # Role Management
    primary_role_id = Column(Integer, ForeignKey("roles.id"), nullable=True)
    
    # Enhanced Relationships
    user = relationship("User", back_populates="personnel")
    personnel_assignments = relationship("PersonnelAssignment", back_populates="personnel")
    transport_assignments = relationship("TransportAssignment", back_populates="personnel")
    current_zone = relationship("Zone", foreign_keys=[current_zone_id])
    zone_assignments = relationship("ZonePersonnelAssignment", back_populates="personnel")
    # role_assignments = relationship("RoleAssignment", back_populates="personnel", foreign_keys="RoleAssignment.personnel_id")
    primary_role = relationship("Role", foreign_keys=[primary_role_id])
    
    # BioTime Enhanced Relationships
    # biometric_templates loaded lazily to avoid import-order issues
    biometric_templates = relationship("BiometricTemplate", back_populates="personnel")
    resignations = relationship("Resignation", back_populates="personnel")
    # access_schedules = relationship("BioTimeAccessSchedule", back_populates="personnel")  # Temporarily disabled due to JSON relationship
    # biotime_sync_logs = relationship("BioTimeSyncLog", foreign_keys=["personnel_id"])  # Temporarily disabled due to class rename
    # biotime_conflicts = relationship("BioTimeConflictResolution", foreign_keys=["personnel_id"])  # Temporarily disabled due to class rename


class PersonnelAssignment(Base):
    __tablename__ = "personnel_assignments"

    id = Column(Integer, primary_key=True, index=True)
    personnel_id = Column(Integer, ForeignKey("personnel.id"), nullable=False)
    location = Column(String(255), nullable=False)  # Changed from zone_id to location
    zone = Column(String(100), nullable=True)  # Changed from zone_id to zone (varchar)
    vessel = Column(String(100), nullable=True)
    platform = Column(String(100), nullable=True)
    
    # Assignment Details
    assignment_type = Column(String(50), nullable=False)  # offshore, onshore, transit
    start_date = Column(TIMESTAMP(timezone=True), nullable=False)
    end_date = Column(TIMESTAMP(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True, server_default='true')
    
    # Transportation
    transport_method = Column(String(50), nullable=True)  # helicopter, vessel, vehicle
    transport_details = Column(JSONB, nullable=True)
    
    # Notes
    notes = Column(Text, nullable=True)
    
    # Relationships
    personnel = relationship("Personnel", back_populates="personnel_assignments")
    # Removed zone relationship since zone is now a string, not a foreign key
    
    # Timestamps
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())
    
    

class AttendanceLog(Base):
    __tablename__ = "attendance_logs"

    id = Column(Integer, primary_key=True, index=True)
    personnel_id = Column(Integer, ForeignKey("personnel.id"), nullable=False)
    device_id = Column(String(50), nullable=True)
    
    # Attendance Details - ZKTeco ADMS specific format
    event_type = Column(String(20), nullable=False)  # check_in, check_out
    timestamp = Column(TIMESTAMP(timezone=True), nullable=False, index=True)  # ZKTeco ADMS format: YYYY-MM-DD HH:mm:ss
    
    # Biometric Verification
    verification_method = Column(String(50), nullable=True)  # fingerprint, face, card, pin
    verification_score = Column(Float, nullable=True)
    
        
    # Device Information
    device_type = Column(String(50), nullable=True)
    network_type = Column(String(20), nullable=True)  # lan, 4g, wifi
    
    # Raw Data - PostgreSQL JSONB for better performance with ZKTeco data
    raw_data = Column(JSONB, nullable=True)
    
    # Processing Status
    is_processed = Column(Boolean, default=False, server_default='false')
    processed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    
    # Timestamps
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    # user = relationship("User", back_populates="personnel")  # Temporarily commented out - no user_id column
    # attendance_logs = relationship("AttendanceLog", back_populates="personnel")  # Temporarily commented out
    # department_assignments = relationship("DepartmentPersonnel", back_populates="personnel")  # Temporarily commented out - no department_id column
    # pob_status = relationship("POBStatus", back_populates="personnel")
    # transport_assignments = relationship("TransportAssignment", back_populates="personnel")  # Removed - no foreign key in AttendanceLog


class TransportAssignment(Base):
    """Transport assignments (vessels, flights, vehicles)"""
    __tablename__ = "transport_assignments"

    id = Column(Integer, primary_key=True, index=True)
    personnel_id = Column(Integer, ForeignKey("personnel.id"), nullable=False)
    
    # Transport details
    transport_type = Column(String(50), nullable=False)  # VESSEL, FLIGHT, VEHICLE, HELICOPTER
    transport_name = Column(String(100), nullable=False)  # Vessel name, flight number
    transport_code = Column(String(20), nullable=True)  # Transport code
    
    # Route and schedule
    departure_location = Column(String(100), nullable=False)
    destination_location = Column(String(100), nullable=False)
    departure_time = Column(TIMESTAMP(timezone=True), nullable=False)
    arrival_time = Column(TIMESTAMP(timezone=True), nullable=True)
    return_time = Column(TIMESTAMP(timezone=True), nullable=True)
    
    # Assignment details
    seat_number = Column(String(10), nullable=True)
    cabin_number = Column(String(20), nullable=True)
    purpose = Column(String(100), nullable=True)  # Work, Emergency, Transfer, etc.
    
    # Status
    status = Column(String(20), default="SCHEDULED")  # SCHEDULED, IN_TRANSIT, ARRIVED, CANCELLED
    
    # Metadata
    booked_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    booked_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    notes = Column(Text, nullable=True)
    
    # Relationships
    personnel = relationship("Personnel", back_populates="transport_assignments")
