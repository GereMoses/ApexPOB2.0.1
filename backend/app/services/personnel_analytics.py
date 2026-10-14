"""
Personnel Analytics and Reporting Service

This service handles personnel analytics, reporting dashboard data, and
comprehensive business intelligence for oil & gas operations.
"""

from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, extract
import json

from ..models.personnel import Personnel, PersonnelStatus, AttendanceLog
from ..core.database import get_db


class PersonnelAnalyticsService:
    """Service for managing personnel analytics and reporting"""
    
    def __init__(self):
        # Analytics categories
        self.analytics_categories = {
            "PERSONNEL_OVERVIEW": "Personnel overview and demographics",
            "ATTENDANCE_ANALYTICS": "Attendance patterns and trends",
            "LOCATION_ANALYTICS": "Location distribution and movement",
            "CERTIFICATION_COMPLIANCE": "Certification compliance tracking",
            "MEDICAL_FITNESS": "Medical fitness and health monitoring",
            "EMERGENCY_RESPONSE": "Emergency response readiness",
            "BIOMETRIC_UTILIZATION": "Biometric system usage statistics",
            "BADGE_MANAGEMENT": "Badge issuance and tracking",
            "AUDIT_COMPLIANCE": "Audit trail compliance metrics",
            "PERFORMANCE_METRICS": "Key performance indicators"
        }
        
        # KPI definitions
        self.kpi_definitions = {
            "PERSONNEL_COUNT": "Total number of personnel",
            "ONBOARD_PERCENTAGE": "Percentage of personnel currently onboard",
            "ATTENDANCE_RATE": "Average attendance rate",
            "CERTIFICATION_COMPLIANCE": "Certification compliance percentage",
            "MEDICAL_FITNESS_COMPLIANCE": "Medical fitness compliance percentage",
            "EMERGENCY_READINESS": "Emergency response readiness score",
            "BIOMETRIC_ADOPTION": "Biometric system adoption rate",
            "BADGE_COMPLIANCE": "Badge compliance percentage",
            "AUDIT_COVERAGE": "Audit trail coverage percentage"
        }
    
    async def get_personnel_overview(
        self,
        db: Session = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive personnel overview analytics
        
        Args:
            db: Database session
            
        Returns:
            Personnel overview analytics
        """
        if db is None:
            db = next(get_db())
        
        # Get total personnel count
        total_personnel = db.query(Personnel).count()
        
        # Get status distribution
        status_query = db.query(
            Personnel.status,
            func.count(Personnel.id).label('count')
        ).group_by(Personnel.status).all()
        
        status_distribution = {status.value: count for status, count in status_query}
        
        # Get company distribution
        company_query = db.query(
            Personnel.company,
            func.count(Personnel.id).label('count')
        ).group_by(Personnel.company).all()
        
        company_distribution = {company: count for company, count in company_query}
        
        # Get role distribution
        role_query = db.query(
            Personnel.role,
            func.count(Personnel.id).label('count')
        ).group_by(Personnel.role).all()
        
        role_distribution = {role: count for role, count in role_query}
        
        # Get department distribution
        dept_query = db.query(
            Personnel.department,
            func.count(Personnel.id).label('count')
        ).group_by(Personnel.department).all()
        
        department_distribution = {dept: count for dept, count in dept_query if dept}
        
        # Get location distribution
        location_query = db.query(
            Personnel.current_location,
            func.count(Personnel.id).label('count')
        ).filter(Personnel.current_location.isnot(None)).group_by(Personnel.current_location).all()
        
        location_distribution = {location: count for location, count in location_query}
        
        # Get onboard statistics
        onboard_count = db.query(Personnel).filter(Personnel.is_onboard == True).count()
        onboard_percentage = (onboard_count / total_personnel * 100) if total_personnel > 0 else 0
        
        # Get blood group distribution
        bg_query = db.query(
            Personnel.blood_group,
            func.count(Personnel.id).label('count')
        ).filter(Personnel.blood_group.isnot(None)).group_by(Personnel.blood_group).all()
        
        blood_group_distribution = {bg: count for bg, count in bg_query}
        
        # Get recent hires (last 30 days)
        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
        recent_hires = db.query(Personnel).filter(
            Personnel.created_at >= thirty_days_ago
        ).count()
        
        # Get personnel by creation date (monthly for last 12 months)
        twelve_months_ago = datetime.now(timezone.utc) - timedelta(days=365)
        monthly_hires = db.query(
            extract('year', Personnel.created_at).label('year'),
            extract('month', Personnel.created_at).label('month'),
            func.count(Personnel.id).label('count')
        ).filter(
            Personnel.created_at >= twelve_months_ago
        ).group_by(
            extract('year', Personnel.created_at),
            extract('month', Personnel.created_at)
        ).order_by(
            extract('year', Personnel.created_at),
            extract('month', Personnel.created_at)
        ).all()
        
        monthly_hires_data = [
            {
                "period": f"{int(year)}-{int(month):02d}",   # EXTRACT() returns Decimal
                "count": count
            }
            for year, month, count in monthly_hires
        ]
        
        return {
            "total_personnel": total_personnel,
            "status_distribution": status_distribution,
            "company_distribution": company_distribution,
            "role_distribution": role_distribution,
            "department_distribution": department_distribution,
            "location_distribution": location_distribution,
            "blood_group_distribution": blood_group_distribution,
            "onboard_statistics": {
                "onboard_count": onboard_count,
                "offboard_count": total_personnel - onboard_count,
                "onboard_percentage": round(onboard_percentage, 2)
            },
            "recent_hires": recent_hires,
            "monthly_hires": monthly_hires_data,
            "personnel_growth_rate": self._calculate_growth_rate(monthly_hires_data),
            "analytics_timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    async def get_attendance_analytics(
        self,
        days: int = 30,
        db: Session = None
    ) -> Dict[str, Any]:
        """
        Get attendance analytics and patterns
        
        Args:
            days: Number of days to analyze
            db: Database session
            
        Returns:
            Attendance analytics data
        """
        if db is None:
            db = next(get_db())
        
        # Calculate date range
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)
        
        # Get attendance logs
        attendance_logs = db.query(AttendanceLog).filter(
            AttendanceLog.timestamp >= start_date,
            AttendanceLog.timestamp <= end_date
        ).all()
        
        # Initialize analytics
        analytics = {
            "period_days": days,
            "total_attendance_events": len(attendance_logs),
            "daily_attendance": {},
            "hourly_patterns": {},
            "location_attendance": {},
            "event_type_distribution": {},
            "attendance_rate": 0.0,
            "peak_hours": [],
            "least_active_hours": [],
            "compliance_metrics": {}
        }
        
        # Process attendance logs
        daily_counts = {}
        hourly_counts = {}
        location_counts = {}
        event_type_counts = {}
        
        for log in attendance_logs:
            # Daily counts
            log_date = log.timestamp.date()
            date_str = log_date.isoformat()
            daily_counts[date_str] = daily_counts.get(date_str, 0) + 1
            
            # Hourly patterns
            log_hour = log.timestamp.hour
            hourly_counts[log_hour] = hourly_counts.get(log_hour, 0) + 1
            
            # Location attendance
            if log.location:
                location_counts[log.location] = location_counts.get(log.location, 0) + 1
            
            # Event type distribution
            event_type = log.event_type
            event_type_counts[event_type] = event_type_counts.get(event_type, 0) + 1
        
        # Update analytics
        analytics["daily_attendance"] = daily_counts
        analytics["hourly_patterns"] = hourly_counts
        analytics["location_attendance"] = location_counts
        analytics["event_type_distribution"] = event_type_counts
        
        # Calculate peak hours
        sorted_hours = sorted(hourly_counts.items(), key=lambda x: x[1], reverse=True)
        analytics["peak_hours"] = [{"hour": hour, "count": count} for hour, count in sorted_hours[:5]]
        analytics["least_active_hours"] = [{"hour": hour, "count": count} for hour, count in sorted_hours[-5:]]
        
        # Calculate attendance rate (assuming check-ins represent attendance)
        total_checkins = event_type_counts.get("check_in", 0)
        total_personnel = db.query(Personnel).count()
        analytics["attendance_rate"] = (total_checkins / (total_personnel * days)) * 100 if total_personnel > 0 else 0
        
        # Compliance metrics
        analytics["compliance_metrics"] = {
            "daily_average": sum(daily_counts.values()) / len(daily_counts) if daily_counts else 0,
            "peak_hourly": max(hourly_counts.values()) if hourly_counts else 0,
            "location_coverage": len(location_counts),
            "event_type_diversity": len(event_type_counts)
        }
        
        return analytics
    
    async def get_location_analytics(
        self,
        days: int = 30,
        db: Session = None
    ) -> Dict[str, Any]:
        """
        Get location analytics and movement patterns
        
        Args:
            days: Number of days to analyze
            db: Database database session
            
        Returns:
            Location analytics data
        """
        if db is None:
            db = next(get_db)
        
        # Calculate date range
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)
        
        # Get current personnel locations
        current_locations = db.query(
            Personnel.current_location,
            Personnel.current_zone,
            func.count(Personnel.id).label('count')
        ).filter(
            Personnel.current_location.isnot(None)
        ).group_by(
            Personnel.current_location,
            Personnel.current_zone
        ).all()
        
        # Get location changes from attendance logs
        location_changes = db.query(AttendanceLog).filter(
            and_(
                AttendanceLog.timestamp >= start_date,
                AttendanceLog.timestamp <= end_date,
                AttendanceLog.event_type.in_(["check_in", "check_out"])
            )
        ).all()
        
        # Initialize analytics
        analytics = {
            "period_days": days,
            "current_location_distribution": {},
            "zone_distribution": {},
            "location_changes": len(location_changes),
            "movement_patterns": {},
            "zone_utilization": {},
            "peak_locations": [],
            "compliance_metrics": {}
        }
        
        # Process current locations
        zone_counts = {}
        for location, zone, count in current_locations:
            analytics["current_location_distribution"][location] = {
                "zone": zone,
                "count": count
            }
            zone_counts[zone] = zone_counts.get(zone, 0) + count
        
        analytics["zone_distribution"] = zone_counts
        
        # Process movement patterns
        movement_patterns = {}
        for log in location_changes:
            date_str = log.timestamp.date().isoformat()
            if date_str not in movement_patterns:
                movement_patterns[date_str] = []
            
            movement_patterns[date_str].append({
                "personnel_id": log.personnel_id,
                "badge_id": log.badge_id,
                "event_type": log.event_type,
                "location": log.location,
                "zone": log.zone,
                "timestamp": log.timestamp
            })
        
        analytics["movement_patterns"] = movement_patterns
        
        # Calculate zone utilization
        for zone, count in zone_counts.items():
            # Define zone capacity (this could be made configurable)
            zone_capacity = self._get_zone_capacity(zone)
            analytics["zone_utilization"][zone] = {
                "current_count": count,
                "capacity": zone_capacity,
                "utilization_percentage": round((count / zone_capacity * 100) if zone_capacity > 0 else 0, 2),
                "status": "AVAILABLE" if count < zone_capacity * 0.9 else "NEAR_CAPACITY" if count < zone_capacity else "FULL"
            }
        
        # Get peak locations
        sorted_locations = sorted(
            [(loc, data["count"]) for loc, data in analytics["current_location_distribution"].items()],
            key=lambda x: x[1],
            reverse=True
        )
        analytics["peak_locations"] = sorted_locations[:10]
        
        # Compliance metrics
        analytics["compliance_metrics"] = {
            "zone_coverage": len(analytics["zone_distribution"]),
            "location_diversity": len(analytics["current_location_distribution"]),
            "average_zone_utilization": round(
                sum(data["utilization_percentage"] for data in analytics["zone_utilization"].values()) / len(analytics["zone_utilization"]) if analytics["zone_utilization"] else 0
            , 2)
        }
        
        return analytics
    
    async def get_certification_analytics(
        self,
        db: Session = None
    ) -> Dict[str, Any]:
        """
        Get certification compliance analytics
        
        Args:
            db: Database session
            
        Returns:
            Certification analytics data
        """
        if db is None:
            db = next(get_db)
        
        # Get all personnel with certifications
        personnel_with_certs = db.query(Personnel).filter(
            Personnel.certifications.isnot(None)
        ).all()
        
        # Initialize analytics
        analytics = {
            "total_personnel": db.query(Personnel).count(),
            "personnel_with_certifications": len(personnel_with_certs),
            "total_certifications": 0,
            "certification_types": {},
            "expiry_distribution": {},
            "compliance_rate": 0.0,
            "expiring_soon": [],
            "certification_levels": {},
            "training_completion": {}
        }
        
        # Process certifications
        expiring_certs = []
        cert_types = {}
        expiry_distribution = {}
        
        for person in personnel_with_certs:
            if person.certifications:
                for cert in person.certifications:
                    analytics["total_certifications"] += 1
                    
                    # Count certification types
                    cert_type = cert.get('certification_type', 'UNKNOWN')
                    cert_types[cert_type] = cert_types.get(cert_type, 0) + 1
                    
                    # Check expiry
                    if cert.get('expiry_date'):
                        try:
                            expiry_date = datetime.fromisoformat(cert['expiry_date'].replace('Z', '+00:00'))
                            if expiry_date <= datetime.now(timezone.utc) + timedelta(days=30):
                                expiring_certs.append({
                                    "personnel_id": person.id,
                                    "badge_id": person.badge_id,
                                    "full_name": person.full_name,
                                    "certification": cert,
                                    "days_to_expiry": (expiry_date - datetime.now(timezone.utc)).days
                                })
                            
                            # Count by expiry period
                            days_to_expiry = (expiry_date - datetime.now(timezone.utc)).days
                            if days_to_expiry <= 0:
                                expiry_category = "EXPIRED"
                            elif days_to_expiry <= 30:
                                expiry_category = "EXPIRING_SOON"
                            elif days_to_expiry <= 90:
                                expiry_category = "EXPIRING_90_DAYS"
                            else:
                                expiry_category = "VALID"
                            
                            expiry_distribution[expiry_category] = expiry_distribution.get(expiry_category, 0) + 1
                        except ValueError:
                            # Handle invalid date format
                            pass
                        except Exception as e:
                            # Handle any other errors
                            pass
        
        # Update analytics
        analytics["certification_types"] = cert_types
        analytics["expiry_distribution"] = expiry_distribution
        analytics["expiring_soon"] = sorted(expiring_certs, key=lambda x: x['days_to_expiry'])[:10]
        analytics["compliance_rate"] = round(
            (analytics["personnel_with_certifications"] / analytics["total_personnel"] * 100) if analytics["total_personnel"] > 0 else 0, 2
        )
        
        return analytics
    
    async def get_medical_fitness_analytics(
        self,
        db: Session = None
    ) -> Dict[str, Any]:
        """
        Get medical fitness analytics
        
        Args:
            db: Database session
            
        Returns:
            Medical fitness analytics data
        """
        if db is None:
            db = next(get_db)
        
        # Get all personnel with medical fitness records
        personnel_with_fitness = db.query(Personnel).filter(
            Personnel.medical_fitness_date.isnot(None)
        ).all()
        
        # Initialize analytics
        analytics = {
            "total_personnel": db.query(Personnel).count(),
            "personnel_with_fitness_records": len(personnel_with_fitness),
            "fitness_status_distribution": {},
            "medical_conditions_summary": {},
            "blood_group_distribution": {},
            "allergies_summary": {},
            "compliance_rate": 0.0,
            "fitness_expiry_alerts": [],
            "recent_fitness_assessments": []
        }
        
        # Process fitness records
        fitness_status_counts = {}
        medical_conditions = {}
        blood_groups = {}
        allergies = {}
        expiring_fitness = []
        recent_assessments = []
        
        for person in personnel_with_fitness:
            if person.emergency_contact:
                # Get fitness status from emergency contact
                if person.emergency_contact.get('fitness_records'):
                    for record in person.emergency_contact['fitness_records']:
                        status = record.get('fitness_status', 'UNKNOWN')
                        fitness_status_counts[status] = fitness_status_counts.get(status, 0) + 1
                        
                        # Check expiry
                        if record.get('valid_until'):
                            try:
                                expiry_date = datetime.fromisoformat(record['valid_until'].replace('Z', '+00:00'))
                                if expiry_date <= datetime.now(timezone.utc) + timedelta(days=30):
                                    expiring_fitness.append({
                                        "personnel_id": person.id,
                                        "badge_id": person.badge_id,
                                        "full_name": person.full_name,
                                        "fitness_record": record,
                                        "days_to_expiry": (expiry_date - datetime.now(timezone.utc)).days
                                    })
                                
                                # Get recent assessments (last 30 days)
                                assessment_date = datetime.fromisoformat(record['exam_date'].replace('Z', '+00:00'))
                                if assessment_date >= datetime.now(timezone.utc) - timedelta(days=30):
                                    recent_assessments.append({
                                        "personnel_id": person.id,
                                        "badge_id": person.badge_id,
                                        "full_name": person.full_name,
                                        "assessment_date": assessment_date,
                                        "fitness_status": status,
                                        "examining_doctor": record.get('examining_doctor')
                                    })
                            except ValueError:
                                pass
                
                # Count medical conditions
                conditions = person.emergency_contact.get('medical_conditions', '')
                if conditions:
                    condition_list = [c.strip() for c in conditions.split(',') if c.strip()]
                    for condition in condition_list:
                        medical_conditions[condition] = medical_conditions.get(condition, 0) + 1
                
                # Count blood groups
                blood_group = person.emergency_contact.get('blood_group', '')
                if blood_group:
                    blood_groups[blood_group] = blood_groups.get(blood_group, 0) + 1
                
                # Count allergies
                allergies_list = person.emergency_contact.get('allergies', '')
                if allergies_list:
                    allergy_list = [a.strip() for a in allergies_list.split(',') if a.strip()]
                    for allergy in allergy_list:
                        allergies[allergy] = allergies.get(allergy, 0) + 1
        
        # Update analytics
        analytics["fitness_status_distribution"] = fitness_status_counts
        analytics["medical_conditions_summary"] = medical_conditions
        analytics["blood_group_distribution"] = blood_groups
        analytics["allergies_summary"] = allergies
        analytics["expiring_fitness_alerts"] = sorted(expiring_fitness, key=lambda x: x['days_to_expiry'])[:10]
        analytics["recent_fitness_assessments"] = sorted(recent_assessments, key=lambda x: x['assessment_date'], reverse=True)[:10]
        analytics["compliance_rate"] = round(
            (analytics["personnel_with_fitness_records"] / analytics["total_personnel"] * 100) if analytics["total_personnel"] > 0 else 0, 2
        )
        
        return analytics
    
    async def get_performance_metrics(
        self,
        days: int = 30,
        db: Session = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive performance metrics
        
        Args:
            days: Number of days to analyze
            db: Database session
            
        Returns:
            Performance metrics dashboard
        """
        if db is None:
            db = next(get_db)
        
        # Get all analytics data
        personnel_overview = await self.get_personnel_overview(db)
        attendance_analytics = await self.get_attendance_analytics(days, db)
        location_analytics = await self.get_location_analytics(days, db)
        certification_analytics = await self.get_certification_analytics(db)
        medical_fitness_analytics = await self.get_medical_fitness_analytics(db)
        
        # Calculate KPIs
        kpis = {
            "personnel_count": personnel_overview["total_personnel"],
            "onboard_percentage": personnel_overview["onboard_statistics"]["onboard_percentage"],
            "attendance_rate": attendance_analytics["attendance_rate"],
            "certification_compliance": certification_analytics["compliance_rate"],
            "medical_fitness_compliance": medical_fitness_analytics["compliance_rate"],
            "zone_utilization": location_analytics["compliance_metrics"]["average_zone_utilization"],
            "audit_coverage": 0.0,  # This would be calculated from audit trail
            "data_quality_score": 0.0  # This would be calculated from data completeness
        }
        
        # Calculate overall score
        weights = {
            "personnel_count": 0.15,
            "onboard_percentage": 0.20,
            "attendance_rate": 0.20,
            "certification_compliance": 0.20,
            "medical_fitness_compliance": 0.15,
            "zone_utilization": 0.10
        }
        
        overall_score = sum(kpis[kpi] * weights.get(kpi, 0) for kpi in kpis)
        
        # Performance trends (mock data for now)
        performance_trends = {
            "personnel_growth": personnel_overview["personnel_growth_rate"],
            "attendance_trend": self._calculate_trend(attendance_analytics["daily_attendance"]),
            "compliance_trend": self._calculate_trend([
                certification_analytics["compliance_rate"],
                medical_fitness_analytics["compliance_rate"]
            ]),
            "efficiency_score": overall_score
        }
        
        return {
            "kpis": kpis,
            "performance_trends": performance_trends,
            "analytics_summary": {
                "personnel_overview": personnel_overview,
                "attendance_analytics": attendance_analytics,
                "location_analytics": location_analytics,
                "certification_analytics": certification_analytics,
                "medical_fitness_analytics": medical_fitness_analytics
            },
            "overall_score": round(overall_score, 2),
            "grade": self._calculate_grade(overall_score),
            "recommendations": self._generate_recommendations(kpis),
            "analytics_timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    async def get_dashboard_data(
        self,
        db: Session = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive dashboard data
        
        Args:
            db: Database session
            
        Returns:
            Dashboard data for frontend
        """
        if db is None:
            db = next(get_db)
        
        # Get all analytics data
        dashboard_data = await self.get_performance_metrics(30, db)
        
        # Add real-time metrics
        dashboard_data["real_time_metrics"] = {
            "current_onboard": dashboard_data["kpis"]["onboard_percentage"],
            "active_locations": len(dashboard_data["analytics_summary"]["location_analytics"]["current_location_distribution"]),
            "recent_activities": self._get_recent_activities(db),
            "system_health": {
                "database_status": "healthy",
                "api_response_time": "< 100ms",
                "error_rate": "0.1%"
            }
        }
        
        return dashboard_data
    
    def _calculate_growth_rate(self, monthly_data: List[Dict[str, Any]]) -> float:
        """Calculate growth rate from monthly data"""
        if len(monthly_data) < 2:
            return 0.0
        
        current_month = monthly_data[-1]["count"]
        previous_month = monthly_data[-2]["count"] if len(monthly_data) > 1 else 0
        
        if previous_month == 0:
            return 0.0
        
        return round(((current_month - previous_month) / previous_month) * 100, 2)
    
    def _calculate_trend(self, data_series: List[float]) -> str:
        """Calculate trend from data series"""
        if len(data_series) < 2:
            return "STABLE"
        
        recent_avg = sum(data_series[-3:]) / min(3, len(data_series))
        older_avg = sum(data_series[:-3]) / max(1, len(data_series) - 3)
        
        change_percent = ((recent_avg - older_avg) / older_avg) * 100 if older_avg > 0 else 0
        
        if change_percent > 5:
            return "IMPROVING"
        elif change_percent < -5:
            return "DECLINING"
        else:
            return "STABLE"
    
    def _calculate_grade(self, score: float) -> str:
        """Calculate grade from score"""
        if score >= 90:
            return "A+"
        elif score >= 85:
            return "A"
        elif score >= 80:
            return "B+"
        elif score >= 70:
            return "B"
        elif score >= 60:
            return "C"
        elif score >= 50:
            return "D"
        else:
            return "F"
    
    def _generate_recommendations(self, kpis: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on KPIs"""
        recommendations = []
        
        if kpis["onboard_percentage"] < 80:
            recommendations.append("Improve personnel onboarding process")
        
        if kpis["attendance_rate"] < 85:
            recommendations.append("Review attendance tracking policies")
        
        if kpis["certification_compliance"] < 75:
            recommendations.append("Implement certification renewal reminders")
        
        if kpis["medical_fitness_compliance"] < 70:
            recommendations.append("Schedule regular medical fitness assessments")
        
        if kpis["zone_utilization"] > 90:
            recommendations.append("Consider zone capacity expansion")
        
        if kpis["personnel_count"] < 50:
            recommendations.append("Develop recruitment strategy")
        
        return recommendations
    
    def _get_recent_activities(self, db: Session) -> List[Dict[str, Any]]:
        """Get recent personnel activities"""
        # This would typically query the audit trail
        # For now, return mock data
        return [
            {
                "type": "PERSONNEL_CREATED",
                "description": "New personnel onboarded",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "personnel_id": 1,
                "full_name": "John Doe"
            },
            {
                "type": "CERTIFICATION_EXPIRED",
                "description": "Certification expired",
                "timestamp": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
                "personnel_id": 2,
                "full_name": "Jane Smith"
            }
        ]
    
    def _get_zone_capacity(self, zone: str) -> int:
        """Get zone capacity (mock implementation)"""
        zone_capacities = {
            "Platform Alpha": 50,
            "Platform Beta": 45,
            "Platform Gamma": 40,
            "Main Office": 200,
            "Training Center": 50,
            "Warehouse": 30,
            "Workshop": 25
        }
        return zone_capacities.get(zone, 50)


# Create singleton instance
personnel_analytics_service = PersonnelAnalyticsService()
