"""Pydantic schemas for access-control controllers and their reader ports."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# ── Reader (door port) ────────────────────────────────────────────────────────
class AccessReaderBase(BaseModel):
    door_no: int = Field(..., ge=1, description="Door number on the controller (1..door_count)")
    direction: str = Field(..., pattern="^(ENTRY|EXIT)$", description="ENTRY or EXIT side of the door")
    name: Optional[str] = None
    zone_id: Optional[int] = Field(None, description="Zone this reader-port controls access to")
    status: str = Field("active", pattern="^(active|inactive)$")
    purpose: str = Field("ACCESS", pattern="^(ATTENDANCE|ACCESS|MUSTERING)$",
                         description="ATTENDANCE = clock in/out (sent to payroll), ACCESS = door only, MUSTERING = muster point")


class AccessReaderCreate(AccessReaderBase):
    pass


class AccessReaderUpdate(BaseModel):
    door_no: Optional[int] = Field(None, ge=1)
    direction: Optional[str] = Field(None, pattern="^(ENTRY|EXIT)$")
    name: Optional[str] = None
    zone_id: Optional[int] = None
    status: Optional[str] = Field(None, pattern="^(active|inactive)$")
    purpose: Optional[str] = Field(None, pattern="^(ATTENDANCE|ACCESS|MUSTERING)$")


class AccessReaderOut(AccessReaderBase):
    id: int
    controller_id: int
    zone_name: Optional[str] = None
    last_event_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ── Controller ────────────────────────────────────────────────────────────────
class AccessControllerBase(BaseModel):
    name: str
    ip_address: str
    port: int = 4370
    model: Optional[str] = None
    serial_number: Optional[str] = None
    manufacturer: Optional[str] = "ZKTeco"
    comm_password: Optional[str] = None
    location: Optional[str] = None
    door_count: int = Field(1, ge=1, le=8)
    poll_enabled: bool = False
    poll_interval_sec: int = Field(5, ge=1, le=3600)
    notes: Optional[str] = None
    fire_alarm_input: Optional[int] = Field(None, ge=1, le=8, description="AUX input the fire alarm contact is wired to")
    fire_alarm_on: str = Field("open", pattern="^(open|close)$", description="Alarm when the contact opens or closes")


class AccessControllerCreate(AccessControllerBase):
    # Optionally seed reader ports on create (e.g. auto-generate IN/OUT per door)
    readers: Optional[List[AccessReaderCreate]] = None


class AccessControllerUpdate(BaseModel):
    name: Optional[str] = None
    ip_address: Optional[str] = None
    port: Optional[int] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    comm_password: Optional[str] = None
    location: Optional[str] = None
    door_count: Optional[int] = Field(None, ge=1, le=8)
    poll_enabled: Optional[bool] = None
    poll_interval_sec: Optional[int] = Field(None, ge=1, le=3600)
    notes: Optional[str] = None
    fire_alarm_input: Optional[int] = Field(None, ge=1, le=8, description="AUX input the fire alarm contact is wired to")
    fire_alarm_on: Optional[str] = Field(None, pattern="^(open|close)$", description="Alarm when the contact opens or closes")


class AccessControllerOut(AccessControllerBase):
    id: int
    status: str
    last_seen: Optional[datetime] = None
    last_error: Optional[str] = None
    readers: List[AccessReaderOut] = []

    class Config:
        from_attributes = True
