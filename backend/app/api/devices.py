"""
Device API for Oil & Gas Personnel Management
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
import logging

from ..core.database import get_db
from ..core.dependencies import get_current_user
from ..models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/devices", tags=["Devices"])

@router.get("/", response_model=List[dict])
async def get_devices(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status: Optional[str] = Query(None),
    device_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all devices with optional filtering"""
    try:
        # Use raw SQL since Device model might have issues
        from sqlalchemy import text
        
        query = "SELECT * FROM devices WHERE 1=1"
        params = {}
        
        if status:
            query += " AND status = :status"
            params["status"] = status
            
        if device_type:
            query += " AND device_type = :device_type"
            params["device_type"] = device_type
            
        query += " ORDER BY created_at DESC LIMIT :limit OFFSET :skip"
        params["limit"] = limit
        params["skip"] = skip
        
        result = db.execute(text(query), params)
        devices = [dict(row._mapping) for row in result.fetchall()]
        
        return devices
    except Exception as e:
        logger.error(f"Error fetching devices: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch devices"
        )

@router.get("/readers", response_model=List[dict])
async def get_readers(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all reader devices"""
    try:
        from sqlalchemy import text
        
        query = "SELECT * FROM devices WHERE device_type = 'biometric_reader'"
        params = {}
        
        if status:
            query += " AND status = :status"
            params["status"] = status
            
        query += " ORDER BY created_at DESC LIMIT :limit OFFSET :skip"
        params["limit"] = limit
        params["skip"] = skip
        
        result = db.execute(text(query), params)
        readers = [dict(row) for row in result.fetchall()]
        
        return readers
    except Exception as e:
        logger.error(f"Error fetching readers: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch readers"
        )

@router.get("/public-readers")
async def get_public_readers(
    db: Session = Depends(get_db)
):
    """Get readers without authentication"""
    try:
        from sqlalchemy import text
        
        query = "SELECT id, device_id, name, status, ip_address, location FROM devices WHERE device_type = 'biometric_reader' ORDER BY name"
        result = db.execute(text(query))
        readers = []
        for row in result.fetchall():
            row_dict = {}
            for i, column in enumerate(row._fields):
                value = row[i]
                if hasattr(value, 'isoformat'):
                    value = value.isoformat()
                row_dict[column] = value
            readers.append(row_dict)
        
        return readers
    except Exception as e:
        logger.error(f"Error fetching public readers: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch readers"
        )
