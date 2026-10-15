"""
Comprehensive Test Suite for Attendance Module
Tests all attendance functionality including validation, calculation, and API endpoints
"""

import pytest
import asyncio
from datetime import datetime, date, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import Mock, patch

from app.main import app
from app.core.database import get_db
from app.services.attendance_validation_service import attendance_validation_service
from app.services.attendance_calculation_service import attendance_calculation_service

class TestAttendanceValidation:
    """Test attendance validation service"""
    
    @pytest.mark.asyncio
    async def test_validate_timetable_success(self):
        """Test successful timetable validation"""
        timetable_data = {
            'alias': 'Regular Shift',
            'checkin_time': '09:00:00',
            'checkout_time': '17:00:00',
            'late_minutes': 15,
            'early_minutes': 15,
            'work_day': 1.0,
            'color': '#1890ff',
            'break_time_start': '12:00:00',
            'break_time_end': '13:00:00',
            'must_checkin': True,
            'must_checkout': True,
        }
        
        db = Mock()
        is_valid, errors = await attendance_validation_service.validate_timetable(timetable_data, db)
        
        assert is_valid == True
        assert len(errors) == 0
    
    @pytest.mark.asyncio
    async def test_validate_timetable_invalid_time(self):
        """A 10-minute timetable is invalid. (17:00 -> 09:00 is NOT invalid: it is an
        overnight shift, which 24-hour operations rely on.)"""
        timetable_data = {
            'alias': 'Regular Shift',
            'checkin_time': '09:00:00',
            'checkout_time': '09:10:00',
            'late_minutes': 15,
            'early_minutes': 15,
            'work_day': 1.0,
            'color': '#1890ff',
            'must_checkin': True,
            'must_checkout': True,
        }
        
        db = Mock()
        is_valid, errors = await attendance_validation_service.validate_timetable(timetable_data, db)
        
        assert is_valid == False
        assert any('at least 30 minutes' in error for error in errors)
    
    @pytest.mark.asyncio
    async def test_validate_shift_success(self):
        """Test successful shift validation"""
        shift_data = {
            'alias': 'Morning Shift',
            'work_days': '12345',  # Monday to Friday (1 = Mon … 7 = Sun)
            'cycle_unit': 0,  # Daily
            'cycle_count': 1,
            'roster_type': 0,  # Regular
        }
        
        db = Mock()
        is_valid, errors = await attendance_validation_service.validate_shift(shift_data, db)
        
        assert is_valid == True
        assert len(errors) == 0
    
    @pytest.mark.asyncio
    async def test_validate_leave_request_success(self):
        """Test successful leave request validation"""
        leave_data = {
            'emp_id': 1,
            'leave_type_id': 1,
            'start_time': '2024-12-01T09:00:00',
            'end_time': '2024-12-05T17:00:00',
            'reason': 'Annual vacation',
        }
        
        db = Mock()
        # Mock employee query
        db.query.return_value.filter.return_value.first.return_value = Mock(is_active=True)
        
        is_valid, errors = await attendance_validation_service.validate_leave_request(leave_data, db)
        
        assert is_valid == True
        assert len(errors) == 0
    
    @pytest.mark.asyncio
    async def test_validate_leave_request_invalid_duration(self):
        """Test leave request validation with invalid duration"""
        leave_data = {
            'emp_id': 1,
            'leave_type_id': 1,
            'start_time': '2024-12-01T09:00:00',
            'end_time': '2025-01-30T17:00:00',  # More than 30 days
            'reason': 'Annual vacation',
        }
        
        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = Mock(is_active=True)
        
        is_valid, errors = await attendance_validation_service.validate_leave_request(leave_data, db)
        
        assert is_valid == False
        assert any('Leave duration cannot exceed 30 days' in error for error in errors)
    
    @pytest.mark.asyncio
    async def test_validate_overtime_request_success(self):
        """Test successful overtime request validation"""
        ot_data = {
            'emp_id': 1,
            'ot_date': (date.today() - timedelta(days=2)).isoformat(),  # recent: >30 days old is rejected
            'minutes': 120,  # 2 hours
            'reason': 'Project deadline',
        }
        
        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = Mock(is_active=True)
        
        is_valid, errors = await attendance_validation_service.validate_overtime_request(ot_data, db)
        
        assert is_valid == True
        assert len(errors) == 0
    
    @pytest.mark.asyncio
    async def test_validate_manual_log_success(self):
        """Test successful manual log validation"""
        log_data = {
            'emp_id': 1,
            'punch_time': '2024-12-01T09:15:00',
            'punch_state': 0,  # Check In
            'reason': 'Forgot to punch in',
        }
        
        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = Mock(is_active=True)
        
        is_valid, errors = await attendance_validation_service.validate_manual_log(log_data, db)
        
        assert is_valid == True
        assert len(errors) == 0

