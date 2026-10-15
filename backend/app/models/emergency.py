"""
Emergency Management Models - POB v2.0 Extension
Complete emergency system with lockdown, fire mode, notifications, and audit trails
"""

from sqlalchemy import Column, Integer, String, DateTime, Date, Boolean, SmallInteger, ForeignKey, BigInteger, Text, Float, Time, ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB
from app.core.database import Base
import enum

class EmergencyEventType(enum.Enum):
    LOCKDOWN = 0
    FIRE = 1
    GAS = 2
    INTRUDER = 3
    MEDICAL = 4
    ALL_CLEAR = 5

class EmergencyStatus(enum.Enum):
    ACTIVE = 0
    RESOLVED = 1
    CANCELLED = 2

class EmergencyScope(enum.Enum):
    GLOBAL = 0
    ZONE = 1
    DOOR = 2
    LOCATION = 3

class EmergencyInitiatedType(enum.Enum):
    MANUAL_UI = 0
    PANIC_BUTTON = 1
    FIRE_PANEL = 2
    API = 3

class NotificationChannel(enum.Enum):
    SMS = 0
    EMAIL = 1
    WHATSAPP = 2
    PUSH = 3
    PA = 4
    SIREN = 5

class NotificationStatus(enum.Enum):
    PENDING = 0
    SENT = 1
    FAILED = 2
    DELIVERED = 3

class RecipientType(enum.Enum):
    USER = 0
    DEPT = 1
    ALL = 2

class PanicType(enum.Enum):
    SOFT_UI = 0
    HARD_AUX = 1

class MaintenanceType(enum.Enum):
    ROUTINE = 0
    MAJOR = 1
    INSPECTION = 2
    REPAIR = 3

class TransportType(enum.Enum):
    HELICOPTER = 0
    VESSEL = 1
    VEHICLE = 2

class TransportStatus(enum.Enum):
    SCHEDULED = 0
    BOARDING = 1
    IN_TRANSIT = 2
    ARRIVED = 3
    CANCELLED = 4

# Core Emergency Tables

class EmergencyEvent(Base):
    """Main emergency event tracking"""
    __tablename__ = "emergency_event"
    
    id = Column(BigInteger, primary_key=True, index=True)
    event_type = Column(SmallInteger, nullable=False, index=True)  # EmergencyEventType enum
    status = Column(SmallInteger, default=EmergencyStatus.ACTIVE.value, index=True)  # EmergencyStatus enum
    scope = Column(SmallInteger, default=EmergencyScope.GLOBAL.value)  # EmergencyScope enum
    
    # Target arrays
    zone_ids = Column(ARRAY(Integer))  # Array of zones.id
    door_ids = Column(ARRAY(Integer))  # Array of acc_door.id
    
    # Timestamps
    start_time = Column(DateTime(timezone=True), nullable=False, default=func.now())
    end_time = Column(DateTime(timezone=True))
    
    # Initiation tracking
    initiated_by = Column(Integer, ForeignKey("auth_user.id"))
    initiated_type = Column(SmallInteger, default=EmergencyInitiatedType.MANUAL_UI.value)  # EmergencyInitiatedType enum
    trigger_source = Column(String(100))  # "Web UI", "Panic Button Gate-01", "API:FirePanel"
    
    # Details
    reason = Column(Text)
    actions = Column(JSONB)  # [{type:"lockdown", doors:[1,2]}, {type:"siren", sns:["SN1"]}, {type:"mustering", zone_id:1}]
    mustering_event_id = Column(BigInteger, ForeignKey("mustering_event.id"))
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    initiator = relationship("AuthUser")
    mustering_event = relationship("MusteringEvent")
    notifications = relationship("EmergencyNotification", back_populates="emergency_event")
    panic_logs = relationship("EmergencyPanicLog", back_populates="emergency_event")

# class EmergencyDevice(Base):
#     """Emergency devices (sirens, strobes, locks, speakers, panic buttons)"""
#     __tablename__ = "emergency_device"
#     
#     id = Column(Integer, primary_key=True, index=True)
#     terminal_sn = Column(String(20), ForeignKey("iclock_terminal.sn"), unique=True, nullable=False)
#     device_type = Column(SmallInteger, nullable=False)  # 1=Siren,2=Strobe,3=Lock,4=Speaker,5=PanicButton
#     zone_id = Column(Integer, ForeignKey("mustering_zone.id"))
#     
#     # Status and monitoring
#     status = Column(SmallInteger, default=0, index=True)  # 0=off,1=on,2=fault
#     last_heartbeat = Column(DateTime(timezone=True))
#     test_schedule = Column(String(50))  # cron "0 12 * * 0"
#     
#     # Device configuration
#     location_description = Column(String(200))
#     installation_date = Column(Date)
#     maintenance_due = Column(Date)
#     
#     created_at = Column(DateTime(timezone=True), server_default=func.now())
#     updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
#     
#     # Relationships
#     terminal = relationship("IClockTerminal")
#     zone = relationship("MusteringZone")

