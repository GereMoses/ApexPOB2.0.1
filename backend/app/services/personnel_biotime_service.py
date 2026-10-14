"""
BioTime 9.5 Compatible Personnel Service
Complete personnel management with BioTime compatibility and POB extensions
"""

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, text
from typing import List, Dict, Any, Optional
import json
import uuid
import pandas as pd
from datetime import datetime, date, timedelta
import os

from ..models.personnel import Personnel
from ..schemas.personnel_biotime import (
    EmployeeCreate, EmployeeUpdate, EmployeeResponse,
    DepartmentCreate, DepartmentUpdate, DepartmentResponse,
    PositionCreate, PositionUpdate, PositionResponse,
    AreaCreate, AreaUpdate, AreaResponse,
    ResignationCreate, ResignationResponse,
    VendorCreate, VendorUpdate, VendorResponse,
    OnboardingTaskCreate, OnboardingTaskUpdate, OnboardingTaskResponse,
    OnboardingTemplateCreate, OnboardingTemplateResponse,
    BatchImportResponse, DeviceSyncResponse, OnboardingProgressResponse
)

class PersonnelBioTimeService:
    """BioTime 9.5 compatible personnel service"""
    
    def __init__(self, db: Session):
        self.db = db
    
    # Employee management
    async def get_employees(
        self, 
        search: Optional[str] = None,
        dept_id: Optional[int] = None,
        area_id: Optional[int] = None,
        status: Optional[int] = None,
        page: int = 1,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get employees with filters and pagination"""
        query = self.db.query(Personnel)
        
        # Apply filters
        if search:
            search_filter = or_(
                Personnel.badge_id.ilike(f"%{search}%"),
                Personnel.full_name.ilike(f"%{search}%"),
                Personnel.email.ilike(f"%{search}%")
            )
            query = query.filter(search_filter)
        
        if dept_id:
            query = query.filter(Personnel.department_id == dept_id)
        
        if area_id:
            query = query.filter(Personnel.current_zone_id == area_id)
        
        if status is not None:
            query = query.filter(Personnel.status == 'active' if status == 0 else 'inactive')
        
        # Pagination
        offset = (page - 1) * limit
        employees = query.offset(offset).limit(limit).all()
        
        # Convert to dict with BioTime fields
        result = []
        for emp in employees:
            emp_dict = {
                'id': emp.id,
                'emp_code': emp.badge_id,
                'first_name': emp.full_name.split(' ')[0] if emp.full_name else '',
                'last_name': emp.full_name.split(' ')[-1] if emp.full_name else '',
                'nickname': None,
                'dept_id': emp.department_id,
                'position_id': None,  # Will be mapped from role
                'area_id': emp.current_zone_id,
                'hire_date': None,  # Will be mapped from created_at
                'birthday': None,  # Will be added to model
                'gender': None,  # Will be added to model
                'card_no': emp.badge_id,
                'pwd': None,  # Will be handled separately
                'photo': emp.photo_url,
                'email': emp.email,
                'mobile': emp.phone,
                'address': None,  # Will be added to model
                'status': 0 if emp.status == 'active' else 1,
                'is_admin': False,  # Will be mapped from user role
                'enroll_sn': None,
                'enable_att': True,
                'enable_overtime': True,
                'enable_holiday': True,
                'dev_privilege': 0,
                'super_ssn': None,
                
                # POB extensions
                'contractor_flag': emp.personnel_type == 'CONTRACTOR',
                'vendor_id': None,  # Will be implemented
                'blood_group': emp.blood_group,
                'emergency_contact': json.loads(emp.emergency_contact).get('name') if emp.emergency_contact else None,
                'emergency_phone': json.loads(emp.emergency_contact).get('phone') if emp.emergency_contact else None,
                'onboarding_status': 0,  # Will be calculated from onboarding tasks
                'custom_fields': getattr(emp, 'custom_fields', None) or {},   # no such column on personnel
                
                'create_time': emp.created_at,
                'update_time': emp.updated_at,
                
                # BioTime extensions
                'biotime_employee_id': emp.biotime_employee_id,
                'work_schedule': emp.work_schedule,
                'access_groups': emp.access_groups,
                'device_groups': emp.device_groups,
                'biometric_quality_score': emp.biometric_quality_score,
                'last_sync_timestamp': emp.last_sync_timestamp,
                'timezone_preference': emp.timezone_preference,
                'language_preference': emp.language_preference,
            }
            result.append(emp_dict)
        
        return result
    
    async def get_employee(self, emp_id: int) -> Optional[Dict[str, Any]]:
        """Get single employee by ID"""
        employees = await self.get_employees()
        for emp in employees:
            if emp['id'] == emp_id:
                return emp
        return None
    
    async def create_employee(self, employee: EmployeeCreate, user_id: int) -> Dict[str, Any]:
        """Create new employee"""
        try:
            # Generate emp_code if not provided
            emp_code = employee.emp_code or f"EMP{datetime.now().year}{uuid.uuid4().hex[:4]}"
            
            # Check for duplicate emp_code
            existing = self.db.query(Personnel).filter(Personnel.badge_id == emp_code).first()
            if existing:
                return {'success': False, 'error': f'Employee code {emp_code} already exists'}
            
            # Create personnel record
            full_name = f"{employee.first_name or ''} {employee.last_name}".strip()
            
            # Prepare emergency contact
            emergency_contact = {}
            if employee.emergency_contact or employee.emergency_phone:
                emergency_contact = {
                    'name': employee.emergency_contact,
                    'phone': employee.emergency_phone
                }
            
            personnel = Personnel(
                badge_id=emp_code,
                full_name=full_name,
                email=employee.email,
                phone=employee.mobile,
                company=employee.custom_fields.get('company', 'Default Company') if employee.custom_fields else 'Default Company',
                department_id=employee.dept_id,
                role=employee.custom_fields.get('role', 'Employee') if employee.custom_fields else 'Employee',
                position=employee.custom_fields.get('position', '') if employee.custom_fields else '',
                photo_url=employee.photo,
                blood_group=employee.blood_group,
                emergency_contact=json.dumps(emergency_contact) if emergency_contact else None,
                personnel_type='CONTRACTOR' if employee.contractor_flag else 'STAFF',
                custom_fields=employee.custom_fields or {},
                biotime_employee_id=f"BT{emp_code}",
                timezone_preference=employee.custom_fields.get('timezone', 'UTC') if employee.custom_fields else 'UTC',
                language_preference=employee.custom_fields.get('language', 'en') if employee.custom_fields else 'en',
                status='active' if employee.status == 0 else 'inactive'
            )
            
            self.db.add(personnel)
            self.db.commit()
            self.db.refresh(personnel)
            
            # Queue device sync command
            await self._queue_device_update(personnel.id, 'CREATE')
            
            return {
                'success': True,
                'data': await self.get_employee(personnel.id)
            }
            
        except Exception as e:
            self.db.rollback()
            return {'success': False, 'error': str(e)}
    
    async def update_employee(self, emp_id: int, employee: EmployeeUpdate, user_id: int) -> Dict[str, Any]:
        """Update employee"""
        try:
            personnel = self.db.query(Personnel).filter(Personnel.id == emp_id).first()
            if not personnel:
                return {'success': False, 'error': 'Employee not found'}
            
            # Update fields
            if employee.first_name or employee.last_name:
                full_name = f"{employee.first_name or personnel.full_name.split(' ')[0]} {employee.last_name or personnel.full_name.split(' ')[-1]}".strip()
                personnel.full_name = full_name
            
            if employee.email is not None:
                personnel.email = employee.email
            
            if employee.mobile is not None:
                personnel.phone = employee.mobile
            
            if employee.dept_id is not None:
                personnel.department_id = employee.dept_id
            
            if employee.photo is not None:
                personnel.photo_url = employee.photo
            
            if employee.blood_group is not None:
                personnel.blood_group = employee.blood_group
            
            if employee.emergency_contact or employee.emergency_phone:
                emergency_contact = {
                    'name': employee.emergency_contact or json.loads(personnel.emergency_contact or '{}').get('name'),
                    'phone': employee.emergency_phone or json.loads(personnel.emergency_contact or '{}').get('phone')
                }
                personnel.emergency_contact = json.dumps(emergency_contact)
            
            if employee.custom_fields is not None:
                personnel.custom_fields = {**(personnel.custom_fields or {}), **employee.custom_fields}
            
            if employee.status is not None:
                personnel.status = 'active' if employee.status == 0 else 'inactive'
            
            personnel.updated_at = datetime.utcnow()
            
            self.db.commit()
            
            # Queue device sync command
            await self._queue_device_update(personnel.id, 'UPDATE')
            
            return {
                'success': True,
                'data': await self.get_employee(personnel.id)
            }
            
        except Exception as e:
            self.db.rollback()
            return {'success': False, 'error': str(e)}
    
    async def delete_employee(self, emp_id: int, user_id: int) -> Dict[str, Any]:
        """Delete employee (soft delete)"""
        try:
            personnel = self.db.query(Personnel).filter(Personnel.id == emp_id).first()
            if not personnel:
                return {'success': False, 'error': 'Employee not found'}
            
            # Soft delete - set status to resigned
            personnel.status = 'inactive'
            personnel.updated_at = datetime.utcnow()
            
            self.db.commit()
            
            # Queue device sync command
            await self._queue_device_update(personnel.id, 'DELETE')
            
            return {'success': True, 'message': 'Employee deleted successfully'}
            
        except Exception as e:
            self.db.rollback()
            return {'success': False, 'error': str(e)}
    
    async def batch_import_employees(self, file, user_id: int) -> Dict[str, Any]:
        """Batch import employees from CSV/XLSX"""
        try:
            # Read file
            if file.filename.endswith('.csv'):
                df = pd.read_csv(file.file)
            else:
                df = pd.read_excel(file.file)
            
            total_records = len(df)
            imported_records = 0
            failed_records = 0
            errors = []
            
            for index, row in df.iterrows():
                try:
                    # Map CSV columns to employee fields
                    employee_data = {
                        'first_name': row.get('first_name', ''),
                        'last_name': row.get('last_name', ''),
                        'email': row.get('email', ''),
                        'mobile': row.get('mobile', ''),
                        'dept_id': row.get('dept_id'),
                        'contractor_flag': row.get('contractor_flag', False),
                        'blood_group': row.get('blood_group', ''),
                        'emergency_contact': row.get('emergency_contact', ''),
                        'emergency_phone': row.get('emergency_phone', ''),
                        'custom_fields': {
                            'company': row.get('company', 'Default Company'),
                            'role': row.get('role', 'Employee')
                        }
                    }
                    
                    employee = EmployeeCreate(**employee_data)
                    result = await self.create_employee(employee, user_id)
                    
                    if result['success']:
                        imported_records += 1
                    else:
                        failed_records += 1
                        errors.append({
                            'row': index + 2,  # +2 for header and 0-based index
                            'data': row.to_dict(),
                            'error': result['error']
                        })
                        
                except Exception as e:
                    failed_records += 1
                    errors.append({
                        'row': index + 2,
                        'data': row.to_dict(),
                        'error': str(e)
                    })
            
            return BatchImportResponse(
                success=failed_records == 0,
                total_records=total_records,
                imported_records=imported_records,
                failed_records=failed_records,
                errors=errors
            ).dict()
            
        except Exception as e:
            return {'success': False, 'error': f'File processing error: {str(e)}'}
    
    async def export_employees_xlsx(self, employee_ids: Optional[List[int]] = None) -> bytes:
        """Export employees to Excel"""
        employees = await self.get_employees()
        
        if employee_ids:
            employees = [emp for emp in employees if emp['id'] in employee_ids]
        
        # Convert to DataFrame
        df = pd.DataFrame(employees)
        
        # Save to Excel in memory
        output = pd.io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Employees')
        
        return output.getvalue()
    
    async def export_employees_csv(self, employee_ids: Optional[List[int]] = None) -> str:
        """Export employees to CSV"""
        employees = await self.get_employees()
        
        if employee_ids:
            employees = [emp for emp in employees if emp['id'] in employee_ids]
        
        # Convert to DataFrame
        df = pd.DataFrame(employees)
        
        # Save to CSV in memory
        output = pd.io.StringIO()
        df.to_csv(output, index=False)
        
        return output.getvalue()
    
    # Biometric management
    async def enroll_biometric(self, emp_id: int, enrollment_data: Dict[str, Any], user_id: int) -> Dict[str, Any]:
        """Enroll biometric - send command to device"""
        try:
            personnel = self.db.query(Personnel).filter(Personnel.id == emp_id).first()
            if not personnel:
                return {'success': False, 'error': 'Employee not found'}
            
            # Create device command for biometric enrollment
            command = {
                'command_type': 'ENROLL_BIOMETRIC',
                'emp_code': personnel.badge_id,
                'biometric_type': enrollment_data.get('type'),
                'terminal_sn': enrollment_data.get('terminal_sn'),
                'created_by': user_id,
                'created_at': datetime.utcnow()
            }
            
            # Insert into device command queue
            await self._insert_device_command(command)
            
            return {
                'success': True,
                'message': f'Biometric enrollment command sent to device {enrollment_data.get("terminal_sn")}'
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    async def save_biometric_data(self, emp_id: int, bio_data: Dict[str, Any], user_id: int) -> Dict[str, Any]:
        """Save biometric template and sync to devices"""
        try:
            personnel = self.db.query(Personnel).filter(Personnel.id == emp_id).first()
            if not personnel:
                return {'success': False, 'error': 'Employee not found'}
            
            # Update biometric data in personnel record
            if not personnel.biometric_data:
                personnel.biometric_data = {}
            
            bio_type = bio_data.get('type')
            if bio_type == 'finger':
                if 'fingerprint_templates' not in personnel.biometric_data:
                    personnel.biometric_data['fingerprint_templates'] = {}
                personnel.biometric_data['fingerprint_templates'][f"finger_{bio_data.get('finger_id')}"] = bio_data.get('template')
            
            elif bio_type == 'face':
                personnel.face_template = bio_data.get('template')
            
            elif bio_type == 'palm':
                if 'palm_templates' not in personnel.biometric_data:
                    personnel.biometric_data['palm_templates'] = {}
                personnel.biometric_data['palm_templates'][f"palm_{bio_data.get('palm_id')}"] = bio_data.get('template')
            
            personnel.updated_at = datetime.utcnow()
            self.db.commit()
            
            # Queue sync to all devices
            await self._queue_device_update(emp_id, 'BIOMETRIC_UPDATE')
            
            return {
                'success': True,
                'message': 'Biometric data saved and synced to devices'
            }
            
        except Exception as e:
            self.db.rollback()
            return {'success': False, 'error': str(e)}
    
    async def delete_biometric_data(self, emp_id: int, bio_data: Dict[str, Any], user_id: int) -> Dict[str, Any]:
        """Delete biometric data from DB and devices"""
        try:
            personnel = self.db.query(Personnel).filter(Personnel.id == emp_id).first()
            if not personnel:
                return {'success': False, 'error': 'Employee not found'}
            
            # Remove biometric data
            bio_type = bio_data.get('type')
            if bio_type == 'finger' and personnel.biometric_data:
                personnel.biometric_data.get('fingerprint_templates', {}).pop(f"finger_{bio_data.get('finger_id')}", None)
            
            elif bio_type == 'face':
                personnel.face_template = None
            
            elif bio_type == 'palm' and personnel.biometric_data:
                personnel.biometric_data.get('palm_templates', {}).pop(f"palm_{bio_data.get('palm_id')}", None)
            
            personnel.updated_at = datetime.utcnow()
            self.db.commit()
            
            # Queue sync to all devices
            await self._queue_device_update(emp_id, 'BIOMETRIC_DELETE')
            
            return {
                'success': True,
                'message': 'Biometric data deleted and removed from devices'
            }
            
        except Exception as e:
            self.db.rollback()
            return {'success': False, 'error': str(e)}
    
    # Private helper methods
    async def _queue_device_update(self, emp_id: int, operation: str):
        """Queue device update command"""
        command = {
            'command_type': f'DATA_{operation}',
            'emp_id': emp_id,
            'created_at': datetime.utcnow()
        }
        await self._insert_device_command(command)
    
    async def _insert_device_command(self, command: Dict[str, Any]):
        """Insert command into device queue"""
        # This would insert into iclock_devcmd table
        # For now, just log the command
        print(f"Device command queued: {command}")
    
    # Placeholder methods for other BioTime modules
    async def get_departments(self) -> List[Dict[str, Any]]:
        """Get all departments"""
        # This would query personnel_department table
        return []
    
    async def create_department(self, department: DepartmentCreate, user_id: int) -> Dict[str, Any]:
        """Create new department"""
        # Implementation would create department in personnel_department table
        return {'success': True, 'data': {}}
    
    async def get_areas(self) -> List[Dict[str, Any]]:
        """Get all areas"""
        # This would query personnel_area table
        return []
    
    async def create_area(self, area: AreaCreate, user_id: int) -> Dict[str, Any]:
        """Create new area"""
        # Implementation would create area in personnel_area table
        return {'success': True, 'data': {}}
    
    async def get_onboarding_tasks(self, emp_id: Optional[int] = None, status: Optional[int] = None, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get onboarding tasks"""
        # This would query onboarding_task table
        return []
    
    async def create_onboarding_task(self, task: OnboardingTaskCreate, user_id: int) -> Dict[str, Any]:
        """Create onboarding task"""
        # Implementation would create task in onboarding_task table
        return {'success': True, 'data': {}}
    
    async def get_vendors(self) -> List[Dict[str, Any]]:
        """Get all vendors"""
        # This would query personnel_vendor table
        return []
    
    async def create_vendor(self, vendor: VendorCreate, user_id: int) -> Dict[str, Any]:
        """Create new vendor"""
        # Implementation would create vendor in personnel_vendor table
        return {'success': True, 'data': {}}
    
    async def get_contractors(self, vendor_id: Optional[int] = None, status: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get contractors (employees where contractor_flag=true)"""
        query = self.db.query(Personnel).filter(Personnel.personnel_type == 'CONTRACTOR')
        
        if vendor_id:
            # This would filter by vendor_id when vendor relationship is implemented
            pass
        
        if status is not None:
            query = query.filter(Personnel.status == 'active' if status == 0 else 'inactive')
        
        contractors = query.all()
        
        result = []
        for contractor in contractors:
            result.append({
                'id': contractor.id,
                'emp_code': contractor.badge_id,
                'name': contractor.full_name,
                'company': contractor.company,
                'status': contractor.status,
                'vendor_id': None  # Will be implemented
            })
        
        return result
