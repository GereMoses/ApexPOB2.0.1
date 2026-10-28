"""
BioTime Reporting and Analytics API

Provides real analytics endpoints backed by actual IClockTransaction
and AttendanceLog data from connected ZKTeco devices.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, extract, distinct
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from ..core.database import get_db
from ..services.biotime_sync_service import biotime_sync_service
from ..models.personnel import Personnel, AttendanceLog
from ..models.biotime_models import IClockTransaction, IClockTerminal

router = APIRouter()

VERIFY_TYPE_MAP = {0: 'password', 1: 'fingerprint', 2: 'face', 3: 'card'}
PUNCH_STATE_MAP = {0: 'check_in', 1: 'check_out', 2: 'break_out', 3: 'break_in'}


# ─── Performance Analytics ────────────────────────────────────────────────────

@router.get("/performance/verification-metrics")
async def get_verification_performance_metrics(
    days: int = Query(30, ge=1, le=365, description="Number of days for analytics"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Real verification metrics from IClockTransaction punch records."""
    try:
        cutoff = datetime.utcnow() - timedelta(days=days)

        # Total transactions in the period
        total = db.query(func.count(IClockTransaction.id)).filter(
            IClockTransaction.punch_time >= cutoff
        ).scalar() or 0

        # Hourly distribution — real punch-time data
        hourly_rows = (
            db.query(
                extract('hour', IClockTransaction.punch_time).label('hr'),
                func.count(IClockTransaction.id).label('cnt'),
            )
            .filter(IClockTransaction.punch_time >= cutoff)
            .group_by('hr')
            .all()
        )
        hourly_distribution = {str(h): 0 for h in range(24)}
        for row in hourly_rows:
            hourly_distribution[str(int(row.hr))] = row.cnt

        # Verification method breakdown from verify_type column
        type_rows = (
            db.query(
                IClockTransaction.verify_type,
                func.count(IClockTransaction.id).label('cnt'),
            )
            .filter(IClockTransaction.punch_time >= cutoff)
            .group_by(IClockTransaction.verify_type)
            .all()
        )
        type_distribution = {v: 0 for v in VERIFY_TYPE_MAP.values()}
        for row in type_rows:
            label = VERIFY_TYPE_MAP.get(row.verify_type, 'unknown')
            type_distribution[label] = row.cnt

        # Punch state breakdown (check-in vs check-out)
        state_rows = (
            db.query(
                IClockTransaction.punch_state,
                func.count(IClockTransaction.id).label('cnt'),
            )
            .filter(IClockTransaction.punch_time >= cutoff)
            .group_by(IClockTransaction.punch_state)
            .all()
        )
        state_distribution = {v: 0 for v in PUNCH_STATE_MAP.values()}
        for row in state_rows:
            label = PUNCH_STATE_MAP.get(row.punch_state, 'other')
            state_distribution[label] = row.cnt

        avg_daily = round(total / days, 2) if days > 0 else 0

        return {
            "success": True,
            "period_days": days,
            "total_verifications": total,
            "avg_daily_verifications": avg_daily,
            "hourly_distribution": hourly_distribution,
            "verification_type_distribution": type_distribution,
            "punch_state_distribution": state_distribution,
            "generated_at": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get verification metrics: {str(e)}")


@router.get("/performance/sync-metrics")
async def get_sync_performance_metrics(
    days: int = Query(7, ge=1, le=90, description="Number of days for sync metrics"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Synchronisation performance from the BioTime sync service."""
    try:
        sync_status = await biotime_sync_service.get_sync_status()
        total_synced = sync_status.get("total_synced", 0)
        error_count = sync_status.get("sync_status", {}).get("error_count", 0)
        if not isinstance(error_count, int):
            error_count = 0

        sync_success_rate = round(((total_synced - error_count) / total_synced) * 100, 2) if total_synced > 0 else 0

        return {
            "success": True,
            "period_days": days,
            "total_sync_operations": total_synced,
            "successful_syncs": total_synced - error_count,
            "failed_syncs": error_count,
            "sync_success_rate": sync_success_rate,
            "last_sync_details": sync_status.get("last_sync_summary", {}),
            "error_rate": round((error_count / total_synced) * 100, 2) if total_synced > 0 else 0,
            "biotime_connection": sync_status.get("biotime_connection", {}),
            "generated_at": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get sync metrics: {str(e)}")


# ─── Usage Analytics ──────────────────────────────────────────────────────────

@router.get("/usage/biometric-templates")
async def get_biometric_template_usage(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Biometric template enrollment statistics."""
    try:
        cutoff = datetime.utcnow() - timedelta(days=days)

        total_personnel = db.query(func.count(Personnel.id)).filter(Personnel.is_active == True).scalar() or 0
        enrolled = db.query(func.count(Personnel.id)).filter(Personnel.is_active == True).filter(
            Personnel.biometric_enrolled == True
        ).scalar() or 0
        recently_enrolled = db.query(func.count(Personnel.id)).filter(Personnel.is_active == True).filter(
            Personnel.biometric_enrolled == True,
            Personnel.updated_at >= cutoff,
        ).scalar() or 0

        # Count fingerprint vs face templates from JSON columns
        fp_count = db.query(func.count(Personnel.id)).filter(Personnel.is_active == True).filter(
            Personnel.biometric_enrolled == True,
            Personnel.fingerprint_templates.isnot(None),
        ).scalar() or 0
        face_count = db.query(func.count(Personnel.id)).filter(Personnel.is_active == True).filter(
            Personnel.biometric_enrolled == True,
            Personnel.face_template.isnot(None),
        ).scalar() or 0

        return {
            "success": True,
            "period_days": days,
            "total_personnel": total_personnel,
            "enrolled_count": enrolled,
            "enrollment_rate": round((enrolled / total_personnel) * 100, 2) if total_personnel > 0 else 0,
            "recently_enrolled": recently_enrolled,
            "biometric_distribution": {
                "fingerprint": fp_count,
                "face": face_count,
                "both": min(fp_count, face_count),
                "total_enrolled": enrolled,
            },
            "generated_at": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get biometric template usage: {str(e)}")


@router.get("/usage/device-activity")
async def get_device_activity_analytics(
    days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Per-device punch counts and verification method breakdown from IClockTransaction."""
    try:
        cutoff = datetime.utcnow() - timedelta(days=days)

        # Aggregate per terminal_sn
        device_rows = (
            db.query(
                IClockTransaction.terminal_sn,
                func.count(IClockTransaction.id).label('punch_count'),
                func.min(IClockTransaction.punch_time).label('first_seen'),
                func.max(IClockTransaction.punch_time).label('last_seen'),
                func.count(distinct(IClockTransaction.emp_code)).label('unique_employees'),
            )
            .filter(IClockTransaction.punch_time >= cutoff)
            .group_by(IClockTransaction.terminal_sn)
            .order_by(func.count(IClockTransaction.id).desc())
            .all()
        )

        total_records = db.query(func.count(IClockTransaction.id)).filter(
            IClockTransaction.punch_time >= cutoff
        ).scalar() or 0

        # Enrich with terminal alias where available
        terminal_aliases: Dict[str, str] = {}
        for t in db.query(IClockTerminal.sn, IClockTerminal.alias).all():
            terminal_aliases[t.sn] = t.alias or t.sn

        device_usage = []
        for row in device_rows:
            sn = row.terminal_sn or 'unknown'
            device_usage.append({
                "terminal_sn": sn,
                "name": terminal_aliases.get(sn, sn),
                "punch_count": row.punch_count,
                "unique_employees": row.unique_employees,
                "first_seen": row.first_seen.isoformat() if row.first_seen else None,
                "last_seen": row.last_seen.isoformat() if row.last_seen else None,
            })

        return {
            "success": True,
            "period_days": days,
            "total_attendance_records": total_records,
            "device_count": len(device_usage),
            "most_active_device": device_usage[0]["terminal_sn"] if device_usage else None,
            "device_usage": device_usage,
            "generated_at": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get device activity analytics: {str(e)}")


# ─── Compliance Reports ───────────────────────────────────────────────────────

@router.get("/compliance/biometric-quality")
async def get_biometric_quality_compliance(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Biometric enrollment quality report based on template presence."""
    try:
        total = db.query(func.count(Personnel.id)).filter(Personnel.is_active == True).scalar() or 0
        enrolled = db.query(func.count(Personnel.id)).filter(Personnel.is_active == True).filter(Personnel.biometric_enrolled == True).scalar() or 0
        both = db.query(func.count(Personnel.id)).filter(Personnel.is_active == True).filter(
            Personnel.biometric_enrolled == True,
            Personnel.fingerprint_templates.isnot(None),
            Personnel.face_template.isnot(None),
        ).scalar() or 0
        fp_only = db.query(func.count(Personnel.id)).filter(Personnel.is_active == True).filter(
            Personnel.biometric_enrolled == True,
            Personnel.fingerprint_templates.isnot(None),
            Personnel.face_template.is_(None),
        ).scalar() or 0
        face_only = db.query(func.count(Personnel.id)).filter(Personnel.is_active == True).filter(
            Personnel.biometric_enrolled == True,
            Personnel.fingerprint_templates.is_(None),
            Personnel.face_template.isnot(None),
        ).scalar() or 0

        not_enrolled = total - enrolled
        compliance_rate = round((enrolled / total) * 100, 2) if total > 0 else 0

        recommendations = []
        if not_enrolled > 0:
            recommendations.append(f"{not_enrolled} personnel have no biometric data enrolled")
        if compliance_rate < 80:
            recommendations.append("Enrollment rate below 80% — schedule biometric enrollment drives")
        if both == 0 and enrolled > 0:
            recommendations.append("No personnel have both fingerprint and face templates — consider dual-modality enrollment")

        return {
            "success": True,
            "total_personnel": total,
            "enrolled_count": enrolled,
            "not_enrolled": not_enrolled,
            "quality_distribution": {
                "both_modalities": both,
                "fingerprint_only": fp_only,
                "face_only": face_only,
                "not_enrolled": not_enrolled,
            },
            "compliance_rate": compliance_rate,
            "recommendations": recommendations,
            "generated_at": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get biometric quality compliance: {str(e)}")


@router.get("/compliance/usage-trends")
async def get_usage_trends_compliance(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Daily punch counts from IClockTransaction for trend analysis."""
    try:
        cutoff = datetime.utcnow() - timedelta(days=days)

        daily_rows = (
            db.query(
                func.date(IClockTransaction.punch_time).label('day'),
                func.count(IClockTransaction.id).label('cnt'),
            )
            .filter(IClockTransaction.punch_time >= cutoff)
            .group_by(func.date(IClockTransaction.punch_time))
            .order_by(func.date(IClockTransaction.punch_time))
            .all()
        )

        daily_usage = {str(row.day): row.cnt for row in daily_rows}
        usage_values = list(daily_usage.values())

        avg_daily = round(sum(usage_values) / len(usage_values), 2) if usage_values else 0
        peak = max(usage_values) if usage_values else 0
        minimum = min(usage_values) if usage_values else 0

        recent_avg = sum(usage_values[-7:]) / 7 if len(usage_values) >= 7 else avg_daily
        prev_avg = sum(usage_values[-14:-7]) / 7 if len(usage_values) >= 14 else avg_daily
        growth_trend = round(((recent_avg - prev_avg) / prev_avg) * 100, 2) if prev_avg > 0 else 0

        return {
            "success": True,
            "period_days": days,
            "daily_usage": daily_usage,
            "trends": {
                "average_daily_usage": avg_daily,
                "peak_daily_usage": peak,
                "minimum_daily_usage": minimum,
                "growth_trend_percent": growth_trend,
            },
            "compliance_status": "good" if growth_trend >= -10 else "needs_attention",
            "generated_at": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get usage trends: {str(e)}")


# ─── Comprehensive Dashboard ──────────────────────────────────────────────────

@router.get("/dashboard")
async def get_biotime_analytics_dashboard(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Composite BioTime analytics dashboard — all key metrics in one call."""
    try:
        sync_status = await biotime_sync_service.get_sync_status()

        total_personnel = db.query(func.count(Personnel.id)).filter(Personnel.is_active == True).scalar() or 0
        biometric_enrolled = db.query(func.count(Personnel.id)).filter(Personnel.is_active == True).filter(
            Personnel.biometric_enrolled == True
        ).scalar() or 0

        total_transactions = db.query(func.count(IClockTransaction.id)).scalar() or 0
        recent_cutoff = datetime.utcnow() - timedelta(hours=24)
        recent_24h = db.query(func.count(IClockTransaction.id)).filter(
            IClockTransaction.punch_time >= recent_cutoff
        ).scalar() or 0

        online_devices = db.query(func.count(IClockTerminal.id)).filter(
            IClockTerminal.state == 1
        ).scalar() or 0
        total_devices = db.query(func.count(IClockTerminal.id)).scalar() or 0

        enrollment_rate = round((biometric_enrolled / total_personnel) * 100, 2) if total_personnel > 0 else 0

        alerts = []
        if total_personnel > 0 and enrollment_rate < 80:
            alerts.append(f"Biometric enrollment at {enrollment_rate}% — below 80% target")
        if total_devices > 0 and online_devices < total_devices:
            alerts.append(f"{total_devices - online_devices} device(s) offline")

        return {
            "success": True,
            "overview": {
                "total_personnel": total_personnel,
                "biometric_enrolled": biometric_enrolled,
                "enrollment_rate": enrollment_rate,
                "total_transactions": total_transactions,
                "recent_activity_24h": recent_24h,
                "online_devices": online_devices,
                "total_devices": total_devices,
            },
            "sync_status": sync_status,
            "alerts": alerts,
            "generated_at": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get analytics dashboard: {str(e)}")
