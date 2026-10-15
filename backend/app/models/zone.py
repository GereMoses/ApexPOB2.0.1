from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Boolean, JSON, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..core.database import Base


class Zone(Base):
    """Enhanced Zone model as primary location concept"""
    __tablename__ = "zones"

    # Basic Information
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, index=True)
    code = Column(String(20), unique=True, nullable=False, index=True)
    zone_type = Column(String(30), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(20), nullable=True, default="ACTIVE")
    
    # Geographic Information
    state = Column(String(100), nullable=True, index=True)  # State for multi-state deployment
    address = Column(Text, nullable=True)
    latitude = Column(String(20), nullable=True)
    longitude = Column(String(20), nullable=True)
    
    # Capacity and Occupancy
    max_capacity = Column(Integer, nullable=True)
    current_occupancy = Column(Integer, default=0)
    current_personnel_count = Column(Integer, default=0)
    
    # Safety and Security
    hazard_level = Column(String(20), default="LOW")  # LOW, MEDIUM, HIGH, CRITICAL
    safety_level = Column(String(20), default="NORMAL")  # LOW, NORMAL, HIGH, CRITICAL
    access_level = Column(String(20), default="RESTRICTED")  # PUBLIC, RESTRICTED, SECURE
    
    # Device Management
    device_count = Column(Integer, default=0)  # Number of ZKTeco devices assigned
    
    # Operational Details
    zone_manager_id = Column(Integer, nullable=True)
    contact_person = Column(String(255), nullable=True)
    contact_phone = Column(String(20), nullable=True)
    
    # ZKTeco Integration
    zkteco_sync_enabled = Column(Boolean, default=True)
    last_sync_at = Column(DateTime(timezone=True), nullable=True)

    # Floor Plan (supports both file upload and external URL)
    floor_plan_url = Column(String(500), nullable=True)
    floor_plan_file_path = Column(String(500), nullable=True)
    floor_plan_filename = Column(String(255), nullable=True)
    floor_plan_uploaded_at = Column(DateTime(timezone=True), nullable=True)

    # Hierarchy & Visual Dashboard
    parent_zone_id = Column(Integer, nullable=True)  # Parent zone for sub-zone grouping
    display_color = Column(String(20), nullable=True)  # Hex color for POB dashboard tile
    tile_position = Column(String(20), nullable=True, default="auto")  # left/right/top/bottom/auto

    # Mustering / Emergency fields (consolidated from legacy mustering_zone table)
    evac_point = Column(String(100), nullable=True)       # evacuation assembly point name
    evac_gps = Column(String(50), nullable=True)          # "lat,lon" for evacuation GPS
    reader_sn = Column(String(50), nullable=True)         # ZKTeco reader used for mustering check-in
    map_x = Column(Float, nullable=True)                  # position on facility map diagram
    map_y = Column(Float, nullable=True)
    map_connections = Column(Text, nullable=True)         # JSON: "[zone_id, ...]" connected zones
    # Site boundary (gate, helideck, jetty): an EXIT here means the person has left
    # site, so they come off POB. Exits anywhere else only move them between zones.
    is_site_boundary = Column(Boolean, default=False, server_default='false', nullable=False)

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    is_active = Column(Boolean, default=True, server_default='true')
    
    # Relationships (without foreign key constraints to avoid database errors)
    devices = relationship("Device", back_populates="zone_assignment")
    personnel_assignments = relationship("ZonePersonnelAssignment", back_populates="zone")
    reader_assignments = relationship("ZoneReaderAssignment", back_populates="zone")
    
    def __repr__(self):
        try:
            return f"<Zone(id={self.id}, name='{self.name}', code='{self.code}')>"
        except Exception:
            return f"<Zone(id={self.id})>"


class ZonePersonnelAssignment(Base):
    """Zone-Personnel assignments for access control"""
    __tablename__ = "zone_personnel_assignments"
    
    id = Column(Integer, primary_key=True, index=True)
    zone_id = Column(Integer, ForeignKey("zones.id"), nullable=False)
    personnel_id = Column(Integer, ForeignKey("personnel.id"), nullable=False)
    
    # Assignment Details
    role = Column(String(100), nullable=True)  # Role within zone
    access_level = Column(String(20), default="STANDARD")  # BASIC, STANDARD, ENHANCED, FULL
    is_primary_zone = Column(Boolean, default=False)  # Primary work zone
    
    # Assignment Period
    assigned_at = Column(DateTime(timezone=True), server_default=func.now())
    unassigned_at = Column(DateTime(timezone=True), nullable=True)
    is_permanent = Column(Boolean, default=False)
    
    # Access Control
    access_times = Column(JSON, nullable=True)  # Allowed access times
    device_access = Column(JSON, nullable=True)  # Specific device access permissions
    
    # Safety and Compliance
    safety_briefing_completed = Column(Boolean, default=False)
    safety_briefing_date = Column(DateTime(timezone=True), nullable=True)
    certifications_verified = Column(Boolean, default=False)
    
    # Status
    status = Column(String(20), default="ACTIVE")  # ACTIVE, INACTIVE, PENDING, EXPIRED
    
    # Approval Workflow
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    
    # Metadata
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    zone = relationship("Zone", back_populates="personnel_assignments")
    personnel = relationship("Personnel", back_populates="zone_assignments")
    approved_by_user = relationship("User", foreign_keys=[approved_by])
    
    def __repr__(self):
        return f"<ZonePersonnelAssignment(zone_id={self.zone_id}, personnel_id={self.personnel_id})>"
