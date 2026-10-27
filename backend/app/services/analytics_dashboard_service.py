"""
Analytics Dashboard Service
Advanced analytics and dashboard data aggregation
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger(__name__)


class AnalyticsDashboardService:
    """
    Advanced analytics dashboard service
    - Attendance trends analysis
    - Headcount analytics
    - Compliance metrics
    - Performance monitoring
    - Real-time dashboards
    """
    
    def __init__(self):
        """Initialize analytics dashboard service"""
    
    def get_attendance_trends(self, db: Session, period: str = 'monthly', 
                             start_date: Optional[date] = None, 
                             end_date: Optional[date] = None) -> Dict[str, Any]:
        """
        Get attendance trends analysis
        
        Args:
            db: Database session
            period: Period type (daily, weekly, monthly)
            start_date: Start date
            end_date: End date
            
        Returns:
            Attendance trends data
        """
        try:
            if not start_date:
                start_date = date.today() - timedelta(days=30)
            if not end_date:
                end_date = date.today()
            
            # Get daily attendance data
            query = """
                SELECT 
                    DATE(punch_time) as date,
                    COUNT(DISTINCT emp_code) as unique_employees,
                    COUNT(*) as total_transactions,
                    AVG(EXTRACT(EPOCH FROM (MAX(punch_time) - MIN(punch_time)))/3600) as avg_work_hours
                FROM iclock_transaction
                WHERE DATE(punch_time) BETWEEN :start_date AND :end_date
                GROUP BY DATE(punch_time)
                ORDER BY date
            """
            
            result = db.execute(text(query), {
                'start_date': start_date,
                'end_date': end_date
            })
            
            trends = []
            for row in result:
                trends.append({
                    'date': row[0].isoformat() if row[0] else None,
                    'unique_employees': row[1],
                    'total_transactions': row[2],
                    'avg_work_hours': round(row[3], 2) if row[3] else 0
                })
            
            # Calculate overall statistics
            total_days = len(trends)
            avg_daily_employees = sum(t['unique_employees'] for t in trends) / total_days if total_days > 0 else 0
            avg_work_hours = sum(t['avg_work_hours'] for t in trends) / total_days if total_days > 0 else 0
            
            return {
                'period': period,
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'trends': trends,
                'summary': {
                    'total_days': total_days,
                    'avg_daily_employees': round(avg_daily_employees, 2),
                    'avg_work_hours': round(avg_work_hours, 2)
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting attendance trends: {e}")
            return {'error': str(e)}
    
    def get_headcount_analytics(self, db: Session, target_date: date = None) -> Dict[str, Any]:
        """
        Get headcount analytics for a specific date
        
        Args:
            db: Database session
            target_date: Target date (default: today)
            
        Returns:
            Headcount analytics data
        """
        try:
            if not target_date:
                target_date = date.today()
            
            # Get total personnel count
            total_result = db.execute(text("""
                SELECT COUNT(*) FROM personnel_employee WHERE status = 0
            """))
            total_count = total_result.fetchone()[0]
            
            # Get onboard count
            onboard_result = db.execute(text("""
                SELECT COUNT(*) FROM personnel_employee 
                WHERE status = 0 AND is_onboard = TRUE
            """))
            onboard_count = onboard_result.fetchone()[0]
            
            # Get present count (based on attendance)
            present_result = db.execute(text("""
                SELECT COUNT(DISTINCT emp_code) FROM iclock_transaction
                WHERE DATE(punch_time) = :target_date
            """), {'target_date': target_date})
            present_count = present_result.fetchone()[0]
            
            # Get count by department
            dept_result = db.execute(text("""
                SELECT 
                    pd.dept_name,
                    COUNT(pe.id) as total_employees,
                    SUM(CASE WHEN pe.is_onboard = TRUE THEN 1 ELSE 0 END) as onboard_count
                FROM personnel_employee pe
                LEFT JOIN (SELECT id, name AS dept_name FROM departments) pd ON pe.dept_id = pd.id
                WHERE pe.status = 0
                GROUP BY pd.dept_name
                ORDER BY total_employees DESC
            """))
            
            department_breakdown = []
            for row in dept_result:
                department_breakdown.append({
                    'department': row[0],
                    'total_employees': row[1],
                    'onboard_count': row[2]
                })
            
            return {
                'date': target_date.isoformat(),
                'total_employees': total_count,
                'onboard_count': onboard_count,
                'present_count': present_count,
                'absent_count': onboard_count - present_count,
                'attendance_rate': round((present_count / onboard_count * 100), 2) if onboard_count > 0 else 0,
                'department_breakdown': department_breakdown
            }
            
        except Exception as e:
            logger.error(f"Error getting headcount analytics: {e}")
            return {'error': str(e)}
    
    def get_compliance_metrics(self, db: Session, start_date: date = None, 
                               end_date: date = None) -> Dict[str, Any]:
        """
        Get compliance metrics
        
        Args:
            db: Database session
            start_date: Start date
            end_date: End date
            
        Returns:
            Compliance metrics data
        """
        try:
            if not start_date:
                start_date = date.today() - timedelta(days=30)
            if not end_date:
                end_date = date.today()
            
            # Calculate attendance compliance
            attendance_result = db.execute(text("""
                SELECT 
                    COUNT(DISTINCT emp_code) as total_employees,
                    COUNT(DISTINCT CASE WHEN DATE(punch_time) BETWEEN :start_date AND :end_date THEN emp_code END) as employees_with_attendance
                FROM personnel_employee
                WHERE status = 0
            """), {'start_date': start_date, 'end_date': end_date})
            
            attendance_row = attendance_result.fetchone()
            attendance_compliance = round((attendance_row[1] / attendance_row[0] * 100), 2) if attendance_row[0] > 0 else 0
            
            # Calculate overtime compliance
            overtime_result = db.execute(text("""
                SELECT 
                    COUNT(*) as total_overtime,
                    SUM(CASE WHEN status = 1 THEN 1 ELSE 0 END) as approved_overtime
                FROM overtime_record
                WHERE overtime_date BETWEEN :start_date AND :end_date
            """), {'start_date': start_date, 'end_date': end_date})
            
            overtime_row = overtime_result.fetchone()
            overtime_compliance = round((overtime_row[1] / overtime_row[0] * 100), 2) if overtime_row[0] > 0 else 0
            
            # Calculate leave request compliance
            leave_result = db.execute(text("""
                SELECT 
                    COUNT(*) as total_leaves,
                    SUM(CASE WHEN status = 1 THEN 1 ELSE 0 END) as approved_leaves
                FROM att_leave
                WHERE start_date BETWEEN :start_date AND :end_date
            """), {'start_date': start_date, 'end_date': end_date})
            
            leave_row = leave_result.fetchone()
            leave_compliance = round((leave_row[1] / leave_row[0] * 100), 2) if leave_row[0] > 0 else 0
            
            return {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'attendance_compliance': attendance_compliance,
                'overtime_compliance': overtime_compliance,
                'leave_compliance': leave_compliance,
                'overall_compliance': round((attendance_compliance + overtime_compliance + leave_compliance) / 3, 2)
            }
            
        except Exception as e:
            logger.error(f"Error getting compliance metrics: {e}")
            return {'error': str(e)}
    
    def get_device_analytics(self, db: Session) -> Dict[str, Any]:
        """
        Get device analytics and performance metrics
        
        Args:
            db: Database session
            
        Returns:
            Device analytics data
        """
        try:
            # Get device status
            status_result = db.execute(text("""
                SELECT 
                    COUNT(*) as total_devices,
                    SUM(CASE WHEN status = 1 THEN 1 ELSE 0 END) as online_devices,
                    SUM(CASE WHEN status = 0 THEN 1 ELSE 0 END) as offline_devices,
                    SUM(CASE WHEN status = 2 THEN 1 ELSE 0 END) as error_devices
                FROM devicemap
            """))
            
            status_row = status_result.fetchone()
            
            # Get device transaction statistics
            transaction_result = db.execute(text("""
                SELECT 
                    terminal_sn,
                    COUNT(*) as transaction_count,
                    MIN(punch_time) as first_transaction,
                    MAX(punch_time) as last_transaction
                FROM iclock_transaction
                WHERE punch_time >= NOW() - INTERVAL '7 days'
                GROUP BY terminal_sn
                ORDER BY transaction_count DESC
            """))
            
            device_stats = []
            for row in transaction_result:
                device_stats.append({
                    'device_sn': row[0],
                    'transaction_count': row[1],
                    'first_transaction': row[2].isoformat() if row[2] else None,
                    'last_transaction': row[3].isoformat() if row[3] else None
                })
            
            return {
                'total_devices': status_row[0],
                'online_devices': status_row[1],
                'offline_devices': status_row[2],
                'error_devices': status_row[3],
                'device_health_percentage': round((status_row[1] / status_row[0] * 100), 2) if status_row[0] > 0 else 0,
                'device_statistics': device_stats
            }
            
        except Exception as e:
            logger.error(f"Error getting device analytics: {e}")
            return {'error': str(e)}
    
    def get_department_analytics(self, db: Session, department_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Get department-wise analytics
        
        Args:
            db: Database session
            department_id: Optional department filter
            
        Returns:
            Department analytics data
        """
        try:
            query = """
                SELECT 
                    pd.id as department_id,
                    pd.dept_name,
                    COUNT(pe.id) as total_employees,
                    SUM(CASE WHEN p.is_onboard = TRUE THEN 1 ELSE 0 END) as onboard_count,
                    AVG(CASE WHEN it.emp_code IS NOT NULL THEN 1 ELSE 0 END) as attendance_rate
                FROM (SELECT id, name AS dept_name FROM departments) pd
                LEFT JOIN personnel_employee pe ON pd.id = pe.dept_id AND pe.status = 0
                LEFT JOIN personnel p ON p.emp_code = pe.emp_code
                LEFT JOIN (
                    SELECT DISTINCT emp_code, DATE(punch_time) as punch_date
                    FROM iclock_transaction
                    WHERE DATE(punch_time) >= CURRENT_DATE - INTERVAL '30 days'
                ) it ON pe.emp_code = it.emp_code
            """
            
            params = {}
            
            if department_id:
                query += " WHERE pd.id = :department_id"
                params['department_id'] = department_id
            
            query += " GROUP BY pd.id, pd.dept_name ORDER BY total_employees DESC"
            
            result = db.execute(text(query), params)
            
            departments = []
            for row in result:
                departments.append({
                    'department_id': row[0],
                    'department_name': row[1],
                    'total_employees': row[2],
                    'onboard_count': row[3],
                    'attendance_rate': round((row[4] * 100), 2) if row[4] else 0
                })
            
            return {
                'departments': departments,
                'total_departments': len(departments)
            }
            
        except Exception as e:
            logger.error(f"Error getting department analytics: {e}")
            return {'error': str(e)}
    
    def get_realtime_dashboard(self, db: Session) -> Dict[str, Any]:
        """
        Get real-time dashboard data
        
        Args:
            db: Database session
            
        Returns:
            Real-time dashboard data
        """
        try:
            today = date.today()
            
            # Get today's headcount
            headcount = self.get_headcount_analytics(db, today)
            
            # Get device status
            devices = self.get_device_analytics(db)
            
            # Get today's attendance
            attendance_result = db.execute(text("""
                SELECT 
                    COUNT(DISTINCT emp_code) as present_today,
                    COUNT(*) as total_transactions_today
                FROM iclock_transaction
                WHERE DATE(punch_time) = :today
            """), {'today': today})
            
            attendance_row = attendance_result.fetchone()
            
            # Get active mustering events
            mustering_result = db.execute(text("""
                SELECT COUNT(*) FROM mustering_event WHERE status = 0
            """))
            active_mustering = mustering_result.fetchone()[0]
            
            return {
                'timestamp': datetime.utcnow().isoformat(),
                'headcount': headcount,
                'devices': {
                    'total': devices['total_devices'],
                    'online': devices['online_devices'],
                    'offline': devices['offline_devices'],
                    'health_percentage': devices['device_health_percentage']
                },
                'attendance': {
                    'present_today': attendance_row[0],
                    'total_transactions_today': attendance_row[1]
                },
                'mustering': {
                    'active_events': active_mustering
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting realtime dashboard: {e}")
            return {'error': str(e)}


# Global analytics dashboard service instance
analytics_dashboard_service = AnalyticsDashboardService()
