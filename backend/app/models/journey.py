"""
Land Journey Management (JMP) models.

Road-transport journey plans with risk assessment, an approval workflow, and
check-in-call tracking so a journey that misses its next check-in is flagged
OVERDUE for escalation to the control room.
"""

from sqlalchemy import (
    Column, Integer, String, Text, Float, Boolean, DateTime, ForeignKey,
)
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from ..core.database import Base


class JourneyPlan(Base):
    """A planned road journey (Journey Management Plan)."""
    __tablename__ = "journey_plan"

    id = Column(Integer, primary_key=True, index=True)
    reference = Column(String(30), unique=True, index=True)  # e.g. JMP-0001

    origin = Column(String(150), nullable=False)
    destination = Column(String(150), nullable=False)
    route_description = Column(Text)                 # waypoints / route notes
    distance_km = Column(Float)
    purpose = Column(String(200))

    # Driver & vehicle
    driver_name = Column(String(150))
    driver_license = Column(String(60))
    driver_personnel_id = Column(Integer, ForeignKey("personnel.id", ondelete="SET NULL"), nullable=True)
    vehicle_reg = Column(String(60))
    vehicle_type = Column(String(60))
    passengers = Column(JSONB)                        # [{name, emp_code}]
    passenger_count = Column(Integer, default=0)

    # Timing
    planned_departure = Column(DateTime(timezone=True), nullable=False)
    planned_arrival = Column(DateTime(timezone=True))
    actual_departure = Column(DateTime(timezone=True))
    actual_arrival = Column(DateTime(timezone=True))

    # Check-in-call tracking
    checkin_interval_min = Column(Integer, default=60)
    last_checkin_at = Column(DateTime(timezone=True))
    next_checkin_due = Column(DateTime(timezone=True))

    # Risk assessment
    risk_level = Column(String(10), default="LOW")    # LOW / MEDIUM / HIGH
    risk_factors = Column(JSONB)                        # list[str]
    risk_notes = Column(Text)
    # Factors the planner chose. risk_factors holds the computed reasons (these plus
    # automatic ones like night driving); keeping them apart stops an edit from
    # dropping manual factors or counting automatic ones twice.
    risk_manual_factors = Column(JSONB)

    # Pre-trip vehicle inspection
    vehicle_check = Column(JSONB)                       # {tyres:true, brakes:true, ...}
    vehicle_check_ok = Column(Boolean, default=False)

    # Workflow
    status = Column(String(20), default="DRAFT", index=True)
    # DRAFT / SUBMITTED / APPROVED / REJECTED / IN_PROGRESS / COMPLETED / CANCELLED
    approved_by_id = Column(Integer, nullable=True)
    approved_at = Column(DateTime(timezone=True))
    # HIGH-risk journeys need a second, different approver.
    second_approved_by_id = Column(Integer, nullable=True)
    second_approved_at = Column(DateTime(timezone=True))
    rejection_reason = Column(Text)

    created_by_id = Column(Integer, nullable=True)
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    checkins = relationship("JourneyCheckIn", back_populates="journey",
                            cascade="all, delete-orphan")


class JourneyCheckIn(Base):
    """A check-in call logged against an in-progress journey."""
    __tablename__ = "journey_checkin"

    id = Column(Integer, primary_key=True, index=True)
    journey_id = Column(Integer, ForeignKey("journey_plan.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    checkin_time = Column(DateTime(timezone=True), server_default=func.now())
    location = Column(String(150))
    status = Column(String(20), default="OK")          # OK / CONCERN
    reported_by = Column(String(150))
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    journey = relationship("JourneyPlan", back_populates="checkins")