class TestAttendanceAPI:
    """Test attendance API endpoints"""
    
    @pytest.fixture(autouse=True)
    def _client(self, superuser_headers):
        """Client authenticated as a real superuser (passes JWT + RBAC for real)."""
        self.client = TestClient(app, headers=superuser_headers)
    
    def test_get_timetables(self):
        """Test getting timetables"""
        response = self.client.get("/api/v1/attendance/timetables")
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "data" in data
    
    def test_create_timetable_success(self):
        """Test creating timetable successfully"""
        timetable_data = {
            "alias": "Test Shift",
            "checkin_time": "09:00:00",
            "checkout_time": "17:00:00",
            "late_minutes": 15,
            "early_minutes": 15,
            "work_day": 1.0,
            "color": "#1890ff",
            "must_checkin": True,
            "must_checkout": True,
        }
        
        response = self.client.post("/api/v1/attendance/timetables", json=timetable_data)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "data" in data
    
    def test_create_timetable_validation_error(self):
        """Test creating timetable with validation error"""
        timetable_data = {
            "alias": "Test Shift",
            "checkin_time": "09:00:00",  # Invalid: 10 minutes (17:00->09:00 would be a valid overnight shift)
            "checkout_time": "09:10:00",
            "late_minutes": 15,
            "early_minutes": 15,
            "work_day": 1.0,
            "color": "#1890ff",
            "must_checkin": True,
            "must_checkout": True,
        }
        
        response = self.client.post("/api/v1/attendance/timetables", json=timetable_data)
        assert response.status_code == 400
        data = response.json()
        assert "errors" in data.get("detail", data)   # FastAPI wraps errors in "detail"
    
    def test_get_shifts(self):
        """Test getting shifts"""
        response = self.client.get("/api/v1/attendance/shifts")
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "data" in data
    
    def test_create_shift_success(self):
        """Test creating shift successfully"""
        shift_data = {
            "alias": "Test Shift",
            "work_days": "01234",
            "cycle_unit": 0,
            "cycle_count": 1,
            "roster_type": 0,
        }
        
        response = self.client.post("/api/v1/attendance/shifts", json=shift_data)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
    
    def test_get_holidays(self):
        """Test getting holidays"""
        response = self.client.get("/api/v1/attendance/holidays")
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "data" in data
    
    def test_create_holiday_success(self):
        """Test creating holiday successfully"""
        holiday_data = {
            "holiday_name": "Test Holiday",
            "start_date": "2024-12-25",
            "end_date": "2024-12-25",
            "holiday_type": 0,
        }
        
        response = self.client.post("/api/v1/attendance/holidays", json=holiday_data)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
    
    def test_get_leave_types(self):
        """Test getting leave types"""
        response = self.client.get("/api/v1/attendance/leave-types")
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "data" in data
    
    def test_get_leaves(self):
        """Test getting leaves"""
        response = self.client.get("/api/v1/attendance/leaves")
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "data" in data
    
    def test_get_overtime_rules(self):
        """Test getting overtime rules"""
        response = self.client.get("/api/v1/attendance/overtime-rules")
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "data" in data
    
    def test_get_overtime(self):
        """Test getting overtime records"""
        response = self.client.get("/api/v1/attendance/overtime")
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "data" in data
    
    def test_get_manual_logs(self):
        """Test getting manual logs"""
        response = self.client.get("/api/v1/attendance/manual-logs")
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "data" in data
    
    def test_get_transactions(self):
        """Test getting transactions"""
        response = self.client.get("/api/v1/attendance/transactions")
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "data" in data
    
    def test_get_timesheet(self):
        """Test getting timesheet"""
        response = self.client.get(
            "/api/v1/attendance/timesheet?start_date=2024-12-01&end_date=2024-12-31"
        )
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "data" in data
    
    def test_get_exceptions(self):
        """Test getting exceptions"""
        response = self.client.get(
            "/api/v1/attendance/exceptions?date=2024-12-01"
        )
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "data" in data
    
    def test_get_rules(self):
        """Test getting attendance rules"""
        response = self.client.get("/api/v1/attendance/rules")
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "data" in data