class EmergencyTemplate(Base):
    """Predefined emergency action templates"""
    __tablename__ = "emergency_template"
    
    id = Column(Integer, primary_key=True, index=True)
    template_name = Column(String(100), nullable=False)
    event_type = Column(SmallInteger, nullable=False)  # EmergencyEventType enum
    description = Column(Text)
    
    # Actions and notifications
    actions = Column(JSONB, nullable=False)  # Full action set
    notify_channels = Column(JSONB)  # {sms:true, email:true, users:[1,2], depts:[3]}
    
    # Auto-triggering
    auto_mustering = Column(Boolean, default=True)
    auto_mustering_zone_id = Column(Integer, ForeignKey("zones.id"))

    # Template management
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    auto_mustering_zone = relationship("Zone", foreign_keys=[auto_mustering_zone_id])

class EmergencyNotification(Base):
    """Emergency notification tracking"""
    __tablename__ = "emergency_notification"
    
    id = Column(BigInteger, primary_key=True, index=True)
    emergency_event_id = Column(BigInteger, ForeignKey("emergency_event.id"), nullable=False, index=True)
    
    # Notification details
    channel = Column(SmallInteger, nullable=False)  # NotificationChannel enum
    recipient_type = Column(SmallInteger)  # RecipientType enum
    recipient_id = Column(Integer)
    recipient_addr = Column(String(255))  # phone/email
    message = Column(Text)
    
    # Status tracking
    status = Column(SmallInteger, default=NotificationStatus.PENDING.value, index=True)  # NotificationStatus enum
    sent_time = Column(DateTime(timezone=True))
    delivered_time = Column(DateTime(timezone=True))
    error_msg = Column(Text)
    
    # Message template variables
    template_vars = Column(JSONB)  # {name: "John", zone: "Platform A", evac_point: "Assembly A"}
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    emergency_event = relationship("EmergencyEvent", back_populates="notifications")

class EmergencyPlan(Base):
    """Emergency response plans and procedures"""
    __tablename__ = "emergency_plan"
    
    id = Column(Integer, primary_key=True, index=True)
    plan_name = Column(String(100), nullable=False)
    event_type = Column(SmallInteger)  # EmergencyEventType enum
    zone_id = Column(Integer, ForeignKey("zones.id"))

    # Plan content
    steps = Column(Text)  # markdown
    pdf_path = Column(String(255))
    contacts = Column(JSONB)  # [{name:"Fire Dept", phone:"xxx"}]

    # Plan management
    is_active = Column(Boolean, default=True)
    last_reviewed = Column(Date)
    next_review = Column(Date)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    zone = relationship("Zone", foreign_keys=[zone_id])

class EmergencyPanicLog(Base):
    """Panic button activation log"""
    __tablename__ = "emergency_panic_log"
    
    id = Column(BigInteger, primary_key=True, index=True)
    terminal_sn = Column(String(20))
    panic_time = Column(DateTime(timezone=True), nullable=False, default=func.now())
    panic_type = Column(SmallInteger)  # PanicType enum
    emp_code = Column(String(20))  # if authenticated
    location = Column(String(100))
    emergency_event_id = Column(BigInteger, ForeignKey("emergency_event.id"))
    
    # Panic details
    reason = Column(Text)
    resolved_by = Column(Integer, ForeignKey("auth_user.id"))
    resolved_time = Column(DateTime(timezone=True))
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    emergency_event = relationship("EmergencyEvent", back_populates="panic_logs")
    resolver = relationship("AuthUser")

# Transport Logistics Tables

