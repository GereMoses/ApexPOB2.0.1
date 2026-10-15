"""
Visitor Management Tests
BioTime 9.5 compatible visitor module tests with POB extensions
Comprehensive test coverage for visitor management functionality
"""

import pytest
import uuid
from datetime import date, datetime, time, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.core.database import get_db, Base
from app.models.visitor import (
    VisitorType, Visitor, VisitorPreRegistration, 
    VisitorVisitLog, VisitorBlacklist
)
from app.models.biotime_models import PersonnelEmployee
from app.models.user import User
from app.services.visitor_service import VisitorService

client = TestClient(app)

BL_ID = 'BL-' + uuid.uuid4().hex[:8]


def _uniq_phone():
    # Each test creates its own visitor: tests share one database per run, and a
    # repeated phone/ID is (correctly) rejected as a duplicate visitor.
    return '+234' + str(uuid.uuid4().int)[:10]


class TestVisitorService:
    """Test visitor service layer"""
    
    def test_create_visitor_type(self, db_session):
        """Test visitor type creation"""
        service = VisitorService(db_session)
        
        visitor_type_data = {
            'type_name': 'Contractor',
            'induction_required': True,
            'default_visit_hours': 8,
            'auto_checkout': True,
            'contractor_visitor': True
        }
        
        visitor_type = service.create_visitor_type(visitor_type_data)
        
        assert visitor_type.id is not None
        assert visitor_type.type_name == 'Contractor'
        assert visitor_type.induction_required is True
        assert visitor_type.default_visit_hours == 8
        assert visitor_type.auto_checkout is True
        assert visitor_type.contractor_visitor is True
    
    def test_create_visitor(self, db_session, sample_visitor_type):
        """Test visitor creation"""
        service = VisitorService(db_session)
        
        visitor_data = {
            'full_name': 'John Doe',
            'phone': _uniq_phone(),
            'email': 'john@example.com',
            'company': 'Test Company',
            'id_type': 0,
            'id_no': 'ID123456-' + uuid.uuid4().hex[:6],
            'visitor_type_id': sample_visitor_type.id
        }
        
        from app.schemas.visitor import VisitorCreate
        visitor = service.create_visitor(VisitorCreate(**visitor_data))
        
        assert visitor.id is not None
        assert visitor.visitor_code.startswith('VIS')
        assert visitor.full_name == 'John Doe'
        assert visitor.phone == visitor_data['phone']
        assert visitor.email == 'john@example.com'
        assert visitor.company == 'Test Company'
        assert visitor.id_no == visitor_data['id_no']
    
    def test_create_pre_registration(self, db_session, sample_visitor, sample_employee):
        """Test pre-registration creation"""
        service = VisitorService(db_session)
        
        pre_reg_data = {
            'visitor_id': sample_visitor.id,
            'host_emp_id': sample_employee.id,
            'visit_date': date.today() + timedelta(days=1),
            'visit_time_start': time(9, 0),
            'visit_time_end': time(17, 0),
            'purpose': 'Meeting',
            'contractor_visitor': True
        }
        
        from app.schemas.visitor import VisitorPreRegistrationCreate
        pre_reg = service.create_pre_registration(
            VisitorPreRegistrationCreate(**pre_reg_data), 
            created_by=1
        )
        
        assert pre_reg.id is not None
        assert pre_reg.visitor_id == sample_visitor.id
        assert pre_reg.host_emp_id == sample_employee.id
        assert pre_reg.status == 0  # pending
        assert pre_reg.qr_code is not None
        assert pre_reg.contractor_visitor is True
    
    def test_check_in_visitor(self, db_session, sample_pre_registration):
        """Test visitor check-in"""
        service = VisitorService(db_session)
        
        check_in_data = {
            'pre_reg_id': sample_pre_registration.id,
            'host_emp_id': sample_pre_registration.host_emp_id
        }
        
        from app.schemas.visitor import VisitorCheckIn
        visit_log = service.check_in_visitor(
            VisitorCheckIn(**check_in_data),
            created_by=1
        )
        
        assert visit_log.id is not None
        assert visit_log.visitor_id == sample_pre_registration.visitor_id
        assert visit_log.status == 0  # checked in
        assert visit_log.card_no is not None
        assert visit_log.check_in_time is not None
    
    def test_check_out_visitor(self, db_session, sample_visit_log):
        """Test visitor check-out"""
        service = VisitorService(db_session)
        
        check_out_data = {
            'visitor_code': sample_visit_log.visitor.visitor_code
        }
        
        from app.schemas.visitor import VisitorCheckOut
        visit_log = service.check_out_visitor(
            VisitorCheckOut(**check_out_data)
        )
        
        assert visit_log.status == 1  # checked out
        assert visit_log.check_out_time is not None
    
    def test_blacklist_visitor(self, db_session, sample_visitor):
        """Test visitor blacklisting"""
        service = VisitorService(db_session)
        
        reason = "Security violation"
        blacklisted_visitor = service.blacklist_visitor(sample_visitor.id, reason)
        
        assert blacklisted_visitor.is_blacklist is True
        assert blacklisted_visitor.blacklist_reason == reason
    
    def test_get_overstay_report(self, db_session, sample_visit_log_overstay):
        """Test overstay report generation"""
        service = VisitorService(db_session)
        
        overstays = service.get_overstay_report(hours=1)
        
        assert len(overstays) >= 1
        assert overstays[0]['visitor_name'] == sample_visit_log_overstay.visitor.full_name
        assert overstays[0]['hours_overdue'] > 0