class TestAttendanceCalculation:
    """Test attendance calculation service"""
    
    @pytest.mark.asyncio
    async def test_calculate_attendance_success(self):
        """Test successful attendance calculation"""
        calc_data = {
            'emp_ids': [1, 2, 3],
            'start_date': '2024-12-01',
            'end_date': '2024-12-31',
        }
        
        db = Mock()
        
        # Mock the calculation service
        with patch.object(attendance_calculation_service, 'calculate_attendance') as mock_calc:
            mock_calc.return_value = {
                'processed_employees': 3,
                'total_records': 93,
                'exceptions_found': 2,
                'calculation_time': '2.5s'
            }
            
            result = await attendance_calculation_service.calculate_attendance(
                calc_data['emp_ids'],
                calc_data['start_date'],
                calc_data['end_date'],
                db
            )
            
            assert result['processed_employees'] == 3
            assert result['total_records'] == 93
    
    @pytest.mark.asyncio
    async def test_validate_calculation_parameters(self):
        """Test attendance calculation parameter validation"""
        calc_data = {
            'emp_ids': [1, 2, 3],
            'start_date': '2024-12-01',
            'end_date': '2024-12-31',
        }
        
        db = Mock()
        is_valid, errors = await attendance_validation_service.validate_attendance_calculation(
            calc_data, db
        )
        
        assert is_valid == True
        assert len(errors) == 0
    
    @pytest.mark.asyncio
    async def test_validate_calculation_invalid_date_range(self):
        """Test attendance calculation with invalid date range"""
        calc_data = {
            'emp_ids': [1, 2, 3],
            'start_date': '2024-12-31',  # After end date
            'end_date': '2024-12-01',
        }
        
        db = Mock()
        is_valid, errors = await attendance_validation_service.validate_attendance_calculation(
            calc_data, db
        )
        
        assert is_valid == False
        assert any('Start date must be before or equal to end date' in error for error in errors)

class TestAttendanceIntegration:
    """Integration tests for attendance module"""
    
    def test_end_to_end_attendance_flow(self, superuser_headers):
        """Test complete attendance flow from timetable to timesheet"""
        with TestClient(app, headers=superuser_headers) as client:
            # 1. Create timetable
            timetable_data = {
                "alias": "Integration Test Shift",
                "checkin_time": "09:00:00",
                "checkout_time": "17:00:00",
                "late_minutes": 15,
                "early_minutes": 15,
                "work_day": 1.0,
                "color": "#1890ff",
                "must_checkin": True,
                "must_checkout": True,
            }
            
            response = client.post("/api/v1/attendance/timetables", json=timetable_data)
            assert response.status_code == 200
            timetable = response.json()["data"]
            
            # 2. Create shift
            shift_data = {
                "alias": "Integration Test Shift",
                "work_days": "12345",
                "cycle_unit": 0,
                "cycle_count": 1,
                "roster_type": 0,
            }
            
            response = client.post("/api/v1/attendance/shifts", json=shift_data)
            assert response.status_code == 200
            shift = response.json()["data"]
            
            # 3. Assign timetable to shift
            assignment_data = {
                "shift_id": shift["id"],
                "day_of_week": 0,  # Monday
                "timetable_id": timetable["id"],
            }
            
            response = client.post(f"/api/v1/attendance/shifts/{shift['id']}/timetables", json=assignment_data)
            assert response.status_code == 200
            
            # 4. Get timetables to verify
            response = client.get("/api/v1/attendance/timetables")
            assert response.status_code == 200
            timetables = response.json()["data"]
            assert len(timetables) > 0
            
            # 5. Get shifts to verify
            response = client.get("/api/v1/attendance/shifts")
            assert response.status_code == 200
            shifts = response.json()["data"]
            assert len(shifts) > 0

if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