class Transport(Base):
    """Transport fleet management"""
    __tablename__ = "transport"
    
    id = Column(Integer, primary_key=True, index=True)
    type = Column(SmallInteger, nullable=False)  # TransportType enum
    identifier = Column(String(50), nullable=False, unique=True)
    registration_number = Column(String(50))
    operator = Column(String(100))
    
    # Capacity and status
    capacity = Column(Integer, default=12)
    max_payload_kg = Column(Float)  # weight-and-balance limit; enforced at check-in when set
    current_pob = Column(Integer, default=0)
    status = Column(SmallInteger, default=TransportStatus.SCHEDULED.value, index=True)  # TransportStatus enum
    
    # Location and fuel
    base_location = Column(String(100))
    current_location = Column(String(100))
    fuel_capacity = Column(Float)
    current_fuel = Column(Float)
    
    # Performance metrics
    flight_hours = Column(Float, default=0)
    max_altitude = Column(Integer)
    max_speed = Column(Float)
    cost_per_hour = Column(Float)
    utilization_rate = Column(Float)
    performance_rating = Column(Float)
    
    # Status flags
    is_available = Column(Boolean, default=True)
    is_maintenance_mode = Column(Boolean, default=False)
    is_inspection_due = Column(Boolean, default=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    maintenance_records = relationship("TransportMaintenance", back_populates="transport")
    flight_logs = relationship("FlightLog", back_populates="transport")
    crew_assignments = relationship("TransportCrew", back_populates="transport")
    schedules = relationship("TransportSchedule", back_populates="transport")
    inventory = relationship("TransportInventory", back_populates="transport")

class TransportMaintenance(Base):
    """Transport maintenance records and scheduling"""
    __tablename__ = "transport_maintenance"
    
    id = Column(Integer, primary_key=True, index=True)
    transport_id = Column(Integer, ForeignKey("transport.id"), nullable=False)
    maintenance_type = Column(SmallInteger, nullable=False)  # MaintenanceType enum
    description = Column(Text, nullable=False)
    
    # Scheduling
    scheduled_date = Column(DateTime(timezone=True), nullable=False)
    completed_date = Column(DateTime(timezone=True))
    status = Column(String(20), default="SCHEDULED")  # SCHEDULED, IN_PROGRESS, COMPLETED, CANCELLED
    
    # Execution details
    technician = Column(String(100))
    cost = Column(Float)
    parts_used = Column(JSONB)  # List of parts used
    next_maintenance = Column(DateTime(timezone=True))
    maintenance_hours = Column(Float)  # Hours spent on maintenance
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    transport = relationship("Transport", back_populates="maintenance_records")

class FlightLog(Base):
    """Flight log entries for helicopter operations"""
    __tablename__ = "flight_log"
    
    id = Column(Integer, primary_key=True, index=True)
    transport_id = Column(Integer, ForeignKey("transport.id"), nullable=False)
    
    # Flight details
    flight_date = Column(DateTime(timezone=True), nullable=False)
    departure_time = Column(DateTime(timezone=True), nullable=False)
    arrival_time = Column(DateTime(timezone=True))
    departure_location = Column(String(100), nullable=False)
    arrival_location = Column(String(100), nullable=False)
    
    # Metrics
    flight_duration = Column(Float, nullable=False)  # Duration in hours
    distance = Column(Float, nullable=False)  # Distance in nautical miles
    fuel_consumed = Column(Float)  # Fuel consumed in liters
    
    # Conditions and personnel
    weather_conditions = Column(String(100))
    pilot_name = Column(String(100))
    co_pilot_name = Column(String(100))
    flight_route = Column(String(200))  # Flight path description
    passengers_count = Column(Integer, default=0)
    cargo_weight = Column(Float)  # Cargo weight in kg
    
    # Incidents
    incidents = Column(Text)  # Any incidents or issues
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    transport = relationship("Transport", back_populates="flight_logs")

class TransportCrew(Base):
    """Transport crew assignments and management"""
    __tablename__ = "transport_crew"
    
    id = Column(Integer, primary_key=True, index=True)
    transport_id = Column(Integer, ForeignKey("transport.id"), nullable=False)
    personnel_id = Column(Integer, ForeignKey("personnel_employee.id"), nullable=False)
    role = Column(String(50), nullable=False)  # PILOT, CO_PILOT, CAPTAIN, CREW
    
    # Assignment details
    start_date = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(DateTime(timezone=True))
    status = Column(String(20), default="ACTIVE")  # ACTIVE, INACTIVE, ON_LEAVE
    
    # Certifications and experience
    certification_number = Column(String(50))
    certification_expiry = Column(Date)
    medical_expiry = Column(Date)
    experience_hours = Column(Float)  # Total experience hours
    flight_hours = Column(Float)  # Flight hours (for pilots)
    last_flight_date = Column(DateTime(timezone=True))
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    transport = relationship("Transport", back_populates="crew_assignments")
    personnel = relationship("PersonnelEmployee")

class TransportSchedule(Base):
    """Transport scheduling and planning"""
    __tablename__ = "transport_schedule"
    
    id = Column(Integer, primary_key=True, index=True)
    transport_id = Column(Integer, ForeignKey("transport.id"), nullable=False)
    schedule_type = Column(String(20), nullable=False)  # REGULAR, CHARTER, STANDBY
    
    # Route and timing
    departure_location = Column(String(100), nullable=False)
    arrival_location = Column(String(100), nullable=False)
    departure_time = Column(DateTime(timezone=True), nullable=False)
    arrival_time = Column(DateTime(timezone=True))

    # Actuals — set when the journey actually departs / arrives (for delay tracking)
    actual_departure_time = Column(DateTime(timezone=True))
    actual_arrival_time = Column(DateTime(timezone=True))

    # Scheduling details
    frequency = Column(String(20))  # DAILY, WEEKLY, MONTHLY, ON_DEMAND
    end_date = Column(DateTime(timezone=True))
    status = Column(String(20), default="SCHEDULED")  # SCHEDULED, CONFIRMED, CANCELLED, COMPLETED
    priority = Column(String(20), default="NORMAL")  # LOW, NORMAL, HIGH, URGENT

    # Cargo, crew and passengers
    passenger_manifest = Column(JSONB)  # List of passengers
    cargo_manifest = Column(JSONB)  # [{description, weight_kg, type, dangerous_goods, un_number, remarks}]
    crew = Column(JSONB)  # [{name, role, license_no}] — pilot / captain / driver assigned to this journey
    estimated_cost = Column(Float)
    actual_cost = Column(Float)
    
    # Requirements
    weather_requirements = Column(String(100))
    special_requirements = Column(Text)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    transport = relationship("Transport", back_populates="schedules")

class TransportInventory(Base):
    """Transport inventory and equipment management"""
    __tablename__ = "transport_inventory"
    
    id = Column(Integer, primary_key=True, index=True)
    transport_id = Column(Integer, ForeignKey("transport.id"), nullable=False)
    
    # Item details
    item_name = Column(String(100), nullable=False)
    item_type = Column(String(50), nullable=False)  # SAFETY_EQUIPMENT, NAVIGATION, COMMUNICATION, MAINTENANCE
    item_description = Column(Text)
    
    # Quantity and location
    quantity = Column(Integer, default=1)
    unit_of_measure = Column(String(20), default="EACH")  # EACH, SET, LITER, KILOGRAM
    location_on_transport = Column(String(50))  # Location on transport
    
    # Expiry and condition
    expiry_date = Column(Date)  # Expiry date for consumables
    last_inspected = Column(DateTime(timezone=True))
    condition_status = Column(String(20), default="GOOD")  # EXCELLENT, GOOD, FAIR, POOR, NEEDS_REPLACEMENT
    replacement_cost = Column(Float)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    transport = relationship("Transport", back_populates="inventory")


class ManifestEntry(Base):
    """Per-passenger reconciliation record for a transport flight/voyage."""
    __tablename__ = "manifest_entry"

    id = Column(Integer, primary_key=True, index=True)
    schedule_id = Column(
        Integer,
        ForeignKey("transport_schedule.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Passenger identity — personnel_id null for visitors / non-registered guests
    personnel_id = Column(Integer, ForeignKey("personnel.id", ondelete="SET NULL"), nullable=True)
    passenger_name = Column(String(200), nullable=False)
    emp_code = Column(String(50))
    company = Column(String(100))
    id_number = Column(String(50))   # passport / national ID

    # Weight & balance (kg) — required for helicopter payload calculations
    body_weight = Column(Float)
    baggage_weight = Column(Float)

    # INBOUND = arriving offshore, OUTBOUND = departing offshore
    direction = Column(String(20), nullable=False, default="INBOUND")

    # MANIFESTED → CONFIRMED / NO_SHOW / OFFLOADED
    status = Column(String(20), nullable=False, default="MANIFESTED", index=True)
    confirmed_at = Column(DateTime(timezone=True))
    confirmed_by_id = Column(Integer, nullable=True)   # auth_user.id
    remarks = Column(Text)
    # When this passenger's POB movement was applied (outbound: flight departed;
    # inbound: flight arrived). NULL = not applied, so a reversal knows what to undo
    # and a repeated status change never applies it twice.
    pob_applied_at = Column(DateTime(timezone=True))

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    schedule = relationship("TransportSchedule", back_populates="manifest_entries")


# Attach manifest_entries to TransportSchedule (avoid modifying the class body above)
TransportSchedule.manifest_entries = relationship(
    "ManifestEntry",
    back_populates="schedule",
    cascade="all, delete-orphan",
    order_by="ManifestEntry.passenger_name",
)

# Add relationships to existing models
from app.models.biotime_models import IClockTerminal, MusteringEvent, AuthUser, PersonnelEmployee

# Extend IClockTerminal with emergency relationships
IClockTerminal.emergency_devices = relationship("EmergencyDevice", foreign_keys="[EmergencyDevice.terminal_sn]", primaryjoin="IClockTerminal.sn == EmergencyDevice.terminal_sn")