class TestVisitorAPI:
    """Test visitor API endpoints"""
    
    def test_create_visitor_type_api(self, auth_headers):
        """Test visitor type creation API"""
        visitor_type_data = {
            'type_name': 'Test Type',
            'induction_required': True,
            'default_visit_hours': 4,
            'auto_checkout': True
        }
        
        response = client.post(
            '/api/visitor/types',
            json=visitor_type_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200, response.text
        data = response.json()
        assert data['success'] is True
        assert data['data']['type_name'] == 'Test Type'
    
    def test_get_visitor_types_api(self, auth_headers):
        """Test get visitor types API"""
        response = client.get('/api/visitor/types/', headers=auth_headers)
        
        assert response.status_code == 200, response.text
        data = response.json()
        assert data['success'] is True
        assert isinstance(data['data'], list)
    
    def test_create_visitor_api(self, auth_headers):
        """Test visitor creation API"""
        visitor_data = {
            'full_name': 'API Test Visitor',
            'phone': _uniq_phone(),
            'email': 'apitest@example.com',
            'company': 'API Test Company',
            'id_type': 0,
            'id_no': 'API123456-' + uuid.uuid4().hex[:6]
        }
        
        response = client.post(
            '/api/visitor/visitors',
            json=visitor_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200, response.text
        data = response.json()
        assert data['success'] is True
        assert data['data']['full_name'] == 'API Test Visitor'
    
    def test_get_visitors_api(self, auth_headers):
        """Test get visitors API"""
        response = client.get('/api/visitor/visitors/', headers=auth_headers)
        
        assert response.status_code == 200, response.text
        data = response.json()
        assert data['success'] is True
        assert isinstance(data['data'], list)
    
    def test_create_pre_registration_api(self, auth_headers, sample_visitor, sample_employee):
        """Test pre-registration creation API"""
        pre_reg_data = {
            'visitor_data': {
                'full_name': 'Pre-reg Test',
                'phone': _uniq_phone(),
                'email': 'prereg@example.com',
                'company': 'Pre-reg Company',
                'id_type': 0,
                'id_no': 'PR123456-' + uuid.uuid4().hex[:6]
            },
            'host_emp_id': sample_employee.id,
            'visit_date': (date.today() + timedelta(days=1)).isoformat(),
            'visit_time_start': '09:00',
            'visit_time_end': '17:00',
            'purpose': 'API Test Meeting'
        }
        
        response = client.post(
            '/api/visitor/pre-register',
            json=pre_reg_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200, response.text
        data = response.json()
        assert data['success'] is True
        assert data['data']['status'] == 0  # pending
    
    def test_check_in_visitor_api(self, auth_headers, sample_pre_registration):
        """Test visitor check-in API"""
        check_in_data = {
            'pre_reg_id': sample_pre_registration.id,
            'host_emp_id': sample_pre_registration.host_emp_id
        }
        
        response = client.post(
            '/api/visitor/check-in',
            json=check_in_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200, response.text
        data = response.json()
        assert data['success'] is True
        assert data['data']['status'] == 0  # checked in
    
    def test_check_out_visitor_api(self, auth_headers, sample_visit_log):
        """Test visitor check-out API"""
        check_out_data = {
            'visitor_code': sample_visit_log.visitor.visitor_code
        }
        
        response = client.post(
            '/api/visitor/check-out',
            json=check_out_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200, response.text
        data = response.json()
        assert data['success'] is True
        assert data['data']['status'] == 1  # checked out
    
    def test_get_on_site_visitors_api(self, auth_headers):
        """Test get on-site visitors API"""
        response = client.get('/api/visitor/records/on-site/', headers=auth_headers)
        
        assert response.status_code == 200, response.text
        data = response.json()
        assert data['success'] is True
        assert isinstance(data['data'], list)
    
    def test_add_to_blacklist_api(self, auth_headers):
        """Test add to blacklist API"""
        blacklist_data = {
            'full_name': 'Blacklisted Person',
            'id_no': BL_ID,
            'phone': _uniq_phone(),
            'email': 'blacklisted@example.com',
            'reason': 'Security violation'
        }
        
        response = client.post(
            '/api/visitor/blacklist',
            json=blacklist_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200, response.text
        data = response.json()
        assert data['success'] is True
        assert data['data']['id_no'] == BL_ID
    
    def test_get_blacklist_api(self, auth_headers):
        """Test get blacklist API"""
        response = client.get('/api/visitor/blacklist/', headers=auth_headers)
        
        assert response.status_code == 200, response.text
        data = response.json()
        assert data['success'] is True
        assert isinstance(data['data'], list)
    
    def test_get_daily_report_api(self, auth_headers):
        """Test daily report API"""
        report_date = date.today().isoformat()
        response = client.get(
            f'/api/visitor/reports/daily/?report_date={report_date}',
            headers=auth_headers
        )
        
        assert response.status_code == 200, response.text
        data = response.json()
        assert data['success'] is True
        assert 'data' in data
        assert 'total_visitors' in data['data']
    
    def test_get_overstay_report_api(self, auth_headers):
        """Test overstay report API"""
        response = client.get(
            '/api/visitor/reports/overstay/?hours=8',
            headers=auth_headers
        )
        
        assert response.status_code == 200, response.text
        data = response.json()
        assert data['success'] is True
        assert isinstance(data['data'], list)
    
    def test_qr_scan_api(self, sample_pre_registration, auth_headers):
        """QR lookup returns visitor personal data, so it requires a login (used by
        the staff Check-In screen); anonymous lookups are refused."""
        anon = client.get(f'/api/visitor/qr/{sample_pre_registration.qr_code}')
        assert anon.status_code == 401
        response = client.get(f'/api/visitor/qr/{sample_pre_registration.qr_code}', headers=auth_headers)
        
        assert response.status_code == 200, response.text
        data = response.json()
        assert data['success'] is True
        assert data['data']['qr_code'] == sample_pre_registration.qr_code


class TestVisitorIntegration:
    """Integration tests for visitor management"""
    
    def test_complete_visitor_flow(self, db_session, auth_headers):
        """Test complete visitor flow: pre-reg -> check-in -> check-out"""
        # 1. Create visitor type
        visitor_type_response = client.post(
            '/api/visitor/types',
            json={
                'type_name': 'Integration Test',
                'induction_required': False,
                'default_visit_hours': 2,
                'auto_checkout': True
            },
            headers=auth_headers
        )
        assert visitor_type_response.status_code == 200, visitor_type_response.text
        visitor_type_id = visitor_type_response.json()['data']['id']
        
        # 2. Pre-register visitor
        pre_reg_response = client.post(
            '/api/visitor/pre-register',
            json={
                'visitor_data': {
                    'full_name': 'Integration Visitor',
                    'phone': _uniq_phone(),
                    'email': 'integration@example.com',
                    'company': 'Integration Company',
                    'id_type': 0,
                    'id_no': 'INT123456-' + uuid.uuid4().hex[:6],
                    'visitor_type_id': visitor_type_id
                },
                'host_emp_id': 1,
                'visit_date': (date.today() + timedelta(days=1)).isoformat(),
                'visit_time_start': '10:00',
                'visit_time_end': '12:00',
                'purpose': 'Integration Test'
            },
            headers=auth_headers
        )
        assert pre_reg_response.status_code == 200, pre_reg_response.text
        pre_reg_data = pre_reg_response.json()['data']
        
        # 3. Approve pre-registration
        approve_response = client.post(
            f'/api/visitor/pre-register/{pre_reg_data["id"]}/approve',
            json={'status': 1, 'note': 'Approved for test'},
            headers=auth_headers
        )
        assert approve_response.status_code == 200, approve_response.text
        # 4. Check-in visitor
        check_in_response = client.post(
            '/api/visitor/check-in',
            json={
                'pre_reg_id': pre_reg_data['id'],
                'host_emp_id': 1
            },
            headers=auth_headers
        )
        assert check_in_response.status_code == 200, check_in_response.text
        visit_data = check_in_response.json()['data']
        
        # 5. Verify visitor is on-site
        on_site_response = client.get('/api/visitor/records/on-site/', headers=auth_headers)
        assert on_site_response.status_code == 200, on_site_response.text
        on_site_visitors = on_site_response.json()['data']
        visitor_codes = [v['visitor']['visitor_code'] for v in on_site_visitors]
        assert visit_data['visitor']['visitor_code'] in visitor_codes
        
        # 6. Check-out visitor
        check_out_response = client.post(
            '/api/visitor/check-out',
            json={'visitor_code': visit_data['visitor']['visitor_code']},
            headers=auth_headers
        )
        assert check_out_response.status_code == 200, check_out_response.text
        check_out_data = check_out_response.json()['data']
        
        # 7. Verify check-out
        assert check_out_data['status'] == 1  # checked out
        assert check_out_data['check_out_time'] is not None


# Fixtures for test data
# db_session comes from tests/conftest.py (throwaway test database). The fixture that
# used to be here ran Base.metadata.drop_all() — DROPPING EVERY TABLE of whatever
# database the app was connected to, i.e. the live one if run on the live stack.


@pytest.fixture
def auth_headers(superuser_headers):
    """Real superuser token (was a login with admin/admin)."""
    return superuser_headers


@pytest.fixture
def sample_visitor_type(db_session):
    """Create sample visitor type"""
    visitor_type = VisitorType(
        type_name='Test Type',
        induction_required=True,
        default_visit_hours=8,
        auto_checkout=True
    )
    db_session.add(visitor_type)
    db_session.commit()
    return visitor_type


@pytest.fixture
def sample_employee(db_session):
    """Create sample employee"""
    import uuid
    employee = PersonnelEmployee(
        emp_code='VH' + uuid.uuid4().hex[:8].upper(),
        first_name='Test',
        last_name='Employee',
        status=0,
    )
    db_session.add(employee)
    db_session.commit()
    return employee


@pytest.fixture
def sample_visitor(db_session, sample_visitor_type):
    """Create sample visitor"""
    visitor = Visitor(
        visitor_code='VIS' + uuid.uuid4().hex[:10].upper(),
        full_name='Test Visitor',
        phone=_uniq_phone(),
        email='visitor@example.com',
        company='Test Company',
        id_type=0,
        id_no='TEST123-' + uuid.uuid4().hex[:6],
        visitor_type_id=sample_visitor_type.id
    )
    db_session.add(visitor)
    db_session.commit()
    return visitor


@pytest.fixture
def sample_pre_registration(db_session, sample_visitor, sample_employee):
    """Create sample pre-registration"""
    pre_reg = VisitorPreRegistration(
        visitor_id=sample_visitor.id,
        host_emp_id=sample_employee.id,
        visit_date=date.today() + timedelta(days=1),
        visit_time_start=time(9, 0),
        visit_time_end=time(17, 0),
        purpose='Test Meeting',
        qr_code='test-qr-' + uuid.uuid4().hex,
        status=1  # approved
    )
    db_session.add(pre_reg)
    db_session.commit()
    return pre_reg


@pytest.fixture
def sample_visit_log(db_session, sample_visitor, sample_employee):
    """Create sample visit log"""
    visit_log = VisitorVisitLog(
        visitor_id=sample_visitor.id,
        host_emp_id=sample_employee.id,
        check_in_time=datetime.utcnow() - timedelta(hours=2),
        status=0  # checked in
    )
    db_session.add(visit_log)
    db_session.commit()
    return visit_log


@pytest.fixture
def sample_visit_log_overstay(db_session, sample_visitor, sample_employee):
    """Create sample overstayed visit log"""
    visit_log = VisitorVisitLog(
        visitor_id=sample_visitor.id,
        host_emp_id=sample_employee.id,
        check_in_time=datetime.utcnow() - timedelta(hours=10),  # 10 hours ago
        status=0  # still checked in (overstayed)
    )
    db_session.add(visit_log)
    db_session.commit()
    return visit_log


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
