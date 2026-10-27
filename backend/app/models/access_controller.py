"""
Access Control Controller models.

WHY THIS IS SEPARATE FROM `iclock_terminal`
-------------------------------------------
The Horus H1 readers used for Time & Attendance and Mustering are standalone
network devices: one reader = one IP = one ADMS push stream. They are modelled by
`iclock_terminal` and ingested through the ADMS protocol — untouched by this file.

The zone access-control readers are different hardware. They are dumb Wiegand
readers wired to a controller (ZKTeco inBio / C3 panel). Only the *controller* is
on the LAN (has an IP); it speaks the C3 "PULL" protocol over TCP 4370 (see
`services/zkteco/c3_controller.py`). Each controller drives several doors, and
each door has an IN reader and an OUT reader. The addressable unit of a reader is
therefore `(controller, door_no, direction)` — it has no IP of its own.

  AccessController (has IP)  ──< AccessReader (door_no + direction, no IP) >── Zone
"""

from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Text, ForeignKey, UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..core.database import Base


class AccessController(Base):
    """A LAN-connected access panel (ZKTeco inBio / C3). The only networked node;
    its readers hang off it by door number and are not individually addressable."""
    __tablename__ = "access_controllers"

    id = Column(Integer, primary_key=True, index=True)

    # Identity
    name = Column(String(100), nullable=False)
    serial_number = Column(String(64), nullable=True, index=True)
    model = Column(String(64), nullable=True)          # e.g. inBio260, C3-400
    manufacturer = Column(String(64), nullable=True, default="ZKTeco")

    # Network (direct LAN — C3 PULL protocol, NOT ADMS push)
    ip_address = Column(String(45), nullable=False, index=True)
    port = Column(Integer, nullable=False, default=4370)
    comm_password = Column(String(64), nullable=True)  # panel comm password, if set

    # Physical location (building / gate / floor) — helps identify the panel on site
    location = Column(String(255), nullable=True)

    # Topology
    door_count = Column(Integer, nullable=False, default=1)

    # Health / status
    status = Column(String(20), nullable=False, default="offline")  # online|offline|error
    last_seen = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(String(255), nullable=True)

    # Realtime-log polling (opt-in; the C3 driver is pull, not push)
    poll_enabled = Column(Boolean, nullable=False, default=False)
    poll_interval_sec = Column(Integer, nullable=False, default=5)
    # Fire alarm panel dry contact wired to this panel's AUX input → fire mode
    fire_alarm_input = Column(Integer, nullable=True)        # AUX IN number, None = not wired
    fire_alarm_on = Column(String(6), nullable=False, default="open", server_default="open")  # open | close

    notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    readers = relationship(
        "AccessReader",
        back_populates="controller",
        cascade="all, delete-orphan",
        order_by="AccessReader.door_no",
    )

    def __repr__(self):
        return f"<AccessController(id={self.id}, name='{self.name}', ip='{self.ip_address}')>"


class AccessReader(Base):
    """One reader port on a controller: identified by door number + direction
    (the IN/OUT side of the door). Mapped to a zone for entry/exit tracking."""
    __tablename__ = "access_readers"
    __table_args__ = (
        UniqueConstraint("controller_id", "door_no", "direction", name="uq_reader_controller_door_dir"),
    )

    id = Column(Integer, primary_key=True, index=True)
    controller_id = Column(Integer, ForeignKey("access_controllers.id", ondelete="CASCADE"),
                           nullable=False, index=True)

    # Position on the controller
    door_no = Column(Integer, nullable=False)          # 1..door_count
    direction = Column(String(5), nullable=False)      # ENTRY | EXIT

    name = Column(String(100), nullable=True)          # friendly label, e.g. "Gate 1 Entry"

    # Zone this reader-port controls access to (entry/exit feeds zone occupancy)
    zone_id = Column(Integer, ForeignKey("zones.id"), nullable=True, index=True)

    status = Column(String(20), nullable=False, default="active")  # active|inactive
    # ATTENDANCE = clock in/out → attendance + SeamlessHR; ACCESS = door only (zones,
    # POB at a site boundary); MUSTERING = reader at an assembly point.
    purpose = Column(String(12), nullable=False, default="ACCESS", server_default="ACCESS")
    last_event_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    controller = relationship("AccessController", back_populates="readers")
    zone = relationship("Zone")

    def __repr__(self):
        return (f"<AccessReader(id={self.id}, controller_id={self.controller_id}, "
                f"door={self.door_no}, dir={self.direction}, zone={self.zone_id})>")
