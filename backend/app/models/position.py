"""
Position Management Database Models
Supports job position hierarchy and management
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean, Float, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..core.database import Base


class Position(Base):
    """Job positions for personnel management"""
    __tablename__ = "positions"
    
    id = Column(Integer, primary_key=True, index=True)
    position_code = Column(String(20), unique=True, nullable=False, index=True)
    position_name = Column(String(100), nullable=False, index=True)
    description = Column(Text, nullable=True)
    
    # Hierarchy
    parent_id = Column(Integer, ForeignKey("positions.id"), nullable=True)
    level = Column(Integer, default=1, index=True)  # Organizational level
    sort_order = Column(Integer, default=0)  # Display order
    
    # Department linkage
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True, index=True)
    
    # Position properties
    position_type = Column(String(20), nullable=True)  # EXECUTIVE, MANAGER, SUPERVISOR, STAFF, CONTRACTOR
    job_category = Column(String(30), nullable=True)  # TECHNICAL, OPERATIONS, SAFETY, ADMIN, SUPPORT
    grade_level = Column(String(10), nullable=True)  # Grade/Level classification
    
    # Requirements
    required_certifications = Column(JSON, nullable=True)  # List of required certifications
    required_skills = Column(JSON, nullable=True)  # List of required skills
    min_experience_years = Column(Integer, default=0)
    education_level = Column(String(50), nullable=True)  # Required education level
    
    # Compensation (optional)
    salary_range_min = Column(Float, nullable=True)
    salary_range_max = Column(Float, nullable=True)
    currency = Column(String(3), default="USD")
    
    # Staffing target
    headcount = Column(Integer, default=1, nullable=True)  # Target number of personnel for this position

    # Status
    is_active = Column(Boolean, default=True, index=True)
    hr_source = Column(String(20), nullable=True)   # 'SEAMLESSHR' = name/code mastered there (read-only here)
    is_safety_critical = Column(Boolean, default=False, index=True)
    requires_background_check = Column(Boolean, default=False)
    
    # Audit trail
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    notes = Column(Text, nullable=True)
    
    # Relationships
    parent = relationship("Position", remote_side=[id], back_populates="children")
    children = relationship("Position", back_populates="parent")
    department = relationship("Department")
    creator = relationship("User", foreign_keys=[created_by])
    updater = relationship("User", foreign_keys=[updated_by])

    # personnel_assignments disabled — Personnel.position is a string, not FK


class PositionAssignment(Base):
    """Position assignments for personnel"""
    __tablename__ = "position_assignments"
    
    id = Column(Integer, primary_key=True, index=True)
    personnel_id = Column(Integer, ForeignKey("personnel.id"), nullable=False, index=True)
    position_id = Column(Integer, ForeignKey("positions.id"), nullable=False, index=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)
    
    # Assignment details
    assignment_type = Column(String(20), default="PRIMARY")  # PRIMARY, SECONDARY, ACTING
    start_date = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(DateTime(timezone=True), nullable=True)
    
    # Assignment status
    status = Column(String(20), default="ACTIVE")  # ACTIVE, INACTIVE, PENDING, COMPLETED
    is_current = Column(Boolean, default=True, index=True)
    
    # Assignment authority
    assigned_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    
    # Audit trail
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    notes = Column(Text, nullable=True)
    
    # Relationships
    personnel = relationship("Personnel")
    position = relationship("Position")
    department = relationship("Department")
    assigner = relationship("User", foreign_keys=[assigned_by])
    approver = relationship("User", foreign_keys=[approved_by])


class PositionTemplate(Base):
    """Position templates for quick creation"""
    __tablename__ = "position_templates"
    
    id = Column(Integer, primary_key=True, index=True)
    template_name = Column(String(100), nullable=False, index=True)
    template_code = Column(String(20), unique=True, nullable=False, index=True)
    position_type = Column(String(20), nullable=True)
    job_category = Column(String(30), nullable=True)
    
    # Template data
    template_data = Column(JSON, nullable=False)  # Position template configuration
    default_requirements = Column(JSON, nullable=True)  # Default requirements
    
    # Usage tracking
    usage_count = Column(Integer, default=0)
    last_used = Column(DateTime(timezone=True), nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True, index=True)
    is_system_template = Column(Boolean, default=False)  # System vs user templates
    
    # Audit
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    creator = relationship("User")


class PositionLevel(Base):
    """Position levels/grades"""
    __tablename__ = "position_levels"
    
    id = Column(Integer, primary_key=True, index=True)
    level_code = Column(String(10), unique=True, nullable=False, index=True)
    level_name = Column(String(50), nullable=False, index=True)
    level_number = Column(Integer, unique=True, nullable=False, index=True)  # 1, 2, 3, etc.
    description = Column(Text, nullable=True)
    
    # Level properties
    level_type = Column(String(20), nullable=True)  # EXECUTIVE, MANAGEMENT, SUPERVISORY, STAFF
    authority_level = Column(Integer, default=1)  # Authority weight
    can_approve = Column(Boolean, default=False)
    can_manage = Column(Boolean, default=False)
    
    # Status
    is_active = Column(Boolean, default=True, index=True)
    
    # Audit
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    # positions relationship disabled — Position has no FK to position_levels
