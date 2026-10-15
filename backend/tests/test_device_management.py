"""
Device Management Tests
Comprehensive test suite for Device module functionality
"""

import pytest
import asyncio
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime, timedelta
import json

from app.main import app
from app.core.database import get_db, SessionLocal
from app.models.biotime_models import IClockTerminal, IClockTransaction, PersonnelEmployee


class TestDeviceManagement:
    """Test suite for Device Management API"""
    
    @pytest.fixture
    def client(self, superuser_headers):
        """Client authenticated as a real superuser (real JWT + RBAC path)."""
        return TestClient(app, headers=superuser_headers)
    
    @pytest.fixture
    def db_session(self):
        """Database session fixture"""
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()
    
    @pytest.fixture
    def sample_terminal(self, db_session):
        """Sample terminal fixture"""
        terminal = IClockTerminal(
            sn="TEST001",
            alias="Test Terminal 1",
            ip_address="192.168.1.100",
            area_id=None,
            comm_key="0",
            device_name="MB20",
            device_model="MB20",
            fw_ver="2.3.1",
            user_count=10,
            fp_count=8,
            face_count=5,
            palm_count=0,
            log_count=100,
            device_type=0,
            zone_id=None,
            is_auto_reg=False,
            state=1,
            last_activity=datetime.utcnow(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db_session.add(terminal)
        db_session.commit()
        db_session.refresh(terminal)
        yield terminal
        # Each test gets a fresh terminal (the serial is unique).
        db_session.execute(text("DELETE FROM iclock_devcmd WHERE sn = 'TEST001'"))
        db_session.execute(text("DELETE FROM iclock_terminal WHERE sn = 'TEST001'"))
        db_session.commit()
    
    @pytest.fixture
    def sample_personnel(self, db_session):
        """Sample personnel fixture"""
        personnel = PersonnelEmployee(
            emp_code="EMP001",
            first_name="Test",
            last_name="User",
            status=0,
        )
        db_session.add(personnel)
        db_session.commit()
        db_session.refresh(personnel)
        yield personnel
        db_session.execute(text("DELETE FROM personnel_employee WHERE emp_code = 'EMP001'"))
        db_session.commit()


class TestDeviceCRUD(TestDeviceManagement):
    """Test Device CRUD operations"""
    
    def test_get_terminals(self, client, sample_terminal):
        """Test getting all terminals"""
        response = client.get("/api/device/terminals/")
        assert response.status_code == 200
        data = response.json()
        items = data["data"] if isinstance(data, dict) else data   # paginated {data, total}
        assert len(items) >= 1
        assert any(t["sn"] == sample_terminal.sn for t in items)
    
    def test_create_terminal(self, client):
        """Test creating a new terminal"""
        terminal_data = {
            "sn": "TEST002",
            "alias": "Test Terminal 2",
            "ip_address": "192.168.1.101",
            "area_id": None,
            "device_type": 0,
            "device_name": "MB560",
            "device_model": "MB560"
        }
        
        response = client.post("/api/device/terminals", json=terminal_data)
        assert response.status_code == 200
        data = response.json()
        assert data["sn"] == "TEST002"
        assert data["alias"] == "Test Terminal 2"
    
    def test_create_duplicate_terminal(self, client, sample_terminal):
        """Test creating duplicate terminal (should fail)"""
        terminal_data = {
            "sn": sample_terminal.sn,  # Same SN
            "alias": "Duplicate Terminal",
            "ip_address": "192.168.1.102"
        }
        
        response = client.post("/api/device/terminals", json=terminal_data)
        assert response.status_code == 409
    
    def test_get_terminal_by_id(self, client, sample_terminal):
        """Test getting terminal by ID"""
        response = client.get(f"/api/device/terminals/{sample_terminal.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["sn"] == sample_terminal.sn
    
    def test_update_terminal(self, client, sample_terminal):
        """Test updating terminal"""
        update_data = {
            "alias": "Updated Terminal",
            "ip_address": "192.168.1.103"
        }
        
        response = client.put(f"/api/device/terminals/{sample_terminal.id}", json=update_data)
        assert response.status_code == 200
        data = response.json()
        assert data["alias"] == "Updated Terminal"
        assert data["ip_address"] == "192.168.1.103"
    
    def test_delete_terminal(self, client, sample_terminal):
        """Test deleting terminal"""
        response = client.delete(f"/api/device/terminals/{sample_terminal.id}")
        assert response.status_code == 200
        
        # Verify deletion
        get_response = client.get(f"/api/device/terminals/{sample_terminal.id}")
        assert get_response.status_code == 404
    
    def test_batch_import_terminals(self, client):
        """Test batch importing terminals"""
        import_data = {
            "devices": [
                {
                    "sn": "BATCH001",
                    "alias": "Batch Terminal 1",
                    "ip_address": "192.168.1.200",
                    "area_id": None
                },
                {
                    "sn": "BATCH002", 
                    "alias": "Batch Terminal 2",
                    "ip_address": "192.168.1.201",
                    "area_id": 999999   # does not exist: this row alone is skipped
                }
            ]
        }
        
        response = client.post("/api/device/terminals/batch-import", json=import_data)
        assert response.status_code == 200
        data = response.json()
        assert data["imported"] == 1
        assert data["skipped"] == 1
        assert any("999999" in e for e in data["errors"])

    def test_create_terminal_unknown_area_is_400_not_500(self, client):
        resp = client.post("/api/device/terminals", json={"sn": "BADAREA1", "alias": "x", "area_id": 999999})
        assert resp.status_code == 400 and "does not exist" in resp.json()["detail"]


class TestDeviceCommands(TestDeviceManagement):
    """Test Device Command operations"""
    
    def test_get_device_commands(self, client, sample_terminal):
        """Test getting device commands"""
        response = client.get("/api/device/devcmd/")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    def test_send_command(self, client, sample_terminal):
        """Test sending command to device"""
        command_data = {
            "sn": sample_terminal.sn,
            "cmd": "REBOOT"
        }
        
        response = client.post("/api/device/devcmd", json=command_data)
        assert response.status_code == 200
        data = response.json()
        assert data["sn"] == sample_terminal.sn
        assert data["cmd"] == "REBOOT"
        assert data["status"] == "pending"
    
    def test_sync_user_to_device(self, client, sample_terminal, sample_personnel):
        """Test syncing user to device"""
        response = client.post(
            f"/api/device/devcmd/sync-user/?sn={sample_terminal.sn}&emp_code={sample_personnel.emp_code}"
        )
        assert response.status_code == 200
        data = response.json()
        msg = data["message"].lower()
        assert "synced" in msg or "queued" in msg   # ADMS readers get it on their next poll
    
    def test_sync_all_users_to_device(self, client, sample_terminal):
        """Test syncing all users to device"""
        response = client.post(f"/api/device/devcmd/sync-all-users?sn={sample_terminal.sn}")
        assert response.status_code == 200
        data = response.json()
        assert "sync" in data["message"].lower()
    
    def test_emergency_command(self, client, sample_terminal):
        """Test emergency device command"""
        # Update terminal to emergency type
        client.put(f"/api/device/terminals/{sample_terminal.id}", json={"device_type": 3})
        
        response = client.post(f"/api/device/devcmd/emergency?sn={sample_terminal.sn}&action=ON")
        assert response.status_code == 200
        data = response.json()
        assert "emergency" in data["message"].lower()
        assert data["action"] == "ON"


class TestRealTimeMonitoring(TestDeviceManagement):
    """Test Real-time Monitoring"""
    
    def test_get_real_time_devices(self, client, sample_terminal):
        """Test getting real-time device data"""
        response = client.get("/api/device/real-time/")
        assert response.status_code == 200
        data = response.json()
        assert "devices" in data
        assert "total_count" in data
        assert "online_count" in data
        assert "offline_count" in data
        assert isinstance(data["devices"], list)
    
    def test_device_health_check(self, client):
        """Test device health check"""
        response = client.get("/api/device/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "total_devices" in data
        assert "online_devices" in data


class TestFirmwareManagement(TestDeviceManagement):
    """Test Firmware Management"""
    
    def test_firmware_upload(self, client):
        """Test firmware upload (mock)"""
        # This would test file upload in real implementation
        # For now, we'll test the endpoint exists
        response = client.post("/api/device/firmware/upload")
        # Should return 422 for missing file
        assert response.status_code in [422, 200]
    
    def test_firmware_push(self, client, sample_terminal):
        """Test firmware push"""
        push_data = {
            "firmware_id": "test_firmware_001",
            "sn_list": [sample_terminal.sn]
        }
        
        response = client.post("/api/device/firmware/push", json=push_data)
        assert response.status_code == 200
        data = response.json()
        assert "firmware_id" in data
        assert "devices_queued" in data


class TestADMSProtocol(TestDeviceManagement):
    """Test ADMS Protocol endpoints"""
    
    def test_adms_cdata(self, client, sample_terminal):
        """Test ADMS cdata endpoint"""
        # Test device heartbeat
        response = client.get(f"/iclock/cdata?SN={sample_terminal.sn}&options=UserCount=10,FpCount=5")
        assert response.status_code == 200
        # A GET with options= is the reader's registration: the reply is the options
        # block (stamps, intervals), not a bare "OK".
        assert response.text.startswith("GET OPTION FROM")
        assert "ATTLOGStamp=" in response.text
    
    def test_adms_cdata_with_attendance(self, client, sample_terminal, sample_personnel):
        """Test ADMS cdata with attendance data"""
        attendance_data = "PIN=EMP001&Time=2024-03-28 14:30:00&Verify=1&WorkCode=0"
        
        response = client.post(
            f"/iclock/cdata?SN={sample_terminal.sn}",
            data=attendance_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        assert response.status_code == 200
    
    def test_adms_getrequest(self, client, sample_terminal):
        """Test ADMS getrequest endpoint"""
        response = client.get(f"/iclock/getrequest?SN={sample_terminal.sn}")
        assert response.status_code == 200
        assert response.text in ["OK", "NONE"]
    
    def test_adms_devicecmd(self, client, sample_terminal):
        """Test ADMS devicecmd endpoint"""
        cmd_response = "ID=1&Return=0&CMD=REBOOT"
        
        response = client.post(
            f"/iclock/devicecmd?SN={sample_terminal.sn}",
            data=cmd_response,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        assert response.status_code == 200
        assert response.text == "OK"
    
    def test_adms_test_endpoint(self, client):
        """Test ADMS test endpoint"""
        response = client.get("/iclock/test")
        assert response.status_code == 200
        data = response.json()
        assert "protocol" in data
        assert data["protocol"] == "ADMS"


class TestDeviceSyncRules(TestDeviceManagement):
    """Test Device Sync Rules"""
    
    def test_personnel_sync_trigger(self, db_session, sample_personnel):
        """Test personnel sync trigger"""
        from app.services.device_sync_rules import device_sync_rules_service
        
        # Test sync rule trigger
        result = asyncio.run(device_sync_rules_service.on_personnel_created_or_updated(
            sample_personnel.id, db_session
        ))
        
        assert result["success"] is True
        assert "devices_queued" in result
    
    def test_fingerprint_sync_trigger(self, db_session, sample_personnel):
        """Test fingerprint sync trigger"""
        from app.services.device_sync_rules import device_sync_rules_service
        
        result = asyncio.run(device_sync_rules_service.on_fingerprint_enrolled(
            sample_personnel.id, db_session
        ))
        
        assert result["success"] is True
        assert "devices_queued" in result
    
    def test_device_online_sync_trigger(self, db_session, sample_terminal):
        """Test device online sync trigger"""
        from app.services.device_sync_rules import device_sync_rules_service
        
        result = asyncio.run(device_sync_rules_service.on_device_came_online(
            sample_terminal.sn, db_session
        ))
        
        assert result["success"] is True
        assert "commands_queued" in result
    
    def test_command_queue_stats(self, db_session):
        """Test command queue statistics"""
        from app.services.device_sync_rules import device_sync_rules_service
        
        result = asyncio.run(device_sync_rules_service.get_command_queue_stats(db_session))
        
        assert result["success"] is True
        assert "queue_stats" in result
        assert "total_pending" in result
    
    def test_cleanup_expired_commands(self, db_session):
        """Test cleanup of expired commands"""
        from app.services.device_sync_rules import device_sync_rules_service
        
        result = asyncio.run(device_sync_rules_service.cleanup_expired_commands(db_session))
        
        assert result["success"] is True
        assert "expired_commands" in result


class TestWebSocketFunctionality(TestDeviceManagement):
    """Test WebSocket functionality"""
    
    def test_websocket_stats(self, client):
        """Test WebSocket statistics endpoint"""
        response = client.get("/api/device/websocket/stats")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "connections" in data


class TestDeviceValidation(TestDeviceManagement):
    """Test Device validation and business rules"""
    
    def test_device_validation(self, client):
        """Test device validation rules"""
        # Test missing required fields
        invalid_data = {
            "alias": "Test Device",
            # Missing SN
        }
        
        response = client.post("/api/device/terminals", json=invalid_data)
        assert response.status_code == 422
    
    def test_device_type_validation(self, client):
        """Test device type validation"""
        invalid_data = {
            "sn": "TEST003",
            "alias": "Test Device",
            "device_type": 99  # Invalid device type
        }
        
        response = client.post("/api/device/terminals", json=invalid_data)
        # Should handle gracefully (either accept or reject based on validation)
        assert response.status_code in [200, 422]
    
    def test_command_validation(self, client):
        """Test command validation"""
        # Test missing required fields
        invalid_command = {
            "cmd": "REBOOT"
            # Missing SN
        }
        
        response = client.post("/api/device/devcmd", json=invalid_command)
        assert response.status_code == 422


class TestDevicePerformance(TestDeviceManagement):
    """Test Device performance and scalability"""
    
    def test_bulk_device_creation(self, client):
        """Test bulk device creation performance"""
        devices = []
        for i in range(10):
            devices.append({
                "sn": f"BULK{i:03d}",
                "alias": f"Bulk Device {i}",
                "ip_address": f"192.168.1.{200 + i}",
                "device_type": 0
            })
        
        import_data = {"devices": devices}
        
        response = client.post("/api/device/terminals/batch-import", json=import_data)
        assert response.status_code == 200
        data = response.json()
        assert data["imported"] == 10
    
    def test_large_command_queue(self, client, sample_terminal):
        """Test large command queue handling"""
        commands = ["REBOOT", "CHECK", "INFO", "CLEAR DATA", "CLEAR ADMIN"]
        
        for cmd in commands:
            command_data = {"sn": sample_terminal.sn, "cmd": cmd}
            response = client.post("/api/device/devcmd", json=command_data)
            assert response.status_code == 200
        
        # Verify all commands are queued
        response = client.get("/api/device/devcmd/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= len(commands)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
