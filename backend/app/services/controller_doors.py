"""
Door + output records for ZKTeco access controllers (C3-100/200/400, inBio).

Lockdown and fire mode act on acc_door rows. A controller's doors used to exist
only if someone created each one by hand in Door Settings, so a freshly added
panel was invisible to emergencies. ensure_controller_doors() creates one door
per port the moment a controller is added (or its door count changes); the
admin then only marks which are fire exits (unlock in a fire) or lock in a fire.
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def ensure_controller_doors(db: Session, controller) -> int:
    from ..models.biotime_models import AccDoor
    have = {d.port for d in db.query(AccDoor).filter(AccDoor.controller_id == controller.id).all()}
    added = 0
    for port in range(1, int(controller.door_count or 1) + 1):
        if port in have:
            continue
        db.add(AccDoor(name=f"{controller.name or 'Controller'} — door {port}"[:50],
                       controller_id=controller.id, port=port, emergency_action=0))
        added += 1
    if added:
        db.commit()
        logger.info("Controller %s: created %d door record(s)", controller.id, added)
    return added


def ensure_all_controller_doors(db: Session) -> int:
    from ..models.access_controller import AccessController
    return sum(ensure_controller_doors(db, c) for c in db.query(AccessController).all())
